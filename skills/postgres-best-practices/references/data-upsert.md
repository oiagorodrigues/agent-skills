---
title: "Use INSERT ... ON CONFLICT for atomic upsert operations"
impact: medium
tags: [upsert, on-conflict, insert, atomicity, concurrency]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Use INSERT ... ON CONFLICT for atomic upsert operations

## Problem

A common pattern is to check if a row exists, then insert or update it. This SELECT-then-INSERT/UPDATE is not atomic — two concurrent transactions can both find no existing row and both attempt the INSERT, causing a unique constraint violation. PostgreSQL's `INSERT ... ON CONFLICT` is a single atomic statement that handles both cases using the database's internal lock on the unique constraint.

## Bad Example

```sql
-- BAD: Non-atomic check-then-insert pattern
-- Two concurrent requests for the same (product_id=10, user_id=42):
-- Both run the SELECT, both see 0 rows, both attempt the INSERT
-- One succeeds, the other gets: ERROR: duplicate key value violates unique constraint

SELECT COUNT(*) FROM reviews WHERE product_id = 10 AND user_id = 42;
-- Application: if count == 0 → INSERT
INSERT INTO reviews (product_id, user_id, rating, title, body, status)
VALUES (10, 42, 5, 'Great product!', 'Loved it', 'pending');
-- RACE CONDITION: between SELECT and INSERT, another connection can insert the same row
```

## Good Example

```sql
-- GOOD 1: INSERT ... ON CONFLICT DO UPDATE (upsert)
-- Inserts if the (product_id, user_id) pair doesn't exist,
-- updates the existing row if it does — atomically
INSERT INTO reviews (product_id, user_id, rating, title, body, status)
VALUES (10, 42, 5, 'Great product!', 'Loved it', 'pending')
ON CONFLICT (product_id, user_id) DO UPDATE
  SET rating     = EXCLUDED.rating,
      title      = EXCLUDED.title,
      body       = EXCLUDED.body,
      updated_at = NOW();
-- EXCLUDED is a pseudo-table holding the row that would have been inserted
-- This is always safe regardless of concurrent requests

-- GOOD 2: INSERT ... ON CONFLICT DO NOTHING (idempotent insert)
-- Insert if not exists, skip silently if already exists
INSERT INTO reviews (product_id, user_id, rating, body, status)
VALUES (10, 42, 5, 'Good!', 'pending')
ON CONFLICT (product_id, user_id) DO NOTHING;
-- No error, no update — just a no-op if the row exists
-- Use when you only want to insert-once (e.g., first write wins)

-- GOOD 3: Conditional update in ON CONFLICT
-- Only update if the existing row has a lower rating (best review wins)
INSERT INTO reviews (product_id, user_id, rating, body, status)
VALUES (10, 42, 5, 'Amazing!', 'pending')
ON CONFLICT (product_id, user_id) DO UPDATE
  SET rating     = EXCLUDED.rating,
      body       = EXCLUDED.body,
      updated_at = NOW()
WHERE  reviews.rating < EXCLUDED.rating;   -- only update if new rating is higher

-- GOOD 4: Upsert on a partial unique index
-- The schema has a unique constraint on (product_id, user_id)
-- For a partial unique index, use ON CONFLICT ON CONSTRAINT:
-- ALTER TABLE reviews ADD CONSTRAINT uq_reviews_active
--   UNIQUE (product_id, user_id) WHERE status != 'rejected';
-- INSERT ... ON CONFLICT ON CONSTRAINT uq_reviews_active DO UPDATE ...

-- GOOD 5: RETURNING clause to get the resulting row
INSERT INTO reviews (product_id, user_id, rating, title, body, status)
VALUES ($1, $2, $3, $4, $5, 'pending')
ON CONFLICT (product_id, user_id) DO UPDATE
  SET rating     = EXCLUDED.rating,
      title      = EXCLUDED.title,
      body       = EXCLUDED.body,
      updated_at = NOW()
RETURNING id, product_id, user_id, rating, updated_at;
-- Returns the final state of the row (whether inserted or updated)
```

## Why It Matters

- **Atomicity**: `ON CONFLICT DO UPDATE` is a single atomic operation. No other transaction can see an intermediate state between the conflict check and the INSERT/UPDATE.
- **`EXCLUDED` pseudo-table**: The `EXCLUDED` table holds the values from the attempted INSERT row. This allows referencing both the existing row values (`reviews.rating`) and the new values (`EXCLUDED.rating`) in the `DO UPDATE` clause.
- **No redundant round trip**: `ON CONFLICT` eliminates the SELECT → INSERT round trip, halving the number of database queries for upsert operations.
- **`DO NOTHING` vs `DO UPDATE`**: Use `DO NOTHING` when the first write should win (idempotent event insertion). Use `DO UPDATE` when new values should overwrite or merge with existing ones.
- **Conflict target**: The conflict target must match an existing unique constraint or primary key. You can use `ON CONFLICT (column)` (names the column), `ON CONFLICT ON CONSTRAINT name` (names the constraint), or `ON CONFLICT DO NOTHING` (matches any conflict).

## EXPLAIN Notes

```sql
-- Show that ON CONFLICT avoids a separate SELECT:
EXPLAIN (ANALYZE, BUFFERS)
INSERT INTO reviews (product_id, user_id, rating, title, body, status)
VALUES (10, 42, 5, 'Great!', 'Loved it', 'pending')
ON CONFLICT (product_id, user_id) DO UPDATE
  SET rating = EXCLUDED.rating, updated_at = NOW();
```

```
Insert on reviews  (actual rows=0 loops=1)
  Conflict Resolution: UPDATE
  Conflict Arbiter Indexes: uq_reviews_product_user
  Tuples Inserted: 0     ← conflict detected, did UPDATE instead
  Conflicting Tuples: 1
  Buffers: shared hit=5
```

## Aurora/RDS Notes

- **Aurora PostgreSQL**: `INSERT ... ON CONFLICT` works identically on Aurora. No Aurora-specific differences.
- **RDS PostgreSQL**: Same behavior as community PostgreSQL.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | `ON CONFLICT DO UPDATE` fully available (since PG 9.5); `RETURNING` with `ON CONFLICT` available |
| PostgreSQL 15 | Same |
| PostgreSQL 16 | Same |
| PostgreSQL 17 | `MERGE` improvements may serve some upsert use cases with better ergonomics |
| Aurora PostgreSQL | `ON CONFLICT` fully supported |
