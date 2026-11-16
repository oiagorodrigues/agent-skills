---
title: "Implement keyset (cursor) pagination for consistent O(log n) page cost"
impact: high
tags: [pagination, keyset, cursor, performance, offset]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Implement keyset (cursor) pagination for consistent O(log n) page cost

## Problem

`LIMIT n OFFSET m` pagination costs O(m) — PostgreSQL reads and discards `m` rows before returning `n`. Deep pages (OFFSET 100,000) are orders of magnitude slower than page 1. Keyset pagination uses the last-seen value from the previous page as a cursor, allowing PostgreSQL to seek directly to the next page position via an index. Every page costs the same O(log n) regardless of depth.

## Bad Example

```sql
-- BAD: Deep OFFSET pagination
-- Page 5,000: reads 100,020 rows to return 20
SELECT id, user_id, status, total_amount, created_at
FROM   orders
WHERE  status = 'paid'
ORDER  BY id DESC
LIMIT  20 OFFSET 100000;
```

## Good Example

```sql
-- GOOD: Simple keyset pagination by PK
-- First page (no cursor):
SELECT id, user_id, status, total_amount, created_at
FROM   orders
WHERE  status = 'paid'
ORDER  BY id DESC
LIMIT  20;
-- Returns rows with id: 1050, 1045, 1040, ..., 1011
-- Last row id = 1011 — encode as cursor for next page

-- Next page (cursor = 1011):
SELECT id, user_id, status, total_amount, created_at
FROM   orders
WHERE  status = 'paid'
  AND  id < 1011          -- $1 = last_seen_id
ORDER  BY id DESC
LIMIT  20;

-- Previous page (cursor = 1050, reverse direction):
SELECT id, user_id, status, total_amount, created_at
FROM   orders
WHERE  status = 'paid'
  AND  id > 1050          -- $1 = first_seen_id
ORDER  BY id ASC
LIMIT  20;
-- Reverse the result in the application to show in descending order
```

```sql
-- GOOD: Composite cursor for non-unique sort key (created_at + id tie-breaker)
-- created_at is not unique — tie-break with id to ensure stable ordering

-- First page:
SELECT id, user_id, status, total_amount, created_at
FROM   orders
WHERE  status = 'paid'
ORDER  BY created_at DESC, id DESC
LIMIT  20;
-- Last row: created_at='2024-12-01 10:00:00+00', id=9876 → encode as cursor

-- Next page (composite cursor):
SELECT id, user_id, status, total_amount, created_at
FROM   orders
WHERE  status = 'paid'
  AND  (created_at, id) < ($1, $2)   -- composite tuple comparison
ORDER  BY created_at DESC, id DESC
LIMIT  20;
-- $1 = '2024-12-01 10:00:00+00', $2 = 9876

-- Index to support this composite cursor:
CREATE INDEX idx_orders_status_created_id
  ON orders (status, created_at DESC, id DESC);
-- This index satisfies both the WHERE status = 'paid' filter
-- and the ORDER BY created_at DESC, id DESC sort
```

```python
# GOOD: Cursor encoding and decoding (Python)
import base64
import json
from datetime import datetime

def encode_cursor(row):
    """Encode the last row of a page as an opaque cursor."""
    payload = {
        'id': row['id'],
        'created_at': row['created_at'].isoformat()
    }
    return base64.urlsafe_b64encode(
        json.dumps(payload).encode()
    ).decode()

def decode_cursor(cursor_str):
    """Decode a cursor back to (created_at, id) tuple."""
    payload = json.loads(
        base64.urlsafe_b64decode(cursor_str.encode()).decode()
    )
    return datetime.fromisoformat(payload['created_at']), payload['id']

def get_orders_page(conn, status='paid', cursor=None, page_size=20):
    """Fetch one page of orders using keyset pagination."""
    cur = conn.cursor()
    if cursor is None:
        cur.execute(
            "SELECT id, user_id, status, total_amount, created_at "
            "FROM orders WHERE status = %s "
            "ORDER BY created_at DESC, id DESC LIMIT %s",
            (status, page_size)
        )
    else:
        created_at, last_id = decode_cursor(cursor)
        cur.execute(
            "SELECT id, user_id, status, total_amount, created_at "
            "FROM orders WHERE status = %s "
            "AND (created_at, id) < (%s, %s) "
            "ORDER BY created_at DESC, id DESC LIMIT %s",
            (status, created_at, last_id, page_size)
        )
    rows = cur.fetchall()
    columns = ['id', 'user_id', 'status', 'total_amount', 'created_at']
    results = [dict(zip(columns, row)) for row in rows]
    next_cursor = encode_cursor(results[-1]) if len(results) == page_size else None
    return results, next_cursor
```

## Why It Matters

- **O(log n) vs O(n)**: OFFSET 100,000 reads 100,000 rows. Keyset seeks directly to the B-tree position using the cursor value — O(log n) for the seek + O(page_size) for the read.
- **Consistent performance**: Users on page 1 and page 5,000 get the same query latency. OFFSET users on deep pages experience increasing timeouts.
- **Stable results**: Keyset pagination is stable under concurrent inserts. OFFSET pagination can skip or duplicate rows when rows are inserted or deleted between pages.
- **Limitation — no random access**: Keyset pagination supports only sequential next/previous navigation. If users need to jump to "page 500 of 1,000," keyset is not suitable — consider search instead.
- **Composite cursor stability**: A cursor on `(created_at, id)` is stable even when two rows have the same `created_at`. The `id` tie-breaker ensures no duplicates across pages.

## EXPLAIN Notes

```sql
-- OFFSET (bad): reads many rows
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, total_amount FROM orders
WHERE status = 'paid' ORDER BY id DESC LIMIT 20 OFFSET 100000;
-- actual rows=100020, Buffers: shared hit=2500

-- Keyset (good): reads only needed rows
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, total_amount FROM orders
WHERE status = 'paid' AND id < 850001
ORDER BY id DESC LIMIT 20;
-- actual rows=20, Buffers: shared hit=4
```

## Aurora/RDS Notes

- **Aurora PostgreSQL**: Keyset pagination is strongly recommended for Aurora reader replicas. Deep OFFSET queries generate heavy distributed storage I/O on Aurora — keyset eliminates this. Always verify the sort index is on the reader replica's buffer cache.
- **RDS PostgreSQL**: Same behavior as community PostgreSQL. Ensure covering indexes (with INCLUDE) for the sort and projection columns to enable index-only scans.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | Composite tuple comparison `(a, b) < ($1, $2)` fully supported |
| PostgreSQL 15 | Same |
| PostgreSQL 16 | Same |
| PostgreSQL 17 | Same |
| Aurora PostgreSQL | Keyset strongly recommended; deep OFFSET is especially costly on Aurora |
