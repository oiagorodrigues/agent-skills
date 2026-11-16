---
title: "Use database constraints as the last line of defense for data integrity"
impact: medium
tags: [constraints, check, unique, foreign-key, exclusion, deferrable, schema-design]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Use database constraints as the last line of defense for data integrity

## Problem

Business rules enforced only in application code can be bypassed by direct SQL access, migrations, multiple application versions running simultaneously, or bugs. PostgreSQL constraints — CHECK, UNIQUE, FOREIGN KEY, NOT NULL, and EXCLUDE — enforce data integrity at the database level. They cannot be bypassed by any SQL client, regardless of what the application does.

## Bad Example

```sql
-- BAD: Business rules enforced only in the application
-- Application code: if rating < 1 or rating > 5: raise ValueError
-- Nothing stops direct SQL from inserting invalid data:
INSERT INTO reviews (product_id, user_id, rating) VALUES (1, 1, 99);
-- rating=99 is stored successfully — application validation was bypassed

-- BAD: Check-then-insert pattern (application-level uniqueness check is not atomic)
-- SELECT COUNT(*) FROM reviews WHERE product_id=1 AND user_id=1;
-- if count == 0: INSERT INTO reviews ... -- race condition between SELECT and INSERT
```

## Good Example

```sql
-- GOOD 1: CHECK constraint for business rules
-- Enforced by the database for all INSERT/UPDATE operations
ALTER TABLE reviews
  ADD CONSTRAINT chk_reviews_rating CHECK (rating BETWEEN 1 AND 5);

ALTER TABLE products
  ADD CONSTRAINT chk_products_price  CHECK (price >= 0),
  ADD CONSTRAINT chk_products_stock  CHECK (stock_qty >= 0);

ALTER TABLE orders
  ADD CONSTRAINT chk_orders_total CHECK (total_amount >= 0);

-- GOOD 2: UNIQUE constraint for deduplication
-- Already in the schema, but demonstrating explicitly:
ALTER TABLE reviews
  ADD CONSTRAINT uq_reviews_product_user UNIQUE (product_id, user_id);
-- Now ON CONFLICT (product_id, user_id) DO UPDATE works correctly

-- GOOD 3: FOREIGN KEY constraints with explicit ON DELETE behavior
ALTER TABLE order_items
  ADD CONSTRAINT fk_order_items_order
  FOREIGN KEY (order_id) REFERENCES orders (id)
  ON DELETE CASCADE     -- delete line items when order is deleted
  DEFERRABLE INITIALLY IMMEDIATE;   -- can be deferred for multi-row operations

ALTER TABLE order_items
  ADD CONSTRAINT fk_order_items_product
  FOREIGN KEY (product_id) REFERENCES products (id)
  ON DELETE RESTRICT;   -- prevent deleting products with existing orders

-- GOOD 4: NOT VALID + VALIDATE for zero-downtime constraint addition
-- Add constraint without scanning existing rows (instant):
ALTER TABLE orders
  ADD CONSTRAINT chk_orders_shipping_not_empty
  CHECK (LENGTH(shipping_addr) > 0) NOT VALID;

-- Validate existing rows separately (allows concurrent writes):
ALTER TABLE orders VALIDATE CONSTRAINT chk_orders_shipping_not_empty;

-- GOOD 5: Deferrable constraints for multi-step operations
-- Example: inserting a parent and child row in the same transaction
ALTER TABLE categories
  DROP CONSTRAINT IF EXISTS fk_categories_parent,
  ADD CONSTRAINT fk_categories_parent
  FOREIGN KEY (parent_id) REFERENCES categories (id)
  ON DELETE SET NULL
  DEFERRABLE INITIALLY DEFERRED;   -- checked at COMMIT, not after each statement

-- Now you can insert parent and child in any order within a transaction:
BEGIN;
INSERT INTO categories (id, parent_id, name, slug) VALUES (100, 200, 'Child', 'child')
  OVERRIDING SYSTEM VALUE;
INSERT INTO categories (id, parent_id, name, slug) VALUES (200, NULL, 'Parent', 'parent')
  OVERRIDING SYSTEM VALUE;
COMMIT;   -- FK is checked here — both rows exist, constraint satisfied

-- GOOD 6: EXCLUDE constraint for preventing overlapping ranges (GiST)
-- Requires a range-type column (not in the main e-commerce schema, but illustrative)
-- CREATE TABLE reservations (
--   room_id    INT NOT NULL,
--   during     TSTZRANGE NOT NULL,
--   EXCLUDE USING gist (room_id WITH =, during WITH &&)
-- );
-- This prevents two reservations for the same room overlapping in time
-- The GiST exclusion constraint uses the && (overlap) operator
```

```sql
-- Check all constraints on a table:
SELECT conname, contype, pg_get_constraintdef(oid) AS definition
FROM   pg_constraint
WHERE  conrelid = 'orders'::regclass
ORDER  BY contype, conname;

-- contype values:
-- 'c' = CHECK
-- 'f' = FOREIGN KEY
-- 'p' = PRIMARY KEY
-- 'u' = UNIQUE
-- 'x' = EXCLUSION
```

## Why It Matters

- **Defense in depth**: Application code can be bypassed (direct psql, migrations, API bugs, concurrent deploys). Database constraints cannot.
- **Atomic enforcement**: A UNIQUE constraint check and the INSERT happen atomically inside PostgreSQL. An application-level check-then-insert is a race condition.
- **`NOT VALID` pattern**: Adds a constraint without scanning existing rows — acquires only a brief `ACCESS EXCLUSIVE` lock. The constraint is immediately enforced for new rows. `VALIDATE CONSTRAINT` checks existing rows with a `SHARE UPDATE EXCLUSIVE` lock that allows concurrent writes.
- **Deferrable constraints**: `DEFERRABLE INITIALLY DEFERRED` defers constraint checking to `COMMIT` time. Useful for multi-row operations where intermediate states would violate the constraint (e.g., reordering parent-child rows, circular references).
- **EXCLUDE constraints**: A unique PostgreSQL feature — prevents two rows from conflicting according to any operator, not just equality. Commonly used with range types to prevent scheduling overlaps.

## Aurora/RDS Notes

- **Aurora PostgreSQL**: All constraint types are fully supported. GiST-based EXCLUDE constraints are supported.
- **RDS PostgreSQL**: Same. No special considerations for constraints on RDS. Deferrable constraints work identically.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | All constraint types available; `NOT VALID` + `VALIDATE CONSTRAINT` pattern available |
| PostgreSQL 15 | `MERGE` statement respects constraints (MERGE added in PG 15) |
| PostgreSQL 16 | Same |
| PostgreSQL 17 | `MERGE` with RETURNING clause added |
| Aurora PostgreSQL | All constraint types fully supported |
