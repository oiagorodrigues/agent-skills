---
title: "Read EXPLAIN (ANALYZE, BUFFERS) to diagnose query execution plans"
impact: critical
tags: [explain, analyze, query-plans, performance, diagnostics]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Read EXPLAIN (ANALYZE, BUFFERS) to diagnose query execution plans

## Problem

`EXPLAIN` alone shows the estimated plan without running the query. `EXPLAIN (ANALYZE, BUFFERS)` runs the query and shows actual row counts, actual timing, and buffer I/O. The most important diagnostic signal is the difference between estimated rows and actual rows — a large discrepancy means stale statistics, which leads to bad plans. Without EXPLAIN, optimization is guesswork.

## How to Use EXPLAIN ANALYZE

```sql
-- Full form — the most diagnostic:
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT id, user_id, total_amount, created_at
FROM   orders
WHERE  status = 'paid'
  AND  user_id = $1
ORDER  BY created_at DESC
LIMIT  20;

-- For write queries: wrap in BEGIN/ROLLBACK to avoid side effects
BEGIN;
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
UPDATE orders SET status = 'shipped' WHERE id = $1;
ROLLBACK;

-- JSON format for programmatic analysis:
EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
SELECT * FROM orders WHERE user_id = $1;

-- Verbose format shows column projections:
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT id, status FROM orders WHERE user_id = $1;
```

## Key Node Types

```
Node Type               Meaning
─────────────────────────────────────────────────────────────
Seq Scan                Full sequential table scan — usually bad on large tables
Index Scan              B-tree index lookup + heap fetch for each row
Index Only Scan         Index lookup without heap fetch — fastest read
Bitmap Index Scan       Builds a bitmap of matching pages; combined with Bitmap Heap Scan
Bitmap Heap Scan        Fetches rows from pages identified by Bitmap Index Scan
Nested Loop             For each outer row, probe inner relation — good if inner is small
Hash Join               Build hash table from smaller relation, probe with larger — good for large inputs
Merge Join              Both inputs must be sorted — efficient when pre-sorted
Hash Aggregate          GROUP BY using a hash table
Sort                    Explicit sort step — an index can eliminate this
Limit                   Top-N result
Append                  Union of multiple scans (e.g., partition scans)
```

## Reading EXPLAIN Output

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, user_id, total_amount
FROM orders
WHERE status = 'paid' AND user_id = 42
ORDER BY created_at DESC
LIMIT 10;
```

```
Limit  (cost=0.56..45.23 rows=10 width=28)
       (actual time=0.18..0.45 rows=10 loops=1)
  ->  Index Scan using idx_orders_user_status_id on orders
        (cost=0.56..4523.00 rows=1000 width=28)
        (actual time=0.17..0.42 rows=10 loops=1)
      Index Cond: ((user_id = 42) AND (status = 'paid'::order_status))
      Filter: (created_at IS NOT NULL)
      Rows Removed by Filter: 0
      Buffers: shared hit=13
Planning Time: 0.3 ms
Execution Time: 0.5 ms
```

**Key fields to read:**

| Field | What It Tells You |
|-------|------------------|
| `cost=0.56..45.23` | Estimated startup cost .. total cost (planner's estimate) |
| `rows=10` | Estimated rows |
| `actual time=0.18..0.45` | Actual start..finish time in ms |
| `actual rows=10` | Rows actually returned |
| `loops=1` | How many times this node was executed (>1 = inner of Nested Loop) |
| `Buffers: shared hit=13` | Pages served from buffer cache (fast) |
| `Buffers: shared read=500` | Pages read from disk/storage (slow) |
| `Rows Removed by Filter: N` | Rows read but discarded after fetch — indicates wasted work |

## Bad Plan Signals

```sql
-- BAD: Large discrepancy between estimated and actual rows
-- estimated: rows=5    actual rows=50000
-- → Statistics are stale. Run ANALYZE.

-- BAD: High "Rows Removed by Filter" on a heap scan
-- Index Cond matches many pages; Filter removes most — add a better index

-- BAD: Sort node when an index could provide pre-sorted data
-- Sort  (actual rows=50000)
-- → Add an index with the same column order as ORDER BY

-- BAD: Nested Loop with a large outer input
-- Nested Loop  (actual rows=1000000)
-- → For large inputs, Hash Join is typically faster

-- BAD: "actual rows=0, loops=1000" — Nested Loop with many outer rows, 0 inner rows
-- → No matching rows in inner; possible missing index on join key

-- BAD: "shared read >> shared hit" — low buffer cache hit rate
-- → Data doesn't fit in shared_buffers; increase shared_buffers or add covering index
```

```sql
-- auto_explain: automatically log EXPLAIN plans for slow queries
-- Enable via parameter group or ALTER SYSTEM:
ALTER SYSTEM SET shared_preload_libraries = 'auto_explain';
-- Reload config (or restart for shared_preload_libraries)
SELECT pg_reload_conf();

-- Set threshold: log plans for queries > 1 second
ALTER SYSTEM SET auto_explain.log_min_duration = 1000;   -- 1000 ms
ALTER SYSTEM SET auto_explain.log_analyze      = true;   -- include ANALYZE output
ALTER SYSTEM SET auto_explain.log_buffers      = true;   -- include buffer stats
SELECT pg_reload_conf();
-- Plans appear in the PostgreSQL log / CloudWatch Logs on RDS
```

```sql
-- PostgreSQL 17: EXPLAIN (SERIALIZE) measures serialization overhead
EXPLAIN (ANALYZE, BUFFERS, SERIALIZE TEXT)
SELECT * FROM orders WHERE user_id = $1;
-- Shows time spent serializing results to the client
```

## Why It Matters

- **Estimated vs actual rows**: The biggest diagnostic signal. If the planner estimates 5 rows but 50,000 are returned, it may choose a Nested Loop instead of a Hash Join — causing catastrophic performance. Fix: run `ANALYZE table` to refresh statistics.
- **Buffer stats reveal I/O**: `shared hit` = served from buffer pool (fast). `shared read` = served from disk or Aurora storage (slow). A query with `shared read >> shared hit` is I/O-bound — either the buffer pool is too small or an index is missing.
- **EXPLAIN ANALYZE runs the query**: Do not run `EXPLAIN ANALYZE` on UPDATE/DELETE in production without wrapping in a BEGIN/ROLLBACK. The query actually executes and modifies data.
- **`auto_explain`**: For production environments where you can't manually run EXPLAIN, `auto_explain` automatically captures plans for slow queries and logs them. Essential for diagnosing intermittent slow queries.

## Aurora/RDS Notes

- **Aurora PostgreSQL**: `EXPLAIN (ANALYZE, BUFFERS)` runs normally on Aurora. The `shared read` count reflects Aurora distributed storage reads — each `shared read` is a network call to Aurora storage.
- **RDS PostgreSQL**: `auto_explain` is available via parameter group. Set `shared_preload_libraries = 'auto_explain'` and configure `auto_explain.log_min_duration`. Logs go to CloudWatch if log exports are enabled.
- **Performance Insights**: Aurora/RDS Performance Insights shows the top SQL statements and their wait events — a visual complement to `EXPLAIN ANALYZE`.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON/TEXT)` available |
| PostgreSQL 15 | Same |
| PostgreSQL 16 | `EXPLAIN` shows generic vs custom plan for prepared statements |
| PostgreSQL 17 | `EXPLAIN (SERIALIZE)` option to measure result serialization time |
| Aurora PostgreSQL | Same output format; `shared read` reflects Aurora storage I/O |
