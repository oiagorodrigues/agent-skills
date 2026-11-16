---
title: "Write sargable predicates to enable index use"
impact: high
tags: [sargable, indexes, predicates, cast, functions, performance]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Write sargable predicates to enable index use

## Problem

A predicate is **sargable** (Search ARGument ABLE) if PostgreSQL can use an index to evaluate it. Wrapping a column in a function, casting it, or comparing it to a value of a different type makes the predicate non-sargable — PostgreSQL must evaluate the expression for every row without index support, forcing a sequential scan. Common non-sargable patterns in PostgreSQL include `EXTRACT()` on timestamps, `LOWER()` on text columns, implicit casts between types, and arithmetic on indexed columns.

## Bad Example

```sql
-- BAD 1: EXTRACT() on an indexed timestamp column
-- idx_orders_created_at cannot be used — evaluated per-row
SELECT id, user_id, total_amount
FROM   orders
WHERE  EXTRACT(year FROM created_at) = 2024;
```

```sql
-- BAD 2: LOWER() on an indexed email column
-- idx_users_email cannot be used
SELECT id, email
FROM   users
WHERE  LOWER(email) = LOWER($1);
```

```sql
-- BAD 3: Implicit cast — comparing BIGINT column to TEXT literal
-- PostgreSQL must cast user_id to TEXT for every row
SELECT id, total_amount
FROM   orders
WHERE  user_id::text = '42';
```

```sql
-- BAD 4: Type mismatch in parameter binding
-- In application code: passing $1 as a string when user_id is BIGINT
-- PostgreSQL adds an implicit cast, preventing index use
SELECT id FROM orders WHERE user_id = $1;  -- $1 bound as varchar, not bigint
```

```sql
-- BAD 5: Arithmetic on the indexed column
-- Prevents index use on price
SELECT id, name FROM products WHERE price * 1.1 > $1;
```

## Good Example

```sql
-- GOOD 1: Rewrite EXTRACT() as a range predicate on the column directly
SELECT id, user_id, total_amount
FROM   orders
WHERE  created_at >= '2024-01-01 00:00:00+00'
  AND  created_at <  '2025-01-01 00:00:00+00';
-- Uses idx_orders_created_at with a range scan
```

```sql
-- GOOD 2a: Create a functional index matching the expression, OR use citext extension
-- Option A: functional index
CREATE INDEX idx_users_email_lower ON users (LOWER(email));
SELECT id, email FROM users WHERE LOWER(email) = LOWER($1);
-- EXPLAIN: Index Scan using idx_users_email_lower

-- Option B: use citext (case-insensitive text type)
CREATE EXTENSION IF NOT EXISTS citext;
-- ALTER TABLE users ALTER COLUMN email TYPE citext;
-- Then: WHERE email = $1  -- case-insensitive comparison, uses regular index
```

```sql
-- GOOD 3: Move the cast to the literal, not the column
SELECT id, total_amount
FROM   orders
WHERE  user_id = 42;              -- integer literal matches BIGINT column

-- In application code: bind $1 as integer/bigint type, not as string
SELECT id, total_amount FROM orders WHERE user_id = $1;  -- $1 bound as int8
```

```sql
-- GOOD 4: Move arithmetic to the literal side
SELECT id, name FROM products WHERE price > $1 / 1.1;
-- price column is untransformed; index on price can be used
```

## Why It Matters

- **Function on column = sequential scan**: Any function call that wraps an indexed column makes the index unusable for that predicate. The function must be evaluated for every row in the table.
- **Type mismatches are silent killers**: `WHERE user_id = '42'` (string vs BIGINT) compiles without error but PostgreSQL adds a hidden `::bigint` cast to the literal (usually) or `::text` cast to the column (less often). The direction of the cast determines whether the index is used. Always bind application parameters with the exact type of the column.
- **EXTRACT vs range**: `EXTRACT(year FROM created_at) = 2024` cannot use a B-tree index. `created_at >= '2024-01-01'` is a sargable range scan.
- **Functional indexes as escape hatch**: If you must search on `LOWER(email)`, create `CREATE INDEX ON users (LOWER(email))` — a functional index that stores the transformed value.

## EXPLAIN Notes

```sql
-- Bad: EXTRACT prevents index use
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, user_id, total_amount FROM orders
WHERE EXTRACT(year FROM created_at) = 2024;
```

```
Seq Scan on orders  (actual rows=1247834 loops=1)
  Filter: (EXTRACT(year FROM created_at) = 2024)
  Rows Removed by Filter: 3752166
  Buffers: shared read=50000
```

```sql
-- Good: range predicate uses the index
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, user_id, total_amount FROM orders
WHERE created_at >= '2024-01-01+00' AND created_at < '2025-01-01+00';
```

```
Index Scan using idx_orders_created_at on orders
  Index Cond: ((created_at >= '2024-01-01 00:00:00+00') AND
               (created_at < '2025-01-01 00:00:00+00'))
  actual rows=1247834
  Buffers: shared hit=12480
```

| Pattern | Sargable? | Fix |
|---------|-----------|-----|
| `EXTRACT(year FROM created_at) = 2024` | No | Use range: `created_at >= '2024-01-01'` |
| `LOWER(email) = $1` | No | Functional index on `LOWER(email)` or `citext` |
| `user_id::text = '42'` | No | Compare as integer: `user_id = 42` |
| `price * 1.1 > $1` | No | Move arithmetic: `price > $1 / 1.1` |
| `to_char(created_at, 'YYYY') = '2024'` | No | Use range predicate |

## Aurora/RDS Notes

- **Aurora PostgreSQL**: Non-sargable predicates on Aurora trigger distributed storage sequential scans. The network latency of Aurora storage amplifies the cost of non-sargable predicates compared to local-disk PostgreSQL.
- **RDS PostgreSQL**: Use `auto_explain` (via parameter group) to log slow query plans and identify non-sargable predicates in production. Set `auto_explain.log_min_duration = 1000` to log queries over 1 second.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | `citext` extension available; functional indexes available |
| PostgreSQL 15 | Same |
| PostgreSQL 16 | Same; improved type coercion in some cases |
| PostgreSQL 17 | Same |
| Aurora PostgreSQL | Same as community; `auto_explain` available via parameter group |
