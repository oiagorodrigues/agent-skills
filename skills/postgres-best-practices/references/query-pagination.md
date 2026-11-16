---
title: "Use keyset pagination instead of LIMIT/OFFSET at scale"
impact: high
tags: [pagination, offset, keyset, cursor, performance]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Use keyset pagination instead of LIMIT/OFFSET at scale

## Problem

`LIMIT n OFFSET m` tells PostgreSQL to read and discard the first `m` rows before returning `n`. As `m` grows, so does the work — `OFFSET 50000` reads 50,020 rows to return 20. At page 2,500 this query takes seconds on a large table and gets slower with every page. Keyset (cursor) pagination uses the last seen value as a bookmark, so every page costs the same O(log n) regardless of depth.

## Bad Example

```sql
-- Page 2,500 of paid orders (20 per page)
-- PostgreSQL must read 50,020 rows, discard 50,000, return 20
SELECT id, user_id, status, total_amount, created_at
FROM   orders
WHERE  status = 'paid'
ORDER  BY id DESC
LIMIT  20 OFFSET 50000;
```

At OFFSET 50,000, PostgreSQL scans 50,020 rows in index order and throws away the first 50,000. The query is 2,500× slower than page 1. On Aurora, each of those 50,000 discarded rows may require a distributed storage page read.

## Good Example

```sql
-- Forward keyset pagination: pass the last id seen on the previous page
-- $1 = last_seen_id (from the previous page's final row)
SELECT id, user_id, status, total_amount, created_at
FROM   orders
WHERE  status = 'paid'
  AND  id < $1          -- keyset bookmark
ORDER  BY id DESC
LIMIT  20;

-- First page (no bookmark yet):
SELECT id, user_id, status, total_amount, created_at
FROM   orders
WHERE  status = 'paid'
ORDER  BY id DESC
LIMIT  20;
-- Return the last id in the result as the cursor for the next page.
```

```sql
-- Composite cursor for non-unique sort key (created_at + id for tie-breaking)
-- $1 = last_seen_created_at, $2 = last_seen_id (both from previous page's last row)
SELECT id, user_id, status, total_amount, created_at
FROM   orders
WHERE  status = 'paid'
  AND  (created_at, id) < ($1, $2)   -- composite cursor
ORDER  BY created_at DESC, id DESC
LIMIT  20;

-- Index to support this: (status, created_at DESC, id DESC)
CREATE INDEX idx_orders_status_created_id
  ON orders (status, created_at DESC, id DESC);
```

```sql
-- Backward navigation: reverse the comparison operator
-- $1 = first_seen_id from the current page
SELECT id, user_id, status, total_amount, created_at
FROM   orders
WHERE  status = 'paid'
  AND  id > $1
ORDER  BY id ASC
LIMIT  20;
-- Then reverse the result in the application to show in descending order.
```

**Cursor encoding** (application side — Python example):
```python
import base64, json

def encode_cursor(last_row):
    payload = {"id": last_row["id"]}
    return base64.b64encode(json.dumps(payload).encode()).decode()

def decode_cursor(cursor_str):
    return json.loads(base64.b64decode(cursor_str).decode())
```

## Why It Matters

- **O(n) vs O(log n)**: OFFSET scans grow linearly. At OFFSET 100,000 on a 10M-row table, PostgreSQL reads 100,020 rows. Keyset pagination reads exactly the 20 rows needed — every page is the same cost.
- **Consistent performance**: Page 1 and page 5,000 take the same time with keyset pagination. Users on deep pages don't experience timeouts.
- **Index efficiency**: Keyset pagination uses a B-tree range scan — exactly what indexes are designed for. OFFSET pagination reads a sorted range and discards most of it.
- **Aurora-specific**: OFFSET is especially costly on Aurora's distributed storage. Each of the 50,000 discarded rows may require a page fetch from the Aurora storage layer. Keyset pagination eliminates these wasted reads entirely.
- **Limitation**: Keyset pagination does not support jumping to an arbitrary page number. It only supports sequential next/previous navigation. If random page access is required, consider a different UX pattern (search instead of pagination).

## EXPLAIN Notes

```sql
-- Bad: OFFSET forces a full index scan up to the offset
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, user_id, status, total_amount, created_at
FROM orders WHERE status = 'paid' ORDER BY id DESC
LIMIT 20 OFFSET 50000;
```

```
Limit  (actual rows=20 loops=1)
  ->  Index Scan using idx_orders_status on orders
        Index Cond: (status = 'paid'::order_status)
        Rows Removed by Filter: 0
        actual rows=50020   ← reads 50,020 rows to return 20
        Buffers: shared hit=1250
```

```sql
-- Good: keyset reads exactly the needed rows
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, user_id, status, total_amount, created_at
FROM orders WHERE status = 'paid' AND id < 950001
ORDER BY id DESC LIMIT 20;
```

```
Limit  (actual rows=20 loops=1)
  ->  Index Scan using idx_orders_user_status_id on orders
        Index Cond: ((status = 'paid') AND (id < 950001))
        actual rows=20   ← reads exactly 20 rows
        Buffers: shared hit=4
```

| Query | Rows Read | Rows Returned | Buffers |
|-------|-----------|--------------|---------|
| OFFSET 50000 | 50,020 | 20 | shared hit=1250 |
| Keyset `id < $1` | 20 | 20 | shared hit=4 |

## Aurora/RDS Notes

- **Aurora PostgreSQL**: The `idx_orders_user_status_id` composite index `(user_id, status, id)` in the schema is designed for keyset pagination. Ensure `random_page_cost = 1.1` in the Aurora parameter group so the planner prefers index scans.
- **Reader replicas**: Keyset pagination is recommended for Aurora reader endpoints. Deep OFFSET queries on a reader can cause the reader to lag behind the writer due to heavy I/O load.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | Keyset pagination with composite cursors fully supported |
| PostgreSQL 15 | Same |
| PostgreSQL 16 | Same |
| PostgreSQL 17 | Same |
| Aurora PostgreSQL | OFFSET is disproportionately expensive; keyset strongly recommended |
