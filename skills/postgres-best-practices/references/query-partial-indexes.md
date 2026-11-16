---
title: "Use partial indexes to index only the rows you query"
impact: high
tags: [indexes, partial-index, performance, selectivity]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Use partial indexes to index only the rows you query

## Problem

A full index on a column includes every row in the table. When queries only ever access a small, well-defined subset of rows (e.g., pending orders, unprocessed jobs, active users), a full index wastes space and write overhead on rows that will never be searched. PostgreSQL's partial index — a `CREATE INDEX ... WHERE` clause — indexes only the rows matching the predicate, creating a much smaller and faster index.

## Bad Example

```sql
-- Full index on status — indexes all 5M rows including 4.75M 'completed' orders
-- that are almost never queried in operational workflows
CREATE INDEX idx_orders_status_full ON orders (status);

-- This query is the hot path — processing pending orders
SELECT id, user_id, total_amount
FROM   orders
WHERE  status = 'pending'
ORDER  BY created_at
LIMIT  100;
```

The full index includes all 5M rows. It works, but it is larger than necessary, slower to update (every INSERT/UPDATE must update the index for all rows), and wastes buffer pool space caching rows that are rarely needed.

## Good Example

```sql
-- Partial index: only indexes the small subset that matters for operational queries
-- If 95% of orders are 'completed', this index covers only 5% of the table
CREATE INDEX idx_orders_pending ON orders (created_at)
WHERE status = 'pending';

-- The query is now served by a tiny, fast partial index
SELECT id, user_id, total_amount
FROM   orders
WHERE  status = 'pending'
ORDER  BY created_at
LIMIT  100;
-- PostgreSQL recognizes that status = 'pending' matches the partial index predicate
-- and uses idx_orders_pending.

-- Partial index for soft-deleted rows (only undeleted users are ever queried)
CREATE INDEX idx_users_active_email ON users (email)
WHERE status != 'deleted';

-- Partial index for unprocessed job queue items
CREATE INDEX idx_orders_unpaid ON orders (created_at)
WHERE status IN ('pending', 'processing');
```

## Why It Matters

- **Index size**: If 95% of orders are `'completed'`, the partial index on `'pending'` is 20× smaller than the full index. It fits in the buffer pool and is read 20× faster.
- **Write overhead**: Every INSERT and UPDATE that affects an indexed column must update the index. A partial index is only updated when the row matches its WHERE predicate — completed orders never touch the partial index.
- **Selectivity**: Partial indexes work best for high-cardinality predicates where the indexed subset is small relative to the full table (active work queues, soft-delete patterns, time-windowed operational data).
- **Query planner matching**: PostgreSQL matches the partial index predicate against the query's WHERE clause automatically. The WHERE clause in the query must logically imply the partial index predicate for PostgreSQL to use it.

## EXPLAIN Notes

```sql
-- Without partial index: full index scan
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, user_id, total_amount FROM orders
WHERE status = 'pending' ORDER BY created_at LIMIT 100;
```

```
Index Scan using idx_orders_status_full on orders
  Index Cond: (status = 'pending'::order_status)
  Rows Removed by Index Recheck: 0
  Buffers: shared hit=4820   ← large index, many pages
```

```sql
-- With partial index: much smaller scan
CREATE INDEX idx_orders_pending ON orders (created_at) WHERE status = 'pending';

EXPLAIN (ANALYZE, BUFFERS)
SELECT id, user_id, total_amount FROM orders
WHERE status = 'pending' ORDER BY created_at LIMIT 100;
```

```
Index Scan using idx_orders_pending on orders
  Filter: (status = 'pending'::order_status)
  Buffers: shared hit=7    ← tiny index, cached easily
```

| Query | Index Size | Buffers | Notes |
|-------|-----------|---------|-------|
| Bad (full index) | 400 MB | shared hit=4820 | All 5M rows indexed |
| Good (partial) | 20 MB | shared hit=7 | Only 250k pending rows |

## Aurora/RDS Notes

- **Aurora PostgreSQL**: Partial indexes are especially valuable on Aurora because the storage cost is per GB per month. A 380 MB reduction in index size reduces both storage cost and distributed storage I/O on every query.
- **RDS PostgreSQL**: Partial index creation uses `CREATE INDEX CONCURRENTLY` to avoid table locks in production. The partial index predicate is visible in `pg_indexes.indexdef`.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | Partial indexes fully supported; predicate matching automatic |
| PostgreSQL 15 | Same |
| PostgreSQL 16 | Same |
| PostgreSQL 17 | Same |
| Aurora PostgreSQL | Same as community; storage cost savings are amplified |
