---
title: "Use PostgreSQL advisory locks for distributed mutual exclusion"
impact: medium
tags: [advisory-locks, distributed-locking, concurrency, pg-locks]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Use PostgreSQL advisory locks for distributed mutual exclusion

## Problem

Applications often need distributed mutual exclusion: ensure only one instance of a background job runs at a time, implement rate limiting, or coordinate between microservices. A common anti-pattern is a dedicated `locks` table with INSERT/SELECT/DELETE. PostgreSQL's advisory locks provide a cleaner, faster, and more reliable mechanism — they are managed by PostgreSQL directly, require no table I/O, and are automatically released when the connection closes.

## Bad Example

```sql
-- BAD: Distributed lock via a dedicated locks table
-- Multiple application instances compete for this lock via INSERT

-- Instance A:
BEGIN;
INSERT INTO distributed_locks (job_name, locked_at, locked_by)
VALUES ('order_processor', NOW(), 'instance-a');  -- fails if another instance inserted first
-- Relies on a unique constraint on job_name — this works but requires a table

-- Other issues:
-- 1. Lock table needs cleanup if instance crashes without releasing
-- 2. Table I/O for every lock acquire/release (slow at high frequency)
-- 3. Dead locks table entries accumulate if not cleaned up

-- BAD: Polling for the lock in a loop (lock table approach):
DO $$
DECLARE
  acquired BOOLEAN := FALSE;
BEGIN
  WHILE NOT acquired LOOP
    BEGIN
      INSERT INTO distributed_locks (job_name) VALUES ('order_processor');
      acquired := TRUE;
    EXCEPTION WHEN unique_violation THEN
      PERFORM pg_sleep(1);  -- wait and retry
    END;
  END LOOP;
END $$;
```

## Good Example

```sql
-- GOOD: Advisory locks — built-in, no table needed, auto-released on disconnect

-- pg_try_advisory_lock: non-blocking, returns FALSE if lock not available
-- Lock key must be a BIGINT (or two INTs). Use hashtext() for string keys.

-- Non-blocking try (returns immediately):
SELECT pg_try_advisory_lock(hashtext('order_processor')::bigint) AS acquired;
-- Returns TRUE if acquired, FALSE if another session holds the lock

-- Blocking wait (waits until lock is available):
SELECT pg_advisory_lock(hashtext('order_processor')::bigint);

-- Release manually:
SELECT pg_advisory_unlock(hashtext('order_processor')::bigint);
-- Or just close the connection — session-scoped locks are auto-released

-- Transaction-scoped advisory lock (auto-released at COMMIT or ROLLBACK):
SELECT pg_advisory_xact_lock(hashtext('order_processor')::bigint);
-- No explicit unlock needed — released automatically when transaction ends
-- Cannot be unlocked manually before transaction end
```

```python
# GOOD: Python background job with advisory lock
import psycopg2
import hashlib

def run_order_processor():
    conn = psycopg2.connect(
        host='pgbouncer', port=6432, dbname='ecommerce',
        user='app_user', password='password123'
    )
    # Use a consistent lock key derived from the job name
    lock_key = int(hashlib.sha256(b'order_processor').hexdigest()[:16], 16) % (2**63)

    try:
        cur = conn.cursor()
        # Non-blocking try — skip if another instance is running
        cur.execute("SELECT pg_try_advisory_lock(%s)", (lock_key,))
        acquired = cur.fetchone()[0]

        if not acquired:
            print("Another instance is running order_processor — skipping")
            conn.close()
            return

        # We have the lock — do the work
        process_pending_orders(conn)

    finally:
        # Release the lock (also released automatically when connection closes)
        cur.execute("SELECT pg_advisory_unlock(%s)", (lock_key,))
        conn.close()
```

```sql
-- Monitor current advisory locks:
SELECT
  pid,
  classid,
  objid,
  objsubid,
  locktype,
  mode,
  granted
FROM   pg_locks
WHERE  locktype = 'advisory'
ORDER  BY pid;

-- Lock key for string-based lock names:
SELECT hashtext('order_processor') AS lock_key;

-- Advisory lock with two integer keys (for namespace isolation):
SELECT pg_try_advisory_lock(1, 42);   -- namespace=1, resource=42
SELECT pg_advisory_unlock(1, 42);
```

## Why It Matters

- **Zero table I/O**: Advisory locks are managed entirely in memory by the PostgreSQL lock manager. Acquiring and releasing an advisory lock is orders of magnitude faster than an INSERT to a lock table.
- **Automatic cleanup**: Session-scoped advisory locks are automatically released when the connection closes, even if the application crashes. No cleanup jobs needed.
- **Transaction vs session scope**: `pg_advisory_xact_lock` is released at COMMIT/ROLLBACK — good for locking during a transaction. `pg_advisory_lock` persists for the session — good for long-running background jobs that span multiple transactions.
- **pgBouncer transaction mode**: Session-scoped advisory locks (`pg_advisory_lock`) do NOT work with pgBouncer transaction mode — the connection is not held between transactions, so the lock is released. Use transaction-scoped advisory locks (`pg_advisory_xact_lock`) with pgBouncer transaction mode.
- **Hash collision risk**: `hashtext()` is 32-bit — collisions are possible. For production use, use a domain-specific integer key or `hashtext()::bigint` with awareness that collisions can occur.

## Aurora/RDS Notes

- **Aurora PostgreSQL**: Advisory locks work identically on Aurora. Session-scoped advisory locks are released when the connection to the writer endpoint closes.
- **RDS Proxy + advisory locks**: RDS Proxy does not preserve session state. Session-scoped advisory locks (`pg_advisory_lock`) will be lost if the proxy routes a new transaction to a different server connection. Use transaction-scoped locks (`pg_advisory_xact_lock`) when connecting through RDS Proxy.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | Advisory locks fully available; `pg_locks` view shows advisory locks |
| PostgreSQL 15 | Same |
| PostgreSQL 16 | Same |
| PostgreSQL 17 | Same |
| Aurora PostgreSQL | Same behavior; avoid session-scoped locks with RDS Proxy |
