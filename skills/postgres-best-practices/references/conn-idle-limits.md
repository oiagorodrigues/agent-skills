---
title: "Set idle_in_transaction_session_timeout to prevent lock-holding idle sessions"
impact: medium
tags: [idle-timeout, locks, transactions, performance, connections]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Set idle_in_transaction_session_timeout to prevent lock-holding idle sessions

## Problem

A PostgreSQL session in the `idle in transaction` state has an open transaction and may be holding row locks, preventing other transactions from proceeding. This happens when an application opens a transaction, performs some work, then pauses (waiting for user input, a slow API call, or due to a bug) without committing or rolling back. By default, PostgreSQL waits indefinitely. `idle_in_transaction_session_timeout` terminates these sessions automatically, releasing their locks.
a
## Bad Example

```sql
-- BAD: No timeout configured (PostgreSQL default — wait forever)
-- SHOW idle_in_transaction_session_timeout;  → '0' (disabled)

-- A session opens a transaction and then goes idle (e.g., due to application bug,
-- network partition, or awaiting user input between transaction steps):

-- Session A (Python application):
-- conn.autocommit = False
-- cur.execute("SELECT * FROM orders WHERE id = $1 FOR UPDATE", (42,))
-- # Application hangs here — waiting for external API response for 10 minutes
-- # Row 42 in orders is locked for the entire 10 minutes
-- # All other sessions trying to update order 42 are blocked

-- This situation is visible in pg_stat_activity:
-- state = 'idle in transaction', wait_event = NULL, transaction open for 10 min
```

## Good Example

```sql
-- GOOD: Set timeouts to prevent stuck sessions from holding locks indefinitely

-- idle_in_transaction_session_timeout: terminate sessions idle IN a transaction
-- This is the most critical timeout — idle-in-transaction sessions hold locks.
-- Set at the database level (applies to all connections):
ALTER DATABASE ecommerce SET idle_in_transaction_session_timeout = '30s';

-- Or at the user level (for the application role):
ALTER ROLE app_user SET idle_in_transaction_session_timeout = '30s';

-- Or at the session level (overrides database/role defaults):
SET idle_in_transaction_session_timeout = '30000';  -- milliseconds

-- statement_timeout: terminate individual queries running longer than N ms
-- Prevents runaway queries from consuming resources indefinitely
ALTER DATABASE ecommerce SET statement_timeout = '30s';
-- Per-role override for admin/reporting users who need longer queries:
ALTER ROLE reporting_user SET statement_timeout = '300s';  -- 5 minutes

-- idle_session_timeout (PostgreSQL 14+): terminate sessions that are idle
-- (not in a transaction) for longer than N. Useful for Lambda-style workloads.
ALTER DATABASE ecommerce SET idle_session_timeout = '600s';  -- 10 minutes
-- (Not set by default — only add if you want to reclaim idle connections)

-- lock_timeout: fail fast rather than waiting indefinitely for a lock
SET lock_timeout = '10s';  -- fail if we can't acquire a lock within 10 seconds
-- Prevents cascading lock waits from blocking the entire application
```

```sql
-- Monitor idle-in-transaction sessions:
SELECT
  pid,
  usename,
  application_name,
  client_addr,
  state,
  wait_event,
  EXTRACT(epoch FROM (NOW() - state_change)) AS idle_in_txn_seconds,
  LEFT(query, 100) AS last_query
FROM   pg_stat_activity
WHERE  state = 'idle in transaction'
ORDER  BY idle_in_txn_seconds DESC;

-- Terminate a specific idle-in-transaction session:
SELECT pg_terminate_backend(12345);  -- replace with actual pid
```

```ini
# Set in postgresql.conf (or via RDS parameter group):
idle_in_transaction_session_timeout = 30000   # 30 seconds (value in ms)
statement_timeout                   = 30000   # 30 seconds
idle_session_timeout                = 600000  # 10 minutes (PG 14+)
lock_timeout                        = 10000   # 10 seconds (set per session, not globally)
```

## Why It Matters

- **Lock escalation**: An `idle in transaction` session holds all locks acquired during the transaction. If it locks a popular row (e.g., `orders.id = 1`), every other session that needs to write that row queues up — leading to a cascade of blocked queries.
- **Connection exhaustion**: Idle-in-transaction sessions occupy connection slots without doing useful work. On a database near `max_connections`, a few stuck sessions can prevent new connections.
- **Statement timeout vs idle_in_transaction_session_timeout**: `statement_timeout` terminates long-running queries. `idle_in_transaction_session_timeout` terminates sessions that are between queries but still inside a transaction. Both are needed.
- **`idle_session_timeout` (PG 14+)**: Terminates sessions that are completely idle (not in a transaction). Useful for cleaning up stale connections from dead Lambda invocations or crashed application instances.
- **Application retry**: Applications should handle `ERROR: terminating connection due to idle-in-transaction timeout` (error code `57P05`) by retrying the transaction from the beginning.

## Aurora/RDS Notes

- **RDS PostgreSQL**: Set `idle_in_transaction_session_timeout` via the parameter group. The parameter name is the same. RDS does not set this by default — you must configure it.
- **Aurora PostgreSQL**: Same configuration as RDS. Aurora also cleans up connections on the proxy side if using RDS Proxy (`IdleClientTimeout` parameter on the proxy).
- **RDS Proxy + idle_in_transaction_session_timeout**: RDS Proxy has its own `IdleClientTimeout` (default: 1,800 seconds). Set the PostgreSQL timeout to a shorter value so the database cleans up before the proxy does.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | `idle_session_timeout` parameter added |
| PostgreSQL 15 | Same |
| PostgreSQL 16 | Same |
| PostgreSQL 17 | Same |
| Aurora PostgreSQL | Same as community; also configure `IdleClientTimeout` on RDS Proxy |
