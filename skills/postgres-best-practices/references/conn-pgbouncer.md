---
title: "Use pgBouncer for connection pooling; understand transaction mode limitations"
impact: critical
tags: [pgbouncer, connection-pooling, prepared-statements, performance, connections]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Use pgBouncer for connection pooling; understand transaction mode limitations

## Problem

PostgreSQL creates a new OS process (or thread in PG 17+) for each client connection. Each connection consumes 5–10 MB of RAM and CPU for connection setup. A production application with 500 app instances × 10 connections each = 5,000 PostgreSQL connections — far exceeding PostgreSQL's default `max_connections = 100` and even RDS's maximum of 400–5,000 (depending on instance class). Without a connection pooler, applications get `FATAL: sorry, too many clients already` errors under load.

## Bad Example

```
# BAD: Application connects directly to PostgreSQL
# Each of 500 app instances holds 10 persistent connections
# Total: 5,000 connections to a PostgreSQL instance with max_connections=200

Application Tier (500 instances)
  ↓ 5,000 direct connections
PostgreSQL (max_connections=200)
  → FATAL: sorry, too many clients already
```

```sql
-- Check current connection count (run this on PostgreSQL):
SELECT COUNT(*) AS active_connections
FROM   pg_stat_activity
WHERE  state IS NOT NULL;

-- Check the limit:
SHOW max_connections;
```

## Good Example

```
# GOOD: pgBouncer sits between the application and PostgreSQL
# pgBouncer maintains a small pool of server connections
# Applications connect to pgBouncer on port 6432

Application Tier (500 instances, 10 conn each = 5,000 client connections to pgBouncer)
  ↓
pgBouncer (max_client_conn=5000, pool_size=50 per database+user pair)
  ↓ 50 persistent server connections
PostgreSQL (max_connections=200, only 50 used by pgBouncer + reserved for superuser)
```

```ini
# pgbouncer.ini
[databases]
ecommerce = host=127.0.0.1 port=5432 dbname=ecommerce

[pgbouncer]
listen_port     = 6432
listen_addr     = 0.0.0.0
auth_type       = md5
auth_file       = /etc/pgbouncer/userlist.txt

# Pooling mode — choose carefully:
pool_mode       = transaction    ; fastest, but has limitations (see below)
# pool_mode     = session        ; safest, one server conn per client session
# pool_mode     = statement      ; most restrictive, only for simple queries

max_client_conn = 5000           ; max connections from application
default_pool_size = 50           ; server connections per database+user pair

# Required in transaction mode to reset session state between uses:
server_reset_query = DISCARD ALL

# Idle connection cleanup:
server_idle_timeout = 600        ; release idle server connections after 10 min
client_idle_timeout = 0          ; keep client connections (managed by app)
```

### Pooling Mode Comparison

| Mode | Session State | Prepared Statements | SET Variables | Advisory Locks | Performance |
|------|--------------|--------------------|--------------------|---------------|-------------|
| **Session** | Preserved | Work fine | Work fine | Work fine | Low pool efficiency |
| **Transaction** | Cleared between transactions | **BROKEN** | **BROKEN** | **BROKEN** | Best efficiency |
| **Statement** | N/A | Not supported | Not supported | Not supported | Very restricted |

### Transaction Mode: Prepared Statement Pitfall

```python
# BAD: Using server-side prepared statements with pgBouncer in transaction mode
# psycopg2 uses protocol-level prepared statements by default

import psycopg2

conn = psycopg2.connect(host='pgbouncer', port=6432, dbname='ecommerce',
                        user='app_user', password='password123')
cur = conn.cursor()

# First transaction: psycopg2 sends PREPARE to server connection A
cur.execute("SELECT id FROM orders WHERE status = %s", ('paid',))

# pgBouncer releases server connection A back to the pool after COMMIT.
# Next transaction may get server connection B — which has no prepared statement.

cur.execute("SELECT id FROM orders WHERE status = %s", ('pending',))
# ERROR: prepared statement "..." does not exist
```

```python
# GOOD option 1: Disable prepared statements in the driver
conn = psycopg2.connect(host='pgbouncer', port=6432, dbname='ecommerce',
                        user='app_user', password='password123',
                        options='-c default_transaction_isolation=read\ committed')
# Use psycopg2 with prepare_threshold=None to disable server-side PS
# Or use asyncpg: asyncpg.connect(statement_cache_size=0)

# GOOD option 2: Use pgBouncer 1.21+ which tracks prepared statement state
# and handles the routing transparently with track_extra_parameters

# GOOD option 3: Switch to session mode if prepared statements are essential
# pool_mode = session   (in pgbouncer.ini)
```

## Why It Matters

- **Connection overhead**: PostgreSQL forks a new backend process per connection. 5,000 connections = 5,000 processes, each consuming ~5–10 MB RAM → 25–50 GB just for connection overhead.
- **max_connections on RDS**: RDS sets `max_connections` based on instance class RAM: approximately `DBInstanceClassMemory / 9,531,392`. A `db.t3.medium` (4 GB RAM) allows only ~420 connections. A `db.r6g.large` (16 GB RAM) allows ~1,700.
- **Transaction mode efficiency**: In transaction mode, a server connection is only held during an active transaction — for a typical OLTP app with 1–5 ms transactions, one server connection can serve hundreds of application connections.
- **Session mode safety**: If your application uses `SET search_path`, advisory locks, `LISTEN/NOTIFY`, or session-level prepared statements, use session mode. Transaction mode will break these silently.

## Aurora/RDS Notes

- **Aurora PostgreSQL**: AWS recommends **RDS Proxy** instead of self-managed pgBouncer for Aurora. RDS Proxy is a managed service that handles Aurora failover transparently, multiplexes connections, and requires no EC2 instance to manage. See `conn-rds-proxy.md`.
- **RDS PostgreSQL**: pgBouncer is not managed by AWS — run it on an EC2 instance or ECS container in the same VPC as the RDS instance. Add the pgBouncer security group to the RDS inbound rules.
- **pgBouncer on RDS**: For RDS for PostgreSQL (not Aurora), pgBouncer is a valid pooling option. For Aurora, prefer RDS Proxy.

## Version Notes

| Version | Behavior |
|---------|----------|
| pgBouncer 1.18 | `idle_transaction_timeout` added |
| pgBouncer 1.21 | `track_extra_parameters` for limited prepared statement support in transaction mode |
| pgBouncer 1.22 | Improved `DISCARD ALL` handling |
| PostgreSQL 14–17 | Connection handling unchanged (process-per-connection model) |
| Aurora PostgreSQL | Use RDS Proxy instead of pgBouncer |
