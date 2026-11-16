---
title: "PostgreSQL 17 key features and upgrade considerations"
impact: high
tags: [postgresql-17, upgrade, new-features, breaking-changes, migration]
applies_to: [postgresql-17, aurora-postgresql]
---

# PostgreSQL 17 key features and upgrade considerations

## New Features in PostgreSQL 17

### 1. Incremental Backup (`pg_basebackup --incremental`)

```bash
# PostgreSQL 17 adds native incremental backup support
# Take an initial full backup:
pg_basebackup --pgdata=/backup/full --wal-method=stream --checkpoint=fast

# Take an incremental backup (only changed blocks since last backup):
pg_basebackup --pgdata=/backup/incr1 \
              --incremental=/backup/full/backup_manifest \
              --wal-method=stream

# Combine incremental backups for restore:
pg_combinebackup /backup/full /backup/incr1 --output=/backup/combined
```

### 2. MERGE Statement Improvements (`RETURNING` clause)

```sql
-- PostgreSQL 15 added MERGE; PostgreSQL 17 adds RETURNING clause
-- Useful for auditing what MERGE did (inserted vs updated vs deleted)

MERGE INTO products AS target
USING (VALUES
  (1, 'Widget A', 19.99),
  (2, 'Widget B', 24.99),
  (999, 'New Widget', 14.99)
) AS source (id, name, price)
ON target.id = source.id
WHEN MATCHED THEN
  UPDATE SET name = source.name, price = source.price, updated_at = NOW()
WHEN NOT MATCHED THEN
  INSERT (category_id, name, sku, price, status)
  VALUES (1, source.name, 'SKU-' || source.id, source.price, 'active')
RETURNING merge_action(), target.id, target.name, target.price;
-- Returns: action ('INSERT' or 'UPDATE'), affected row values
-- merge_action() returns 'INSERT', 'UPDATE', or 'DELETE'
```

### 3. COPY FROM ... ON_ERROR IGNORE

```sql
-- PostgreSQL 17: skip bad rows during COPY instead of aborting the entire load
-- Extremely useful for bulk imports of data with occasional format errors

COPY products (category_id, name, sku, price, status)
FROM '/tmp/products.csv'
WITH (FORMAT csv, HEADER true, ON_ERROR IGNORE);
-- Bad rows are skipped; a NOTICE message counts the skipped rows
-- Before PG 17: one bad row would abort the entire COPY

-- From STDIN (via psql or application):
-- \copy products (category_id, name, sku, price) FROM 'file.csv' CSV HEADER ON_ERROR IGNORE
```

### 4. JSON_TABLE() SQL/JSON Function

```sql
-- PostgreSQL 17 adds JSON_TABLE() for converting JSON arrays to rows
-- Useful for importing JSON data into relational tables

-- Example: extract order items from a JSON array in products.attributes
SELECT jt.*
FROM   products p,
JSON_TABLE(
  p.attributes,
  '$.variants[*]'
  COLUMNS (
    variant_id   INT          PATH '$.id',
    color        TEXT         PATH '$.color',
    size         TEXT         PATH '$.size',
    extra_price  NUMERIC(8,2) PATH '$.extra_price' DEFAULT '0' ON EMPTY
  )
) AS jt
WHERE p.id = 42;
```

### 5. VACUUM Performance Improvements

```sql
-- PostgreSQL 17 VACUUM is significantly more aggressive about dead tuple cleanup
-- Key improvement: VACUUM can skip index scans when it knows a page is clean
-- Result: VACUUM runs faster, keeping tables cleaner with less resource usage

-- New: VACUUM can detect and skip pages where all tuples are already frozen
-- (reduces VACUUM FREEZE duration on large tables dramatically)

-- Monitor vacuum efficiency (new pg_stat_io columns in PG 16+):
SELECT
  backend_type,
  object,
  context,
  reads,
  writes,
  extends,
  hits
FROM pg_stat_io
WHERE backend_type = 'autovacuum worker'
ORDER BY reads DESC;
```

### 6. EXPLAIN (SERIALIZE) for Serialization Overhead

```sql
-- PostgreSQL 17 adds EXPLAIN (SERIALIZE) to measure result serialization time
-- Serialization = converting query result rows to the network wire format
-- For queries returning millions of rows, serialization can dominate execution time

EXPLAIN (ANALYZE, SERIALIZE TEXT)
SELECT id, user_id, total_amount, status, created_at
FROM   orders
WHERE  status = 'paid';
-- Output includes: "Serialization: format: text, options: ..., time: 234.56 ms"

-- Use SERIALIZE BINARY for binary protocol:
EXPLAIN (ANALYZE, SERIALIZE BINARY)
SELECT * FROM orders LIMIT 1000;
```

### 7. reserved_connections Parameter

```sql
-- PostgreSQL 17 formalizes reserved_connections for non-superuser roles
-- superuser_reserved_connections: connections reserved for superusers (default: 3)
-- reserved_connections: connections reserved for specific roles (default: 0)

-- Set reserved slots for monitoring users (PostgreSQL 16+):
SHOW reserved_connections;           -- check current setting
SHOW superuser_reserved_connections; -- check superuser reservation

-- In postgresql.conf:
-- max_connections = 200
-- superuser_reserved_connections = 3   -- for superusers (total: 200-3=197 for everyone)
-- reserved_connections = 5             -- for pg_use_reserved_connections role
-- Net user connections: 200-3-5 = 192

-- Grant reserved connection privilege to monitoring user:
GRANT pg_use_reserved_connections TO monitoring_user;
-- monitoring_user can now connect even when 192 regular connections are full
```

## Breaking Changes / Behavior Changes (PG 15 → 16 → 17)

```sql
-- PG 15 breaking changes:
-- 1. Non-superuser CREATE privilege on public schema removed by default
--    → GRANT CREATE ON SCHEMA public TO app_user (must be explicit now)
-- 2. regexp_replace() and related functions: behavior change for empty patterns
-- 3. pg_dump excludes publication tables by default (use --publication option)

-- PG 16 breaking changes:
-- 1. Logical replication: walsender now uses replication slot for new subscriptions
-- 2. pg_dump uses pg_read_server_files for COPY ... TO — permission change
-- 3. Parallel hash join improvements may change query plans

-- PG 17 breaking changes:
-- 1. COPY FROM with ON_ERROR changes error handling semantics
-- 2. JSON_TABLE() added — may shadow application-defined functions named json_table
-- 3. pg_dump --format=d directory format changes
-- 4. Transaction ID freeze limit changes (more aggressive freezing by default)
-- 5. Some changes to pg_stat_io columns
```

## Pre-Upgrade Checklist (to PostgreSQL 17)

```sql
-- Step 1: Run pg_upgrade check in dry-run mode
-- pg_upgrade -b /old/bin -B /new/bin -d /old/data -D /new/data --check
-- This checks compatibility without modifying data

-- Step 2: Check for deprecated functions and syntax
-- pg_upgrade will list issues in the check output

-- Step 3: Check extension compatibility
SELECT name, installed_version, default_version
FROM   pg_available_extensions
WHERE  installed_version IS NOT NULL
ORDER  BY name;
-- Verify all installed extensions have PG 17 versions available

-- Step 4: Check for non-standard column default expressions (some changed in PG 17)
SELECT table_name, column_name, column_default
FROM   information_schema.columns
WHERE  column_default IS NOT NULL
  AND  table_schema = 'public'
ORDER  BY table_name, column_name;

-- Step 5: Test application with PG 17 in staging before production upgrade
-- Run pg_upgrade --check on a staging clone first
```

## Aurora/RDS Notes

- **Aurora PostgreSQL**: Aurora typically supports a new major PostgreSQL version 3–6 months after community release. Check the AWS documentation for Aurora PostgreSQL 17.x availability.
- **RDS PostgreSQL 17**: Available on RDS. Use `aws rds describe-db-engine-versions --engine postgres --major-engine-version 17` to check availability in your region.
- **Blue/Green deployment**: Use RDS Blue/Green Deployments for zero-downtime major version upgrades. AWS creates a staging environment with the new version, replicates changes, and switches over with minimal downtime.

## Version Notes

| Version | Notes |
|---------|-------|
| PostgreSQL 17.0 | Released September 2024 |
| Aurora PostgreSQL 17 | Check AWS documentation for availability date |
| RDS PostgreSQL 17 | Available; check AWS regional availability |
