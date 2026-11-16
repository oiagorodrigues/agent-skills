---
title: "Use declarative partitioning for large time-series and categorical tables"
impact: medium
tags: [partitioning, range-partition, list-partition, partition-pruning, performance]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Use declarative partitioning for large time-series and categorical tables

## Problem

A single table accumulating years of time-series data (orders, events, logs) grows to hundreds of millions of rows. Queries for a specific time window scan far more data than necessary. Declarative partitioning (PostgreSQL 10+) splits the table into child tables by range, list, or hash — the planner prunes irrelevant partitions, dramatically reducing rows examined. Bulk data expiration becomes an instant `DETACH PARTITION` instead of a slow batch DELETE.

## Bad Example

```sql
-- BAD: All events in a single table — 5 years × 10M events/month = 600M rows
CREATE TABLE events (
  id          BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id     BIGINT      NOT NULL,
  event_type  TEXT        NOT NULL,
  payload     JSONB       DEFAULT '{}',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Query for last month's events must scan (or index-scan) all 600M rows
-- even though only ~10M are relevant
SELECT COUNT(*) FROM events
WHERE created_at >= '2024-11-01' AND created_at < '2024-12-01';

-- Deleting old events is a slow batch DELETE with lock implications:
DELETE FROM events WHERE created_at < '2022-01-01';
-- 240M rows deleted — takes hours, holds locks, bloats dead tuple count
```

## Good Example

```sql
-- GOOD: Declarative range partitioning by month
CREATE TABLE events (
  id          BIGINT      NOT NULL,
  user_id     BIGINT      NOT NULL,
  event_type  TEXT        NOT NULL,
  payload     JSONB       DEFAULT '{}',
  created_at  TIMESTAMPTZ NOT NULL
) PARTITION BY RANGE (created_at);

-- Create monthly partitions:
CREATE TABLE events_2024_11
  PARTITION OF events
  FOR VALUES FROM ('2024-11-01') TO ('2024-12-01');

CREATE TABLE events_2024_12
  PARTITION OF events
  FOR VALUES FROM ('2024-12-01') TO ('2025-01-01');

CREATE TABLE events_2025_01
  PARTITION OF events
  FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');

-- Default partition for rows that don't match any defined range:
CREATE TABLE events_default
  PARTITION OF events DEFAULT;

-- Add indexes to each partition (or to the parent — propagates to children in PG 11+):
CREATE INDEX ON events (user_id, created_at);
CREATE INDEX ON events USING gin (payload);

-- Now the same query only scans the November 2024 partition (~10M rows, not 600M):
SELECT COUNT(*) FROM events
WHERE created_at >= '2024-11-01' AND created_at < '2024-12-01';
-- EXPLAIN shows: Seq Scan on events_2024_11 (not the parent table)

-- Expire old data instantly — no DELETE, no locks on live partitions:
ALTER TABLE events DETACH PARTITION events_2022_01;
DROP TABLE events_2022_01;   -- instant — no row-by-row delete
```

```sql
-- List partitioning for categorical data:
CREATE TABLE orders_by_region (
  id         BIGINT      NOT NULL,
  region     TEXT        NOT NULL,
  user_id    BIGINT      NOT NULL,
  total_amount NUMERIC(12,2) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
) PARTITION BY LIST (region);

CREATE TABLE orders_us   PARTITION OF orders_by_region FOR VALUES IN ('US');
CREATE TABLE orders_eu   PARTITION OF orders_by_region FOR VALUES IN ('EU', 'UK');
CREATE TABLE orders_apac PARTITION OF orders_by_region FOR VALUES IN ('APAC');
CREATE TABLE orders_rest PARTITION OF orders_by_region DEFAULT;
```

```sql
-- Hash partitioning for even distribution:
CREATE TABLE sessions (
  id         BIGINT      NOT NULL,
  user_id    BIGINT      NOT NULL,
  session_data JSONB     DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL
) PARTITION BY HASH (user_id);

CREATE TABLE sessions_0 PARTITION OF sessions FOR VALUES WITH (MODULUS 4, REMAINDER 0);
CREATE TABLE sessions_1 PARTITION OF sessions FOR VALUES WITH (MODULUS 4, REMAINDER 1);
CREATE TABLE sessions_2 PARTITION OF sessions FOR VALUES WITH (MODULUS 4, REMAINDER 2);
CREATE TABLE sessions_3 PARTITION OF sessions FOR VALUES WITH (MODULUS 4, REMAINDER 3);
```

```sql
-- Automated partition management with pg_partman extension:
-- CREATE EXTENSION pg_partman;
-- SELECT partman.create_parent(
--   p_parent_table  => 'public.events',
--   p_control       => 'created_at',
--   p_type          => 'native',
--   p_interval      => 'monthly',
--   p_premake       => 3    -- pre-create 3 future partitions
-- );
-- pg_partman automatically creates future partitions and can drop/detach old ones
```

## Why It Matters

- **Partition pruning**: The query planner eliminates entire partitions from the scan when the WHERE clause matches the partition key. A 600M-row table with monthly partitions means a "last month" query scans 10M rows, not 600M.
- **Instant data expiration**: `DETACH PARTITION` + `DROP TABLE` drops an entire month of data in milliseconds with no lock on the parent table. Equivalent batch DELETE takes hours and creates massive dead-tuple bloat.
- **Parallel partition scans**: PostgreSQL can scan multiple partitions in parallel (`enable_parallel_append = on`), further improving performance for queries spanning multiple partitions.
- **Partition gotchas**: Unique constraints must include the partition key (unless using PG 11+ with global unique constraints). Foreign keys to partitioned tables are supported from PG 12+. Every partition must have its own indexes.

## Aurora/RDS Notes

- **Aurora PostgreSQL**: Declarative partitioning is supported on Aurora. Aurora's distributed storage means partition data is stored across the Aurora storage layer — partition pruning still eliminates storage reads for pruned partitions.
- **RDS PostgreSQL**: `pg_partman` is available on RDS PostgreSQL. Install with `CREATE EXTENSION pg_partman`. The `pg_partman` background worker needs to be enabled in `shared_preload_libraries`.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | Declarative partitioning fully supported; `ATTACH PARTITION ... CONCURRENTLY` not available |
| PostgreSQL 15 | Row-level security for partitioned tables improved |
| PostgreSQL 16 | Partition pruning improvements for complex queries |
| PostgreSQL 17 | `COPY` improvements for partitioned tables; `ATTACH PARTITION` lock improvements |
| Aurora PostgreSQL | Partitioning supported on all Aurora versions matching community PG |
