---
title: "Use logical replication for zero-downtime upgrades, CDC, and cross-region sync"
impact: medium
tags: [logical-replication, publication, subscription, cdc, upgrade, wal-level]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Use logical replication for zero-downtime upgrades, CDC, and cross-region sync

## Problem

Physical (streaming) replication creates an exact binary copy of the primary — same PostgreSQL major version required, same OS architecture. Logical replication replicates changes at the row level using a publication/subscription model — allowing replication between different PostgreSQL major versions, different schemas, and different databases. The primary use cases are: zero-downtime major version upgrades, Change Data Capture (CDC), and selective table replication.

## Bad Example

```sql
-- BAD: Attempting to use physical replication for a major version upgrade
-- Physical replica must be the same major version as the primary
-- To upgrade from PG 14 to PG 17 with minimal downtime using physical replication:
-- 1. Stop application (no writes)
-- 2. pg_upgrade on the replica
-- 3. Promote replica
-- 4. Total downtime: 15-60+ minutes depending on catalog size

-- BAD: No monitoring of replication slot lag
-- A stalled replication slot can fill the disk with unreleased WAL:
SELECT slot_name, active, pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) AS lag_bytes
FROM pg_replication_slots;
-- If lag_bytes > 1 GB for an unused slot — disk fill risk!
```

## Good Example

### Setup: Publication and Subscription

```sql
-- On the SOURCE (publisher) — PostgreSQL 14:
-- Step 1: Ensure wal_level = logical
SHOW wal_level;   -- must be 'logical'
-- On RDS: set rds.logical_replication = 1 in parameter group and reboot

-- Step 2: Create a publication for the tables to replicate
CREATE PUBLICATION ecommerce_pub
  FOR TABLE users, products, categories, orders, order_items, reviews;
-- Or publish all tables:
-- CREATE PUBLICATION ecommerce_all FOR ALL TABLES;

-- Check publication status:
SELECT pubname, puballtables, pubinsert, pubupdate, pubdelete
FROM   pg_publication
WHERE  pubname = 'ecommerce_pub';

-- Step 3: Create a replication user with minimal privileges
CREATE USER replication_user WITH PASSWORD 'password123' REPLICATION;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO replication_user;
-- Or grant rds_replication on RDS:
-- GRANT rds_replication TO replication_user;
```

```sql
-- On the TARGET (subscriber) — PostgreSQL 17:
-- The target schema must already exist (logical replication replicates data, not DDL)
-- Copy the schema first: pg_dump --schema-only from source

-- Step 4: Create the subscription
CREATE SUBSCRIPTION ecommerce_sub
  CONNECTION 'host=source-db.xxxx.us-east-1.rds.amazonaws.com
              port=5432 dbname=ecommerce
              user=replication_user password=password123
              sslmode=require'
  PUBLICATION ecommerce_pub;
-- PostgreSQL starts copying initial data (COPY from source)
-- After initial sync, switches to streaming WAL changes

-- Monitor subscription status:
SELECT
  subname,
  pid,
  received_lsn,
  latest_end_lsn,
  pg_wal_lsn_diff(latest_end_lsn, received_lsn) AS lag_bytes
FROM   pg_stat_subscription;

-- Check initial table sync status (during initial copy):
SELECT subname, relid::regclass AS table_name, srsubstate AS state
FROM   pg_subscription_rel
ORDER  BY table_name;
-- srsubstate: 'i' = initializing, 'd' = data copy, 'f' = finished
```

```sql
-- Row filtering (PostgreSQL 15+ publisher-side):
-- Only replicate paid orders (filter on publisher):
CREATE PUBLICATION paid_orders_pub
  FOR TABLE orders
  WHERE (status = 'paid');
-- Subscriber only receives INSERT/UPDATE/DELETE events for paid orders
```

```sql
-- Zero-downtime major version upgrade procedure:
-- 1. Set up logical replication from PG 14 (source) to PG 17 (target)
-- 2. Wait for initial sync to complete (srsubstate = 'f' for all tables)
-- 3. Wait for replication lag to reach near-zero
-- 4. Short maintenance window:
--    a. Stop application writes (disable write endpoint)
--    b. Wait for subscriber lag = 0 (pg_wal_lsn_diff returns 0)
--    c. Verify row counts match on both source and target
--    d. Switch application to PG 17 endpoint
-- 5. Disable subscription on PG 17:
--    ALTER SUBSCRIPTION ecommerce_sub DISABLE;
-- 6. Total downtime: typically < 60 seconds (just the cutover, not the sync)
```

```sql
-- Cleanup: remove replication slot on source if subscription is dropped
-- Stalled slots hold WAL indefinitely!

-- List slots:
SELECT slot_name, active, restart_lsn,
       pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) AS retained_bytes
FROM   pg_replication_slots;

-- Drop a stalled slot:
SELECT pg_drop_replication_slot('ecommerce_sub');
-- Only do this if you are certain the subscriber will never reconnect
```

### Logical Replication Limitations

```
Logical replication DOES NOT replicate:
  - DDL changes (CREATE TABLE, ALTER TABLE, DROP TABLE)
  - Sequences (sequence values are NOT replicated — gaps on subscriber)
  - Large objects (pg_largeobject)
  - TRUNCATE (not replicated in PG 14; replicated as DML in PG 15+)
  - Views, materialized views

Logical replication requires:
  - wal_level = logical on the publisher
  - Primary keys or REPLICA IDENTITY on all replicated tables (for UPDATE/DELETE)
  - Tables on subscriber must exist before subscribing

Row filtering (PG 15+):
  - Filter on publisher side (reduces WAL volume)
  - WHERE clause in CREATE PUBLICATION ... FOR TABLE t WHERE (...)
```

```sql
-- Check that replicated tables have primary keys or REPLICA IDENTITY:
SELECT
  c.relname,
  c.relreplident  -- 'd' = default (PK), 'n' = nothing, 'f' = full, 'i' = index
FROM   pg_class c
JOIN   pg_namespace n ON n.oid = c.relnamespace
WHERE  n.nspname = 'public'
  AND  c.relkind = 'r'
  AND  c.relreplident IN ('n', 'f');   -- 'n' means no PK — UPDATE/DELETE won't replicate

-- Fix: add primary key or set REPLICA IDENTITY FULL (less efficient)
-- ALTER TABLE table_name REPLICA IDENTITY FULL;
-- Or: add a primary key
```

## Why It Matters

- **Zero-downtime upgrades**: Physical replication cannot cross major versions. Logical replication can replicate from PG 14 to PG 17 — allowing a live cutover with < 60 seconds of downtime instead of hours of pg_upgrade.
- **CDC (Change Data Capture)**: Logical replication exposes row-level changes as events. Tools like Debezium, Kafka Connect PostgreSQL, and AWS DMS use logical replication slots to stream changes to Kafka, S3, or data warehouses.
- **Selective replication**: Replicate only specific tables or rows to a second database (for analytics, reporting, or a different application). Physical replication copies everything.
- **Replication slot danger**: A logical replication slot retains all WAL since the last consumed LSN. If a subscriber disconnects permanently, WAL accumulates indefinitely. Monitor `retained_bytes` in `pg_replication_slots` and alert at > 1 GB.

## Aurora/RDS Notes

- **Aurora PostgreSQL**: Logical replication is available. Set `rds.logical_replication = 1` in the parameter group (requires restart). Aurora uses logical replication for Blue/Green Deployments and Aurora Global Database.
- **RDS PostgreSQL**: Same — `rds.logical_replication = 1`. The `rds_replication` role is required for the replication user.
- **AWS DMS**: AWS Database Migration Service uses logical replication under the hood for PostgreSQL CDC. For cross-database migration, DMS can replicate from self-managed PostgreSQL to RDS.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | Logical replication fully available; `pg_stat_subscription` for monitoring |
| PostgreSQL 15 | Row filtering on publisher (`FOR TABLE t WHERE ...`); TRUNCATE replication |
| PostgreSQL 16 | Logical replication from standby (subscriber can be a physical replica) |
| PostgreSQL 17 | Improved logical replication parallelism; `pg_stat_replication_slots` view |
| Aurora PostgreSQL | `rds.logical_replication = 1` required; used internally for Blue/Green and Global DB |
