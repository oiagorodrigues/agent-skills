---
title: "Understand CTE inlining vs materialization in PostgreSQL 12+"
impact: medium
tags: [cte, with-clause, materialized, recursive, query-optimization, pg-12]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Understand CTE inlining vs materialization in PostgreSQL 12+

## Problem

In PostgreSQL 11 and earlier, CTEs (Common Table Expressions, `WITH` clauses) were always **materialized** — executed once and the results stored temporarily, acting as an optimization fence. In PostgreSQL 12+, the default changed: CTEs are **inlined** (treated as subqueries) when the planner decides it's cheaper. This change broke some query patterns that relied on CTEs as optimization fences, and made others faster. Understanding when CTEs are materialized vs inlined — and how to control it — is essential.

## Bad Example

```sql
-- BAD (PostgreSQL 11 only): CTE was always materialized — acted as fence
-- This could cause performance regressions in PG 12+ (CTE is now inlined,
-- which is usually good, but sometimes surprising)

-- PostgreSQL 11: this CTE ran once and cached results (optimization fence)
WITH filtered_orders AS (
  SELECT id, user_id, total_amount
  FROM   orders
  WHERE  status = 'paid'
    AND  created_at >= '2024-01-01'
)
SELECT u.email, fo.total_amount
FROM   filtered_orders fo
JOIN   users u ON u.id = fo.user_id;
-- In PG 11: filtered_orders executed once, results stored
-- In PG 12+: CTE is inlined — planner rewrites as a direct subquery

-- BAD (PG 12+ only): Assuming CTE is an optimization fence when it's not
-- This is problematic when the CTE has side effects (VOLATILE functions)
-- or when you explicitly need the fence behavior for performance
WITH random_sample AS (
  SELECT id FROM orders ORDER BY RANDOM() LIMIT 100
)
SELECT * FROM random_sample r1
JOIN   random_sample r2 ON r2.id > r1.id;
-- In PG 12+, random_sample is inlined — RANDOM() is called twice!
-- The two references get different random samples, so the JOIN is wrong
```

## Good Example

```sql
-- GOOD 1: Explicit MATERIALIZED keyword to force the fence behavior
-- Use when you need to guarantee the CTE executes exactly once
WITH random_sample AS MATERIALIZED (
  SELECT id FROM orders ORDER BY RANDOM() LIMIT 100
)
SELECT * FROM random_sample r1
JOIN   random_sample r2 ON r2.id > r1.id;
-- With MATERIALIZED: random_sample executes once, results reused — correct

-- GOOD 2: Explicit NOT MATERIALIZED to force inlining (PG 12 default behavior)
-- Use when you know the CTE should be inlined for performance
WITH paid_orders AS NOT MATERIALIZED (
  SELECT id, user_id, total_amount
  FROM   orders
  WHERE  status = 'paid'
)
SELECT u.email, po.total_amount
FROM   paid_orders po
JOIN   users u ON u.id = po.user_id
WHERE  po.total_amount > 100;
-- NOT MATERIALIZED: planner can push the WHERE total_amount > 100 into the CTE
-- and use better indexes — just like a subquery

-- GOOD 3: CTE for avoiding over-join aggregation (ALWAYS use MATERIALIZED here)
-- Even if the planner would inline it, explicit materialization ensures
-- each CTE is executed independently (see query-aggregation-over-join.md)
WITH revenue AS MATERIALIZED (
  SELECT product_id, SUM(unit_price * quantity) AS total_revenue
  FROM   order_items
  GROUP  BY product_id
),
avg_rating AS MATERIALIZED (
  SELECT product_id, AVG(rating) AS avg_rating
  FROM   reviews WHERE status = 'approved'
  GROUP  BY product_id
)
SELECT p.id, p.name, r.total_revenue, a.avg_rating
FROM   products p
LEFT JOIN revenue  r ON r.product_id = p.id
LEFT JOIN avg_rating a ON a.product_id = p.id;

-- GOOD 4: Recursive CTE for tree traversal
-- Find all subcategories of a given category (recursive closure)
WITH RECURSIVE category_tree AS (
  -- Base case: start with the target category
  SELECT id, parent_id, name, slug, 0 AS depth
  FROM   categories
  WHERE  id = $1   -- root category ID

  UNION ALL

  -- Recursive case: find children
  SELECT c.id, c.parent_id, c.name, c.slug, ct.depth + 1
  FROM   categories c
  JOIN   category_tree ct ON ct.id = c.parent_id
  WHERE  ct.depth < 10   -- guard against infinite loops (circular references)
)
SELECT id, name, slug, depth
FROM   category_tree
ORDER  BY depth, name;
```

```sql
-- GOOD 5: CTE for the DELETE ... RETURNING pattern
-- Delete and return old values atomically
WITH deleted AS (
  DELETE FROM orders
  WHERE  status = 'cancelled'
    AND  created_at < NOW() - INTERVAL '1 year'
  RETURNING id, user_id, total_amount
)
INSERT INTO archived_orders (id, user_id, total_amount, archived_at)
SELECT id, user_id, total_amount, NOW()
FROM   deleted;
-- CTE DELETE + INSERT is atomic — no risk of data appearing in both tables
-- This is always materialized by definition (it's a DML CTE with RETURNING)
```

## When to Use MATERIALIZED vs NOT MATERIALIZED

| Scenario | Recommendation |
|----------|---------------|
| CTE referenced multiple times with VOLATILE function (RANDOM, NOW, etc.) | `MATERIALIZED` — execute once |
| CTE used for over-join aggregation | `MATERIALIZED` — ensure independent execution |
| CTE with no side effects, used once | `NOT MATERIALIZED` (default in PG 12+) — let planner inline |
| Recursive CTE | Always materialized — `RECURSIVE` implies materialization |
| DML CTE with `RETURNING` | Always materialized — DML is always a fence |
| CTE as optimization fence for known-bad planner decision | `MATERIALIZED` — forces barrier |

## EXPLAIN Notes

```sql
-- Check if a CTE is being materialized or inlined:
EXPLAIN (ANALYZE, VERBOSE)
WITH paid_orders AS (
  SELECT id, user_id FROM orders WHERE status = 'paid'
)
SELECT u.email FROM paid_orders po JOIN users u ON u.id = po.user_id;
```

```
-- Inlined (default in PG 12+) — no CTE node in plan:
Hash Join  (cost=...)
  ->  Index Scan on orders (status = 'paid')
  ->  Hash
        ->  Seq Scan on users

-- Materialized (with MATERIALIZED keyword) — CTE appears as a separate node:
Hash Join
  ->  CTE Scan on paid_orders   ← separate materialized node
  ->  Hash
        ->  Seq Scan on users
        CTE paid_orders
          ->  Index Scan on orders (status = 'paid')
```

## Aurora/RDS Notes

- **Aurora PostgreSQL 12+**: CTE behavior matches community PostgreSQL — inlined by default, `MATERIALIZED`/`NOT MATERIALIZED` keywords available.
- **Aurora PostgreSQL 10/11**: CTEs always materialized (old behavior). Queries relying on fence behavior work correctly. After upgrading to Aurora PG 12+, test CTE queries for behavior changes.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | CTEs inlined by default (since PG 12); `MATERIALIZED` keyword available |
| PostgreSQL 15 | Same |
| PostgreSQL 16 | Same |
| PostgreSQL 17 | Same |
| Aurora PostgreSQL 12+ | Same as community; Aurora PG 11 and earlier always materializes CTEs |
