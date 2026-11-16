---
title: "Choose the right transaction isolation level for your workload"
impact: medium
tags: [isolation-levels, transactions, serializable, repeatable-read, mvcc]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Choose the right transaction isolation level for your workload

## Problem

PostgreSQL supports three effective isolation levels: READ COMMITTED (default), REPEATABLE READ, and SERIALIZABLE. Choosing the wrong level causes either phantom reads, non-repeatable reads, or unnecessary serialization failures. PostgreSQL's SERIALIZABLE uses Serializable Snapshot Isolation (SSI) — fundamentally different from MySQL's SERIALIZABLE which uses gap locks. Understanding the differences prevents both correctness bugs and performance problems.

## Isolation Level Comparison

| Level | Dirty Reads | Non-Repeatable Reads | Phantom Reads | PG Implementation |
|-------|-------------|---------------------|--------------|------------------|
| READ UNCOMMITTED | Possible* | Possible | Possible | *PG treats as READ COMMITTED |
| READ COMMITTED | Not possible | Possible | Possible | Snapshot per statement |
| REPEATABLE READ | Not possible | Not possible | **Not possible** (PG) | Snapshot at transaction start |
| SERIALIZABLE | Not possible | Not possible | Not possible | SSI — no gap locks |

*PostgreSQL does not actually allow dirty reads — READ UNCOMMITTED behaves like READ COMMITTED.

**Key PostgreSQL difference**: REPEATABLE READ in PostgreSQL prevents phantom reads. In MySQL, REPEATABLE READ allows phantom reads (which is why MySQL uses gap locks to prevent them).

## Bad Example

```sql
-- BAD: Using SERIALIZABLE for all transactions in a high-throughput OLTP system
-- SERIALIZABLE requires the application to handle serialization failures (40001)
-- and retry the entire transaction — most OLTP code does not do this correctly
BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE;
SELECT total_amount FROM orders WHERE id = $1;
UPDATE orders SET status = 'shipped' WHERE id = $1;
COMMIT;
-- Under high concurrency: ERROR: could not serialize access due to concurrent update
-- If the application doesn't retry, the operation silently fails
```

```sql
-- BAD: Using READ COMMITTED for financial account balance operations
-- Two concurrent transactions both read the balance, both compute new balance,
-- both write — one update is silently lost (lost update problem)
BEGIN;  -- READ COMMITTED (default)
SELECT balance FROM accounts WHERE id = $1;  -- reads $1000
-- Concurrent transaction also reads $1000 and adds $100
UPDATE accounts SET balance = balance + 200 WHERE id = $1;  -- writes $1200
COMMIT;
-- The other transaction also writes $1100 (its $1000 + $100)
-- One of these updates is lost — the final balance should be $1300 but is either $1200 or $1100
```

## Good Example

```sql
-- GOOD: READ COMMITTED (default) for standard OLTP
-- Most web application queries should use READ COMMITTED:
-- SELECT operations see the latest committed data on each statement
-- UPDATE operations use the latest committed data for the WHERE clause
BEGIN;  -- READ COMMITTED (default)
SELECT id, status, total_amount FROM orders WHERE user_id = $1 LIMIT 20;
-- Each SELECT sees all transactions committed before this statement started
COMMIT;

-- GOOD: REPEATABLE READ for snapshot consistency across multiple reads
-- Use when a transaction must see a consistent view of data across multiple queries
-- Example: generating a consistent report with multiple queries
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ;
SELECT COUNT(*) AS total_orders FROM orders WHERE status = 'paid';
SELECT SUM(total_amount) AS revenue FROM orders WHERE status = 'paid';
-- Both queries see the same snapshot — consistent results even if orders are
-- being inserted/updated concurrently
COMMIT;

-- GOOD: SERIALIZABLE for financial operations with write skew risk
-- Write skew: two transactions read overlapping data and each writes based on
-- what it read, resulting in a state that neither would have allowed alone
-- SSI detects this pattern and aborts one transaction (error 40001)
BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE;
SELECT COUNT(*) FROM orders WHERE user_id = $1 AND status = 'pending';
-- If < 5 pending orders, allow a new one:
INSERT INTO orders (user_id, status, total_amount) VALUES ($1, 'pending', $2);
COMMIT;
-- If two concurrent transactions both read 4 pending orders and both insert,
-- SSI detects the write skew and aborts one with: ERROR: could not serialize access
```

```python
# GOOD: Python retry pattern for serialization failures (error code 40001)
import psycopg2
import psycopg2.errors
import time

def create_order_serializable(conn, user_id, amount, max_retries=3):
    for attempt in range(max_retries):
        try:
            with conn.cursor() as cur:
                conn.autocommit = False
                cur.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
                cur.execute(
                    "SELECT COUNT(*) FROM orders WHERE user_id = %s AND status = 'pending'",
                    (user_id,)
                )
                count = cur.fetchone()[0]
                if count < 5:
                    cur.execute(
                        "INSERT INTO orders (user_id, status, total_amount) "
                        "VALUES (%s, 'pending', %s) RETURNING id",
                        (user_id, amount)
                    )
                    order_id = cur.fetchone()[0]
                    conn.commit()
                    return order_id
                else:
                    conn.rollback()
                    return None
        except psycopg2.errors.SerializationFailure:  # SQLSTATE 40001
            conn.rollback()
            if attempt < max_retries - 1:
                time.sleep(0.05 * (2 ** attempt))
                continue
            raise
```

```sql
-- Set isolation level for the current transaction:
SET TRANSACTION ISOLATION LEVEL READ COMMITTED;
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;

-- Or set the default for a session or role:
SET default_transaction_isolation = 'repeatable read';
ALTER ROLE reporting_user SET default_transaction_isolation = 'repeatable read';
```

## Why It Matters

- **PG REPEATABLE READ vs MySQL**: PostgreSQL's REPEATABLE READ prevents phantom reads (unlike MySQL REPEATABLE READ which requires gap locks to prevent them). Use PostgreSQL REPEATABLE READ for snapshot-consistent multi-query transactions without serialization overhead.
- **SSI vs gap locks**: PostgreSQL's SERIALIZABLE uses Serializable Snapshot Isolation — no gap locks, no predicate locking in the traditional sense. Instead, the system tracks read/write dependencies and aborts transactions that form a dangerous cycle.
- **`serialization_failure` (40001) retry is mandatory**: Applications using SERIALIZABLE *must* retry on `40001`. Any transaction aborted due to serialization failure must be retried from the beginning — a partial retry does not help.
- **READ COMMITTED and lost updates**: READ COMMITTED does not protect against lost updates. Use `SELECT FOR UPDATE` or `UPDATE ... WHERE version = $expected_version` (optimistic locking) for concurrent updates to the same row.

## Aurora/RDS Notes

- **Aurora PostgreSQL**: All three isolation levels are supported. SSI behavior is identical to community PostgreSQL.
- **RDS PostgreSQL**: `default_transaction_isolation` is configurable via parameter group. Consider setting it to `repeatable read` for reporting-heavy workloads.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | SSI available (since PG 9.1); all three levels available |
| PostgreSQL 15 | Same |
| PostgreSQL 16 | Same |
| PostgreSQL 17 | Same |
| Aurora PostgreSQL | All isolation levels supported; same SSI behavior |
