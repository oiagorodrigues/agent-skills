---
title: "Understand MVCC, dead tuples, vacuum, and transaction ID wraparound"
impact: critical
tags: [mvcc, vacuum, dead-tuples, bloat, wraparound, autovacuum, operations]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Understand MVCC, dead tuples, vacuum, and transaction ID wraparound

## Problem

PostgreSQL's MVCC (Multi-Version Concurrency Control) model means that every UPDATE creates a new row version and marks the old version as "dead." Every DELETE also marks a row as dead. These dead tuples accumulate until `VACUUM` reclaims them. Without proper autovacuum tuning:

1. **Table bloat**: Tables grow to 10× their live data size
2. **Query plan degradation**: Statistics become stale, sequential scans slow down
3. **Transaction ID (XID) wraparound**: The most critical PostgreSQL operational risk — if a table's `age(relfrozenxid)` reaches 2 billion, PostgreSQL will shut down the cluster to prevent data corruption

## Bad Example

```sql
-- BAD: Ignoring vacuum — typical UPDATE-heavy table behavior
-- Every UPDATE writes a new row version; the old one is "dead"
UPDATE orders SET status = 'shipped' WHERE status = 'processing';
-- If this runs 1000 times/second on 10k rows, dead tuples accumulate rapidly

-- After one week without vacuum on an orders table:
-- n_live_tup: 100,000
-- n_dead_tup: 7,000,000   ← 70× more dead than live tuples
-- Table size: 10 GB (data fits in ~100 MB)

-- No monitoring for XID age:
-- age(relfrozenxid) = 1,800,000,000   ← emergency territory (> 1.5B)
-- PostgreSQL will shut down the cluster if this reaches ~2.0 billion
```

```sql
-- Checking the warning signs (run this NOW if you don't already):
SELECT
  relname,
  n_live_tup,
  n_dead_tup,
  ROUND(n_dead_tup::numeric / NULLIF(n_live_tup + n_dead_tup, 0) * 100, 1) AS dead_pct,
  last_autovacuum,
  last_autoanalyze,
  age(relfrozenxid) AS xid_age
FROM   pg_stat_user_tables
ORDER  BY age(relfrozenxid) DESC;

-- ALERT: XID age > 1.5 billion is critical
-- ALERT: dead_pct > 20% means autovacuum is not keeping up
```

## Good Example

```sql
-- GOOD 1: Monitor autovacuum health regularly
SELECT
  schemaname,
  relname,
  n_live_tup,
  n_dead_tup,
  last_autovacuum,
  last_autoanalyze,
  autovacuum_count,
  age(relfrozenxid)   AS xid_age
FROM   pg_stat_user_tables
WHERE  n_dead_tup > 10000
   OR  age(relfrozenxid) > 500000000   -- 500M — start watching
ORDER  BY age(relfrozenxid) DESC;

-- GOOD 2: Tune autovacuum per table for high-churn tables
-- The default scale_factor = 0.2 means vacuum after 20% of rows change.
-- For a 1M-row table, that's 200,000 dead tuples before vacuum runs.
-- Reduce for high-churn tables:
ALTER TABLE orders SET (
  autovacuum_vacuum_scale_factor    = 0.01,   -- vacuum after 1% change (10k rows)
  autovacuum_vacuum_threshold       = 1000,   -- or 1000 dead tuples, whichever comes first
  autovacuum_analyze_scale_factor   = 0.005,  -- analyze after 0.5% change
  autovacuum_analyze_threshold      = 500
);

-- GOOD 3: Manual VACUUM ANALYZE for urgent cases
VACUUM (ANALYZE, VERBOSE) orders;
-- VERBOSE shows statistics: pages removed, dead tuples removed, etc.

-- GOOD 4: Emergency VACUUM FREEZE for XID wraparound risk
-- Run this if age(relfrozenxid) > 1.5 billion
VACUUM FREEZE VERBOSE orders;
-- FREEZE marks all rows as permanently frozen (no future XID age concern)
-- This is aggressive — only use when absolutely needed

-- GOOD 5: Monitor vacuum progress
SELECT
  phase,
  heap_blks_total,
  heap_blks_scanned,
  heap_blks_vacuumed,
  index_vacuum_count,
  num_dead_tuples,
  num_index_scans
FROM   pg_stat_progress_vacuum
WHERE  relid = 'orders'::regclass;
```

```sql
-- GOOD 6: Set autovacuum_freeze_max_age to control when forced vacuums run
-- Default: 200,000,000 (200M transactions before forced VACUUM FREEZE)
-- Conservative setting for production:
-- ALTER SYSTEM SET autovacuum_freeze_max_age = 150000000;  -- 150M
-- SELECT pg_reload_conf();

-- Monitor cluster-wide XID age:
SELECT MAX(age(relfrozenxid)) AS max_xid_age
FROM   pg_class
WHERE  relkind IN ('r', 't', 'm')  -- regular tables, TOAST tables, materialized views
  AND  relpersistence = 'p';        -- permanent tables only
```

## Why It Matters

- **MVCC dead tuples**: Every UPDATE creates a new row and marks the old one as dead. Every DELETE marks a row as dead. Dead rows remain physically in the table until VACUUM reclaims them. A table with 10M dead tuples is 10× larger than necessary — sequential scans read all of it.
- **Query plan degradation**: Dead tuples distort row count statistics. `pg_stats` counts only live rows, but the table's physical size (including dead rows) affects the planner's cost estimates. `ANALYZE` must run regularly.
- **XID wraparound — the most critical risk**: PostgreSQL uses 32-bit transaction IDs. When a table's `age(relfrozenxid)` approaches 2 billion, PostgreSQL cannot safely determine which rows are visible to which transactions. PostgreSQL will **stop accepting new transactions** and require `VACUUM FREEZE` to run on all tables. If ignored, PostgreSQL **shuts down the cluster** to prevent data corruption. This has happened to production systems.
- **Difference from MySQL**: MySQL InnoDB also has MVCC but uses an undo log that is purged automatically. PostgreSQL's MVCC is in-place (dead tuples in the heap) — vacuum is essential and has no equivalent in MySQL.

## Aurora/RDS Notes

- **Aurora PostgreSQL**: Aurora handles storage differently — vacuum does not cause I/O contention with live queries (no shared disk I/O). However, dead tuple accumulation is identical. XID wraparound risk is the same. `VACUUM FREEZE` must still run on Aurora.
- **Aurora storage**: Aurora does not free storage back to the OS after vacuum — Aurora storage only grows. Vacuum eliminates dead tuples from query scan paths but does not reduce Aurora's billed storage size.
- **RDS PostgreSQL**: Autovacuum is enabled and cannot be disabled on RDS. Tune `autovacuum_vacuum_scale_factor` and `autovacuum_vacuum_threshold` via parameter groups. Monitor XID age via `pg_stat_user_tables` or CloudWatch metrics (`MaximumUsedTransactionIDs`).

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | `pg_stat_progress_vacuum` available for monitoring in-progress vacuums |
| PostgreSQL 15 | Vacuum parallelism improvements |
| PostgreSQL 16 | `vacuum_buffer_usage_limit` for controlling buffer pool impact during vacuum |
| PostgreSQL 17 | Significantly improved vacuum performance — more aggressive dead tuple cleanup; `VACUUM` can now skip index scans under certain conditions |
| Aurora PostgreSQL | No vacuum I/O contention with live queries; XID wraparound risk is the same as community |
