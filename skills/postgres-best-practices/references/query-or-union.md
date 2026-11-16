---
title: "Replace OR across unrelated columns with UNION ALL"
impact: medium
tags: [or, union-all, indexes, bitmap-scan, query-optimization]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Replace OR across unrelated columns with UNION ALL

## Problem

A WHERE clause with `OR` across two columns that have separate indexes may prevent effective index use. PostgreSQL has a `BitmapOr` plan type that combines two bitmap index scans, but it is not always used, and when it is, the bitmap heap scan that follows it can be slow when the combined result set is large or spread across many heap pages. Rewriting as `UNION ALL` gives each branch its own execution plan with a clean index scan.

## Bad Example

```sql
-- OR across two unrelated columns: status and role
-- PostgreSQL may try BitmapOr, but may fall back to Seq Scan
-- depending on selectivity estimates
SELECT id, email, status, role
FROM   users
WHERE  status = 'active'
   OR  role   = 'admin';
```

For large tables, PostgreSQL estimates the combined selectivity of the OR condition. If either branch is highly selective but together they cover most of the table, the planner may skip both indexes and do a sequential scan.

```sql
-- OR across order status and user_id (unrelated columns, different indexes)
SELECT id, user_id, total_amount, created_at
FROM   orders
WHERE  status = 'pending'
   OR  user_id = $1;
```

## Good Example

```sql
-- UNION ALL: each branch gets its own Index Scan plan
-- Branch 1 uses idx_users_status, Branch 2 uses idx_users (role index if exists)
SELECT id, email, status, role
FROM   users
WHERE  status = 'active'
UNION ALL
SELECT id, email, status, role
FROM   users
WHERE  role = 'admin'
  AND  status <> 'active';   -- exclude overlap to avoid duplicates
```

```sql
-- When duplicates are acceptable or impossible:
SELECT id, user_id, total_amount, created_at
FROM   orders
WHERE  status = 'pending'
UNION ALL
SELECT id, user_id, total_amount, created_at
FROM   orders
WHERE  user_id = $1
  AND  status <> 'pending';   -- avoid double-counting the user's pending orders
```

```sql
-- When BitmapOr is acceptable (both columns indexed, result set is small):
-- PostgreSQL will automatically use BitmapOr for two indexes on the same table
-- Check EXPLAIN to see whether BitmapOr or UNION ALL is faster for your data
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, email FROM users WHERE status = 'active' OR role = 'admin';
-- If EXPLAIN shows BitmapOr with low buffer reads and fast execution, keep the OR.
-- If it shows Seq Scan, rewrite as UNION ALL.
```

```sql
-- Add an index on role if it doesn't exist:
CREATE INDEX idx_users_role ON users (role);
-- With both idx_users_status and idx_users_role present,
-- PostgreSQL can do BitmapOr for small result sets.
```

## Why It Matters

- **BitmapOr is conditional**: PostgreSQL uses BitmapOr when both columns are indexed and the combined selectivity is high (small result). For low-selectivity predicates (large result), BitmapOr degrades to a sequential scan.
- **UNION ALL guarantees two Index Scans**: Each branch of UNION ALL is planned independently. Even if each branch has high selectivity, both get their own index path.
- **Duplicate handling**: `UNION ALL` includes duplicates. If both branches can return the same row, add a `NOT IN` or `AND col <> val` exclusion to one branch, or use `UNION` (which deduplicates, but is slower).
- **Three or more OR conditions**: The BitmapOr approach degrades quickly with more conditions. For three or more unrelated column ORs, UNION ALL is almost always faster.

## EXPLAIN Notes

```sql
-- Check which plan PostgreSQL chooses:
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, email, status FROM users WHERE status = 'active' OR role = 'admin';
```

PostgreSQL may produce:
```
-- BitmapOr (acceptable when result set is small):
Bitmap Heap Scan on users  (actual rows=1250 loops=1)
  Recheck Cond: ((status = 'active') OR (role = 'admin'))
  ->  BitmapOr
        ->  Bitmap Index Scan on idx_users_status  (rows=1200)
        ->  Bitmap Index Scan on idx_users_role    (rows=50)
  Buffers: shared hit=185
```

Or worse:
```
-- Seq Scan (bad — planner decided OR scan is cheaper):
Seq Scan on users  (actual rows=1250 loops=1)
  Filter: ((status = 'active') OR (role = 'admin'))
  Rows Removed by Filter: 98750
  Buffers: shared hit=2500
```

With UNION ALL:
```
-- Each branch uses its own index:
Append
  ->  Index Scan using idx_users_status on users
        Index Cond: (status = 'active')
        actual rows=1200
  ->  Index Scan using idx_users_role on users
        Index Cond: (role = 'admin')
        Filter: (status <> 'active')
        actual rows=50
  Total Buffers: shared hit=28
```

| Query | Node | Buffers | Notes |
|-------|------|---------|-------|
| OR (bad plan) | Seq Scan | shared hit=2500 | Planner avoided both indexes |
| OR (BitmapOr) | BitmapOr | shared hit=185 | Acceptable for small results |
| UNION ALL | 2 × Index Scan | shared hit=28 | Guaranteed index use |

## Aurora/RDS Notes

- **Aurora PostgreSQL**: `random_page_cost = 1.1` in the parameter group makes BitmapOr more attractive (random I/O is cheap on Aurora). Even with this setting, UNION ALL is more predictable for large OR conditions.
- **RDS PostgreSQL**: Same behavior as community PostgreSQL. Check `pg_stat_statements` for high-execution queries with sequential scans and OR predicates.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | BitmapOr available; UNION ALL behavior unchanged |
| PostgreSQL 15 | Same |
| PostgreSQL 16 | Same |
| PostgreSQL 17 | Same |
| Aurora PostgreSQL | Same; `random_page_cost = 1.1` in parameter group recommended |
