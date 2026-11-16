---
title: "Batch bulk DELETE and UPDATE to limit lock duration and WAL volume"
impact: high
tags: [bulk-delete, bulk-update, truncate, copy, performance, locks]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Batch bulk DELETE and UPDATE to limit lock duration and WAL volume

## Problem

A large `DELETE FROM table WHERE created_at < $1` in a single statement holds exclusive row locks on all matching rows for the entire duration. On a 100M-row table this can take minutes, generate massive WAL, create huge bloat from dead tuples, block concurrent transactions, and amplify replication lag. Batching bulk operations into smaller chunks limits lock scope and allows autovacuum to reclaim dead tuples between batches.

## Bad Example

```sql
-- BAD: Delete all old order_items in one statement
-- On a 100M-row table with 20M matching rows: may run for 10-30 minutes
-- Holds exclusive row locks on all 20M rows for the entire duration
-- Generates 20M dead tuples instantly — massive bloat

DELETE FROM order_items
WHERE created_at < NOW() - INTERVAL '2 years';
-- All concurrent INSERTs/UPDATEs to those rows are blocked
-- Autovacuum cannot reclaim dead tuples until the DELETE completes
-- WAL size: potentially tens of GB for one statement

-- BAD: Similarly large UPDATE
UPDATE products
SET    status = 'discontinued'
WHERE  updated_at < '2022-01-01'
  AND  status = 'active';
-- Locks hundreds of thousands of rows for many minutes
```

## Good Example

```sql
-- GOOD 1: Batched DELETE — delete 1,000 rows at a time
-- Loop from application until 0 rows deleted

-- Each iteration:
DELETE FROM order_items
WHERE id IN (
  SELECT id
  FROM   order_items
  WHERE  created_at < NOW() - INTERVAL '2 years'
  ORDER  BY id           -- consistent ordering helps avoid lock conflicts
  LIMIT  1000
);
-- Repeat until DELETE COUNT = 0
-- Sleep 50-100ms between iterations to allow other transactions to proceed

-- GOOD 2: Batched DELETE with keyset bookmark (avoids re-scanning from the start)
-- First batch: delete rows with id < 1000 and old created_at
DELETE FROM order_items
WHERE id < $1   -- $1 = max id from previous scan, start at 0
  AND created_at < NOW() - INTERVAL '2 years'
LIMIT 1000
RETURNING MAX(id) AS last_deleted_id;
-- Use the returned max id as $1 for the next batch
```

```python
# GOOD 3: Python batched DELETE loop
import psycopg2
import time

def delete_old_order_items(conn, cutoff_days=730, batch_size=1000, sleep_ms=100):
    """Delete old order_items in small batches to limit lock scope."""
    total_deleted = 0
    conn.autocommit = False

    while True:
        cur = conn.cursor()
        cur.execute("""
            DELETE FROM order_items
            WHERE id IN (
              SELECT id FROM order_items
              WHERE created_at < NOW() - INTERVAL '%s days'
              ORDER BY id
              LIMIT %s
            )
        """, (cutoff_days, batch_size))
        deleted = cur.rowcount
        conn.commit()
        total_deleted += deleted

        if deleted == 0:
            break   # no more rows to delete

        time.sleep(sleep_ms / 1000.0)  # allow autovacuum and other transactions

    print(f"Total deleted: {total_deleted} rows")
    return total_deleted
```

```sql
-- GOOD 4: TRUNCATE for full table wipe (faster than DELETE, non-MVCC)
-- TRUNCATE is dramatically faster than DELETE for removing all rows
-- WARNING: TRUNCATE acquires ACCESS EXCLUSIVE lock (blocks all reads and writes)
-- WARNING: TRUNCATE is NOT MVCC-safe — concurrent transactions see empty table immediately
-- Use only when you know no concurrent transactions are reading the table

TRUNCATE TABLE events RESTART IDENTITY;   -- also resets sequences

-- Partition-based expiry is even better (instant, no lock on live partitions):
ALTER TABLE events DETACH PARTITION events_2022;
DROP TABLE events_2022;   -- instant data removal
-- See: schema-partitioning.md
```

```sql
-- GOOD 5: COPY for data export/import
-- Export a subset of data:
COPY (
  SELECT id, user_id, total_amount, created_at
  FROM orders
  WHERE status = 'paid' AND created_at >= '2024-01-01'
) TO '/tmp/paid_orders_2024.csv' WITH (FORMAT csv, HEADER true);

-- Import from CSV (client-side via psql \copy):
-- \copy products (category_id, name, sku, price, status) FROM 'products.csv' CSV HEADER

-- GOOD 6: Temporary tables for staging large changes
-- Load changes into a temp table, then merge in one transaction
CREATE TEMP TABLE products_to_update AS
SELECT id, 'discontinued' AS new_status
FROM products
WHERE updated_at < '2022-01-01' AND status = 'active';

CREATE INDEX ON products_to_update (id);

-- Apply in batches from temp table:
UPDATE products p
SET    status = u.new_status,
       updated_at = NOW()
FROM   (
  SELECT id, new_status FROM products_to_update
  LIMIT 1000
) u
WHERE  p.id = u.id;
-- Repeat, deleting processed rows from temp table between batches
```

## Why It Matters

- **Lock scope**: A single 20M-row DELETE holds exclusive locks on all 20M rows for minutes. Batching limits locks to 1,000 rows at a time — other transactions can proceed between batches.
- **WAL volume**: Bulk DELETE generates one WAL record per deleted row. 20M rows = potentially 5–20 GB of WAL in one transaction. Batching reduces peak WAL volume and allows WAL archiving to keep up.
- **Dead tuple management**: After each batch DELETE, autovacuum can reclaim the dead tuples before the next batch. A single large DELETE generates all dead tuples at once, requiring a full table vacuum before storage is reclaimed.
- **Aurora replication lag**: Large bulk operations amplify replication lag to Aurora reader replicas. Batching spreads the WAL writes over time, keeping reader lag low.
- **TRUNCATE caveats**: `TRUNCATE` requires `ACCESS EXCLUSIVE` lock (blocks all reads and writes). It is also not safe to use if concurrent transactions (even REPEATABLE READ) are reading the table — they will see an empty table mid-transaction.

## Aurora/RDS Notes

- **Aurora PostgreSQL**: Large bulk operations replicate to Aurora readers and can cause significant replication lag (`aurora_replica_lag` CloudWatch metric). Batching keeps replication lag under 100 ms even during large deletes.
- **RDS PostgreSQL**: Same as community PostgreSQL. Use maintenance windows for truly large bulk operations. Monitor `pg_stat_user_tables.n_dead_tup` after large deletes to verify autovacuum is reclaiming dead tuples.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | Batched DELETE and TRUNCATE behavior unchanged |
| PostgreSQL 15 | `MERGE` added — can be used for conditional bulk updates |
| PostgreSQL 16 | Same |
| PostgreSQL 17 | Improved VACUUM performance reduces bloat recovery time after bulk deletes |
| Aurora PostgreSQL | Batching strongly recommended to manage replication lag |
