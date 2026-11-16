---
title: "Use SELECT FOR UPDATE SKIP LOCKED for job queue patterns"
impact: medium
tags: [skip-locked, job-queue, locking, concurrency, queue]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Use SELECT FOR UPDATE SKIP LOCKED for job queue patterns

## Problem

Using a database table as a job queue is a common pattern. The naive approach — `SELECT FOR UPDATE` to claim a job — causes all workers to block on the same locked row, creating a "thundering herd" where all workers queue up waiting for the current holder to release. `SKIP LOCKED` (PostgreSQL 9.5+) makes each worker atomically skip rows that are currently locked, claiming the next available job without blocking.

## Bad Example

```sql
-- BAD: SELECT FOR UPDATE without SKIP LOCKED — all workers pile up on the same row

-- Worker 1:
BEGIN;
SELECT id, user_id, status FROM orders
WHERE  status = 'pending'
ORDER  BY created_at
LIMIT  1
FOR UPDATE;  -- acquires row lock on the first pending order
-- Workers 2, 3, 4, 5 all try to SELECT FOR UPDATE on the same row
-- They all WAIT for Worker 1 to release the lock
-- Result: workers serialize instead of running in parallel

-- Worker 2 (waiting):
BEGIN;
SELECT id, user_id, status FROM orders
WHERE  status = 'pending'
ORDER  BY created_at
LIMIT  1
FOR UPDATE;  -- BLOCKS — waiting for Worker 1's lock on the same row
```

## Good Example

```sql
-- GOOD: SKIP LOCKED — each worker claims the next unlocked row atomically

-- Worker 1:
BEGIN;
SELECT id, user_id, status, total_amount FROM orders
WHERE  status = 'pending'
ORDER  BY created_at
LIMIT  1
FOR UPDATE SKIP LOCKED;
-- Acquires lock on row 1001 (first pending order)

-- Worker 2 (concurrent — does NOT block):
BEGIN;
SELECT id, user_id, status, total_amount FROM orders
WHERE  status = 'pending'
ORDER  BY created_at
LIMIT  1
FOR UPDATE SKIP LOCKED;
-- Row 1001 is locked by Worker 1 — SKIP LOCKED skips it
-- Acquires lock on row 1002 instead — no waiting

-- Worker 3, 4, 5 each get their own row — true parallel processing
```

```sql
-- Full job queue worker pattern:
-- Step 1: Claim a job (atomic SELECT + lock)
BEGIN;
WITH claimed AS (
  SELECT id
  FROM   orders
  WHERE  status = 'pending'
  ORDER  BY created_at
  LIMIT  1
  FOR UPDATE SKIP LOCKED
)
UPDATE orders
SET    status = 'processing',
       updated_at = NOW()
FROM   claimed
WHERE  orders.id = claimed.id
RETURNING orders.id, orders.user_id, orders.total_amount;
-- If no rows returned: no pending orders available (all claimed or queue empty)

-- Step 2: Do the work outside the transaction if it takes long
-- (holding an open transaction during long work blocks vacuum and holds locks)
-- Better: commit the status change first, then do work, then update to 'shipped'
COMMIT;

-- Step 3: After work completes successfully, update status
BEGIN;
UPDATE orders SET status = 'shipped', shipped_at = NOW(), updated_at = NOW()
WHERE id = $1 AND status = 'processing';
COMMIT;

-- Step 4: If work fails, revert to pending (or increment retry count)
BEGIN;
UPDATE orders SET status = 'pending', updated_at = NOW()
WHERE id = $1 AND status = 'processing';
COMMIT;
```

```sql
-- Pattern with retry count and dead-letter queue:
-- Add retry tracking columns to the orders table (or a separate jobs table):
ALTER TABLE orders ADD COLUMN IF NOT EXISTS retry_count INT NOT NULL DEFAULT 0;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS last_error  TEXT;

-- Claim a job with retry limit:
WITH claimed AS (
  SELECT id
  FROM   orders
  WHERE  status = 'pending'
    AND  retry_count < 3      -- skip jobs that have failed too many times
  ORDER  BY created_at
  LIMIT  1
  FOR UPDATE SKIP LOCKED
)
UPDATE orders
SET    status = 'processing',
       updated_at = NOW()
FROM   claimed
WHERE  orders.id = claimed.id
RETURNING orders.id;

-- On failure: increment retry count, reset to pending
UPDATE orders
SET    status      = 'pending',
       retry_count = retry_count + 1,
       last_error  = $2,
       updated_at  = NOW()
WHERE  id = $1;

-- Move permanently failed jobs to dead-letter status:
UPDATE orders SET status = 'failed' WHERE retry_count >= 3 AND status = 'processing';
```

## Why It Matters

- **No blocking**: Without SKIP LOCKED, all workers block on the same locked row — serializing what should be parallel work. With SKIP LOCKED, workers immediately move to the next available row.
- **Atomic claim**: The `FOR UPDATE SKIP LOCKED` + immediate `UPDATE status = 'processing'` pattern is atomic — no other worker can claim the same row between the SELECT and UPDATE because the row is held locked.
- **No external queue required**: This pattern replaces Redis/SQS for many workloads when data locality (orders are already in PostgreSQL) and transactional semantics are important.
- **Transaction scope**: Keep the lock-acquiring transaction short. Do not process the job while the transaction is open — hold the lock just long enough to update the status to `'processing'`, then commit and do work.
- **SKIP LOCKED vs advisory locks**: SKIP LOCKED is simpler for row-level job claiming. Advisory locks (`lock-advisory-locks.md`) are better for global mutual exclusion (one job runs at a time across all instances).

## Aurora/RDS Notes

- **Aurora PostgreSQL**: `SKIP LOCKED` works identically on Aurora. Multiple worker instances connecting to the Aurora writer endpoint can use SKIP LOCKED concurrently.
- **Aurora readers**: Do NOT run job queue workers against Aurora reader endpoints — reader replicas are read-only and cannot execute `SELECT FOR UPDATE`.
- **RDS Proxy**: `FOR UPDATE SKIP LOCKED` works through RDS Proxy (it is a standard DML operation). The proxy routes to the writer.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | `SKIP LOCKED` available (since PG 9.5) |
| PostgreSQL 15 | Same |
| PostgreSQL 16 | Same |
| PostgreSQL 17 | Same |
| Aurora PostgreSQL | `SKIP LOCKED` fully supported; use writer endpoint only |
