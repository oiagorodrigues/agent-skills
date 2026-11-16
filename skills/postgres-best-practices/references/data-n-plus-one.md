---
title: "Eliminate N+1 queries with JOINs or array batch fetching"
impact: high
tags: [n-plus-one, performance, joins, batch-fetching, query-optimization]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Eliminate N+1 queries with JOINs or array batch fetching

## Problem

An N+1 query pattern occurs when an application fetches N parent records and then issues one query per record to fetch associated child data — N+1 total queries instead of 1. Each query has network round-trip latency (0.5–5 ms within a VPC). For 1,000 parent records, this adds 500 ms–5 seconds of pure latency overhead. N+1 is especially harmful with pgBouncer transaction mode, where each query requires a connection checkout from the pool.

## Bad Example

```python
# BAD: Python loop with one query per user to fetch their orders
# 1,000 active users = 1,001 database queries

import psycopg2

conn = psycopg2.connect(host='localhost', dbname='ecommerce',
                        user='app_user', password='password123')
cur = conn.cursor()

# Query 1: fetch all active users (1 query)
cur.execute("SELECT id, email FROM users WHERE status = 'active' LIMIT 1000")
users = cur.fetchall()

results = []
for user_id, email in users:
    # Query 2..1001: one query per user (N queries)
    cur.execute(
        "SELECT id, status, total_amount FROM orders "
        "WHERE user_id = %s AND status = 'paid' LIMIT 5",
        (user_id,)
    )
    orders = cur.fetchall()
    results.append({'user_id': user_id, 'email': email, 'orders': orders})

# Total: 1,001 queries, ~500 ms–5 s of network overhead
```

## Good Example

```sql
-- GOOD 1: Single JOIN — fetch all data in one query
SELECT
  u.id         AS user_id,
  u.email,
  o.id         AS order_id,
  o.status,
  o.total_amount
FROM   users  u
JOIN   orders o ON o.user_id = u.id
WHERE  u.status   = 'active'
  AND  o.status   = 'paid'
ORDER  BY u.id, o.id
LIMIT  5000;   -- application groups results by user_id
```

```python
# GOOD 2: Batch fetch with = ANY() — PostgreSQL array parameter
# Useful when you already have the parent IDs in memory

import psycopg2

conn = psycopg2.connect(host='localhost', dbname='ecommerce',
                        user='app_user', password='password123')
cur = conn.cursor()

# Query 1: fetch parent records
cur.execute("SELECT id, email FROM users WHERE status = 'active' LIMIT 1000")
users = cur.fetchall()
user_ids = [row[0] for row in users]

# Query 2: fetch all child records in ONE query using = ANY()
# $1::bigint[] binds the Python list as a PostgreSQL bigint array
cur.execute(
    "SELECT user_id, id AS order_id, status, total_amount "
    "FROM orders "
    "WHERE user_id = ANY(%s) AND status = 'paid' "
    "ORDER BY user_id, id",
    (user_ids,)   # psycopg2 adapts Python list to PG array
)
orders = cur.fetchall()

# Group orders by user_id in application memory (O(n) dictionary)
from collections import defaultdict
orders_by_user = defaultdict(list)
for user_id, order_id, status, total_amount in orders:
    orders_by_user[user_id].append({
        'order_id': order_id,
        'status': status,
        'total_amount': total_amount
    })

results = [
    {'user_id': uid, 'email': email, 'orders': orders_by_user[uid]}
    for uid, email in users
]
# Total: 2 queries regardless of how many users
```

```sql
-- GOOD 3: Batch size considerations for = ANY()
-- For very large parent sets (>10k IDs), break into batches of 1k-5k:
-- SELECT ... WHERE user_id = ANY($1::bigint[]) -- $1 = first 5000 IDs
-- SELECT ... WHERE user_id = ANY($1::bigint[]) -- $1 = next 5000 IDs
-- etc.

-- Large arrays bind efficiently but the IN list in the planner has limits.
-- PostgreSQL handles = ANY($1::bigint[]) more efficiently than IN (1,2,3,...)
-- for large arrays (the array is passed as a bind parameter, not inlined).
```

## Why It Matters

- **Network latency multiplier**: Each database round trip within a VPC takes 0.5–2 ms. 1,000 queries = 0.5–2 seconds of pure network overhead. A single JOIN eliminates this entirely.
- **pgBouncer transaction mode**: Each query is a separate transaction in pgBouncer transaction mode. 1,000 queries = 1,000 connection checkouts from the pool, increasing pool contention.
- **= ANY() vs IN()**: `WHERE id = ANY($1::bigint[])` binds the array as a single parameter (efficient for large lists). `WHERE id IN (1,2,...,1000)` inlines 1,000 values into the SQL string (inefficient for large lists, plan not cached).
- **JOIN vs application grouping**: For complex aggregation or multi-level nesting, a JOIN with application-side grouping is often clearer and more flexible than multiple IN queries.
- **Aurora-specific**: N+1 on Aurora readers can cause increased replication lag, as each of the 1,000 queries goes through the storage layer. A single JOIN is a single storage operation.

## EXPLAIN Notes

```sql
-- N+1 (1000 individual queries) vs single JOIN:
EXPLAIN (ANALYZE, BUFFERS)
SELECT u.id, u.email, o.id, o.status, o.total_amount
FROM users u
JOIN orders o ON o.user_id = u.id
WHERE u.status = 'active' AND o.status = 'paid'
ORDER BY u.id, o.id
LIMIT 5000;
```

```
Hash Join  (actual rows=5000 loops=1)
  Hash Cond: (o.user_id = u.id)
  ->  Index Scan using idx_orders_status on orders
        Index Cond: (status = 'paid')
  ->  Hash
        ->  Index Scan using idx_users_status on users
              Index Cond: (status = 'active')
  Buffers: shared hit=250
  Total time: 12.4 ms  ← vs 500-2000 ms for 1000 individual queries
```

## Aurora/RDS Notes

- **Aurora PostgreSQL**: N+1 queries on Aurora are especially costly — each query may involve Aurora storage I/O. A single JOIN reduces storage reads proportionally.
- **RDS Proxy**: N+1 through RDS Proxy means 1,000 connection multiplexing operations. Reduce to 1–2 queries to maximize proxy efficiency.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | `= ANY($1::bigint[])` binding fully supported |
| PostgreSQL 15 | Same |
| PostgreSQL 16 | Same |
| PostgreSQL 17 | Same |
| Aurora PostgreSQL | Same; single JOIN dramatically reduces Aurora storage I/O |
