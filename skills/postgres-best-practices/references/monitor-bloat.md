---
title: "Monitor and remediate table and index bloat"
impact: high
tags: [bloat, vacuum, pg-repack, index-bloat, table-bloat, monitoring]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Monitor and remediate table and index bloat

## Problem

PostgreSQL's MVCC model means UPDATE and DELETE operations create dead tuples that remain in the table until VACUUM reclaims them. If autovacuum is not keeping up, tables and their indexes grow much larger than the live data — this is "bloat." A bloated table is slower to scan (more pages to read), and a bloated index has empty or half-empty pages that waste I/O. Bloat accumulates silently and can grow to 10× the live data size.

## Bad Example

```sql
-- BAD: High-churn table with no autovacuum tuning
-- After 3 months of heavy ORDER status updates:

SELECT
  relname,
  pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
  n_live_tup,
  n_dead_tup
FROM pg_stat_user_tables WHERE relname = 'orders';
-- Result:
-- total_size: 12 GB
-- n_live_tup: 800,000   (live data fits in ~80 MB)
-- n_dead_tup: 8,200,000 (dead tuples occupying ~12 GB)
-- → Table is ~150× bloated
-- Every sequential scan reads 12 GB instead of 80 MB
```

## Good Example

```sql
-- GOOD 1: Measure bloat using pg_relation_size vs estimated data size
-- Quick bloat estimate (no extension needed):
SELECT
  relname,
  pg_size_pretty(pg_relation_size(relid))       AS heap_size,
  pg_size_pretty(pg_indexes_size(relid))        AS index_size,
  pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
  n_live_tup,
  n_dead_tup,
  CASE WHEN n_live_tup + n_dead_tup > 0
       THEN ROUND(100.0 * n_dead_tup / (n_live_tup + n_dead_tup), 1)
       ELSE 0
  END AS dead_pct
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 20;

-- GOOD 2: Precise bloat measurement with pgstattuple extension
CREATE EXTENSION IF NOT EXISTS pgstattuple;

-- Table bloat:
SELECT * FROM pgstattuple('orders');
-- Returns: table_len, tuple_count, tuple_len, dead_tuple_count, dead_tuple_len, free_space

-- Index bloat:
SELECT * FROM pgstatindex('idx_orders_status');
-- Returns: index_size, leaf_fragmentation, avg_leaf_density, etc.
```

```sql
-- GOOD 3: Remediation options (least to most disruptive)

-- Option A: VACUUM ANALYZE (non-blocking, marks dead tuples as reclaimable)
-- Does NOT reduce table size — only marks space for reuse
-- Needed before new rows can reuse the freed pages
VACUUM (ANALYZE, VERBOSE) orders;

-- Option B: REINDEX CONCURRENTLY (PostgreSQL 12+) — rebuild bloated indexes online
-- Takes ShareUpdateExclusiveLock — allows concurrent reads and writes
REINDEX INDEX CONCURRENTLY idx_orders_status;
REINDEX TABLE CONCURRENTLY orders;  -- rebuilds all indexes on the table

-- Check for invalid indexes after concurrent reindex (rare failure case):
SELECT indexname, indexdef
FROM   pg_indexes
WHERE  tablename = 'orders'
  AND  indexname NOT IN (
    SELECT indexname FROM pg_indexes
    JOIN pg_index ON indexrelid = (schemaname || '.' || indexname)::regclass
    WHERE indisvalid = true
  );

-- Option C: VACUUM FULL (blocking — acquires ACCESS EXCLUSIVE lock)
-- Rewrites the entire table — compacts storage to minimum size
-- WARNING: Blocks all reads and writes for the duration
-- Use only during a maintenance window for severe bloat
VACUUM FULL VERBOSE orders;

-- Option D: pg_repack (online table reorganization — requires extension)
-- Rebuilds the table and all indexes online with minimal locking
-- CREATE EXTENSION pg_repack;
-- Then from the command line:
-- pg_repack -h localhost -U app_user -d ecommerce -t orders --no-superuser-check
```

```sql
-- GOOD 4: Monitor index fragmentation
SELECT
  indexname,
  pg_size_pretty(pg_relation_size(indexrelid::regclass)) AS index_size,
  idx_scan,
  idx_tup_read,
  idx_tup_fetch
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY pg_relation_size(indexrelid::regclass) DESC
LIMIT 20;

-- Identify unused indexes (candidates for dropping to reduce write overhead and bloat):
SELECT
  schemaname,
  tablename,
  indexname,
  pg_size_pretty(pg_relation_size(indexrelid::regclass)) AS index_size,
  idx_scan
FROM   pg_stat_user_indexes
WHERE  idx_scan = 0
  AND  schemaname = 'public'
ORDER  BY pg_relation_size(indexrelid::regclass) DESC;
```

## Bloat Remediation Decision Tree

```
Is the table bloated (dead_pct > 20%)?
  YES → Is autovacuum keeping up? (check last_autovacuum < 1 hour)
          NO → Tune autovacuum per table (ALTER TABLE ... SET autovacuum_vacuum_scale_factor = 0.01)
               Run VACUUM ANALYZE immediately
          YES → Run VACUUM ANALYZE manually (temporary fix)
               Consider pg_repack for online repack without downtime

Is the INDEX bloated (leaf_fragmentation > 30% via pgstatindex)?
  YES → Use REINDEX CONCURRENTLY (PG 12+) for online rebuild
        Or pg_repack for table + index rebuild in one operation

Is the bloat so severe that VACUUM ANALYZE won't help (very old dead tuples, page corruption)?
  YES → Schedule a maintenance window, run VACUUM FULL
        Or use pg_repack for online alternative (if available)
```

## Why It Matters

- **Sequential scan cost**: A bloated 12 GB table with 80 MB of live data forces sequential scans to read 150× more pages than necessary. This is a 150× slowdown for full-table scans.
- **Index bloat**: B-tree index pages that are partially empty reduce index density. The index is larger than needed, takes more buffer pool space, and requires more page reads per lookup.
- **VACUUM vs VACUUM FULL**: Regular `VACUUM` marks dead tuple space for reuse but does not compact the file. The OS-level file size stays the same. `VACUUM FULL` rewrites the table file — file size shrinks but it requires an exclusive lock.
- **`pg_repack` advantage**: Rebuilds the table online with the same result as `VACUUM FULL` but without the long exclusive lock. Requires a brief lock at the end of the rebuild (seconds, not minutes).

## Aurora/RDS Notes

- **Aurora PostgreSQL**: Aurora's storage is append-only — `VACUUM FULL` does not reduce billed Aurora storage (Aurora never frees storage back to the OS). However, `VACUUM FULL` still improves query performance by compacting the logical table structure.
- **`pg_repack` on Aurora**: `pg_repack` is NOT supported on Aurora PostgreSQL (Aurora's storage layer is different from community PostgreSQL's file system). Use `REINDEX CONCURRENTLY` for index bloat and `VACUUM FULL` (with maintenance window) for table bloat on Aurora.
- **RDS PostgreSQL**: `pg_repack` is available on RDS PostgreSQL 13+. `VACUUM FULL` on RDS requires a maintenance window.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | `REINDEX CONCURRENTLY` available (since PG 12) |
| PostgreSQL 15 | Same |
| PostgreSQL 16 | Same |
| PostgreSQL 17 | Improved vacuum makes bloat less likely with default settings; VACUUM can skip index scans when page is clean |
| Aurora PostgreSQL | No storage reduction from VACUUM/VACUUM FULL; `pg_repack` not supported |
