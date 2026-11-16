---
title: "Use window functions for ranked, running, and partitioned calculations"
impact: medium
tags: [window-functions, row-number, rank, lag, lead, distinct-on, performance]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Use window functions for ranked, running, and partitioned calculations

## Problem

Without window functions, calculations like "top N per group," "running total," or "previous row value" require correlated subqueries or self-joins that are slow and hard to read. Window functions perform these calculations in a single pass over the sorted data with O(n log n) complexity instead of O(n²) for self-join approaches. PostgreSQL also has `DISTINCT ON` — a unique syntax for the "latest record per group" pattern that outperforms most alternatives.

## Bad Example

```sql
-- BAD: Correlated subquery for row number per group
-- O(n²): for each order, count all earlier orders for the same user
SELECT o.id, o.user_id, o.total_amount, o.created_at,
  (SELECT COUNT(*) + 1
   FROM orders o2
   WHERE o2.user_id = o.user_id
     AND o2.created_at < o.created_at) AS order_number
FROM orders o
WHERE o.status = 'paid';
-- Executes a subquery once per row — 100k orders = 100k subqueries

-- BAD: Self-join for "latest order per user"
SELECT o.*
FROM   orders o
LEFT JOIN orders o2 ON o2.user_id = o.user_id AND o2.created_at > o.created_at
WHERE  o2.id IS NULL;   -- no newer order exists → this is the latest
-- Full self-join: O(n²) — extremely slow on large tables
```

## Good Example

```sql
-- GOOD 1: ROW_NUMBER() for row ranking within a partition
SELECT
  id,
  user_id,
  total_amount,
  created_at,
  ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at ASC) AS order_number
FROM orders
WHERE status = 'paid';
-- Single pass over the data — O(n log n) for the sort

-- GOOD 2: Top-N per group using ROW_NUMBER in a CTE
-- Get the 3 most recent orders per user:
WITH ranked_orders AS (
  SELECT
    id,
    user_id,
    total_amount,
    created_at,
    ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at DESC) AS rn
  FROM orders
  WHERE status = 'paid'
)
SELECT id, user_id, total_amount, created_at
FROM   ranked_orders
WHERE  rn <= 3;

-- GOOD 3: DISTINCT ON — PostgreSQL-specific syntax for "latest per group"
-- More concise than ROW_NUMBER() for simple "first/last per group" cases
SELECT DISTINCT ON (user_id)
  id, user_id, total_amount, created_at
FROM   orders
WHERE  status = 'paid'
ORDER  BY user_id, created_at DESC;
-- Returns exactly one row per user_id — the most recent paid order
-- EXPLAIN: uses a sort + unique or index scan with DISTINCT ON
-- Requires: ORDER BY must start with the DISTINCT ON columns

-- GOOD 4: Running total with SUM() OVER
SELECT
  id,
  user_id,
  total_amount,
  created_at,
  SUM(total_amount) OVER (
    PARTITION BY user_id
    ORDER BY created_at
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS running_total
FROM orders
WHERE status = 'paid'
ORDER BY user_id, created_at;

-- GOOD 5: LAG() and LEAD() for previous/next row values
-- Calculate day-over-day revenue change:
WITH daily_revenue AS (
  SELECT
    DATE_TRUNC('day', created_at) AS order_date,
    SUM(total_amount)              AS daily_revenue
  FROM orders
  WHERE status = 'paid'
  GROUP BY DATE_TRUNC('day', created_at)
)
SELECT
  order_date,
  daily_revenue,
  LAG(daily_revenue, 1) OVER (ORDER BY order_date) AS prev_day_revenue,
  daily_revenue - LAG(daily_revenue, 1) OVER (ORDER BY order_date) AS day_over_day_change,
  ROUND(
    100.0 * (daily_revenue - LAG(daily_revenue, 1) OVER (ORDER BY order_date))
    / NULLIF(LAG(daily_revenue, 1) OVER (ORDER BY order_date), 0),
    2
  ) AS pct_change
FROM daily_revenue
ORDER BY order_date;

-- GOOD 6: RANK() vs DENSE_RANK() vs ROW_NUMBER()
SELECT
  id,
  user_id,
  total_amount,
  ROW_NUMBER() OVER (ORDER BY total_amount DESC) AS row_num,  -- 1,2,3,4... (no ties)
  RANK()       OVER (ORDER BY total_amount DESC) AS rank_num, -- 1,2,2,4... (gaps on ties)
  DENSE_RANK() OVER (ORDER BY total_amount DESC) AS dense_rk  -- 1,2,2,3... (no gaps)
FROM orders
WHERE status = 'paid';

-- GOOD 7: FIRST_VALUE / LAST_VALUE for reference values within a window
SELECT
  id,
  user_id,
  total_amount,
  created_at,
  FIRST_VALUE(total_amount) OVER (
    PARTITION BY user_id
    ORDER BY created_at
    ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
  ) AS first_order_amount,
  LAST_VALUE(total_amount) OVER (
    PARTITION BY user_id
    ORDER BY created_at
    ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
  ) AS latest_order_amount
FROM orders
WHERE status = 'paid';
```

## Performance Notes

```sql
-- Window functions require a sort (or index) for the ORDER BY in OVER()
-- Check if EXPLAIN shows a Sort node or Index Scan:
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, user_id, total_amount,
       ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at DESC) AS rn
FROM orders WHERE status = 'paid';

-- An index on (user_id, created_at DESC) can eliminate the Sort node:
CREATE INDEX idx_orders_user_created_desc ON orders (user_id, created_at DESC)
WHERE status = 'paid';  -- partial index if mostly filtering for paid

-- DISTINCT ON performance:
-- Needs ORDER BY starting with DISTINCT ON columns
-- An index on (user_id, created_at DESC) enables Index Only Scan for DISTINCT ON
```

## Why It Matters

- **Single pass vs multiple queries**: Window functions scan the data once. Correlated subqueries scan it once per row.
- **`DISTINCT ON` uniqueness**: PostgreSQL's `DISTINCT ON` is not standard SQL but is more concise and often faster than `ROW_NUMBER() WHERE rn = 1` for the latest-per-group pattern.
- **Sort elimination**: Window functions with `ORDER BY` require sorting. If an appropriate B-tree index exists matching the `PARTITION BY` + `ORDER BY` columns, PostgreSQL can use an Index Scan instead of a Sort node.
- **ROWS vs RANGE framing**: `ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` is the typical running-total frame. `RANGE` framing handles ties differently — be explicit.

## Aurora/RDS Notes

- **Aurora PostgreSQL**: Window functions work identically on Aurora. `DISTINCT ON` syntax is fully supported.
- **RDS PostgreSQL**: Same as community PostgreSQL.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | All standard window functions available; `DISTINCT ON` available |
| PostgreSQL 15 | Same |
| PostgreSQL 16 | Same |
| PostgreSQL 17 | Same |
| Aurora PostgreSQL | Window functions and `DISTINCT ON` fully supported |
