---
title: "Add indexes for WHERE, JOIN, and ORDER BY columns"
impact: critical
tags: [indexes, sequential-scan, performance, query-optimization]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Add indexes for WHERE, JOIN, and ORDER BY columns

## Problem

When a query's WHERE clause, JOIN condition, or ORDER BY references a column with no index, PostgreSQL performs a sequential scan — reading every row in the table to find matching ones. On a table with millions of rows this turns a millisecond lookup into a multi-second operation. Missing indexes are the single most common cause of PostgreSQL performance problems.

PostgreSQL's cost-based planner may still choose a sequential scan on small tables (below roughly 1,000–10,000 rows) even when an index exists, because the overhead of an index scan exceeds the cost of reading a few pages. As data grows, this threshold is crossed and the missing index becomes critical.

## Bad Example

```sql
-- Find all pending orders (status column has no index)
SELECT id, user_id, total_amount, created_at
FROM   orders
WHERE  status = 'pending';
```

Without an index on `orders.status`, PostgreSQL reads every row in `orders` and evaluates the WHERE predicate on each one. On a 5M-row table with only 1,000 `'pending'` rows, PostgreSQL still reads all 5M.

```sql
-- ORDER BY on a non-indexed column causes a Sort node
SELECT id, total_amount
FROM   orders
WHERE  user_id = $1
ORDER  BY total_amount DESC;
```

If `total_amount` is not part of any index, PostgreSQL fetches all orders for user `$1` (using an index on `user_id`) and then sorts them with a separate Sort node in the plan.

## Good Example

```sql
-- Create an index on the filtered column
CREATE INDEX idx_orders_status ON orders (status);

-- The query is now an index scan instead of a sequential scan
SELECT id, user_id, total_amount, created_at
FROM   orders
WHERE  status = 'pending';
```

```sql
-- Better: composite index serves both the WHERE and ORDER BY
CREATE INDEX idx_orders_user_total ON orders (user_id, total_amount);

SELECT id, total_amount
FROM   orders
WHERE  user_id = $1
ORDER  BY total_amount DESC;
-- EXPLAIN: Index Scan using idx_orders_user_total — no separate Sort node
```

The composite index `(user_id, total_amount)` satisfies the equality predicate on `user_id` and provides pre-sorted `total_amount` values, eliminating the separate sort step.

## Why It Matters

- **Sequential scan cost**: Each sequential scan reads every data page. On a 10 GB table with a cold buffer cache, this is potentially 10 GB of I/O and full buffer pool eviction for every query.
- **Row examination ratio**: A missing-index query on 5M rows with 1,000 matching rows examines 5,000× more rows than necessary.
- **Planner cost thresholds**: PostgreSQL uses `random_page_cost` (default 4.0) vs `seq_page_cost` (default 1.0) to decide between index and sequential scans. On SSDs or Aurora, setting `random_page_cost = 1.1` makes the planner prefer index scans for smaller selectivities.
- **Concurrency**: Sequential scans hold `AccessShareLock` on every page for longer, increasing lock contention with concurrent DDL.
- **Aurora-specific**: On Aurora PostgreSQL, sequential scans trigger distributed storage reads. Each buffer-cache miss is a network call to the Aurora storage layer, adding 1–5 ms per page miss compared to local SSD.

## EXPLAIN Notes

```sql
-- Check the bad query plan:
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT id, user_id, total_amount, created_at
FROM orders WHERE status = 'pending';
```

Expected bad output:
```
Seq Scan on orders  (cost=0.00..98765.00 rows=1024 width=40)
                    (actual time=0.05..2341.00 rows=1024 loops=1)
  Filter: (status = 'pending'::order_status)
  Rows Removed by Filter: 4999000
  Buffers: shared read=50000
```

```sql
-- After adding the index:
CREATE INDEX idx_orders_status ON orders (status);
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT id, user_id, total_amount, created_at
FROM orders WHERE status = 'pending';
```

Expected good output:
```
Index Scan using idx_orders_status on orders
                    (cost=0.43..5123.00 rows=1024 width=40)
                    (actual time=0.08..12.40 rows=1024 loops=1)
  Index Cond: (status = 'pending'::order_status)
  Buffers: shared hit=1027
```

| Query | Node | Rows Removed | Buffers | Time |
|-------|------|-------------|---------|------|
| Bad   | Seq Scan | 4,999,000 | shared read=50000 | ~2,341 ms |
| Good  | Index Scan | 0 | shared hit=1027 | ~12 ms |

## How to Find Missing Indexes

```sql
-- Queries with sequential scans, via pg_stat_statements
SELECT
  LEFT(query, 120)                          AS query_snippet,
  calls,
  ROUND(total_exec_time::numeric, 2)        AS total_ms,
  ROUND(mean_exec_time::numeric, 2)         AS mean_ms,
  rows
FROM   pg_stat_statements
WHERE  query ILIKE '%orders%'
ORDER  BY total_exec_time DESC
LIMIT  20;

-- Tables with high sequential scan counts
SELECT
  schemaname,
  relname,
  seq_scan,
  seq_tup_read,
  idx_scan,
  n_live_tup
FROM   pg_stat_user_tables
WHERE  seq_scan > 0
ORDER  BY seq_tup_read DESC
LIMIT  20;
```

## Aurora/RDS Notes

- **Aurora PostgreSQL**: Setting `random_page_cost = 1.1` in the parameter group is strongly recommended on Aurora — Aurora storage is network-attached SSD and random I/O cost is similar to sequential. This makes the planner more likely to choose index scans.
- **RDS PostgreSQL**: Enable `pg_stat_statements` via the parameter group (`shared_preload_libraries = pg_stat_statements`) to identify missing-index queries. Changes to `shared_preload_libraries` require an instance reboot.
- **RDS Proxy**: Connections that hold long sequential scans reduce effective pool capacity. Short-circuit with indexes.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | `EXPLAIN (ANALYZE, BUFFERS)` available; `pg_stat_statements` extension available |
| PostgreSQL 15 | Same; `pg_stat_statements` tracks WAL usage per query |
| PostgreSQL 16 | `pg_stat_io` added for finer I/O breakdown |
| PostgreSQL 17 | Same; vacuum improvements reduce bloat that inflates seq scan cost |
| Aurora PostgreSQL | `random_page_cost` should be set to `1.1`; Performance Insights integrates with `pg_stat_statements` |
