---
title: "Use INCLUDE columns for index-only scans"
impact: high
tags: [indexes, covering-index, index-only-scan, include, performance]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Use INCLUDE columns for index-only scans

## Problem

An index scan in PostgreSQL has two steps: (1) look up the matching entries in the index B-tree, and (2) fetch the actual row from the heap (the table itself) to retrieve columns not stored in the index. Step 2 is a "heap fetch" — a random I/O for each matching row. If the query only needs columns that are already in the index, the heap fetch can be skipped entirely in an **Index Only Scan**. Without an `INCLUDE` clause, every projected column that is not in the index key forces a heap fetch.

## Bad Example

```sql
-- Index only covers the lookup column
CREATE INDEX idx_orders_user_id ON orders (user_id);

-- Query needs status and total_amount — neither is in the index
SELECT id, user_id, status, total_amount
FROM   orders
WHERE  user_id = $1
ORDER  BY id DESC
LIMIT  20;
```

PostgreSQL does an Index Scan using `idx_orders_user_id`, then fetches each row from the heap to get `status` and `total_amount`. For 20 rows this is 20 random heap reads. For a hot query called millions of times per day, the heap reads dominate I/O.

## Good Example

```sql
-- INCLUDE adds columns to the index leaf pages without changing the sort order
-- PostgreSQL 11+ required for INCLUDE clause
CREATE INDEX idx_orders_user_covering
  ON orders (user_id, id)
  INCLUDE (status, total_amount);

-- Now PostgreSQL can satisfy the query with an Index Only Scan — no heap fetch
SELECT id, user_id, status, total_amount
FROM   orders
WHERE  user_id = $1
ORDER  BY id DESC
LIMIT  20;
```

The `INCLUDE` columns (`status`, `total_amount`) are stored in the index leaf pages but are not part of the sort key. PostgreSQL returns them directly from the index without touching the heap.

```sql
-- Confirm the query uses Index Only Scan:
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, user_id, status, total_amount
FROM   orders
WHERE  user_id = $1
ORDER  BY id DESC
LIMIT  20;
-- Expected: Index Only Scan using idx_orders_user_covering
--           Heap Fetches: 0
```

**Important caveat — visibility map**: PostgreSQL can only skip the heap fetch if the page containing the row is marked as all-visible in the **visibility map**. The visibility map is maintained by VACUUM. If autovacuum has not run recently on a busy table, heap fetches will occur even with a covering index. Monitor `pg_stat_user_tables.n_dead_tup` and ensure autovacuum is running.

## Why It Matters

- **Heap fetch elimination**: For a query returning 1,000 rows, an Index Scan does 1,000 random heap page reads. An Index Only Scan does 0 — all data comes from the index.
- **Buffer cache efficiency**: Index pages are much smaller than heap pages. Covering indexes keep hot data in the buffer cache more efficiently.
- **Aurora-specific**: On Aurora PostgreSQL, heap fetches for non-visible pages are network calls to the Aurora storage layer. Index-only scans dramatically reduce Aurora storage reads.
- **INCLUDE vs key columns**: Columns in `INCLUDE` are not part of the B-tree sort key — they cannot be used for filtering or ordering. Use `INCLUDE` only for columns that appear in the SELECT list but not in WHERE or ORDER BY.
- **Visibility map dependency**: `VACUUM` must have run to mark pages as all-visible. Monitor with `SELECT relname, n_dead_tup, last_autovacuum FROM pg_stat_user_tables`.

## EXPLAIN Notes

```sql
-- Bad: Index Scan with heap fetches
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, user_id, status, total_amount
FROM orders WHERE user_id = 42 ORDER BY id DESC LIMIT 20;
```

```
Index Scan using idx_orders_user_id on orders
  (actual rows=20, loops=1)
  Index Cond: (user_id = 42)
  Buffers: shared hit=23  ← index reads + heap fetches
  Heap Fetches: 20
```

```sql
-- Good: Index Only Scan (after VACUUM to update visibility map)
VACUUM orders;
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, user_id, status, total_amount
FROM orders WHERE user_id = 42 ORDER BY id DESC LIMIT 20;
```

```
Index Only Scan using idx_orders_user_covering on orders
  (actual rows=20, loops=1)
  Index Cond: (user_id = 42)
  Buffers: shared hit=3   ← only index reads, no heap I/O
  Heap Fetches: 0
```

| Query | Node | Heap Fetches | Buffers |
|-------|------|-------------|---------|
| Bad   | Index Scan | 20 | shared hit=23 |
| Good  | Index Only Scan | 0 | shared hit=3 |

## Aurora/RDS Notes

- **Aurora PostgreSQL**: Aurora storage is network-attached. Every heap fetch that misses the buffer pool is a distributed storage read. Index-only scans provide larger gains on Aurora than on local-disk PostgreSQL.
- **RDS PostgreSQL**: Autovacuum is enabled by default on RDS but may not keep up on rapidly updated tables. If `Heap Fetches` remains high despite a covering index, check `n_dead_tup` in `pg_stat_user_tables` and consider a manual `VACUUM` or adjusting `autovacuum_vacuum_scale_factor` for that table.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | `INCLUDE` clause available; `Heap Fetches` shown in EXPLAIN ANALYZE |
| PostgreSQL 15 | Same |
| PostgreSQL 16 | Same |
| PostgreSQL 17 | Same; improved vacuum makes visibility map more current, improving Index Only Scan hit rates |
| Aurora PostgreSQL | `INCLUDE` supported; set `autovacuum_vacuum_scale_factor` aggressively on write-heavy tables |
