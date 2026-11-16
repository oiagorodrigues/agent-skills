---
title: "Understand PostgreSQL sequences: gaps are normal, exhaustion is not"
impact: medium
tags: [sequences, serial, identity, gaps, schema-design, operations]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Understand PostgreSQL sequences: gaps are normal, exhaustion is not

## Problem

PostgreSQL sequences are the standard mechanism for generating auto-incrementing primary key values. Common mistakes include: assuming gap-free sequential IDs (sequences can and do skip values on transaction rollback), using `SELECT MAX(id) + 1` for the next ID (race condition), using `INT`-based sequences that can exhaust at 2.1 billion, and resetting sequences incorrectly after data migrations.

## Bad Example

```sql
-- BAD 1: Assuming gap-free IDs — sequences skip on rollback
-- This assumption breaks any business logic that relies on ID continuity

-- Transaction A inserts a row (sequence value: 1001)
BEGIN;
INSERT INTO orders (user_id, status) VALUES (42, 'pending');  -- gets id=1001
-- Transaction A rolls back
ROLLBACK;
-- id 1001 is GONE — the next successful INSERT gets id=1002
-- Sequence never "gives back" consumed values

-- BAD 2: SELECT MAX(id) + 1 for next ID — race condition
SELECT MAX(id) + 1 AS next_id FROM orders;
-- Two concurrent sessions both read MAX(id) = 1000
-- Both try to INSERT with id = 1001 — one gets a duplicate key violation
-- Even in a transaction, this is not safe without an explicit FOR UPDATE

-- BAD 3: Using SERIAL (INT-based) without verifying range
CREATE TABLE high_volume_events (
  id         SERIAL PRIMARY KEY,   -- INT: max 2,147,483,647 (~2.1B)
  event_type TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
-- At 1,000 inserts/second: exhausts in ~25 days
-- At 10,000 inserts/second: exhausts in ~2.5 days
-- Sequence exhaustion produces: ERROR: nextval: reached maximum value of sequence
```

## Good Example

```sql
-- GOOD 1: Accept sequence gaps — they are normal and correct
-- Gaps occur from: rolled-back transactions, sequence caching (cache > 1),
-- server restarts (with cache > 1), and manual sequence manipulation.
-- Never write business logic that depends on gap-free IDs.

-- GOOD 2: Always use sequences (GENERATED ALWAYS AS IDENTITY or BIGSERIAL)
-- Let PostgreSQL manage ID generation — never compute "next ID" manually
CREATE TABLE orders (
  id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,   -- BIGINT: 9.2 quintillion
  user_id BIGINT NOT NULL REFERENCES users(id),
  status  order_status NOT NULL DEFAULT 'pending'
);

-- GOOD 3: Monitor sequence exhaustion risk
SELECT
  s.schemaname,
  s.sequencename,
  s.last_value,
  s.max_value,
  ROUND(s.last_value::numeric / s.max_value::numeric * 100, 2) AS percent_used
FROM   pg_sequences s
ORDER  BY percent_used DESC NULLS LAST;
-- Alert when percent_used > 80% for INT-backed sequences

-- GOOD 4: Inspect a sequence:
SELECT * FROM pg_sequences WHERE sequencename = 'orders_id_seq';

-- GOOD 5: Reset a sequence after bulk data import (set to max(id) + 1)
SELECT setval('orders_id_seq',
              (SELECT MAX(id) FROM orders),
              true);    -- true = next call returns max+1
-- 'true' means the last_value IS the last used value (next call returns last_value + 1)
-- 'false' means the last_value will be returned on the NEXT call

-- GOOD 6: Create sequence explicitly with BIGINT range:
CREATE SEQUENCE IF NOT EXISTS order_id_seq
  AS BIGINT
  START 1
  INCREMENT 1
  NO CYCLE;              -- NO CYCLE prevents wrapping around (fails gracefully instead)
```

```sql
-- Sequence behavior: CYCLE vs NO CYCLE
-- CYCLE: after max_value, wraps back to min_value (potential duplicate IDs!)
-- NO CYCLE (recommended): raises an error when exhausted — safe failure

-- Check if an existing sequence uses CYCLE:
SELECT sequencename, cycle
FROM   pg_sequences
WHERE  schemaname = 'public';

-- Convert a cycling sequence to non-cycling (requires ALTER SEQUENCE):
ALTER SEQUENCE orders_id_seq NO CYCLE;
```

## Why It Matters

- **Gaps are by design**: PostgreSQL sequences use `nextval()` which is non-transactional for performance. The value is consumed even if the transaction rolls back. This is intentional — rolling back a sequence would require serializing all sequence access (a bottleneck). Accept gaps.
- **INT exhaustion is silent until it explodes**: A `SERIAL` (INT) column silently approaches 2.1 billion. When it hits the limit, `nextval()` raises an error and all INSERTs fail immediately. Migrating to `BIGINT` on a live production table requires a multi-step ALTER that takes significant time.
- **`SELECT MAX(id) + 1` is always wrong**: Two concurrent transactions that both read the same MAX(id) will both attempt to insert the same next ID. The unique constraint will reject one of them. This is a classic race condition.
- **Sequence caching**: `CACHE n` in the sequence definition makes each backend pre-allocate `n` values. This improves INSERT throughput but increases gap size (gaps of `n` when the backend restarts). The default cache is 1.
- **Aurora/RDS**: Sequences on Aurora are local to the writer node. Read replicas have the sequence value at replication time — do NOT insert through reader endpoints, as they cannot advance sequences.

## Aurora/RDS Notes

- **Aurora PostgreSQL**: Sequences are replicated as WAL to reader nodes, but reader nodes cannot call `nextval()`. All INSERT operations must go through the writer endpoint. Read-only replicas will show the sequence state but cannot advance it.
- **RDS PostgreSQL**: Same behavior as community PostgreSQL. No special considerations for sequences on RDS.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | `pg_sequences` view available for monitoring |
| PostgreSQL 15 | Same |
| PostgreSQL 16 | Same |
| PostgreSQL 17 | Same |
| Aurora PostgreSQL | Sequences local to writer; not advanceable on reader replicas |
