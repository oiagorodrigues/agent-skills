---
title: "Use online DDL patterns to avoid table locks in production"
impact: high
tags: [ddl, online-ddl, lock, create-index-concurrently, not-valid, pg-repack]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Use online DDL patterns to avoid table locks in production

## Problem

Many `ALTER TABLE` operations in PostgreSQL acquire an `ACCESS EXCLUSIVE` lock — the strongest lock level, blocking all reads and writes. On a large production table, `ADD COLUMN NOT NULL DEFAULT 'x'` rewrites the entire table in PostgreSQL < 11. `CREATE INDEX` locks the table for the duration. Understanding which DDL operations are lock-safe and which require special handling prevents accidental production outages.

## Bad Example

```sql
-- BAD 1: Adding NOT NULL column with DEFAULT in PostgreSQL < 11 rewrites the table
-- This holds ACCESS EXCLUSIVE lock for the entire table rewrite duration
ALTER TABLE orders ADD COLUMN payment_method TEXT NOT NULL DEFAULT 'credit_card';
-- On a 100M-row orders table: may take 5-30 minutes, all queries blocked during that time

-- BAD 2: CREATE INDEX (non-concurrent) locks the table for index build duration
CREATE INDEX idx_orders_new ON orders (user_id, created_at, status);
-- Blocks all writes to orders until the index is built (minutes on large tables)

-- BAD 3: Adding a CHECK constraint without NOT VALID — scans entire table
ALTER TABLE orders ADD CONSTRAINT chk_positive_amount CHECK (total_amount >= 0);
-- Acquires ACCESS EXCLUSIVE lock AND scans all rows to validate existing data
```

## Good Example

```sql
-- GOOD 1: Add nullable column (instant, no table rewrite)
-- In PostgreSQL 11+, adding a NOT NULL column WITH DEFAULT is also instant
-- (the default is stored in pg_attrdef, not written to every row)

-- PostgreSQL 11+ (instant — default stored in catalog, not written to rows):
ALTER TABLE orders ADD COLUMN payment_method TEXT NOT NULL DEFAULT 'credit_card';
-- This is instant in PG 11+ regardless of table size!

-- For PostgreSQL 10 and earlier (if applicable), use the safe pattern:
-- Step 1: Add nullable column (instant on all versions)
ALTER TABLE orders ADD COLUMN payment_method TEXT;
-- Step 2: Backfill in batches (no lock held between batches)
UPDATE orders SET payment_method = 'credit_card'
WHERE  id BETWEEN 1 AND 100000 AND payment_method IS NULL;
-- ... repeat for all rows in batches of 100k
-- Step 3: Add NOT NULL constraint with NOT VALID (instant — doesn't scan old rows)
ALTER TABLE orders
  ADD CONSTRAINT chk_payment_method_not_null
  CHECK (payment_method IS NOT NULL) NOT VALID;
-- Step 4: Validate the constraint (scans rows but only needs SHARE UPDATE EXCLUSIVE lock)
ALTER TABLE orders VALIDATE CONSTRAINT chk_payment_method_not_null;
```

```sql
-- GOOD 2: CREATE INDEX CONCURRENTLY — does not lock the table
-- Takes longer to build (2-3× slower) but allows concurrent reads and writes
CREATE INDEX CONCURRENTLY idx_orders_new ON orders (user_id, created_at, status);
-- If it fails, a INVALID index may remain — drop it first:
-- DROP INDEX CONCURRENTLY idx_orders_new;

-- GOOD 3: DROP INDEX CONCURRENTLY — does not block queries using the index
DROP INDEX CONCURRENTLY idx_orders_old;

-- GOOD 4: REINDEX CONCURRENTLY (PostgreSQL 12+) — rebuilds an index without locking
REINDEX INDEX CONCURRENTLY idx_orders_user_id;
-- Use this to fix index bloat (see monitor-bloat.md) without downtime
```

```sql
-- GOOD 5: Add FOREIGN KEY with NOT VALID then validate (zero downtime)
-- NOT VALID adds the FK constraint without scanning existing rows
ALTER TABLE order_items
  ADD CONSTRAINT fk_order_items_order
  FOREIGN KEY (order_id) REFERENCES orders (id)
  NOT VALID;
-- The constraint is now enforced for NEW rows but old rows are not checked

-- VALIDATE asynchronously (SHARE UPDATE EXCLUSIVE lock — allows reads and writes)
ALTER TABLE order_items VALIDATE CONSTRAINT fk_order_items_order;
-- This scans existing rows but does not block concurrent reads or writes
```

```sql
-- GOOD 6: pg_repack for online table reorganization (requires pg_repack extension)
-- Use to reclaim bloated table/index space without ACCESS EXCLUSIVE lock
-- First: CREATE EXTENSION pg_repack;
-- Then: pg_repack -h localhost -U app_user -d ecommerce -t orders
-- pg_repack creates a new copy of the table, swaps it in, with only a brief lock at swap time
```

### PostgreSQL Lock Levels for DDL

| DDL Operation | Lock Required | Notes |
|---------------|--------------|-------|
| `ADD COLUMN NULL` | ACCESS EXCLUSIVE | Instant — no table scan |
| `ADD COLUMN NOT NULL DEFAULT` (PG 11+) | ACCESS EXCLUSIVE | Instant — default in catalog |
| `ADD COLUMN NOT NULL DEFAULT` (PG <11) | ACCESS EXCLUSIVE | Table rewrite — minutes on large tables |
| `CREATE INDEX` | SHARE | Blocks writes during index build |
| `CREATE INDEX CONCURRENTLY` | ShareUpdateExclusiveLock | Does not block reads or writes |
| `ADD CONSTRAINT CHECK NOT VALID` | ACCESS EXCLUSIVE | Instant — does not scan rows |
| `VALIDATE CONSTRAINT` | SHARE UPDATE EXCLUSIVE | Scans rows but allows concurrent writes |
| `DROP COLUMN` | ACCESS EXCLUSIVE | Instant — column marked as dropped |
| `RENAME TABLE` | ACCESS EXCLUSIVE | Instant |
| `ALTER COLUMN TYPE` | ACCESS EXCLUSIVE | Table rewrite (unless same underlying type) |

## Why It Matters

- **ACCESS EXCLUSIVE blocks everything**: An `ACCESS EXCLUSIVE` lock prevents all reads and writes. On a busy production table, even a 5-second DDL operation can queue hundreds of waiting queries.
- **PG 11 not-null default optimization**: The most impactful improvement — in PG 11+, `ADD COLUMN col TYPE NOT NULL DEFAULT val` stores the default in the catalog and does not rewrite the table. This is instant regardless of table size.
- **`NOT VALID` pattern**: Adding a constraint with `NOT VALID` validates only new rows (requires only a brief `ACCESS EXCLUSIVE` lock). `VALIDATE CONSTRAINT` validates existing rows but only requires `SHARE UPDATE EXCLUSIVE` — allowing concurrent inserts and updates.
- **`CREATE INDEX CONCURRENTLY` caveats**: Concurrent index creation cannot run inside a transaction block. It may leave an invalid index if it fails — check `pg_indexes` for `indisvalid = false` and drop/recreate.

## Aurora/RDS Notes

- **Aurora PostgreSQL**: DDL lock behavior is identical to community PostgreSQL. `CREATE INDEX CONCURRENTLY` is supported. Aurora's shared storage means table rewrites write to the distributed storage layer.
- **RDS PostgreSQL**: Use maintenance windows for any DDL that requires `ACCESS EXCLUSIVE` on large tables. For critical online DDL, use `CREATE INDEX CONCURRENTLY` and the `NOT VALID` + `VALIDATE CONSTRAINT` pattern.
- **`pg_repack` on RDS**: Available via `CREATE EXTENSION pg_repack` on RDS PostgreSQL 13+. Not available on Aurora PostgreSQL (Aurora handles storage differently).

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | `REINDEX CONCURRENTLY` available (since PG 12) |
| PostgreSQL 15 | Same |
| PostgreSQL 16 | Reduced lock contention for some ALTER TABLE operations |
| PostgreSQL 17 | Same |
| Aurora PostgreSQL | Same DDL lock levels as community PG; `pg_repack` not available |
