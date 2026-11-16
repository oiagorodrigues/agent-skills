---
title: "Monitor streaming replication lag and read-replica safety"
impact: high
tags: [replication, lag, monitoring, aurora, read-replica, pg-stat-replication]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Monitor streaming replication lag and read-replica safety

## Problem

Replication lag is the delay between a write on the primary and its visibility on a replica. Reading from a replica with high lag returns stale data. For time-sensitive reads (inventory levels, account balances, order status), reading from a lagging replica can cause application bugs. Monitoring lag in both bytes (WAL position difference) and time (seconds since last transaction replay) is essential for safe read replica usage.

## Bad Example

```sql
-- BAD: Reading time-sensitive data from a replica without checking lag
-- Application configured with replica for all reads
-- A bulk import job causes 30 seconds of replication lag
-- Users checking their order status see stale data or missing orders

-- Connection: read replica endpoint
SELECT id, status, total_amount FROM orders WHERE user_id = $1 ORDER BY created_at DESC LIMIT 10;
-- Might return orders from 30 seconds ago — user just placed an order, doesn't see it

-- BAD: No replication monitoring — lag detected only when users complain
```

## Good Example

```sql
-- GOOD 1: Monitor replication from the PRIMARY

-- pg_stat_replication shows connected replicas and their lag
SELECT
  client_addr,
  usename,
  application_name,
  state,
  sent_lsn,
  write_lsn,
  flush_lsn,
  replay_lsn,
  -- Lag in bytes (difference between primary LSN and replica's replay position):
  pg_wal_lsn_diff(sent_lsn,   replay_lsn) AS sent_minus_replay_bytes,
  -- Lag as time:
  write_lag,
  flush_lag,
  replay_lag
FROM   pg_stat_replication
ORDER  BY replay_lag DESC NULLS LAST;

-- Alert if replay_lag > '5 seconds'::interval or sent_minus_replay_bytes > 50MB
```

```sql
-- GOOD 2: Monitor lag from the REPLICA (standby)

-- Check if this instance is a replica:
SELECT pg_is_in_recovery();   -- TRUE on replica, FALSE on primary

-- Lag in bytes (difference between last received and last replayed WAL):
SELECT
  pg_last_wal_receive_lsn()                                   AS received_lsn,
  pg_last_wal_replay_lsn()                                    AS replayed_lsn,
  pg_wal_lsn_diff(
    pg_last_wal_receive_lsn(),
    pg_last_wal_replay_lsn()
  )                                                           AS lag_bytes,
  pg_last_xact_replay_timestamp()                             AS last_replay_ts,
  EXTRACT(epoch FROM NOW() - pg_last_xact_replay_timestamp()) AS lag_seconds;

-- Alert if lag_seconds > 10 or lag_bytes > 52428800 (50 MB)
```

```sql
-- GOOD 3: Protect time-sensitive reads — check lag before reading from replica

-- Application-level lag check before using a replica:
-- (Python / psycopg2 example)
-- replica_conn = connect to replica
-- lag_result = cur.execute("SELECT EXTRACT(epoch FROM NOW() - pg_last_xact_replay_timestamp())")
-- lag_seconds = lag_result[0][0]
-- if lag_seconds > 10:
--     use primary_conn for this query
-- else:
--     use replica_conn for this query

-- Or: always use primary for writes and time-sensitive reads,
-- use replica only for analytical/reporting queries where some staleness is acceptable
```

```sql
-- GOOD 4: Streaming vs logical replication monitoring

-- Streaming replication (physical) -- check on replica:
SELECT
  pg_is_in_recovery()                                          AS is_replica,
  pg_last_wal_receive_lsn()                                    AS receive_lsn,
  pg_last_wal_replay_lsn()                                     AS replay_lsn,
  pg_last_xact_replay_timestamp()                              AS last_replay_time;

-- Logical replication -- check subscription lag on subscriber:
SELECT
  subname,
  received_lsn,
  latest_end_lsn,
  pg_wal_lsn_diff(latest_end_lsn, received_lsn) AS lag_bytes
FROM   pg_stat_subscription;

-- Check replication slots (can cause WAL accumulation if consumer falls behind):
SELECT
  slot_name,
  slot_type,
  active,
  restart_lsn,
  confirmed_flush_lsn,
  pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) AS retained_wal_bytes
FROM   pg_replication_slots
ORDER  BY retained_wal_bytes DESC;
-- ALERT: retained_wal_bytes > 1 GB means a stalled replication slot is holding WAL
-- Stalled replication slots eventually fill disk with unreleased WAL
```

## Why It Matters

- **Stale reads**: Replica lag means queries return data that was accurate N seconds ago. For financial data, this causes incorrect balances. For order data, this causes "where is my order?" support tickets.
- **Bytes vs time**: Lag in bytes (`pg_wal_lsn_diff`) measures unacknowledged WAL. Lag in seconds (`pg_last_xact_replay_timestamp`) measures how far behind the replica is in commit time. Both are needed — a replica might have caught up in bytes but be behind in time if the primary had a period of high write activity.
- **Replication slot danger**: If a logical replication subscriber disconnects, its replication slot retains all WAL since the slot was last consumed. On a high-write primary, this can fill the disk with unreleased WAL in hours. Monitor `retained_wal_bytes` and drop stalled slots.
- **`pg_is_in_recovery()`**: Returns TRUE on a replica/standby, FALSE on a primary. Use this in application code to detect if a connection is to a replica (e.g., after an accidental routing to the replica endpoint for a write).

## Aurora/RDS Notes

- **Aurora PostgreSQL**: Aurora replicas have extremely low lag — typically < 100 ms due to Aurora's shared storage architecture. The writer and readers share the same distributed storage; replicas only need to replay WAL log pointers, not full page writes.
- **Aurora CloudWatch metric**: Monitor `AuroraReplicaLag` (milliseconds) and `AuroraReplicaLagMaximum` in CloudWatch. Alert at > 500 ms for time-sensitive workloads.
- **Aurora Global Database**: Cross-region replication lag is measured by `aurora_global_db_instance_status()`. Typically 1–2 seconds for cross-region.
- **RDS PostgreSQL**: Standard streaming replication. Monitor `ReplicaLag` CloudWatch metric (seconds). Performance Insights shows replica lag alongside query metrics.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | `pg_stat_replication`, `pg_last_wal_replay_lsn()`, `pg_stat_subscription` available |
| PostgreSQL 15 | Row filtering in logical replication subscriptions (publisher-side) |
| PostgreSQL 16 | Logical replication from standby replicas; improved logical replication parallelism |
| PostgreSQL 17 | Logical replication improvements; `pg_stat_replication_slots` view |
| Aurora PostgreSQL | Shared storage reduces replica lag to < 100 ms; `AuroraReplicaLag` CloudWatch metric |
