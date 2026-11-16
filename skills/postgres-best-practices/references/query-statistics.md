---
title: "Tune ANALYZE statistics targets for high-cardinality and skewed columns"
impact: medium
tags: [statistics, analyze, planner, cardinality, performance]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Tune ANALYZE statistics targets for high-cardinality and skewed columns

## Problem

PostgreSQL's query planner makes decisions based on column statistics: the number of distinct values (`n_distinct`), common value frequencies (`most_common_vals`), and histogram bounds. These statistics are gathered by `ANALYZE` and stored in `pg_statistic`. The default statistics target of 100 samples is insufficient for high-cardinality columns or columns with skewed distributions — the planner underestimates row counts and chooses bad plans (wrong join order, wrong join type, seq scan vs index scan).

## Bad Example

```sql
-- Default statistics target (100) on a high-cardinality user_id column
-- The planner has coarse histograms and may underestimate rows for specific users

-- Query: get all orders for a very active user (has 50,000 orders)
SELECT id, status, total_amount, created_at
FROM   orders
WHERE  user_id = $1
ORDER  BY created_at DESC
LIMIT  100;
```

With default statistics, if the histogram has only 100 buckets for `user_id`, the planner estimates ~50 rows for any given user. For a user with 50,000 orders, the planner underestimates 1,000× — it may choose a Nested Loop where a Hash Join would be faster, or choose an index scan where a sequential scan is better.

```sql
-- Bad: no multi-column statistics for correlated columns
-- city and state are highly correlated — knowing city = 'Portland' almost
-- implies state = 'OR'. Without extended statistics, the planner treats them
-- as independent and severely underestimates the combined selectivity.
SELECT * FROM users WHERE city = 'Portland' AND state = 'OR';
```

## Good Example

```sql
-- GOOD 1: Increase statistics target for high-cardinality columns
ALTER TABLE orders ALTER COLUMN user_id SET STATISTICS 500;
ANALYZE orders;
-- Now ANALYZE samples 500 values for user_id — better histogram resolution
-- EXPLAIN estimates will be much closer to actual row counts for specific users

-- Reset to default if needed:
-- ALTER TABLE orders ALTER COLUMN user_id SET STATISTICS -1;  -- use default
```

```sql
-- GOOD 2: Create extended (multi-column) statistics for correlated columns
-- This teaches the planner that city and state are correlated
CREATE STATISTICS stat_users_city_state ON city, state FROM users;
-- (assumes users table has city and state columns)
ANALYZE users;
-- Now WHERE city = 'Portland' AND state = 'OR' has an accurate combined estimate

-- For the e-commerce schema: correlated status + user_id on orders
CREATE STATISTICS stat_orders_user_status ON user_id, status FROM orders;
ANALYZE orders;
```

```sql
-- GOOD 3: Check current statistics for a column
SELECT
  attname,
  n_distinct,
  correlation,
  most_common_vals,
  most_common_freqs,
  histogram_bounds
FROM   pg_stats
WHERE  tablename = 'orders'
  AND  attname   = 'user_id';

-- Check if statistics are stale (last analyze time)
SELECT
  relname,
  last_analyze,
  last_autoanalyze,
  n_live_tup,
  n_mod_since_analyze
FROM pg_stat_user_tables
WHERE relname = 'orders';
```

```sql
-- GOOD 4: Manually run ANALYZE on a fast-growing table
-- RDS auto-analyze may not run often enough on tables growing by millions
-- of rows per day
ANALYZE orders;
ANALYZE order_items;
-- Or analyze a specific column:
ANALYZE orders (user_id, status, created_at);   -- PostgreSQL 15+
```

## Why It Matters

- **Statistics target = histogram resolution**: The default target of 100 means `ANALYZE` collects up to 100 common values and 100 histogram buckets. For a column with 1M distinct values, 100 buckets are coarse — row count estimates for specific values can be off by 10–1000×.
- **Skewed distributions**: If 5% of users account for 80% of orders, a 100-bucket histogram may not capture the hottest users accurately. Increasing the target to 500 gives 5× more resolution.
- **Multi-column correlations**: Two correlated columns (e.g., `status` and `paid_at` — if `status = 'paid'` then `paid_at IS NOT NULL` always) appear independent to the planner without extended statistics. The planner multiplies their individual selectivities, severely underestimating the combined result.
- **Impact on join order**: The planner's hash join vs. nested loop decision depends on row count estimates. A 1000× row count underestimate can cause the planner to choose a nested loop join that scans a large table once per outer row.

## EXPLAIN Notes

```sql
-- Check estimated vs actual row counts after ANALYZE
EXPLAIN (ANALYZE)
SELECT id, status, total_amount FROM orders WHERE user_id = 12345;
```

Without tuned statistics:
```
Index Scan using idx_orders_user_id on orders
  (cost=0.43..125.00 rows=50 width=40)       ← estimated: 50 rows
  (actual time=0.12..18.50 rows=50000 loops=1) ← actual: 50,000 rows
```

After `ALTER TABLE orders ALTER COLUMN user_id SET STATISTICS 500; ANALYZE orders;`:
```
Index Scan using idx_orders_user_id on orders
  (cost=0.43..48500.00 rows=50000 width=40)    ← estimated: 50,000 rows (accurate)
  (actual time=0.12..18.50 rows=50000 loops=1)
```

When estimated ≈ actual, the planner makes better join and scan type decisions.

## Aurora/RDS Notes

- **RDS PostgreSQL**: `autovacuum_analyze_scale_factor = 0.05` (default: analyze after 5% of rows change). On tables growing rapidly by INSERTs alone (new rows don't trigger autovacuum), auto-analyze may not run often enough. Schedule manual `ANALYZE` for fast-growing tables.
- **Aurora PostgreSQL**: Aurora Performance Insights shows queries with high `rows examined / rows returned` ratios — a signal of poor statistics. The fix is always `ANALYZE` + possibly increasing the statistics target.
- **RDS parameter**: `default_statistics_target` can be increased globally via the parameter group (from 100 to 200–500 for analytics-heavy workloads) — but increasing it globally slows down `ANALYZE`. Per-column overrides are preferred.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | Extended statistics (`CREATE STATISTICS`) available; `pg_stats` view available |
| PostgreSQL 15 | `ANALYZE table (column1, column2)` for per-column selective analyze |
| PostgreSQL 16 | Extended statistics improvements |
| PostgreSQL 17 | Same |
| Aurora PostgreSQL | Same as community; Performance Insights shows row estimate accuracy metrics |
