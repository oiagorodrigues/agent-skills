-- =============================================================================
-- bad_queries.sql
-- 15 PostgreSQL query patterns with before/after/why commentary
-- All examples reference the ecommerce schema in sample/schema.sql
-- Use $1, $2 parameter placeholders (PostgreSQL protocol, not ?)
-- =============================================================================

-- =============================================================================
-- Pattern 1: LIKE with leading wildcard forces a sequential scan
-- Reference: references/query-sargable-expressions.md, references/advanced-full-text-search.md
-- =============================================================================

-- Leading wildcard: PostgreSQL cannot use any B-tree index on `name`.
--                   PostgreSQL performs a sequential scan — reads every products row.
SELECT id, name, price
FROM   products
WHERE  name LIKE '%wireless%';

-- With GIN trigram index: idx_products_name_trgm (GIN) in the schema supports this query.
SELECT id, name, price
FROM   products
WHERE  name LIKE '%wireless%';
-- Requires: CREATE EXTENSION pg_trgm;
-- Requires: CREATE INDEX idx_products_name_trgm ON products USING gin(name gin_trgm_ops);
-- EXPLAIN shows Bitmap Index Scan on idx_products_name_trgm instead of sequential scan.

-- WHY: B-tree indexes store values in sorted order. A leading wildcard means the
--      matching prefix is unknown, so no range scan is possible. GIN trigram indexes
--      split strings into all 3-character substrings and support arbitrary substring
--      matching efficiently. On a 1M-row table, the difference is seconds vs milliseconds.


-- =============================================================================
-- Pattern 2: OFFSET-based pagination scans and discards rows
-- Reference: references/query-pagination.md, references/data-keyset-pagination.md
-- =============================================================================

-- OFFSET: PostgreSQL must read and discard 50,000 rows to return 20.
--         At page 2,500 (OFFSET 50000) the cost grows linearly.
SELECT id, user_id, total_amount, created_at
FROM   orders
WHERE  status = 'paid'
ORDER  BY id DESC
LIMIT  20 OFFSET 50000;

-- Keyset (cursor) pagination: pass the last seen id from the previous page.
--                             Uses idx_orders_status + PK — cost is O(log n) regardless of depth.
SELECT id, user_id, total_amount, created_at
FROM   orders
WHERE  status = 'paid'
  AND  id < $1          -- $1 = last_seen_id from previous page response
ORDER  BY id DESC
LIMIT  20;

-- WHY: OFFSET tells PostgreSQL to scan and discard all preceding rows. At
--      OFFSET 50000, 50,020 rows are read to return 20. Keyset pagination
--      uses the PK B-tree directly — every page costs the same regardless of depth.
--      On Aurora PostgreSQL, OFFSET is especially costly because each discarded
--      page read may involve distributed storage I/O.


-- =============================================================================
-- Pattern 3: Implicit cast in WHERE prevents index use
-- Reference: references/query-sargable-expressions.md
-- =============================================================================

-- Implicit cast: comparing a BIGINT column to a TEXT literal forces a cast on every row.
--                PostgreSQL cannot use idx_orders_user_id because the types don't match
--                without row-by-row casting.
SELECT id, total_amount
FROM   orders
WHERE  user_id = '42';      -- user_id is BIGINT, '42' is TEXT

-- Correct type: use the correct type for the parameter. In application code, bind $1 as
--               integer/bigint — not as a string.
SELECT id, total_amount
FROM   orders
WHERE  user_id = 42;        -- integer literal, or $1::bigint from application

-- WHY: PostgreSQL is strongly typed. When the comparison operand type does not
--      match the column type, PostgreSQL must cast each column value before
--      comparing, making the predicate non-sargable. This prevents index use
--      and turns an index lookup into a sequential scan.


-- =============================================================================
-- Pattern 4: OR across unrelated columns prevents reliable index use
-- Reference: references/query-or-union.md
-- =============================================================================

-- OR across two columns: PostgreSQL may try a BitmapOr plan but
--                        it is often slower than two separate index lookups, and on large
--                        tables the planner may fall back to a sequential scan.
SELECT id, email, status
FROM   users
WHERE  status = 'active'
   OR  role   = 'admin';

-- UNION ALL: each branch gets its own Index Scan plan.
SELECT id, email, status FROM users WHERE status = 'active'
UNION ALL
SELECT id, email, status FROM users WHERE role = 'admin'
  AND status <> 'active';   -- avoid duplicates for users who are both admin and active

-- WHY: Each branch of UNION ALL gets a separate execution plan and can use its
--      own index. idx_users_status handles the first branch; a separate index on
--      role handles the second. The total cost is two fast index lookups rather
--      than an uncertain BitmapOr or sequential scan.


-- =============================================================================
-- Pattern 5: Correlated subquery in SELECT list executes once per row
-- Reference: references/data-n-plus-one.md
-- =============================================================================

-- Correlated subquery: the subquery executes once for every row in users.
--                      For 100k active users this is 100k additional queries against orders.
SELECT
  u.id,
  u.email,
  (SELECT COUNT(*) FROM orders o WHERE o.user_id = u.id) AS order_count
FROM users u
WHERE u.status = 'active';

-- LEFT JOIN with aggregation: PostgreSQL executes one pass over orders.
SELECT
  u.id,
  u.email,
  COALESCE(oc.order_count, 0) AS order_count
FROM       users u
LEFT JOIN  (
  SELECT user_id, COUNT(*) AS order_count
  FROM   orders
  GROUP  BY user_id
) oc ON oc.user_id = u.id
WHERE u.status = 'active';

-- WHY: A correlated subquery in the SELECT list re-executes for every output row.
--      The explicit LEFT JOIN + subquery is planned as a hash aggregate + hash join,
--      scanning orders exactly once. EXPLAIN shows Nested Loop for the first version
--      vs Hash Join for the second.


-- =============================================================================
-- Pattern 6: Over-join aggregation silently inflates SUM
-- Reference: references/query-aggregation-over-join.md
-- =============================================================================

-- Over-join: joining order_items and reviews before aggregating.
--            An order with 3 order_items rows and 4 reviews rows produces 12 joined rows.
--            SUM(oi.unit_price * oi.quantity) is counted 4× — result is not accurate.
SELECT
  p.id,
  p.name,
  SUM(oi.unit_price * oi.quantity) AS total_revenue,   -- inflated 4x due to join
  AVG(r.rating)                    AS avg_rating
FROM       products    p
JOIN       order_items oi ON oi.product_id = p.id
JOIN       reviews     r  ON r.product_id  = p.id
GROUP BY   p.id, p.name;

-- Separate CTEs: aggregate each one-to-many relationship independently, then join
--               the already-aggregated results. No Cartesian product.
WITH revenue AS (
  SELECT   product_id, SUM(unit_price * quantity) AS total_revenue
  FROM     order_items
  GROUP BY product_id
),
avg_rating AS (
  SELECT   product_id, AVG(rating) AS avg_rating
  FROM     reviews
  WHERE    status = 'approved'
  GROUP BY product_id
)
SELECT
  p.id,
  p.name,
  COALESCE(rev.total_revenue, 0) AS total_revenue,
  COALESCE(rat.avg_rating,    0) AS avg_rating
FROM       products    p
LEFT JOIN  revenue     rev ON rev.product_id = p.id
LEFT JOIN  avg_rating  rat ON rat.product_id = p.id;

-- WHY: When two one-to-many relationships are joined at the same level, the
--      Cartesian product of their rows inflates every aggregate. 3 items × 4 reviews
--      = 12 rows; revenue is counted 4×. No error is raised — data is silently
--      incorrect. The CTE approach aggregates each relation to one row per product
--      before joining.


-- =============================================================================
-- Pattern 7: N+1 query loop — one query per item
-- Reference: references/data-n-plus-one.md
-- =============================================================================

-- N+1 loop: application fetches all paid orders, then issues one query per order
--           to get the product names. 1000 orders = 1001 round trips.
--
-- orders = SELECT id, user_id, total_amount FROM orders WHERE status = 'paid' LIMIT 1000;
-- FOR EACH order IN orders:
--     items = SELECT p.name, oi.quantity FROM order_items oi
--             JOIN products p ON p.id = oi.product_id
--             WHERE oi.order_id = order.id;

-- Representation of the N+1 SQL:
SELECT id, user_id, total_amount FROM orders WHERE status = 'paid' LIMIT 1000;
-- then 1000 individual calls:
SELECT p.name, oi.quantity FROM order_items oi
JOIN products p ON p.id = oi.product_id
WHERE oi.order_id = 1;
-- ... repeated 999 more times

-- Single JOIN: returns everything in one round trip.
SELECT o.id, o.total_amount, p.name, oi.quantity
FROM   orders      o
JOIN   order_items oi ON oi.order_id   = o.id
JOIN   products    p  ON p.id          = oi.product_id
WHERE  o.status = 'paid'
LIMIT  1000;

-- Batch fetch with = ANY() for IDs already in memory:
-- SELECT p.name, oi.quantity, oi.order_id
-- FROM order_items oi JOIN products p ON p.id = oi.product_id
-- WHERE oi.order_id = ANY($1::bigint[]);   -- $1 = array of order IDs

-- WHY: Each round trip has network latency (typically 0.5–5 ms within a VPC).
--      1000 individual queries add 500 ms–5 s of latency that a single JOIN
--      eliminates. In pgBouncer transaction mode, N+1 also means 1000 connection
--      checkouts, increasing pool contention.


-- =============================================================================
-- Pattern 8: Single-row INSERT in a loop
-- Reference: references/data-batch-inserts.md
-- =============================================================================

-- Single-row inserts: each INSERT is a separate statement, a separate round trip, and
--                     (without an outer transaction) a separate WAL flush.
--                     1000 products = 1000 round trips + 1000 WAL syncs.
INSERT INTO products (category_id, name, sku, price, status)
VALUES (1, 'Widget A', 'SKU-001', 9.99, 'active');
INSERT INTO products (category_id, name, sku, price, status)
VALUES (1, 'Widget B', 'SKU-002', 14.99, 'active');
INSERT INTO products (category_id, name, sku, price, status)
VALUES (1, 'Widget C', 'SKU-003', 19.99, 'active');
-- ... 997 more INSERT statements

-- Multi-row INSERT: one statement, one round trip, one WAL record.
INSERT INTO products (category_id, name, sku, price, status)
VALUES
  (1, 'Widget A', 'SKU-001',  9.99, 'active'),
  (1, 'Widget B', 'SKU-002', 14.99, 'active'),
  (1, 'Widget C', 'SKU-003', 19.99, 'active');
-- Batch 500–1000 rows per INSERT statement for optimal throughput.

-- COPY FROM STDIN for bulk loads (10–100× faster than INSERT):
-- COPY products (category_id, name, sku, price, status)
-- FROM STDIN WITH (FORMAT csv, HEADER false);

-- WHY: Multi-row INSERT batches rows into one statement and one WAL flush.
--      COPY bypasses the SQL parser entirely and writes directly to storage.
--      On Aurora PostgreSQL, COPY also reduces write amplification to the
--      distributed storage layer.


-- =============================================================================
-- Pattern 9: SELECT * across a large table
-- Reference: references/query-covering-indexes.md
-- =============================================================================

-- SELECT *: forces PostgreSQL to fetch every column including wide TEXT and
--           JSONB columns the application never uses. Prevents index-only scans.
SELECT *
FROM   orders
WHERE  user_id = 42
ORDER  BY created_at DESC
LIMIT  10;

-- Explicit column list: select only the columns the application needs.
--                       idx_orders_user_status_id covers (user_id, status, id) — if we also
--                       INCLUDE (created_at, total_amount) the query can be satisfied by an
--                       index-only scan without touching the heap.
SELECT id, status, total_amount, created_at
FROM   orders
WHERE  user_id = 42
ORDER  BY created_at DESC
LIMIT  10;

-- WHY: SELECT * (1) transfers unused data over the network, (2) prevents
--      index-only scans (PostgreSQL can only do an index-only scan if all
--      projected columns are in the index), (3) breaks when columns are added
--      or removed. Always project only the columns needed.


-- =============================================================================
-- Pattern 10: Missing index on a foreign key column
-- Reference: references/query-missing-indexes.md
-- =============================================================================

-- No FK index: assume order_items.order_id has no index. Every JOIN from orders to
--              order_items performs a sequential scan of the entire order_items table.
SELECT o.id, SUM(oi.unit_price * oi.quantity) AS total
FROM   orders      o
JOIN   order_items oi ON oi.order_id = o.id
WHERE  o.status = 'paid'
GROUP  BY o.id;
-- If order_items has 50M rows and order_id is unindexed, this is a 50M row
-- sequential scan for each matching order.

-- With FK index: ensure every FK column is indexed. Create it if missing:
CREATE INDEX idx_order_items_order_id ON order_items (order_id);
-- Now the JOIN uses an index scan: O(log n) per order.

-- WHY: Unlike MySQL InnoDB, PostgreSQL does NOT automatically create an index
--      on a foreign key column — it only checks that the referenced column is
--      indexed on the referenced table. A missing FK index also makes
--      ON DELETE CASCADE significantly slower.


-- =============================================================================
-- Pattern 11: Inconsistent lock ordering leads to deadlock
-- Reference: references/lock-deadlock-prevention.md
-- =============================================================================

-- Inconsistent order: Session A transfers stock from product 5 to product 3.
--                     Session B transfers stock from product 3 to product 5.
--                     Session A locks product 5 first; Session B locks product 3 first.
--                     Each waits for the other's lock → deadlock (error code 40P01).

-- Session A:
BEGIN;
UPDATE products SET stock_qty = stock_qty - 10 WHERE id = 5;  -- locks id=5
UPDATE products SET stock_qty = stock_qty + 10 WHERE id = 3;  -- waits for id=3
COMMIT;

-- Session B (concurrently):
BEGIN;
UPDATE products SET stock_qty = stock_qty - 5  WHERE id = 3;  -- locks id=3
UPDATE products SET stock_qty = stock_qty + 5  WHERE id = 5;  -- waits for id=5 → DEADLOCK
COMMIT;

-- Single atomic UPDATE with CASE: one statement, locks both rows in
--                                  one operation ordered by the planner, no opportunity for deadlock.
UPDATE products
SET    stock_qty = stock_qty + CASE
         WHEN id = 3 THEN +10
         WHEN id = 5 THEN -10
       END
WHERE  id IN (3, 5);

-- WHY: The deadlock occurs because two transactions acquire locks in opposite
--      order on the same rows. A single multi-row UPDATE acquires all needed
--      locks atomically. If separate statements are required, always lock rows
--      in ascending PK order in every code path (SELECT ... FOR UPDATE ORDER BY id).


-- =============================================================================
-- Pattern 12: Non-atomic check-then-insert race condition
-- Reference: references/data-upsert.md
-- =============================================================================

-- Check-then-insert: two concurrent requests both run the SELECT, both see no row, both
--                    attempt the INSERT — one succeeds, the other gets a unique violation
--                    (or the application ignores the error and creates a duplicate).
SELECT COUNT(*) FROM reviews WHERE product_id = 10 AND user_id = 42;
-- application: if count == 0 then INSERT
INSERT INTO reviews (product_id, user_id, rating, body, status)
VALUES (10, 42, 5, 'Great product!', 'pending');

-- ON CONFLICT: INSERT ... ON CONFLICT DO UPDATE is atomic. The unique constraint on
--              (product_id, user_id) prevents duplicates; EXCLUDED holds the attempted values.
INSERT INTO reviews (product_id, user_id, rating, title, body, status)
VALUES (10, 42, 5, 'Great!', 'Loved it', 'pending')
ON CONFLICT (product_id, user_id) DO UPDATE
  SET rating     = EXCLUDED.rating,
      title      = EXCLUDED.title,
      body       = EXCLUDED.body,
      updated_at = NOW();

-- WHY: SELECT + INSERT is never atomic. Between the SELECT and the INSERT,
--      another transaction can insert the same row. ON CONFLICT DO UPDATE is
--      a single atomic statement that handles both insert and update paths
--      using PostgreSQL's internal lock on the unique constraint.


-- =============================================================================
-- Pattern 13: Unbatched bulk DELETE holds locks too long
-- Reference: references/data-bulk-operations.md
-- =============================================================================

-- Single large DELETE: deleting all old events in one statement acquires row locks
--                      on every matching row for the entire duration, blocking
--                      concurrent writes to those rows.
DELETE FROM order_items
WHERE created_at < NOW() - INTERVAL '2 years';
-- Could lock and delete 10M rows over 5 minutes, blocking the entire table.

-- Batched DELETE: delete in small batches to limit lock scope and duration.
--                 Repeat in a loop from the application until 0 rows are deleted.
DELETE FROM order_items
WHERE id IN (
  SELECT id FROM order_items
  WHERE  created_at < NOW() - INTERVAL '2 years'
  LIMIT  1000
);
-- Loop until DELETE returns 0 rows, sleeping 50–100 ms between iterations.

-- WHY: A single large DELETE holds exclusive row locks on all matching rows
--      for the full duration of the statement. Batching limits the maximum
--      rows locked at any time, reduces WAL write volume per transaction,
--      and allows other transactions to proceed between batches.


-- =============================================================================
-- Pattern 14: Function on timestamp column prevents index range scan
-- Reference: references/query-sargable-expressions.md
-- =============================================================================

-- EXTRACT() on indexed column: PostgreSQL must evaluate EXTRACT(year FROM created_at)
--                               for every row — idx_orders_created_at cannot be used.
SELECT id, user_id, total_amount
FROM   orders
WHERE  EXTRACT(year FROM created_at) = 2024;

-- Range predicate: rewrite directly on the column — PostgreSQL uses the index.
SELECT id, user_id, total_amount
FROM   orders
WHERE  created_at >= '2024-01-01 00:00:00+00'
  AND  created_at <  '2025-01-01 00:00:00+00';

-- WHY: Any function wrapping an indexed column makes the predicate non-sargable.
--      PostgreSQL cannot invert EXTRACT() to look up a range in the B-tree, so
--      it falls back to a sequential scan. Moving the transformation to the
--      literal side of the comparison preserves index use. Use TIMESTAMPTZ range
--      bounds with explicit timezone offsets to avoid timezone-related surprises.


-- =============================================================================
-- Pattern 15: JSON (not JSONB) for queried data
-- Reference: references/advanced-jsonb-indexing.md, references/schema-data-types.md
-- =============================================================================

-- JSON type: stores the raw text representation. It cannot be indexed
--             with GIN, and every query involving JSON operators must re-parse
--             the text on every row.
-- (Hypothetical: if products.attributes were JSON instead of JSONB)
SELECT id, name
FROM   products
WHERE  attributes->>'color' = 'red';    -- sequential scan, no index possible on JSON

-- JSONB type: stored as a parsed binary structure; supports GIN indexes for fast
--              containment queries.
-- Ensure the column is JSONB (as in the schema):
-- attributes JSONB DEFAULT '{}'

-- Index for containment (@>) queries:
-- CREATE INDEX idx_products_attributes_gin ON products USING gin(attributes);

-- Now this query uses a GIN index scan:
SELECT id, name
FROM   products
WHERE  attributes @> '{"color": "red"}';    -- GIN index scan

-- Or use a functional index for a specific path:
-- CREATE INDEX idx_products_attr_color ON products ((attributes->>'color'));
SELECT id, name
FROM   products
WHERE  attributes->>'color' = 'red';    -- uses functional index

-- WHY: JSON stores a verbatim text copy with no internal structure.
--      JSONB decomposes JSON into a binary format that supports GIN indexing,
--      faster access to individual keys, and @> / ? / @@ operators.
--      There is no performance advantage to JSON over JSONB for queried data —
--      use JSONB unless you explicitly need to preserve whitespace or key order.
