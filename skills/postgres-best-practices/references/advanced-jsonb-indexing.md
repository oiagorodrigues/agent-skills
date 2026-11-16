---
title: "Index JSONB columns with GIN for containment queries"
impact: high
tags: [jsonb, gin-index, json, indexing, performance, jsonb-path-ops]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Index JSONB columns with GIN for containment queries

## Problem

JSONB columns that are frequently queried with containment operators (`@>`, `?`, `@?`, `@@`) require GIN indexes to avoid sequential scans. Without a GIN index, every JSONB query scans the entire table and re-parses the JSONB binary for every row. Additionally, the choice between the default GIN opclass and `jsonb_path_ops` affects index size and supported operations.

## Bad Example

```sql
-- BAD: JSON (not JSONB) — no GIN indexing possible
CREATE TABLE products_bad (
  id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  attributes JSON   -- stored as raw text, cannot be GIN-indexed
);

-- Containment query on JSON — forces sequential scan:
SELECT id, name FROM products_bad WHERE attributes @> '{"color":"red"}';
-- ERROR: operator does not exist: json @> unknown
-- OR: full sequential scan re-parsing JSON text for every row

-- BAD: JSONB without a GIN index
-- The @> operator on JSONB without GIN causes a sequential scan:
SELECT id FROM products WHERE attributes @> '{"color": "red", "in_stock": true}';
-- Seq Scan: re-parses JSONB binary for all 5M rows
```

## Good Example

```sql
-- GOOD 1: JSONB column (already in the schema)
-- All queryable JSON must use JSONB, not JSON
ALTER TABLE products
  ALTER COLUMN attributes TYPE JSONB USING attributes::jsonb;

-- GOOD 2: Default GIN index for full JSONB operator support
-- Supports: @>, ?, ?|, ?&, @?, @@
CREATE INDEX idx_products_attributes_gin
  ON products USING gin (attributes);

-- Containment query uses GIN index:
SELECT id, name FROM products
WHERE  attributes @> '{"color": "red"}';
-- EXPLAIN: Bitmap Index Scan on idx_products_attributes_gin

-- Key existence query:
SELECT id, name FROM products
WHERE  attributes ? 'discount_price';  -- has this key?

-- Any key from a list:
SELECT id, name FROM products
WHERE  attributes ?| ARRAY['sale', 'clearance'];

-- jsonpath query (PG 12+):
SELECT id, name FROM products
WHERE  attributes @@ '$.price > 100';
```

```sql
-- GOOD 3: jsonb_path_ops GIN — smaller, faster for @> only
-- jsonb_path_ops only supports the @> operator but the index is 30-50% smaller
-- and faster for containment queries
CREATE INDEX idx_products_attributes_path_ops
  ON products USING gin (attributes jsonb_path_ops);

-- When to use jsonb_path_ops vs default:
-- Use jsonb_path_ops when: you ONLY use @> containment queries
-- Use default GIN when:    you also use ?, ?|, ?&, @?, @@ operators

-- GOOD 4: Functional index on a specific JSONB path
-- For queries on a specific key (e.g., always filter on attributes->>'color'):
CREATE INDEX idx_products_color
  ON products ((attributes->>'color'));

-- This is smaller than a full GIN index and faster for equality:
SELECT id, name FROM products
WHERE  attributes->>'color' = 'red';
-- EXPLAIN: Index Scan using idx_products_color
```

```sql
-- GOOD 5: Generated column from JSONB path (PG 12+, see schema-generated-columns.md)
ALTER TABLE products
  ADD COLUMN color TEXT
  GENERATED ALWAYS AS (attributes->>'color') STORED;

CREATE INDEX idx_products_generated_color ON products (color);
-- Regular B-tree index on the generated column — smaller than GIN, faster for =

-- GOOD 6: JSONB array operations
-- Query for products where tags array contains 'wireless':
SELECT id, name FROM products
WHERE  attributes @> '{"tags": ["wireless"]}';   -- containment in nested array

-- Or using the array column directly (see sample schema):
SELECT id, name FROM products
WHERE  'wireless' = ANY(tags);    -- using the TEXT[] tags column
-- GIN index on tags array: CREATE INDEX ON products USING gin(tags);

-- GOOD 7: jsponb_to_record for table-valued expansion
SELECT
  p.id,
  p.name,
  r.color,
  r.size,
  r.material
FROM products p,
LATERAL jsonb_to_record(p.attributes) AS r(color text, size text, material text)
WHERE r.color = 'red';
-- Returns structured columns from JSONB — cleaner than repeated ->> operators
```

### JSONB Operator Reference

| Operator | Description | Index |
|----------|-------------|-------|
| `@>` | Does left JSONB contain right? | GIN (default or path_ops) |
| `<@` | Is left JSONB contained in right? | GIN (default) |
| `?` | Does key exist at top level? | GIN (default only) |
| `?|` | Any of these keys exist? | GIN (default only) |
| `?&` | All of these keys exist? | GIN (default only) |
| `->` | Get JSON object field / array element | None |
| `->>` | Get as text | Functional index on expr |
| `@?` | Does jsonpath match? | GIN (default) |
| `@@` | Check jsonpath predicate | GIN (default) |

## Why It Matters

- **JSON vs JSONB**: JSON stores raw text — every access re-parses the text. JSONB stores a parsed binary structure — key access is O(log n), and GIN indexes are possible. Always use JSONB for queried data.
- **GIN index size**: A GIN index on a JSONB column may be 2–5× the column data size — monitor with `pg_indexes_size()`. `jsonb_path_ops` reduces this by 30–50%.
- **Functional index trade-off**: A functional index on `(attributes->>'color')` is much smaller than a GIN index but only helps for that specific key. Use when one key dominates your access patterns.
- **Generated column vs functional index**: Both achieve similar results; generated columns are more readable and can be used in ORDER BY without repeating the expression.

## EXPLAIN Notes

```sql
-- Without GIN index: Seq Scan
EXPLAIN SELECT id FROM products WHERE attributes @> '{"color": "red"}';
-- Seq Scan on products ... Filter: (attributes @> '{"color": "red"}'::jsonb)

-- With GIN index: Bitmap Index Scan
CREATE INDEX ON products USING gin(attributes);
EXPLAIN SELECT id FROM products WHERE attributes @> '{"color": "red"}';
-- Bitmap Heap Scan on products
--   ->  Bitmap Index Scan on idx_products_attributes_gin
--         Index Cond: (attributes @> '{"color": "red"}'::jsonb)
```

## Aurora/RDS Notes

- **Aurora PostgreSQL**: JSONB and GIN indexes work identically on Aurora. GIN index sizes count toward Aurora storage billing.
- **RDS PostgreSQL**: Same as community PostgreSQL.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | JSONB GIN, `jsonb_path_ops`, functional indexes all available |
| PostgreSQL 15 | Same |
| PostgreSQL 16 | Same |
| PostgreSQL 17 | `JSON_TABLE()` added for SQL/JSON; `@@` jsonpath improvements |
| Aurora PostgreSQL | JSONB fully supported |
