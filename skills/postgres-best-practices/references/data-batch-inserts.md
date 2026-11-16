---
title: "Use multi-row INSERT or COPY for bulk data loading"
impact: high
tags: [batch-inserts, copy, performance, bulk-load, wal]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Use multi-row INSERT or COPY for bulk data loading

## Problem

Inserting rows one at a time in a loop is the slowest possible bulk loading pattern. Each single-row `INSERT` is a separate round trip, a separate WAL record, and (without an outer transaction) a separate WAL flush. For 10,000 rows, this means 10,000 round trips and 10,000 WAL syncs. Multi-row `INSERT` and `COPY FROM STDIN` batch the work and are 10–100× faster for bulk loads.

## Bad Example

```sql
-- BAD: Single-row INSERT in a loop
-- 1,000 rows = 1,000 round trips, 1,000 WAL flushes (if not in an outer transaction)
INSERT INTO products (category_id, name, sku, price, status)
VALUES (1, 'Widget A', 'SKU-001', 9.99, 'active');
INSERT INTO products (category_id, name, sku, price, status)
VALUES (1, 'Widget B', 'SKU-002', 14.99, 'active');
INSERT INTO products (category_id, name, sku, price, status)
VALUES (1, 'Widget C', 'SKU-003', 19.99, 'active');
-- ... 997 more single-row INSERT statements
```

```python
# BAD: Python loop calling execute() once per row
import psycopg2

conn = psycopg2.connect(...)
cur = conn.cursor()

products = [
    (1, 'Widget A', 'SKU-001', 9.99, 'active'),
    (1, 'Widget B', 'SKU-002', 14.99, 'active'),
    # ... 998 more
]

for product in products:
    cur.execute(
        "INSERT INTO products (category_id, name, sku, price, status) "
        "VALUES (%s, %s, %s, %s, %s)",
        product
    )
conn.commit()
# 1,000 round trips — slow even with a transaction wrapper
```

## Good Example

```sql
-- GOOD 1: Multi-row INSERT — one statement, one round trip, one WAL record
INSERT INTO products (category_id, name, sku, price, status)
VALUES
  (1, 'Widget A', 'SKU-001',  9.99, 'active'),
  (1, 'Widget B', 'SKU-002', 14.99, 'active'),
  (1, 'Widget C', 'SKU-003', 19.99, 'active');
  -- ... up to 500-1000 rows per batch for optimal throughput

-- With ON CONFLICT for idempotent upsert:
INSERT INTO products (category_id, name, sku, price, status)
VALUES
  (1, 'Widget A', 'SKU-001',  9.99, 'active'),
  (1, 'Widget B', 'SKU-002', 14.99, 'active')
ON CONFLICT (sku) DO NOTHING;   -- skip duplicates silently
```

```python
# GOOD 2: psycopg2 executemany() — still multiple round trips but batched by driver
# Better than one-by-one, but COPY is faster for large datasets

cur.executemany(
    "INSERT INTO products (category_id, name, sku, price, status) "
    "VALUES (%s, %s, %s, %s, %s)",
    products
)
conn.commit()

# GOOD 3: psycopg2 execute_values() — batches multiple rows into one SQL statement
from psycopg2.extras import execute_values

execute_values(
    cur,
    "INSERT INTO products (category_id, name, sku, price, status) VALUES %s",
    products,
    page_size=500    # batch 500 rows per INSERT statement
)
conn.commit()
# Much faster — 1,000 rows becomes 2 INSERT statements
```

```python
# BEST: COPY FROM STDIN — 10-100x faster than INSERT for bulk loads
# Bypasses SQL parser, writes directly to table pages
from psycopg2.extras import execute_values
import io

def bulk_insert_products(conn, products_data):
    """
    products_data: list of tuples (category_id, name, sku, price, status)
    """
    # Build a StringIO buffer with tab-separated values (COPY format)
    buffer = io.StringIO()
    for row in products_data:
        buffer.write('\t'.join(str(v) for v in row) + '\n')
    buffer.seek(0)

    cur = conn.cursor()
    # COPY FROM STDIN with tab-separated format
    cur.copy_expert(
        "COPY products (category_id, name, sku, price, status) FROM STDIN",
        buffer
    )
    conn.commit()
    print(f"Inserted {len(products_data)} rows via COPY")
```

```sql
-- COPY from a file (server-side) — fastest for large CSV files
-- Requires the file to be accessible on the PostgreSQL server
COPY products (category_id, name, sku, price, status)
FROM '/tmp/products.csv'
WITH (FORMAT csv, HEADER true, DELIMITER ',');

-- COPY with error handling (PostgreSQL 17+):
COPY products (category_id, name, sku, price, status)
FROM '/tmp/products.csv'
WITH (FORMAT csv, HEADER true, ON_ERROR IGNORE);  -- PG 17+: skip bad rows
-- Returns count of skipped rows in NOTICE messages

-- Export to CSV:
COPY products TO '/tmp/products_export.csv'
WITH (FORMAT csv, HEADER true);
```

## Performance Comparison

| Method | 10k rows | 100k rows | Notes |
|--------|----------|-----------|-------|
| Single-row INSERT | ~10 s | ~100 s | 1 round trip per row |
| Multi-row INSERT (500/batch) | ~200 ms | ~2 s | 20 round trips |
| `execute_values` (500/batch) | ~150 ms | ~1.5 s | Same as multi-row |
| `COPY FROM STDIN` | ~30 ms | ~300 ms | Best for bulk loads |

## Why It Matters

- **Round trips**: Each INSERT statement is a round trip to the database. 10,000 single-row INSERTs = 10,000 round trips × 1 ms each = 10 seconds of network latency alone.
- **WAL overhead**: Each INSERT writes to the WAL. Inside a transaction, WAL is flushed on COMMIT (not per-statement). But even with a transaction, the WAL records for 10,000 single-row INSERTs are written individually — less efficient than one large COPY record.
- **COPY efficiency**: `COPY` bypasses the SQL parser and query planner entirely. It writes data directly to heap pages. For bulk loads, COPY is typically 5–20× faster than equivalent multi-row INSERTs.
- **Batch size**: For multi-row INSERT, optimal batch size is 500–1,000 rows. Larger batches increase memory pressure without proportional speed gains. COPY has no such limitation.
- **Aurora**: COPY on Aurora also reduces write amplification to the Aurora distributed storage layer.

## Aurora/RDS Notes

- **Aurora PostgreSQL**: `COPY FROM STDIN` is supported and recommended for bulk loads. It writes efficiently to the Aurora storage layer with fewer distributed I/O operations than individual INSERTs.
- **RDS PostgreSQL**: Server-side `COPY FROM '/path/to/file'` requires the file to be on the RDS instance — not practical for managed RDS. Use `COPY FROM STDIN` (via `\copy` in psql or `copy_expert` in psycopg2) which uploads from the client.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | `COPY FROM STDIN`, multi-row INSERT, `execute_values` all available |
| PostgreSQL 15 | Same |
| PostgreSQL 16 | Same |
| PostgreSQL 17 | `COPY FROM ... ON_ERROR IGNORE` — skip bad rows during bulk load |
| Aurora PostgreSQL | `COPY FROM STDIN` supported; `aws_s3.table_import_from_s3` available for S3-based imports |
