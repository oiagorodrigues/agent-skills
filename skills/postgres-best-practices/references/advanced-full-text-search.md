---
title: "Use tsvector/GIN for full-text search and pg_trgm for LIKE/ILIKE"
impact: medium
tags: [full-text-search, tsvector, tsquery, gin, pg-trgm, like, ilike]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Use tsvector/GIN for full-text search and pg_trgm for LIKE/ILIKE

## Problem

`WHERE name LIKE '%term%'` with a leading wildcard forces a sequential scan — PostgreSQL cannot use a B-tree index because the matching prefix is unknown. For full-text search (word matching with stemming and ranking), `tsvector` with a GIN index is the right tool. For substring matching (LIKE/ILIKE with wildcards), `pg_trgm` (trigram extension) provides a GIN index that supports arbitrary substring queries. Each solves a different problem — know which to use.

## Bad Example

```sql
-- BAD: Leading wildcard LIKE forces sequential scan
SELECT id, name, price FROM products
WHERE  name LIKE '%wireless%';
-- Seq Scan: evaluates LIKE for every product row

-- BAD: ILIKE without trigram index (case-insensitive + leading wildcard)
SELECT id, name FROM products
WHERE  name ILIKE '%acme%';
-- Seq Scan: no index can help without pg_trgm

-- BAD: to_tsvector in a WHERE clause without a GIN index
SELECT id, name FROM products
WHERE  to_tsvector('english', name) @@ to_tsquery('english', 'wireless');
-- Seq Scan: to_tsvector computed per-row without a stored tsvector column or index
```

## Good Example

### pg_trgm: Substring Search (LIKE/ILIKE with wildcards)

```sql
-- Install the trigram extension (required):
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- GIN trigram index enables LIKE/ILIKE with wildcards:
CREATE INDEX idx_products_name_trgm ON products USING gin (name gin_trgm_ops);

-- Now LIKE with leading wildcard uses the GIN trigram index:
SELECT id, name, price FROM products WHERE name LIKE '%wireless%';
-- EXPLAIN: Bitmap Index Scan on idx_products_name_trgm

-- Case-insensitive ILIKE also uses the trigram index:
SELECT id, name, price FROM products WHERE name ILIKE '%acme%';
-- EXPLAIN: Bitmap Index Scan on idx_products_name_trgm

-- Similarity search (fuzzy matching):
SELECT id, name, similarity(name, 'wirelss') AS sim
FROM   products
WHERE  similarity(name, 'wirelss') > 0.3   -- 0-1 scale, 0.3 = 30% similar
ORDER  BY sim DESC
LIMIT  10;
-- Use GiST with gist_trgm_ops for similarity (GIN doesn't support ORDER BY similarity):
CREATE INDEX idx_products_name_gist ON products USING gist (name gist_trgm_ops);
```

### tsvector/tsquery: Full-Text Search (word matching, stemming, ranking)

```sql
-- GIN index on a stored tsvector (pre-computed, fastest at query time):
-- The sample schema already has this on reviews:
-- CREATE INDEX idx_reviews_fts ON reviews
--   USING gin (to_tsvector('english', COALESCE(title,'') || ' ' || COALESCE(body,'')));

-- For products: index on name + description
CREATE INDEX idx_products_fts
  ON products
  USING gin (to_tsvector('english', name || ' ' || COALESCE(description, '')));

-- Full-text search query:
SELECT id, name, description
FROM   products
WHERE  to_tsvector('english', name || ' ' || COALESCE(description, ''))
       @@ to_tsquery('english', 'wireless & bluetooth');
-- EXPLAIN: Bitmap Index Scan on idx_products_fts

-- plainto_tsquery: converts a plain string to tsquery (no operators needed)
SELECT id, name FROM products
WHERE  to_tsvector('english', name) @@ plainto_tsquery('english', 'wireless bluetooth');
-- plainto_tsquery('english', 'wireless bluetooth') = to_tsquery('wireless & bluetooth')

-- websearch_to_tsquery (PG 11+): Google-style query syntax
SELECT id, name FROM products
WHERE  to_tsvector('english', name) @@ websearch_to_tsquery('english', 'wireless -wired');
-- -wired means "NOT wired"

-- Relevance ranking with ts_rank:
SELECT id, name,
  ts_rank(
    to_tsvector('english', name || ' ' || COALESCE(description, '')),
    to_tsquery('english', 'wireless')
  ) AS rank
FROM   products
WHERE  to_tsvector('english', name || ' ' || COALESCE(description, ''))
       @@ to_tsquery('english', 'wireless')
ORDER  BY rank DESC
LIMIT  20;

-- Highlighting matches with ts_headline:
SELECT id, name,
  ts_headline('english', description,
    to_tsquery('english', 'wireless'),
    'StartSel=<b>, StopSel=</b>, MaxWords=30'
  ) AS snippet
FROM   products
WHERE  to_tsvector('english', COALESCE(description,''))
       @@ to_tsquery('english', 'wireless');
```

```sql
-- BEST PRACTICE: Store tsvector in a generated column for performance
-- Avoids recomputing to_tsvector() for every query
ALTER TABLE products
  ADD COLUMN fts_vector TSVECTOR
  GENERATED ALWAYS AS (
    to_tsvector('english', name || ' ' || COALESCE(description, ''))
  ) STORED;

CREATE INDEX idx_products_fts_vector ON products USING gin (fts_vector);

-- Now the query is simpler and faster:
SELECT id, name FROM products WHERE fts_vector @@ to_tsquery('english', 'wireless');
-- EXPLAIN: Bitmap Index Scan on idx_products_fts_vector (no per-row to_tsvector call)
```

### When to Use Which Approach

| Use Case | Tool | Index |
|----------|------|-------|
| `LIKE '%term%'` (arbitrary substring) | `pg_trgm` | GIN (`gin_trgm_ops`) |
| `ILIKE '%term%'` (case-insensitive) | `pg_trgm` | GIN (`gin_trgm_ops`) |
| Word search with stemming (English, French, etc.) | `tsvector` + `tsquery` | GIN on `tsvector` |
| Fuzzy/similarity matching | `pg_trgm` `similarity()` | GiST (`gist_trgm_ops`) |
| Relevance ranking | `tsvector` + `ts_rank()` | GIN on `tsvector` |
| Search in multiple languages | `tsvector` (specify language) | GIN on tsvector |

## Why It Matters

- **LIKE '%term%' without pg_trgm**: Sequential scan — reads every row. On a 1M-product table: seconds per query.
- **pg_trgm GIN index**: Splits strings into 3-character trigrams. `'wireless'` = `{'wi', 'ir', 're', 'el', 'le', 'es', 'ss', ...}`. A GIN index can find rows that match all trigrams in the search string — typical queries go from seconds to milliseconds.
- **tsvector vs trigrams**: tsvector provides linguistic features (stemming: 'running' matches 'run'), multi-language support, AND/OR/NOT query syntax, and relevance ranking. Trigrams provide substring matching without linguistic awareness.
- **Stored tsvector column**: Computing `to_tsvector('english', ...)` at query time evaluates the function for every scanned row. A stored generated column or trigger-maintained tsvector column avoids this computation.

## Aurora/RDS Notes

- **Aurora PostgreSQL**: Both `pg_trgm` and `tsvector`/`tsquery` full-text search are fully supported. GIN indexes work identically.
- **RDS PostgreSQL**: `CREATE EXTENSION pg_trgm` available without any parameter group changes. GIN trigram indexes work on RDS.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | `pg_trgm`, `tsvector`, GIN indexes all fully available |
| PostgreSQL 15 | Same |
| PostgreSQL 16 | Same |
| PostgreSQL 17 | Same |
| Aurora PostgreSQL | `pg_trgm` and full-text search fully supported |
