---
title: "Use pg_hint_plan for targeted planner overrides, not global GUC disables"
impact: medium
tags: [optimizer, hints, pg_hint_plan, planner, statistics, explain]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Use pg_hint_plan for targeted planner overrides, not global GUC disables

## Problem

PostgreSQL's cost-based planner occasionally chooses a suboptimal plan due to stale statistics, bad row count estimates, or incorrect cost parameters. Unlike MySQL, PostgreSQL has no built-in `USE INDEX` or `FORCE INDEX` syntax. The common workaround — disabling planner options globally with `SET enable_seqscan = off` — is dangerous in production because it affects every query in the session or globally. The correct approach is `pg_hint_plan` for targeted overrides, or fixing the root cause (running `ANALYZE`, adjusting statistics targets, or tuning `random_page_cost`).

## Bad Example

```sql
-- BAD: Disabling sequence scans globally for the session to force an index scan
-- This forces every query in this session to avoid sequential scans,
-- even queries where sequential scans are legitimately faster.
SET enable_seqscan = off;

SELECT id, user_id, total_amount
FROM   orders
WHERE  status = 'paid'
ORDER  BY created_at DESC
LIMIT  20;

-- Setting this in postgresql.conf or RDS parameter group affects ALL sessions
-- SET enable_seqscan = off;  -- DO NOT do this globally
```

```sql
-- BAD: Disabling nested loops globally to fix one slow JOIN
SET enable_nestloop = off;
-- Now all nested loops are avoided, even where they are optimal (small outer input)
```

## Good Example

```sql
-- GOOD 1: Fix the root cause — stale statistics
-- The planner chooses a bad plan because it underestimates row counts
ANALYZE orders;    -- updates statistics for the orders table
-- Re-run the query — the planner now has accurate cardinality estimates

-- GOOD 2: Increase statistics target for high-cardinality columns
ALTER TABLE orders ALTER COLUMN user_id SET STATISTICS 500;
ANALYZE orders;
-- Default statistics target is 100 — increase for columns with high cardinality
-- or skewed distributions where the default underestimates row counts
```

```sql
-- GOOD 3: Use pg_hint_plan for targeted plan overrides (PostgreSQL extension)
-- Install: CREATE EXTENSION pg_hint_plan;
-- Then use hint comments to guide the planner for one specific query

-- Force an index scan on orders using a specific index
/*+ IndexScan(orders idx_orders_status_created_total) */
SELECT id, user_id, total_amount
FROM   orders
WHERE  status = 'paid'
ORDER  BY created_at DESC
LIMIT  20;

-- Force a hash join between orders and users
/*+ HashJoin(orders users) */
SELECT o.id, u.email, o.total_amount
FROM   orders o
JOIN   users  u ON u.id = o.user_id
WHERE  o.status = 'paid';

-- Force a sequential scan on a small table (override an index that hurts here)
/*+ SeqScan(categories) */
SELECT * FROM categories WHERE is_active = TRUE;
```

```sql
-- GOOD 4: Session-scoped GUC with immediate reset — acceptable for single queries
SET LOCAL enable_seqscan = off;    -- only affects the current transaction
SELECT id, user_id, total_amount
FROM   orders
WHERE  status = 'paid'
ORDER  BY created_at DESC
LIMIT  20;
RESET enable_seqscan;              -- or let the transaction end
```

```sql
-- GOOD 5: Adjust random_page_cost for SSD/Aurora storage
-- Tells the planner index random I/O is cheap (appropriate for SSDs and Aurora)
ALTER SYSTEM SET random_page_cost = 1.1;
SELECT pg_reload_conf();
-- Now the planner prefers index scans more aggressively for all queries
-- This is a global change but a correct tuning for SSD-backed instances
```

## Why It Matters

- **Root cause first**: Most "bad plans" are caused by stale statistics (`n_distinct`, `correlation`, histogram bounds). Run `ANALYZE` on the affected table and re-check the plan before reaching for hints.
- **`enable_*` GUCs are blunt instruments**: `SET enable_seqscan = off` does not make sequential scans impossible — it makes their cost artificially high (10,000×). The planner will avoid them but the setting affects every query in the scope.
- **`pg_hint_plan` is surgical**: Hints are embedded in the query comment and only affect that specific query. No global state is changed.
- **When to use hints**: Hints are appropriate when: (1) you have verified the plan is wrong via EXPLAIN, (2) you have run ANALYZE and the plan is still wrong, and (3) you have a specific known-good alternative plan. Do not use hints as a substitute for proper statistics.
- **Aurora availability**: `pg_hint_plan` is available on Aurora PostgreSQL as a supported extension.

## EXPLAIN Notes

```sql
-- Diagnose a bad plan: compare estimated rows vs actual rows
EXPLAIN (ANALYZE, FORMAT TEXT)
SELECT id, user_id, total_amount
FROM orders WHERE status = 'paid' ORDER BY created_at DESC LIMIT 20;
```

Key signals of a bad plan:
```
Index Scan using idx_orders_created_at on orders
  (cost=0.56..9999.00 rows=5000000 width=40)   ← estimated 5M rows
  (actual time=0.10..2341.00 rows=50 loops=1)  ← actually 50 rows
```

Large discrepancy between `rows=5000000` (estimate) and `rows=50` (actual) means the statistics are stale. Fix:
```sql
ANALYZE orders;   -- or increase statistics target for the status column
-- Then re-run EXPLAIN — estimates should now be close to actuals
```

## Aurora/RDS Notes

- **Aurora PostgreSQL**: `pg_hint_plan` is available as a supported extension. Load it via `CREATE EXTENSION pg_hint_plan` (requires `shared_preload_libraries = 'pg_hint_plan'` in the parameter group and a reboot).
- **RDS PostgreSQL**: `random_page_cost` should be set to `1.1` in the parameter group for all RDS/Aurora PostgreSQL instances backed by GP2, GP3, or io1 EBS. The default `4.0` is for spinning disks and causes the planner to underuse indexes on SSD-backed instances.
- **`auto_explain`**: Available on both RDS and Aurora PostgreSQL via parameter group. Set `auto_explain.log_min_duration = 1000` to automatically log EXPLAIN plans for slow queries without manual intervention.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | `plan_cache_mode` GUC available (auto/force_generic_plan/force_custom_plan) |
| PostgreSQL 15 | Same |
| PostgreSQL 16 | Same |
| PostgreSQL 17 | Same; `EXPLAIN (SERIALIZE)` added to measure serialization overhead |
| Aurora PostgreSQL | `pg_hint_plan` supported; `random_page_cost = 1.1` recommended in parameter group |
