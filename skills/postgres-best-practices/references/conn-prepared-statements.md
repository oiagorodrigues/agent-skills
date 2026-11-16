---
title: "Understand server-side prepared statements and their pgBouncer incompatibility"
impact: medium
tags: [prepared-statements, pgbouncer, performance, plan-cache, connections]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Understand server-side prepared statements and their pgBouncer incompatibility

## Problem

PostgreSQL prepared statements (`PREPARE ... AS`) store a query plan on the server, avoiding repeated parse and plan overhead for frequently executed queries. However, prepared statements are scoped to the **server connection**. When pgBouncer is in transaction mode, each transaction may be routed to a different server connection — and the prepared statement from the previous connection does not exist on the new one. This produces `ERROR: prepared statement "stmt" does not exist` silently at runtime and is one of the most common pgBouncer integration bugs.

## Bad Example

```sql
-- BAD: Using explicit server-side PREPARE with pgBouncer transaction mode

-- Session connects to pgBouncer (transaction mode), gets server connection A
PREPARE get_orders AS
  SELECT id, status, total_amount FROM orders WHERE user_id = $1;

-- First EXECUTE: works fine — still on server connection A
EXECUTE get_orders(42);

-- COMMIT: pgBouncer releases server connection A back to the pool

-- Next transaction: pgBouncer assigns server connection B
EXECUTE get_orders(43);
-- ERROR: prepared statement "get_orders" does not exist
-- (server connection B has never seen this PREPARE statement)
```

```python
# BAD: psycopg2 with pgBouncer in transaction mode
# psycopg2 uses protocol-level prepared statements by default (prepare_threshold=5)
# After 5 executions, psycopg2 sends a named Prepare to the server
# This breaks silently with pgBouncer transaction mode

import psycopg2
conn = psycopg2.connect("host=pgbouncer port=6432 dbname=ecommerce user=app_user")
cur = conn.cursor()

for i in range(100):
    # After 5 executions, psycopg2 promotes to a named prepared statement
    # On transaction 6+, pgBouncer may route to a different server connection
    # where the named statement does not exist → ERROR
    cur.execute("SELECT id FROM orders WHERE user_id = %s", (i,))
```

## Good Example

```sql
-- GOOD: Explicit SQL-level prepared statements (appropriate for session mode or direct connections)
PREPARE get_orders AS
  SELECT id, status, total_amount
  FROM   orders
  WHERE  user_id    = $1
    AND  status     = $2
  ORDER  BY created_at DESC
  LIMIT  $3;

-- Execute with actual values
EXECUTE get_orders(42, 'paid', 20);

-- Execute again — plan is cached, no re-parsing
EXECUTE get_orders(43, 'pending', 10);

-- Release when done
DEALLOCATE get_orders;
-- Or: DEALLOCATE ALL;

-- List all prepared statements in the current session:
SELECT name, statement, prepare_time, parameter_types
FROM   pg_prepared_statements;
```

```python
# GOOD: Disable server-side prepared statements in psycopg2 when using pgBouncer transaction mode
import psycopg2

conn = psycopg2.connect(
    host='pgbouncer', port=6432, dbname='ecommerce',
    user='app_user', password='password123'
)
# Disable automatic server-side prepared statements:
conn.autocommit = False
cur = conn.cursor()
# psycopg2 3.0+: use prepare_threshold=None to never promote to named PS
# psycopg2 2.x: use cursor.execute() directly — it uses unnamed (unnamed PS is safe)
```

```python
# GOOD: asyncpg with pgBouncer transaction mode — disable statement cache
import asyncpg

async def get_connection():
    return await asyncpg.connect(
        host='pgbouncer', port=6432, database='ecommerce',
        user='app_user', password='password123',
        statement_cache_size=0   # disable server-side prepared statement cache
    )
```

```sql
-- Generic plan vs custom plan (PostgreSQL 12+)
-- By default, PostgreSQL uses a generic plan after 5 executions of a prepared statement
-- For highly skewed data distributions, generic plans may be suboptimal.
-- Override with plan_cache_mode:

-- Force custom plan (re-plan every execution) — safer for skewed data
SET plan_cache_mode = 'force_custom_plan';

-- Force generic plan (always reuse the cached plan)
SET plan_cache_mode = 'force_generic_plan';

-- Default: auto (PostgreSQL decides based on cost)
SET plan_cache_mode = 'auto';
```

## Why It Matters

- **`PREPARE` is connection-scoped**: A prepared statement exists only on the server connection where it was created. pgBouncer transaction mode does not guarantee the same server connection across transactions.
- **Protocol-level vs SQL-level PS**: psycopg2, asyncpg, and most PostgreSQL drivers use the protocol-level extended query protocol for parameterized queries — this sends Parse/Bind/Execute messages. psycopg2 also promotes frequently-used queries to named prepared statements after a threshold number of executions, which triggers the pgBouncer problem.
- **Generic plan caching (PG 12+)**: PostgreSQL caches a generic plan (without specific parameter values) after 5 executions. For columns with skewed distributions (most orders have `status = 'paid'`), the generic plan may be suboptimal for rare values (`status = 'pending'`). Use `plan_cache_mode = 'force_custom_plan'` for highly selective queries.
- **Safe approach with pgBouncer transaction mode**: Use unnamed prepared statements (single-use, not cached on the server), or switch to session mode for applications that require server-side PS.

## Aurora/RDS Notes

- **Aurora PostgreSQL**: Same behavior as community PostgreSQL. If using RDS Proxy (recommended for Aurora), RDS Proxy supports protocol-level prepared statements (parameterized queries) but not SQL-level named `PREPARE` statements across connections.
- **RDS Proxy prepared statement support**: RDS Proxy does not route to the same server connection for named prepared statements. Use parameterized queries (protocol-level) rather than SQL-level `PREPARE`.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | `plan_cache_mode` available; `pg_prepared_statements` view available |
| PostgreSQL 15 | Same |
| PostgreSQL 16 | Same |
| PostgreSQL 17 | Same |
| pgBouncer 1.21+ | `track_extra_parameters` allows limited named PS support in transaction mode |
| Aurora PostgreSQL | Same as community; use parameterized queries with RDS Proxy |
