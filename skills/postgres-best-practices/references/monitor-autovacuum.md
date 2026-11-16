---
title: "Monitor and tune autovacuum to prevent bloat and XID wraparound"
impact: critical
tags: [autovacuum, vacuum, bloat, dead-tuples, xid-wraparound, monitoring]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Monitor and tune autovacuum to prevent bloat and XID wraparound

## Problem

Autovacuum is PostgreSQL's background daemon that reclaims dead tuples, updates statistics, and prevents transaction ID wraparound. Without proper monitoring and tuning, autovacuum falls behind on high-churn tables, leading to: table bloat (tables 10× larger than needed), stale statistics (bad query plans), and the catastrophic XID wraparound risk. Most PostgreSQL performance emergencies are autovacuum failures.

## Bad Example

```sql
-- BAD: Ignoring autovacuum health — no monitoring in place
-- Using default scale factors for all tables regardless of churn rate

-- Default autovacuum settings (often too conservative for busy tables):
-- autovacuum_vacuum_scale_factor = 0.2  → vacuum after 20% of rows change
-- For a 5M-row table: vacuum after 1M dead tuples accumulate (too late!)
-- For a 100M-row table: vacuum after 20M dead tuples accumulate (catastrophic!)

-- A typical unmonitored table after heavy traffic:
SELECT relname, n_live_tup, n_dead_tup, last_autovacuum
FROM pg_stat_user_tables WHERE relname = 'orders';
-- n_live_tup:  100,000
-- n_dead_tup:  4,200,000  ← 42× more dead than live
-- last_autovacuum: 3 days ago  ← autovacuum is falling behind
```

## Good Example

```sql
-- GOOD 1: Regular autovacuum health check query
SELECT
  schemaname,
  relname,
  n_live_tup,
  n_dead_tup,
  CASE WHEN n_live_tup > 0
       THEN ROUND(100.0 * n_dead_tup / n_live_tup, 1)
       ELSE 0
  END                              AS dead_pct,
  last_autovacuum,
  last_autoanalyze,
  autovacuum_count,
  autoanalyze_count,
  age(relfrozenxid)                AS xid_age
FROM   pg_stat_user_tables
ORDER  BY dead_pct DESC, age(relfrozenxid) DESC
LIMIT  20;

-- Alert thresholds:
-- dead_pct > 10% → autovacuum not keeping up — tune scale_factor
-- xid_age > 1,500,000,000 → emergency — run VACUUM FREEZE immediately
-- last_autovacuum older than 1 hour on a busy table → investigate
```

```sql
-- GOOD 2: Per-table autovacuum tuning for high-churn tables
-- Reduce scale factors to trigger vacuum earlier

-- For orders table (high UPDATE rate — status transitions):
ALTER TABLE orders SET (
  autovacuum_vacuum_scale_factor    = 0.01,   -- vacuum after 1% dead tuples
  autovacuum_vacuum_threshold       = 1000,   -- or after 1k dead tuples absolute
  autovacuum_analyze_scale_factor   = 0.005,  -- analyze after 0.5% change
  autovacuum_analyze_threshold      = 500,
  autovacuum_vacuum_cost_delay      = 2       -- ms; lower = more aggressive vacuum
);

-- For order_items table (high INSERT rate, occasional DELETE):
ALTER TABLE order_items SET (
  autovacuum_vacuum_scale_factor  = 0.02,
  autovacuum_vacuum_threshold     = 5000,
  autovacuum_analyze_scale_factor = 0.01
);

-- Check effective settings (including per-table overrides):
SELECT relname, reloptions
FROM   pg_class
WHERE  relname IN ('orders', 'order_items')
  AND  relkind = 'r';
```

```sql
-- GOOD 3: Monitor in-progress vacuum operations
SELECT
  p.phase,
  p.heap_blks_total,
  p.heap_blks_scanned,
  ROUND(100.0 * p.heap_blks_scanned / NULLIF(p.heap_blks_total, 0), 1) AS scan_pct,
  p.heap_blks_vacuumed,
  p.num_dead_tuples,
  p.num_index_scans,
  a.query,
  a.pid
FROM   pg_stat_progress_vacuum p
JOIN   pg_stat_activity a ON a.pid = p.pid;

-- GOOD 4: Manual vacuum for urgent cases
-- After heavy bulk updates that generated many dead tuples:
VACUUM (ANALYZE, VERBOSE) orders;

-- Emergency VACUUM FREEZE when XID age > 1.5 billion:
VACUUM FREEZE VERBOSE orders;
-- This marks all existing rows as frozen (safe from XID wraparound)
-- Takes significant time on large tables — schedule in a maintenance window
```

```sql
-- GOOD 5: Monitor cluster-wide XID wraparound risk
SELECT
  c.oid::regclass AS table_name,
  age(c.relfrozenxid)  AS xid_age,
  c.reltuples::bigint  AS estimated_rows,
  pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size
FROM   pg_class c
JOIN   pg_namespace n ON n.oid = c.relnamespace
WHERE  c.relkind IN ('r', 't')
  AND  n.nspname NOT IN ('pg_catalog', 'information_schema')
ORDER  BY age(c.relfrozenxid) DESC
LIMIT  20;

-- Critical threshold: age > 1,500,000,000 (1.5 billion)
-- Danger zone:        age > 1,800,000,000 (1.8 billion)
-- PostgreSQL shuts down at approximately 2,100,000,000 (2.1 billion)
```

## Why It Matters

- **Default scale factor is wrong for large tables**: `autovacuum_vacuum_scale_factor = 0.20` means vacuum after 20% of rows are dead. On a 100M-row table, that's 20M dead tuples — weeks of accumulation. Set it to 0.01–0.05 for large, frequently updated tables.
- **XID wraparound is a cluster-wide emergency**: PostgreSQL uses 32-bit transaction IDs. When any table's `age(relfrozenxid)` reaches approximately 2 billion, PostgreSQL shuts down ALL connections to prevent data corruption. Recovery requires `VACUUM FREEZE` on every table — potentially days of downtime.
- **Autovacuum vs manual VACUUM**: Autovacuum runs in the background with limited resources to avoid impacting production queries. Manual `VACUUM ANALYZE` runs at full speed — use it after large batch operations.
- **Aurora storage and vacuum**: Aurora PostgreSQL does not suffer from vacuum I/O contention (vacuum writes go directly to the storage layer without competing with read I/O). However, dead tuples still accumulate and hurt query plans — vacuum is still essential.

## Aurora/RDS Notes

- **Aurora PostgreSQL**: Autovacuum is enabled and cannot be disabled. Tune via parameter group or per-table `ALTER TABLE ... SET (autovacuum_*)`. Aurora CloudWatch emits `MaximumUsedTransactionIDs` — set an alarm at 1.5 billion.
- **RDS PostgreSQL**: Autovacuum is enabled. `autovacuum_vacuum_scale_factor` and related parameters are configurable in the parameter group. Monitor `MaximumUsedTransactionIDs` CloudWatch metric.
- **Aurora storage behavior**: Aurora does not reduce billed storage after VACUUM — Aurora storage is append-only. VACUUM reclaims dead tuple space for reuse within PostgreSQL but does not reduce the Aurora storage allocation.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | `pg_stat_progress_vacuum` available; per-table autovacuum settings available |
| PostgreSQL 15 | Autovacuum improvements for parallel index vacuuming |
| PostgreSQL 16 | `vacuum_buffer_usage_limit` to control vacuum's buffer pool impact |
| PostgreSQL 17 | Significantly improved vacuum performance; more aggressive dead tuple cleanup; vacuum can skip redundant index scans |
| Aurora PostgreSQL | No I/O contention for vacuum; XID wraparound monitoring via CloudWatch |
