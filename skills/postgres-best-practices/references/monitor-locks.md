---
title: "Monitor and resolve lock contention with pg_locks and pg_stat_activity"
impact: high
tags: [locks, pg-locks, blocking, deadlock, monitoring, lock-timeout]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Monitor and resolve lock contention with pg_locks and pg_stat_activity

## Problem

Lock contention occurs when one transaction waits for another to release a lock. Undetected lock waits cascade: a blocked transaction holds other locks, which block more transactions, eventually leading to a pile-up that can take the application offline. `pg_locks` joined with `pg_stat_activity` shows the complete picture: which PID is blocking, which query caused the lock, and how long the wait has been ongoing.

## Bad Example

```sql
-- BAD: No lock monitoring — lock waits accumulate silently
-- Application sees: slow queries, timeouts, connection pool exhaustion
-- DBA sees: high connection count, but no visibility into why

-- Without lock monitoring, you might miss:
-- Session A: long-running UPDATE holds a row lock for 10 minutes
-- Sessions B-Z: all waiting for that lock
-- Users: experiencing 10-minute page load timeouts
-- Developers: blame the application tier, not the database
```

## Good Example

```sql
-- GOOD 1: Find blocking and blocked queries (the most important monitoring query)
-- Uses pg_blocking_pids() function (PostgreSQL 9.6+)
SELECT
  blocked.pid                              AS blocked_pid,
  blocked.usename                          AS blocked_user,
  blocked.application_name                 AS blocked_app,
  blocked.query_start                      AS blocked_since,
  EXTRACT(epoch FROM NOW() - blocked.query_start) AS blocked_seconds,
  blocked.query                            AS blocked_query,
  blocking.pid                             AS blocking_pid,
  blocking.usename                         AS blocking_user,
  blocking.query_start                     AS blocking_since,
  blocking.query                           AS blocking_query,
  blocking.state                           AS blocking_state
FROM   pg_stat_activity AS blocked
JOIN   pg_stat_activity AS blocking
  ON   blocking.pid = ANY(pg_blocking_pids(blocked.pid))
WHERE  blocked.pid <> pg_backend_pid()
ORDER  BY blocked_seconds DESC;
```

```sql
-- GOOD 2: Full lock inventory with table and lock type details
SELECT
  a.pid,
  a.usename,
  a.application_name,
  a.state,
  EXTRACT(epoch FROM NOW() - a.state_change) AS state_duration_sec,
  l.locktype,
  l.relation::regclass AS locked_table,
  l.mode,
  l.granted,
  LEFT(a.query, 100) AS query_snippet
FROM   pg_locks l
JOIN   pg_stat_activity a ON a.pid = l.pid
WHERE  l.relation IS NOT NULL
  AND  l.relation::regclass::text NOT LIKE 'pg_%'
ORDER  BY state_duration_sec DESC
LIMIT  50;
```

```sql
-- GOOD 3: Cancel a long-running query (graceful — sends SIGINT to the backend)
-- This does NOT terminate the connection, just the current query
SELECT pg_cancel_backend(pid)
FROM   pg_stat_activity
WHERE  state = 'active'
  AND  query_start < NOW() - INTERVAL '5 minutes'
  AND  pid <> pg_backend_pid();

-- GOOD 4: Terminate a connection (forceful — sends SIGTERM to the backend)
-- Only use when pg_cancel_backend does not work (e.g., idle in transaction)
SELECT pg_terminate_backend(pid)
FROM   pg_stat_activity
WHERE  state = 'idle in transaction'
  AND  state_change < NOW() - INTERVAL '10 minutes'
  AND  pid <> pg_backend_pid();
```

```sql
-- GOOD 5: Set lock_timeout to fail fast instead of waiting indefinitely
-- Set at the session level before a potentially conflicting operation:
SET lock_timeout = '10s';   -- fail if we can't acquire a lock in 10 seconds
-- After the operation, reset:
RESET lock_timeout;

-- Or set globally for the application role:
ALTER ROLE app_user SET lock_timeout = '30s';

-- GOOD 6: Enable lock wait logging (log when a lock wait exceeds N ms)
ALTER SYSTEM SET log_lock_waits = on;
ALTER SYSTEM SET deadlock_timeout = '1s';  -- also sets log_lock_waits threshold
SELECT pg_reload_conf();
-- Lock waits longer than deadlock_timeout are logged to the PostgreSQL log
-- This helps identify the root cause of recurring lock contention
```

```sql
-- GOOD 7: Identify tables with the most lock contention
SELECT
  relname AS table_name,
  COUNT(*) FILTER (WHERE NOT granted) AS waiting_locks,
  COUNT(*) FILTER (WHERE granted) AS held_locks
FROM   pg_locks l
LEFT JOIN pg_class c ON c.oid = l.relation
WHERE  l.relation IS NOT NULL
GROUP  BY relname
ORDER  BY waiting_locks DESC
LIMIT  10;
```

## Lock Mode Hierarchy

```
Lock Mode               Conflicts With
───────────────────────────────────────────────────────────────
AccessShareLock         AccessExclusiveLock only
                        (held by SELECT — conflicts only with DROP TABLE etc.)
RowShareLock            ExclusiveLock, AccessExclusiveLock
                        (held by SELECT FOR UPDATE/SHARE)
RowExclusiveLock        ShareLock, ShareRowExclusiveLock, ExclusiveLock, AccessExclusiveLock
                        (held by INSERT, UPDATE, DELETE)
ShareUpdateExclusiveLock ShareUpdateExclusiveLock, ShareRowExclusiveLock, ExclusiveLock, AccessExclusiveLock
                        (held by VACUUM, CREATE INDEX CONCURRENTLY, ANALYZE)
ShareLock               RowExclusiveLock, ShareRowExclusiveLock, ExclusiveLock, AccessExclusiveLock
                        (held by CREATE INDEX)
ShareRowExclusiveLock   RowShareLock, ShareUpdateExclusiveLock, ShareLock, ShareRowExclusiveLock, ExclusiveLock, AccessExclusiveLock
ExclusiveLock           All except AccessShareLock
AccessExclusiveLock     ALL (blocks everything)
                        (held by ALTER TABLE, DROP TABLE, VACUUM FULL, TRUNCATE)
```

## Why It Matters

- **Lock cascade**: A single `idle in transaction` session holding a row lock on a popular row can block dozens of application requests. Each blocked request holds its own connections and potentially other locks.
- **`pg_blocking_pids()`**: The cleanest way to find blocking chains. Returns an array of PIDs that are blocking the specified PID. Joining back to `pg_stat_activity` gives the blocking query text.
- **`lock_timeout` vs waiting forever**: Without `lock_timeout`, a transaction waits indefinitely for a lock. Setting `lock_timeout = '10s'` causes the waiting transaction to fail with `ERROR: canceling statement due to lock timeout` — allowing the application to retry or fail fast.
- **`log_lock_waits`**: PostgreSQL logs a `LOG: process N waited N.N ms for ShareLock on transaction N` message when a lock wait exceeds `deadlock_timeout`. Enable this in production to diagnose recurring lock patterns.

## Aurora/RDS Notes

- **Aurora PostgreSQL**: Lock monitoring via `pg_locks` and `pg_stat_activity` works identically on Aurora. `pg_blocking_pids()` function is available.
- **RDS PostgreSQL**: `log_lock_waits = on` is configurable via parameter group. PostgreSQL logs can be exported to CloudWatch Logs. `pg_cancel_backend()` and `pg_terminate_backend()` require appropriate privileges — `rds_superuser` role has them.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | `pg_blocking_pids()` available (since PG 9.6) |
| PostgreSQL 15 | Same |
| PostgreSQL 16 | Same |
| PostgreSQL 17 | Same |
| Aurora PostgreSQL | Same lock visibility; `rds_superuser` can call `pg_terminate_backend` |
