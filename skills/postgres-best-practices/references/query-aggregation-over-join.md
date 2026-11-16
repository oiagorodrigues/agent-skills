---
title: "Aggregate before joining to avoid Cartesian product inflation"
impact: high
tags: [aggregation, join, correctness, cte, sum-inflation]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Aggregate before joining to avoid Cartesian product inflation

## Problem

When two one-to-many relationships are joined in the same query before aggregating, the result is a Cartesian product of the child rows. Aggregates like `SUM()`, `AVG()`, and `COUNT()` operate on the inflated row set and produce silently wrong results — no error is raised. This is one of the most dangerous bugs in SQL because the query returns values that look plausible but are mathematically incorrect.

## Bad Example

```sql
-- Trying to get total revenue and average rating per product
-- BAD: Both order_items and reviews are joined to products before aggregation
SELECT
  p.id,
  p.name,
  SUM(oi.unit_price * oi.quantity) AS total_revenue,   -- WRONG: inflated
  AVG(r.rating)                    AS avg_rating        -- WRONG: inflated
FROM       products    p
JOIN       order_items oi ON oi.product_id = p.id
JOIN       reviews     r  ON r.product_id  = p.id
GROUP BY   p.id, p.name;
```

**What actually happens for product_id = 42:**
- `order_items` has 3 rows for this product (quantities: 1, 2, 1; prices: $10, $20, $15)
- `reviews` has 4 rows for this product (ratings: 5, 4, 3, 5)
- The JOIN produces 3 × 4 = **12 rows**
- `SUM(unit_price * quantity)` counts each of the 3 order_item rows **4 times** → `(10 + 40 + 15) × 4 = $260` instead of the correct `$65`
- `AVG(rating)` counts each of the 4 reviews **3 times** → still correct average (3 copies of each review), but COUNT(*) would be 12 instead of 4

No error, no warning — just wrong data flowing silently into reports, dashboards, and financial records.

## Good Example

```sql
-- GOOD: Aggregate each one-to-many relationship independently in a CTE,
--       then join the pre-aggregated results
WITH revenue AS (
  SELECT
    product_id,
    SUM(unit_price * quantity)  AS total_revenue,
    COUNT(*)                    AS total_units_sold
  FROM     order_items
  GROUP BY product_id
),
avg_rating AS (
  SELECT
    product_id,
    AVG(rating)     AS avg_rating,
    COUNT(*)        AS review_count
  FROM     reviews
  WHERE    status = 'approved'
  GROUP BY product_id
)
SELECT
  p.id,
  p.name,
  COALESCE(rev.total_revenue,    0)    AS total_revenue,
  COALESCE(rev.total_units_sold, 0)    AS total_units_sold,
  COALESCE(rat.avg_rating,       NULL) AS avg_rating,
  COALESCE(rat.review_count,     0)    AS review_count
FROM       products    p
LEFT JOIN  revenue     rev ON rev.product_id = p.id
LEFT JOIN  avg_rating  rat ON rat.product_id = p.id
ORDER BY   total_revenue DESC NULLS LAST;
```

Each CTE reduces its one-to-many relation to one row per `product_id` before the final join. There is no Cartesian product — the final join is many-to-one on both sides.

## Why It Matters

- **Silent correctness bug**: The query succeeds and returns data that appears valid. Without already knowing the correct answer, there is no way to detect the inflation at the query level.
- **Numeric demonstration**: 3 order_items × 4 reviews = 12 combined rows. Revenue is counted 4× (once per review). On a product with 10 order_items and 50 reviews, revenue is inflated 50×.
- **Compound effect**: Adding a third one-to-many join (e.g., `product_views`) makes it exponentially worse: 3 × 4 × 100 = 1,200 rows per product.
- **Performance**: The Cartesian product also blows up the intermediate result set. PostgreSQL's EXPLAIN shows the actual row count, making it diagnosable — but the data is still wrong.

## EXPLAIN Notes

```sql
-- Bad: shows row count blowup in the Hash Join node
EXPLAIN (ANALYZE, BUFFERS)
SELECT p.id, p.name,
       SUM(oi.unit_price * oi.quantity) AS total_revenue,
       AVG(r.rating) AS avg_rating
FROM products p
JOIN order_items oi ON oi.product_id = p.id
JOIN reviews r ON r.product_id = p.id
GROUP BY p.id, p.name;
```

```
HashAggregate  (actual rows=1000 loops=1)
  ->  Hash Join  (actual rows=120000 loops=1)   ← 120k rows from Cartesian product
        Hash Cond: (r.product_id = p.id)
        ->  Hash Join  (actual rows=30000 loops=1)
              (order_items × products intermediate)
        ->  Hash  (actual rows=40000 loops=1)    ← reviews rows
```

```sql
-- Good: CTE approach — row counts are correct at each step
EXPLAIN (ANALYZE, BUFFERS)
WITH revenue AS (
  SELECT product_id, SUM(unit_price * quantity) AS total_revenue
  FROM order_items GROUP BY product_id
),
avg_rating AS (
  SELECT product_id, AVG(rating) AS avg_rating
  FROM reviews WHERE status = 'approved' GROUP BY product_id
)
SELECT p.id, p.name, rev.total_revenue, rat.avg_rating
FROM products p
LEFT JOIN revenue rev ON rev.product_id = p.id
LEFT JOIN avg_rating rat ON rat.product_id = p.id;
```

```
Hash Left Join  (actual rows=1000 loops=1)   ← 1 row per product
  ->  Hash Left Join  (actual rows=1000 loops=1)
        ->  Seq Scan on products  (actual rows=1000 loops=1)
        ->  Hash  (actual rows=1000 loops=1)  ← revenue CTE: 1 row/product
  ->  Hash  (actual rows=950 loops=1)          ← avg_rating CTE: 1 row/product
```

| Query | Intermediate Rows | Result Rows | Revenue Correct? |
|-------|------------------|-------------|-----------------|
| Bad (double JOIN) | 120,000 | 1,000 | No — inflated 4× |
| Good (separate CTEs) | 1,000 per CTE | 1,000 | Yes |

## Aurora/RDS Notes

- **Aurora PostgreSQL**: The correctness bug is identical on Aurora. EXPLAIN ANALYZE on Aurora shows the same row count blowup. The fix — aggregating in separate CTEs — is the same on community PostgreSQL and Aurora.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | CTEs inlined by default (PG 12+); add `MATERIALIZED` if you need a separate execution step |
| PostgreSQL 15 | Same |
| PostgreSQL 16 | Same |
| PostgreSQL 17 | Same |
| Aurora PostgreSQL | Same as community; CTE behavior (inlined vs materialized) matches community PG version |
