---
title: "Prevent deadlocks with consistent lock ordering and atomic updates"
impact: critical
tags: [deadlock, locking, transactions, pg-locks, performance]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Prevent deadlocks with consistent lock ordering and atomic updates

## Problem

A deadlock occurs when two transactions each hold a lock the other needs. PostgreSQL detects deadlocks using `deadlock_timeout` (default: 1 second) and automatically aborts one of the transactions with error code `40P01`. Deadlocks are preventable by: always locking rows in a consistent order (e.g., ascending PK), using atomic multi-row updates, and keeping transactions short.

## Bad Example

```sql
-- BAD: Stock transfer between two products — classic deadlock pattern

-- Session A: transfer 10 units from product_id=5 to product_id=3
BEGIN;
UPDATE products SET stock_qty = stock_qty - 10 WHERE id = 5;  -- acquires row lock on id=5
-- (Session A now waits or proceeds to the next statement)
UPDATE products SET stock_qty = stock_qty + 10 WHERE id = 3;  -- tries to lock id=3
COMMIT;

-- Session B (concurrently): transfer 5 units from product_id=3 to product_id=5
BEGIN;
UPDATE products SET stock_qty = stock_qty - 5  WHERE id = 3;  -- acquires row lock on id=3
UPDATE products SET stock_qty = stock_qty + 5  WHERE id = 5;  -- tries to lock id=5 → DEADLOCK
COMMIT;

-- PostgreSQL detects the cycle:
-- Session A holds lock on id=5, wants id=3
-- Session B holds lock on id=3, wants id=5
-- One transaction is aborted: ERROR: deadlock detected  DETAIL: Process 12345 waits for ShareLock...
```

## Good Example

```sql
-- GOOD 1: Single atomic UPDATE — one statement, no deadlock possible
UPDATE products
SET    stock_qty = stock_qty + CASE
         WHEN id = 3 THEN +10
         WHEN id = 5 THEN -10
       END
WHERE  id IN (3, 5)
  AND  (id = 3 OR stock_qty >= 10);  -- validate stock availability atomically
-- Both rows are updated in a single statement — PostgreSQL locks them in index order
-- No window for another transaction to interleave

-- GOOD 2: Consistent PK ordering if separate statements are truly required
-- Always lock in ascending id order — both transactions agree on order
BEGIN;
-- Lock in ascending PK order (lower id first):
UPDATE products SET stock_qty = stock_qty + 10 WHERE id = 3;  -- always lock smaller id first
UPDATE products SET stock_qty = stock_qty - 10 WHERE id = 5;  -- then larger id
COMMIT;

-- Session B must also use the same ordering:
BEGIN;
UPDATE products SET stock_qty = stock_qty - 5 WHERE id = 3;   -- smaller id first
UPDATE products SET stock_qty = stock_qty + 5 WHERE id = 5;   -- then larger id
COMMIT;
-- No deadlock: both sessions lock id=3 first; the second one waits

-- GOOD 3: SELECT FOR UPDATE with explicit ordering before UPDATE
BEGIN;
-- Acquire locks in consistent PK order before modifying
SELECT id, stock_qty FROM products
WHERE id IN (3, 5)
ORDER BY id FOR UPDATE;   -- locks both rows in id=3, id=5 order
-- Now proceed with UPDATEs in any order — locks are already held
UPDATE products SET stock_qty = stock_qty + 10 WHERE id = 3;
UPDATE products SET stock_qty = stock_qty - 10 WHERE id = 5;
COMMIT;
```

```python
# GOOD 4: Application-level retry for deadlocks (Python / psycopg2)
import psycopg2
import psycopg2.errors
import time

def transfer_stock(conn, from_id, to_id, quantity, max_retries=3):
    for attempt in range(max_retries):
        try:
            with conn.cursor() as cur:
                conn.autocommit = False
                cur.execute("""
                    UPDATE products
                    SET stock_qty = stock_qty + CASE
                        WHEN id = %s THEN %s
                        WHEN id = %s THEN -%s
                    END
                    WHERE id IN (%s, %s)
                """, (to_id, quantity, from_id, quantity, to_id, from_id))
                conn.commit()
                return True
        except psycopg2.errors.DeadlockDetected:  # error code: 40P01
            conn.rollback()
            if attempt < max_retries - 1:
                time.sleep(0.1 * (2 ** attempt))  # exponential backoff
                continue
            raise
```

```sql
-- Monitor for deadlocks:
-- Enable logging:
ALTER SYSTEM SET log_deadlocks = on;
SELECT pg_reload_conf();

-- Check deadlock_timeout (default: 1s — do not lower in production):
SHOW deadlock_timeout;

-- View current locks:
SELECT
  pid,
  locktype,
  relation::regclass AS table_name,
  mode,
  granted,
  transactionid
FROM   pg_locks
WHERE  NOT granted
ORDER  BY pid;

-- Find blocking queries:
SELECT
  blocked_activity.pid           AS blocked_pid,
  blocked_activity.query         AS blocked_query,
  blocking_activity.pid          AS blocking_pid,
  blocking_activity.query        AS blocking_query
FROM   pg_stat_activity AS blocked_activity
JOIN   pg_stat_activity AS blocking_activity
  ON   blocking_activity.pid = ANY(pg_blocking_pids(blocked_activity.pid))
WHERE  blocked_activity.wait_event_type = 'Lock';
```

## Why It Matters

- **Error code 40P01**: PostgreSQL returns `SQLSTATE 40P01` for deadlock. Applications must catch this error and retry the entire transaction from the beginning.
- **`deadlock_timeout`**: PostgreSQL waits `deadlock_timeout` (default: 1 second) before checking for a deadlock cycle. This means a transaction may appear to hang for up to 1 second before the deadlock is detected and one transaction is aborted.
- **Do not lower `deadlock_timeout`**: A lower timeout means more frequent deadlock checks, which increases CPU overhead. The default of 1 second is appropriate for most OLTP workloads.
- **`log_deadlocks = on`**: Logs deadlock information to the PostgreSQL log including the full lock graph. Enable this in production to diagnose recurring deadlock patterns.
- **Single-row lock vs table lock**: PostgreSQL uses row-level locks for DML. Deadlocks typically involve two rows locked in opposite order. Full table locks (ACCESS EXCLUSIVE) can also deadlock with row locks.

## Aurora/RDS Notes

- **Aurora PostgreSQL**: Deadlock detection and behavior is identical to community PostgreSQL. `log_deadlocks` is configurable via the parameter group.
- **RDS PostgreSQL**: `deadlock_timeout` and `log_deadlocks` are configurable via parameter group. PostgreSQL logs are exported to CloudWatch Logs via the `log_exports` parameter.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | `pg_blocking_pids()` function available (since PG 9.6) |
| PostgreSQL 15 | Same |
| PostgreSQL 16 | Same |
| PostgreSQL 17 | Same |
| Aurora PostgreSQL | Same deadlock detection; configure via parameter group |
