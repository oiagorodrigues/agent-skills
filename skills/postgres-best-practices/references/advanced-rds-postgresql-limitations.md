---
title: "RDS PostgreSQL limitations and workarounds"
impact: high
tags: [rds-postgresql, limitations, superuser, parameter-group, rds-specific]
applies_to: [rds-postgresql, aurora-postgresql]
---

# RDS PostgreSQL limitations and workarounds

## Problem

RDS PostgreSQL is a managed service — AWS owns the underlying OS and PostgreSQL process. As a result, certain operations that are possible on self-managed PostgreSQL are restricted or unavailable on RDS. Understanding these limitations prevents failed deployments and forces the use of proper RDS-native alternatives.

## What You Cannot Do on RDS PostgreSQL

```sql
-- 1. NO true superuser access
-- The master user is rds_superuser, NOT a true PostgreSQL superuser
-- rds_superuser can do most things but not:
--   CREATE EXTENSION that requires superuser (some extensions only)
--   Modify system catalogs directly
--   Bypass Row Level Security (unless BYPASSRLS is granted explicitly)

-- What you have instead:
\du rds_superuser  -- shows what rds_superuser can and cannot do
-- rds_superuser has: CREATEROLE, CREATEDB, LOGIN, REPLICATION
-- but NOT: SUPERUSER attribute

-- 2. NO direct pg_hba.conf editing
-- pg_hba.conf controls host-based authentication
-- On RDS, use rds.force_ssl parameter to enforce SSL instead
-- IAM authentication replaces pg_hba.conf hostssl entries

-- 3. NO OS-level access
-- Cannot run shell commands, access the filesystem, or install OS packages
-- Cannot access /var/log/postgresql directly — use CloudWatch Logs export

-- 4. FILE operations are restricted
-- COPY TO/FROM with a server-side file path requires the file on the RDS server
-- Workaround: use COPY FROM STDIN (client-side) or aws_s3 extension

-- BAD (doesn't work on RDS):
COPY orders FROM '/tmp/orders.csv' WITH (FORMAT csv);
-- ERROR: must be superuser or a member of the pg_read_server_files role

-- GOOD (works on RDS):
-- Use psql \copy (client-side):
-- \copy orders FROM '/local/path/orders.csv' CSV HEADER

-- Or use aws_s3 extension (Aurora/RDS):
-- SELECT aws_s3.table_import_from_s3(...)

-- 5. shared_preload_libraries requires parameter group change AND reboot
-- To add pg_stat_statements, pg_hint_plan, or auto_explain:

-- BAD: ALTER SYSTEM on RDS (parameter group changes override this):
ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements';
-- This works but is overridden by the parameter group at next restart

-- GOOD: Set via RDS parameter group in AWS Console or AWS CLI:
-- aws rds modify-db-parameter-group \
--   --db-parameter-group-name myapp-pg15 \
--   --parameters "ParameterName=shared_preload_libraries,ParameterValue=pg_stat_statements,ApplyMethod=pending-reboot"
-- aws rds reboot-db-instance --db-instance-identifier mydb
```

## Available Extensions on RDS PostgreSQL

```sql
-- Check available extensions:
SELECT name, default_version, comment
FROM   pg_available_extensions
ORDER  BY name;

-- Key extensions available on RDS PostgreSQL (sample):
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;   -- query performance stats
CREATE EXTENSION IF NOT EXISTS pg_hint_plan;         -- optimizer hints (requires shared_preload_libraries)
CREATE EXTENSION IF NOT EXISTS auto_explain;         -- auto log slow query plans (requires shared_preload_libraries)
CREATE EXTENSION IF NOT EXISTS pg_trgm;              -- trigram indexes for LIKE
CREATE EXTENSION IF NOT EXISTS pgcrypto;             -- cryptographic functions
CREATE EXTENSION IF NOT EXISTS uuid-ossp;            -- UUID generation
CREATE EXTENSION IF NOT EXISTS postgis;              -- geospatial functions
CREATE EXTENSION IF NOT EXISTS pg_partman;           -- partition management
CREATE EXTENSION IF NOT EXISTS pgstattuple;          -- bloat analysis
CREATE EXTENSION IF NOT EXISTS pg_repack;            -- online table reorg (RDS PG 13+, NOT Aurora)
CREATE EXTENSION IF NOT EXISTS dblink;               -- cross-database queries

-- Extensions NOT available on RDS:
-- pg_cron (available on RDS but requires parameter group setup)
-- Custom C extensions (no OS access to load .so files)
```

## RDS-Specific Roles and Authentication

```sql
-- rds_superuser: the master role on RDS
-- Similar to superuser but with restrictions listed above
-- Grant to trusted admin users:
GRANT rds_superuser TO my_admin_user;

-- rds_replication: allows logical replication
-- Required for logical replication subscriptions on RDS
GRANT rds_replication TO replication_user;

-- rds_password: allows BYPASSRLS (Row Level Security bypass)
-- Use carefully — only for roles that legitimately bypass RLS
-- GRANT rds_iam TO app_user;  -- enables IAM authentication for this user

-- rds_iam: allows IAM database authentication
GRANT rds_iam TO app_iam_user;
-- Generate token:
-- aws rds generate-db-auth-token \
--   --hostname db.xxxx.us-east-1.rds.amazonaws.com \
--   --port 5432 --username app_iam_user
```

## Common RDS Operations via AWS CLI

```bash
# Check RDS instance parameters:
aws rds describe-db-parameters \
  --db-parameter-group-name myapp-pg15 \
  --query 'Parameters[?ParameterName==`max_connections`]'

# Enable logical replication (requires restart):
aws rds modify-db-parameter-group \
  --db-parameter-group-name myapp-pg15 \
  --parameters "ParameterName=rds.logical_replication,ParameterValue=1,ApplyMethod=pending-reboot"

# Force reboot:
aws rds reboot-db-instance --db-instance-identifier mydb

# Enable CloudWatch log exports:
aws rds modify-db-instance \
  --db-instance-identifier mydb \
  --cloudwatch-logs-export-configuration '{"EnableLogTypes":["postgresql","upgrade"]}'

# Create a manual snapshot:
aws rds create-db-snapshot \
  --db-instance-identifier mydb \
  --db-snapshot-identifier mydb-snapshot-$(date +%Y%m%d)

# Restore to point in time:
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier mydb \
  --target-db-instance-identifier mydb-restored \
  --restore-time 2024-12-01T10:00:00Z

# Check RDS max_connections formula:
# max_connections = LEAST(DBInstanceClassMemory / 9531392, 5000)
```

## RDS Parameter Group Key Settings

```ini
# Recommended settings for a production RDS PostgreSQL instance:
max_connections = 200                      # adjust based on instance class and pooler usage
shared_buffers = {DBInstanceClassMemory*25/102400}  # 25% of RAM (RDS formula)
effective_cache_size = {DBInstanceClassMemory*75/102400}  # 75% of RAM
work_mem = 16384                           # 16 MB per sort operation (per query × sorts)
random_page_cost = 1.1                     # SSD-optimized (RDS uses EBS SSD)
log_min_duration_statement = 1000         # log queries > 1s
log_checkpoints = on
log_connections = off                      # noisy in production
log_disconnections = off
idle_in_transaction_session_timeout = 30000  # 30s
statement_timeout = 30000                    # 30s (override for specific users)
shared_preload_libraries = 'pg_stat_statements,auto_explain'  # requires restart
```

## Why It Matters

- **`rds_superuser` ≠ `superuser`**: Developers coming from self-managed PostgreSQL expect full superuser access. On RDS, `rds_superuser` has most capabilities but cannot bypass certain restrictions. Know the difference before planning a migration.
- **Parameter group vs ALTER SYSTEM**: On RDS, `ALTER SYSTEM` is technically allowed but parameter group settings take precedence at the instance level. Always use parameter groups for persistent parameter changes.
- **`shared_preload_libraries` requires restart**: Adding `pg_stat_statements`, `pg_hint_plan`, or `auto_explain` requires a parameter group change AND a reboot. Plan this during a maintenance window.

## Version Notes

| Version | Behavior |
|---------|----------|
| RDS PostgreSQL 14 | `pg_stat_statements`, `pg_hint_plan`, `auto_explain` available |
| RDS PostgreSQL 15 | `pg_partman`, `pg_repack` available |
| RDS PostgreSQL 16 | Same extensions available |
| RDS PostgreSQL 17 | Same; check AWS documentation for new extensions |
| Aurora PostgreSQL | Same limitations as RDS plus Aurora-specific extensions (aws_s3, aws_lambda) |
