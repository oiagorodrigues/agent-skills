---
title: "Order composite index columns: equality first, range last"
impact: high
tags: [indexes, composite-index, query-optimization, column-order]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Order composite index columns: equality first, range last

## Problem

A composite (multi-column) B-tree index must be used in the leftmost-prefix order. A query that filters on column B but not column A cannot use an index defined as `(A, B)`. Beyond the leftmost-prefix rule, column order also determines how efficiently the index handles mixed equality + range predicates: equality columns must come before range columns, and higher-selectivity columns (fewer distinct values in the matching set) should come first within equality columns.

## Bad Example

```sql
-- Index defined with range column first, equality column second
CREATE INDEX idx_orders_bad ON orders (created_at, user_id);

-- Query: orders for a specific user created after a date
SELECT id, status, total_amount
FROM   orders
WHERE  user_id    = $1
  AND  created_at > $2;
```

`idx_orders_bad` starts with `created_at`. PostgreSQL can only use the `created_at` range scan — it cannot efficiently filter `user_id` via the index because `user_id` comes second. The planner either uses only the `created_at` portion of the index (reading many rows) or skips the index entirely and does a sequential scan.

## Good Example

```sql
-- Equality column first, range column second
CREATE INDEX idx_orders_user_created ON orders (user_id, created_at);

-- Same query now uses the full composite index efficiently
SELECT id, status, total_amount
FROM   orders
WHERE  user_id    = $1            -- equality: seeks to user's partition in index
  AND  created_at > $2;           -- range: scans forward from the date within that partition
```

The index seeks to the `user_id = $1` partition, then range-scans `created_at > $2` within that partition. Rows examined is proportional to the number of matching rows — not the entire table.

```sql
-- For a covering index that also satisfies the SELECT columns:
CREATE INDEX idx_orders_user_created_covering
  ON orders (user_id, created_at)
  INCLUDE (status, total_amount);   -- INCLUDE clause (PostgreSQL 11+)

-- Now PostgreSQL can do an Index Only Scan — no heap fetch needed
SELECT id, status, total_amount
FROM   orders
WHERE  user_id    = $1
  AND  created_at > $2;
```

## Why It Matters

- **Leftmost prefix rule**: An index on `(user_id, created_at)` is also usable for queries on `user_id` alone. An index on `(created_at, user_id)` is only usable for queries on `created_at` alone — adding `user_id` to a filter gains nothing.
- **Equality then range**: After an equality match on `user_id`, the index is sorted by `created_at` — a range scan is O(log n + k) where k is matching rows. If `created_at` came first, the equality on `user_id` would not be contiguous in the index and PostgreSQL would have to scan many more entries.
- **Selectivity**: Place the most selective equality column first. If `status` has 7 distinct values and `user_id` has 100,000, put `user_id` first.
- **Planner overrides**: `SET enable_indexscan = off` can test whether the planner would choose a sequential scan. `SET random_page_cost = 1.1` (recommended on Aurora) makes the planner more aggressive about index scans.

## EXPLAIN Notes

```sql
-- Bad: index starts with range column
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, status, total_amount FROM orders
WHERE user_id = 42 AND created_at > '2024-01-01';
```

With `(created_at, user_id)` index:
```
Index Scan using idx_orders_bad on orders
  Index Cond: (created_at > '2024-01-01 00:00:00+00'::timestamptz)
  Filter: (user_id = 42)
  Rows Removed by Filter: 98000   ← most index rows filtered out after fetch
  Buffers: shared hit=1200
```

```sql
-- Good: equality column first
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, status, total_amount FROM orders
WHERE user_id = 42 AND created_at > '2024-01-01';
```

With `(user_id, created_at)` index:
```
Index Scan using idx_orders_user_created on orders
  Index Cond: ((user_id = 42) AND (created_at > '2024-01-01 00:00:00+00'::timestamptz))
  Rows Removed by Filter: 0
  Buffers: shared hit=12
```

| Query | Index Used | Rows Removed by Filter | Buffers |
|-------|-----------|----------------------|---------|
| Bad   | `(created_at, user_id)` — only range portion used | 98,000 | shared hit=1200 |
| Good  | `(user_id, created_at)` — full index used | 0 | shared hit=12 |

## Aurora/RDS Notes

- **Aurora PostgreSQL**: `random_page_cost = 1.1` in the parameter group is recommended. At the default `4.0`, the planner may prefer a sequential scan for moderately selective indexes. With `1.1`, composite indexes on Aurora are used more aggressively.
- **RDS PostgreSQL**: Index creation on large tables (`CREATE INDEX`) takes an `ShareLock` on the table. Use `CREATE INDEX CONCURRENTLY` in production to avoid blocking reads. See `schema-online-ddl.md`.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | Composite indexes and leftmost prefix behavior unchanged |
| PostgreSQL 15 | Same |
| PostgreSQL 16 | Same |
| PostgreSQL 17 | Same |
| Aurora PostgreSQL | Same; set `random_page_cost = 1.1` in parameter group |
