---
title: "Use generated columns for computed values that need to be indexed"
impact: medium
tags: [generated-columns, computed-columns, schema-design, indexes, jsonb]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Use generated columns for computed values that need to be indexed

## Problem

When applications repeatedly compute the same expression (total order value, extracted JSONB field, normalized text) in queries, the computation runs on every row scan. Generated columns store the computed result physically in the row and can be indexed — eliminating per-row computation and enabling index use. PostgreSQL supports only **stored** generated columns (computed on write, stored on disk), unlike MySQL's virtual generated columns.

## Bad Example

```sql
-- BAD: Computing line item total in every query
-- This expression is evaluated for every row in order_items on every query
SELECT order_id, SUM(unit_price * quantity) AS order_total
FROM   order_items
GROUP  BY order_id;
-- unit_price * quantity computed on every row, cannot be indexed

-- BAD: Extracting a JSONB field in every query
SELECT id, name, attributes->>'color' AS color
FROM   products
WHERE  attributes->>'color' = 'red';
-- attributes->>'color' evaluated for every row; cannot use a simple index
-- (must use a functional index workaround — or a generated column)

-- BAD: LOWER() applied repeatedly for case-insensitive search
SELECT id, email FROM users WHERE LOWER(email) = LOWER($1);
-- LOWER(email) computed per-row without a functional index
```

## Good Example

```sql
-- GOOD 1: Generated column for line item total (stored, indexed)
ALTER TABLE order_items
  ADD COLUMN line_total NUMERIC(12,2)
  GENERATED ALWAYS AS (unit_price * quantity) STORED;

-- Now index the generated column:
CREATE INDEX idx_order_items_line_total ON order_items (line_total);

-- Queries can filter on line_total without computing it:
SELECT order_id, SUM(line_total) AS order_total
FROM   order_items
GROUP  BY order_id;

-- Find high-value line items:
SELECT id, order_id, product_id, line_total
FROM   order_items
WHERE  line_total > 500.00;
-- Uses idx_order_items_line_total — no computation per row
```

```sql
-- GOOD 2: Generated column extracting a JSONB path (stored, indexed)
ALTER TABLE products
  ADD COLUMN color TEXT
  GENERATED ALWAYS AS (attributes->>'color') STORED;

CREATE INDEX idx_products_color ON products (color);

-- Now index-supported lookup:
SELECT id, name, color FROM products WHERE color = 'red';
-- EXPLAIN: Index Scan using idx_products_color
```

```sql
-- GOOD 3: Generated column for normalized email (case-insensitive search)
ALTER TABLE users
  ADD COLUMN email_lower TEXT
  GENERATED ALWAYS AS (LOWER(email)) STORED;

CREATE INDEX idx_users_email_lower ON users (email_lower);

-- Case-insensitive email lookup via index:
SELECT id, email FROM users WHERE email_lower = LOWER($1);
-- EXPLAIN: Index Scan using idx_users_email_lower
```

```sql
-- Verify generated column definition:
SELECT column_name, generation_expression, is_nullable
FROM   information_schema.columns
WHERE  table_name   = 'order_items'
  AND  column_name  = 'line_total';

-- Generated columns are NOT updatable:
-- UPDATE order_items SET line_total = 100;  -- ERROR: cannot update generated column
-- The value is automatically recomputed when unit_price or quantity changes
```

## Why It Matters

- **Compute-once, query-many**: A generated column is computed on INSERT/UPDATE and stored. Every subsequent query reads the pre-computed value — O(1) instead of recomputing per row.
- **Indexable**: Generated columns can be indexed. A functional index on `LOWER(email)` and a generated column `email_lower` with an index on it are functionally equivalent — but the generated column approach is more readable and doesn't require the index definition to match the query expression exactly.
- **PostgreSQL: stored only**: Unlike MySQL, PostgreSQL only supports `GENERATED ALWAYS AS (...) STORED`. There is no virtual (computed-on-read) generated column. Every generated column adds to row storage size — only add for columns you actually need to query or index.
- **Aurora**: Generated columns are supported on Aurora PostgreSQL 13+. On earlier Aurora versions, use a functional index as an alternative.

## Aurora/RDS Notes

- **Aurora PostgreSQL 13+**: `GENERATED ALWAYS AS ... STORED` is fully supported.
- **Aurora PostgreSQL 12 and earlier**: Generated columns not available (they were added in PostgreSQL 12). Use functional indexes: `CREATE INDEX ON products ((attributes->>'color'))`.
- **RDS PostgreSQL**: Supported on all RDS PostgreSQL versions that correspond to PG 12+.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | Generated columns (stored) available since PG 12; can be indexed |
| PostgreSQL 15 | Same |
| PostgreSQL 16 | Same |
| PostgreSQL 17 | Same |
| Aurora PostgreSQL 13+ | Supported; Aurora PostgreSQL < 13 must use functional indexes |
