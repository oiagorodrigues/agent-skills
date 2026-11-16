---
title: "Choose the right PostgreSQL index type for each access pattern"
impact: high
tags: [indexes, gin, gist, brin, btree, hash, index-types, jsonb, full-text]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Choose the right PostgreSQL index type for each access pattern

## Problem

PostgreSQL supports six index types: B-tree, Hash, GIN, GiST, BRIN, and SP-GiST. The default `CREATE INDEX` creates a B-tree, which is optimal for equality and range queries on scalar values. Using a B-tree for JSONB containment queries, array operations, full-text search, or large sequential tables forces sequential scans or slow index operations. Choosing the right index type can reduce index size by 10–100× and query time by similar factors.

## Index Types Reference

| Type | Best For | Not Good For |
|------|----------|-------------|
| **B-tree** | Equality, range (`<`, `>`, `BETWEEN`), ORDER BY, `IS NULL` | JSONB containment, arrays, full-text |
| **Hash** | Equality only (`=`); smaller than B-tree for this case | Range queries, anything requiring ordering |
| **GIN** | JSONB (`@>`, `?`), arrays, full-text (`@@`), trigrams (`LIKE '%x%'`) | Range queries, scalar equality |
| **GiST** | Geometric types, range types (`&&`), full-text, nearest-neighbor | Pure equality on scalars |
| **BRIN** | Very large append-only tables with naturally ordered data (time-series, logs) | High-cardinality lookups, random access |
| **SP-GiST** | Partitioned, non-balanced structures (IPs, phone numbers, quad-trees) | General purpose |

## Bad Example

```sql
-- BAD: B-tree index on JSONB column — cannot be used for containment queries
CREATE INDEX idx_products_attributes_btree ON products (attributes);

-- JSONB containment query — cannot use B-tree, forces sequential scan
SELECT id, name
FROM   products
WHERE  attributes @> '{"color": "red", "size": "L"}';
```

B-tree indexes on JSONB columns are nearly useless — they can only be used for equality on the entire JSONB value (extremely rare) and cannot handle `@>`, `?`, or `@@` operators.

```sql
-- BAD: B-tree index on a huge append-only event log table
-- Table has 500M rows, always inserted in timestamp order
CREATE INDEX idx_events_created_btree ON events (created_at);
-- Index size: ~15 GB, slow to build, high write overhead
```

## Good Example

```sql
-- GOOD: GIN index for JSONB containment (@>) and key existence (?) queries
CREATE INDEX idx_products_attributes_gin ON products USING gin (attributes);

-- Now uses GIN index for containment
SELECT id, name
FROM   products
WHERE  attributes @> '{"color": "red", "size": "L"}';
-- EXPLAIN: Bitmap Index Scan on idx_products_attributes_gin

-- Smaller GIN with jsonb_path_ops — only supports @> but is 30-50% smaller
CREATE INDEX idx_products_attributes_path_ops
  ON products USING gin (attributes jsonb_path_ops);
```

```sql
-- GOOD: GIN trigram index for LIKE/ILIKE substring search
-- Requires: CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_products_name_trgm ON products USING gin (name gin_trgm_ops);

-- Now LIKE with leading wildcard uses the GIN trigram index
SELECT id, name FROM products WHERE name LIKE '%wireless%';
SELECT id, name FROM products WHERE name ILIKE '%wireless%';
-- EXPLAIN: Bitmap Index Scan on idx_products_name_trgm
```

```sql
-- GOOD: BRIN index for large sequential tables (500M rows, always inserted in order)
-- Index is ~128 KB instead of 15 GB — 100,000× smaller
CREATE INDEX idx_events_created_brin ON events USING brin (created_at);

-- Efficient for range queries on naturally ordered data
SELECT COUNT(*) FROM events
WHERE created_at BETWEEN '2024-01-01' AND '2024-02-01';
-- EXPLAIN: Bitmap Index Scan on idx_events_created_brin (reads only relevant block ranges)
```

```sql
-- GOOD: Hash index for pure equality lookups (smaller than B-tree for this use case)
CREATE INDEX idx_products_sku_hash ON products USING hash (sku);

-- SKU lookup by exact equality — slightly faster than B-tree for this pattern
SELECT id, name, price FROM products WHERE sku = $1;
```

```sql
-- GOOD: GiST index for date/time range overlap queries (schedule conflicts)
-- Requires a table with tstzrange column or similar range type
CREATE INDEX idx_reservations_range ON reservations USING gist (during);

-- Overlap query uses GiST
SELECT * FROM reservations WHERE during && '[2024-06-01, 2024-06-07)'::tstzrange;
```

## Why It Matters

- **B-tree on JSONB**: A B-tree cannot represent JSONB's nested structure. The `@>` operator requires a GIN index. Without it, every JSONB containment query does a sequential scan.
- **GIN size vs B-tree**: A GIN index on a `TEXT[]` column is typically 3–5× smaller than a B-tree on the same column for array operations, and supports operators B-tree cannot.
- **BRIN size vs B-tree**: On a 500M-row time-series table ordered by `created_at`, a BRIN index is ~128 KB vs ~15 GB for a B-tree — 100,000× smaller. BRIN is effective only when data is physically stored in the same order as the indexed column (correlation close to 1.0 in `pg_stats`).
- **Hash index**: Hash indexes in PostgreSQL 10+ are WAL-logged and crash-safe. They are 10–20% smaller than B-tree for pure equality lookups. They cannot serve range queries or ORDER BY.

## EXPLAIN Notes

```sql
-- Check which index type is used:
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, name FROM products WHERE attributes @> '{"color": "red"}';
```

With B-tree (bad):
```
Seq Scan on products  (rows=50000)
  Filter: (attributes @> '{"color": "red"}'::jsonb)
  Buffers: shared hit=5000
```

With GIN (good):
```
Bitmap Heap Scan on products  (rows=1250)
  Recheck Cond: (attributes @> '{"color": "red"}'::jsonb)
  ->  Bitmap Index Scan on idx_products_attributes_gin
      Index Cond: (attributes @> '{"color": "red"}'::jsonb)
  Buffers: shared hit=42
```

| Scenario | Bad Index | Good Index | Size Ratio | Scan Type |
|----------|-----------|------------|-----------|-----------|
| JSONB containment | B-tree (unusable) | GIN | ~3–5× smaller | Bitmap Index Scan |
| LIKE '%term%' | None (seq scan) | GIN trigram | — | Bitmap Index Scan |
| Time-series range | B-tree (15 GB) | BRIN (128 KB) | 100,000× smaller | Bitmap Index Scan |
| Exact equality | B-tree | Hash | ~20% smaller | Index Scan |

## Aurora/RDS Notes

- **Aurora PostgreSQL**: All PostgreSQL index types are supported. GIN and BRIN indexes reduce storage costs on Aurora's per-GB billing model significantly.
- **RDS PostgreSQL**: `pg_trgm` and `btree_gin` extensions must be created with `CREATE EXTENSION` — they are available but not enabled by default.
- **Hash indexes on Aurora**: Fully supported and WAL-replicated to Aurora replicas (crash-safe since PG 10).

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | All six types available; Hash indexes WAL-safe since PG 10 |
| PostgreSQL 15 | GiST index improvements for nearest-neighbor queries |
| PostgreSQL 16 | Same |
| PostgreSQL 17 | Same |
| Aurora PostgreSQL | All index types supported; BRIN especially cost-effective on large Aurora tables |
