---
title: "Monitor and enforce PostgreSQL connection limits"
impact: high
tags: [connections, max-connections, pg-stat-activity, performance, operations]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Monitor and enforce PostgreSQL connection limits

## Problem

PostgreSQL has a hard limit (`max_connections`) on simultaneous client connections. Exceeding it produces `FATAL: sorry, too many clients already` — all subsequent connection attempts fail until existing connections close. Each connection also consumes memory (the `work_mem` × sort operations, shared memory buffers, etc.). Running at or near `max_connections` degrades query planning performance and increases deadlock risk. Monitoring, reserving capacity for administration, and using a connection pooler are essential at scale.

## Bad Example

```sql
-- BAD: Application creates connections without a pooler, hitting max_connections
-- 300 app connections on an instance with max_connections = 100
-- Result: FATAL: sorry, too many clients already

-- Developer attempts to investigate while the database is at capacity:
-- psql: FATAL: sorry, too many clients already
-- Unable to connect even with superuser — reserved connections exhausted too
```

```python
# BAD: Django/SQLAlchemy default pool without connection limit matching Postgres
# Each worker process in gunicorn creates its own pool
# 8 gunicorn workers × 10 pool_size = 80 connections per dyno
# 10 dynos × 80 = 800 connections — far exceeds max_connections on small RDS
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'OPTIONS': {
            # No CONN_MAX_AGE or pool_size constraint — each thread gets a connection
        }
    }
}
```

## Good Example

```sql
-- Check current connection count and state
SELECT
  state,
  wait_event_type,
  wait_event,
  COUNT(*) AS connection_count
FROM   pg_stat_activity
GROUP  BY state, wait_event_type, wait_event
ORDER  BY connection_count DESC;

-- Check the configured limit
SHOW max_connections;

-- Check reserved connections (available since PostgreSQL 14)
SHOW reserved_connections;     -- PostgreSQL 16+
SHOW superuser_reserved_connections;  -- PostgreSQL 14/15

-- Find long-running idle connections (candidates for termination)
SELECT pid, usename, application_name, client_addr, state,
       EXTRACT(epoch FROM (NOW() - state_change)) AS idle_seconds
FROM   pg_stat_activity
WHERE  state = 'idle'
  AND  state_change < NOW() - INTERVAL '10 minutes'
ORDER  BY idle_seconds DESC;
```

```sql
-- Cancel a query on a connection (sends SIGINT — graceful)
SELECT pg_cancel_backend(pid)
FROM   pg_stat_activity
WHERE  pid <> pg_backend_pid()
  AND  state = 'active'
  AND  query_start < NOW() - INTERVAL '5 minutes';

-- Terminate a connection (sends SIGTERM — forceful, use as last resort)
SELECT pg_terminate_backend(pid)
FROM   pg_stat_activity
WHERE  pid <> pg_backend_pid()
  AND  state = 'idle'
  AND  state_change < NOW() - INTERVAL '30 minutes';
```

```sql
-- Connection limit sizing formula (community PostgreSQL):
-- max_connections = min(4 × vCPU_count, RAM_GB × 100)
-- For a 4-vCPU, 32 GB RAM instance:
--   4 × 4 = 16 (too low for most apps)
--   32 × 100 = 3,200 (theoretical max)
--   Practical recommendation: 200–400 with a connection pooler

-- Reserve connections for superuser (to allow admin access when db is full):
-- superuser_reserved_connections = 3   (default — always reserve for emergencies)
-- PostgreSQL 16+: reserved_connections = 5  (for rds_superuser and monitoring)
```

```sql
-- PostgreSQL 16+: reserved_connections for non-superuser roles
-- This allows monitoring users to connect even when max_connections is reached
SHOW reserved_connections;    -- New in PG 16, replaces part of superuser_reserved

-- Grant the reserved connection slot to a monitoring user:
-- ALTER ROLE monitoring_user CONNECTION LIMIT -1;  -- unlimited (use carefully)
```

### RDS max_connections Formula

```sql
-- RDS PostgreSQL sets max_connections dynamically based on instance RAM:
-- max_connections = LEAST(DBInstanceClassMemory / 9531392, 5000)
--
-- Instance class      RAM       max_connections
-- db.t3.micro         1 GB      34
-- db.t3.small         2 GB      68
-- db.t3.medium        4 GB      420
-- db.r6g.large        16 GB     1,700
-- db.r6g.4xlarge      128 GB    5,000 (capped)
--
-- Check your instance's actual limit:
SHOW max_connections;
```

## Why It Matters

- **Hard failure**: Unlike many database errors that degrade gracefully, exceeding `max_connections` is a hard failure — new connections are refused entirely.
- **Memory per connection**: Each PostgreSQL connection uses approximately 5–10 MB of RAM for the backend process (pre-fork), plus `work_mem` per sort operation inside that connection. At 500 connections × 10 MB = 5 GB just for connection overhead.
- **`reserved_connections` (PG 16+)**: PostgreSQL 16 introduced `reserved_connections` that works like `superuser_reserved_connections` but for specified roles. This allows monitoring and admin tools to always connect even when the database is at capacity.
- **Always use a pooler**: For any production application, use pgBouncer or RDS Proxy. Set `max_connections` conservatively (enough for the pooler + monitoring + superuser) rather than matching the number of application threads.

## Aurora/RDS Notes

- **Aurora PostgreSQL**: Aurora sets `max_connections` based on the instance class. You can override it in the parameter group, but increasing it beyond the formula causes memory pressure. Use RDS Proxy instead.
- **RDS PostgreSQL**: The formula `DBInstanceClassMemory / 9,531,392` is set in the default parameter group and cannot be overridden with a custom value that exceeds it. Create a custom parameter group to reduce `max_connections` if needed.
- **rds_superuser**: On RDS, the `rds_superuser` role always has reserved connection slots via `superuser_reserved_connections` (default: 3). Ensure your admin user has this role.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | `superuser_reserved_connections` available |
| PostgreSQL 15 | Same |
| PostgreSQL 16 | `reserved_connections` parameter added for non-superuser reserved slots |
| PostgreSQL 17 | Same |
| Aurora PostgreSQL | `max_connections` set by instance class; use RDS Proxy for pooling |
