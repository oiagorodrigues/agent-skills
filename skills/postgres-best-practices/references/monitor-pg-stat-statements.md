---
title: "Use pg_stat_statements to identify the top slow and frequent queries"
impact: critical
tags: [monitoring, pg-stat-statements, performance, slow-queries, observability]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Use pg_stat_statements to identify the top slow and frequent queries

## Problem

Without query-level performance data, it is impossible to identify which queries are consuming the most database resources. `pg_stat_statements` is the standard PostgreSQL extension for query performance monitoring — it tracks execution time, call counts, rows returned, and buffer usage per normalized query. It is the first tool to reach for when investigating PostgreSQL performance problems.

## Bad Example

```sql
-- BAD: Trying to find slow queries without pg_stat_statements
-- Only option without the extension: look at pg_stat_activity (point-in-time snapshot)
SELECT pid, query, query_start, state
FROM   pg_stat_activity
WHERE  state = 'active';
-- This only shows currently running queries — not historical data or aggregated stats
-- You cannot find which queries have run the most or taken the most total time
```

## Good Example

```sql
-- Step 0: Enable pg_stat_statements (one-time setup)
-- Add to shared_preload_libraries in postgresql.conf (or RDS parameter group):
-- shared_preload_libraries = 'pg_stat_statements'
-- Requires restart. Then:
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Verify it's active:
SELECT * FROM pg_stat_statements LIMIT 1;
```

```sql
-- Top 10 queries by TOTAL execution time (biggest impact on database throughput)
SELECT
  LEFT(query, 150)                                    AS query_snippet,
  calls,
  ROUND(total_exec_time::numeric, 2)                  AS total_ms,
  ROUND(mean_exec_time::numeric, 2)                   AS mean_ms,
  ROUND(stddev_exec_time::numeric, 2)                 AS stddev_ms,
  rows,
  ROUND(total_exec_time::numeric / calls, 2)          AS avg_ms_per_call,
  ROUND(100 * total_exec_time /
    SUM(total_exec_time) OVER (), 2)                  AS pct_total_time
FROM   pg_stat_statements
WHERE  calls > 10
ORDER  BY total_exec_time DESC
LIMIT  10;
```

```sql
-- Top 10 queries by MEAN execution time (individual slow queries)
SELECT
  LEFT(query, 150)                        AS query_snippet,
  calls,
  ROUND(mean_exec_time::numeric, 2)       AS mean_ms,
  ROUND(max_exec_time::numeric, 2)        AS max_ms,
  ROUND(total_exec_time::numeric, 2)      AS total_ms,
  rows
FROM   pg_stat_statements
ORDER  BY mean_exec_time DESC
LIMIT  10;
```

```sql
-- Top 10 queries by CALL COUNT (highest frequency — cache miss candidates)
SELECT
  LEFT(query, 150)                        AS query_snippet,
  calls,
  ROUND(mean_exec_time::numeric, 2)       AS mean_ms,
  ROUND(total_exec_time::numeric, 2)      AS total_ms,
  rows,
  shared_blks_hit,
  shared_blks_read,
  ROUND(
    100.0 * shared_blks_hit /
    NULLIF(shared_blks_hit + shared_blks_read, 0), 2
  )                                       AS buffer_cache_hit_pct
FROM   pg_stat_statements
ORDER  BY calls DESC
LIMIT  10;
```

```sql
-- Queries with low buffer cache hit rate (I/O-bound — missing indexes or cold cache)
SELECT
  LEFT(query, 150)               AS query_snippet,
  calls,
  shared_blks_hit,
  shared_blks_read,
  ROUND(
    100.0 * shared_blks_hit /
    NULLIF(shared_blks_hit + shared_blks_read, 0), 2
  )                              AS buffer_cache_hit_pct,
  ROUND(mean_exec_time::numeric, 2) AS mean_ms
FROM   pg_stat_statements
WHERE  shared_blks_read > 1000    -- queries with significant I/O
  AND  calls > 5
ORDER  BY shared_blks_read DESC
LIMIT  10;
```

```sql
-- Reset statistics (e.g., after a deployment or index creation):
SELECT pg_stat_statements_reset();

-- Reset stats for a specific query (PostgreSQL 14+):
-- SELECT pg_stat_statements_reset(userid, dbid, queryid)
-- from pg_stat_statements where query like '%orders%' limit 1;
```

```sql
-- Key pg_stat_statements columns:
-- query           : normalized query text ($1, $2 for parameters)
-- calls           : number of times the query was executed
-- total_exec_time : total execution time across all calls (ms)
-- mean_exec_time  : mean time per call (ms)
-- max_exec_time   : slowest single call (ms)
-- stddev_exec_time: standard deviation — high stddev = inconsistent performance
-- rows            : total rows returned
-- shared_blks_hit : buffer pool hits (fast, from RAM)
-- shared_blks_read: buffer pool misses (slow, from disk/storage)
-- wal_bytes       : WAL generated (PostgreSQL 13+) — high for write-heavy queries
```

## Why It Matters

- **Aggregated history**: Unlike `pg_stat_activity` (point-in-time), `pg_stat_statements` accumulates data over time. A query that runs in 5 ms but executes 1M times/day has more total impact than a 500 ms query that runs once.
- **Normalized queries**: Parameters are replaced with `$1`, `$2`, so all executions of the same query structure are aggregated together regardless of specific parameter values.
- **Buffer cache insight**: `shared_blks_read` reveals queries that generate disk I/O. High `shared_blks_read` indicates missing indexes or data that doesn't fit in the buffer pool.
- **`shared_preload_libraries` requirement**: `pg_stat_statements` must be loaded at startup — it cannot be enabled without a restart. Plan accordingly on RDS/Aurora.

## Aurora/RDS Notes

- **Aurora PostgreSQL**: `pg_stat_statements` is available and recommended. Aurora Performance Insights integrates with `pg_stat_statements` to provide visual query analysis without running SQL manually.
- **RDS PostgreSQL**: Enable via parameter group: set `shared_preload_libraries` to include `pg_stat_statements`. Requires a **reboot** of the RDS instance. After enabling, run `CREATE EXTENSION pg_stat_statements` in each database.
- **Performance Insights**: On both Aurora and RDS, enable Performance Insights (free tier: 7 days retention). It shows `DBLoad` by SQL, waits, and host — a more visual interface over the same underlying data.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | `pg_stat_statements_reset(userid, dbid, queryid)` for per-query reset |
| PostgreSQL 15 | `wal_bytes` column added for WAL accounting |
| PostgreSQL 16 | `parallel_workers_to_launch`, `parallel_workers_launched` columns added |
| PostgreSQL 17 | `pg_stat_statements` tracks serialization overhead (SERIALIZE); `shared_blk_read_time` improvements |
| Aurora PostgreSQL | Available via parameter group; integrates with Performance Insights |
