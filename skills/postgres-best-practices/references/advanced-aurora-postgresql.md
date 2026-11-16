---
title: "Aurora PostgreSQL architecture differences and Aurora-specific features"
impact: critical
tags: [aurora-postgresql, storage-layer, serverless, global-database, aurora-specific]
applies_to: [aurora-postgresql]
---

# Aurora PostgreSQL architecture differences and Aurora-specific features

## Problem

Aurora PostgreSQL is not a drop-in replacement for community PostgreSQL — it has a fundamentally different storage architecture, Aurora-specific extensions, different operational behaviors, and AWS-managed features (IAM auth, fast cloning, Serverless v2) that don't exist in community PostgreSQL. Understanding these differences prevents misapplication of community PostgreSQL tuning advice and unlocks Aurora-specific capabilities.

## Aurora PostgreSQL Storage Architecture

```
Community PostgreSQL:
  PostgreSQL process → page cache (shared_buffers) → local SSD
  - Each instance has its own storage
  - Vacuum causes I/O contention with live queries
  - Storage must be provisioned; not auto-scaling

Aurora PostgreSQL:
  PostgreSQL process → page cache (shared_buffers) → Aurora Storage Layer
                                                        (distributed, 6-way replicated, 3 AZ)
  - Storage is shared between writer and all readers
  - Vacuum I/O does not compete with read queries (different I/O path)
  - Storage auto-scales (no over-provisioning needed)
  - Replicas are near-instant to add (no data copying)
  - Failover: new writer resumes from last LSN (~30 seconds)
```

## Aurora PostgreSQL Specific Extensions

```sql
-- Available Aurora PostgreSQL extensions (not in community PostgreSQL):

-- aurora_stat_utils: Aurora-specific statistics
CREATE EXTENSION IF NOT EXISTS aurora_stat_utils;

-- Check Aurora-specific storage stats:
SELECT * FROM aurora_stat_dml_activity();   -- DML activity per table
SELECT * FROM aurora_stat_wait_activity();  -- Aurora wait events

-- Aurora version:
SELECT aurora_version();   -- Returns Aurora-specific version (e.g., '3.04.0')
SELECT version();          -- Returns community PG version (e.g., 'PostgreSQL 15.4')

-- aws_s3: Load data from S3 directly into Aurora PostgreSQL
CREATE EXTENSION IF NOT EXISTS aws_s3 CASCADE;

-- Import from S3:
SELECT aws_s3.table_import_from_s3(
  'orders',
  'id,user_id,status,total_amount,created_at',
  '(FORMAT CSV, HEADER true)',
  aws_commons.create_s3_uri('my-bucket', 'orders/export.csv', 'us-east-1')
);

-- Export to S3:
SELECT * FROM aws_s3.query_export_to_s3(
  'SELECT * FROM orders WHERE status = ''paid''',
  aws_commons.create_s3_uri('my-bucket', 'exports/paid_orders.csv', 'us-east-1'),
  options := '(FORMAT CSV, HEADER true)'
);

-- aws_lambda: Invoke Lambda functions from PostgreSQL
CREATE EXTENSION IF NOT EXISTS aws_lambda CASCADE;
SELECT aws_lambda.invoke(
  aws_commons.create_lambda_function_arn('my-function', 'us-east-1'),
  '{"action": "send_email", "user_id": 42}'::json
);
```

## Aurora Serverless v2

```
Aurora Serverless v2 (ASv2):
  - Scales in units of Aurora Capacity Units (ACUs)
  - 1 ACU = ~2 GB RAM
  - Scales from min to max ACUs based on database load
  - Scale-up: within seconds (no connection interruption)
  - Scale-down: gradual (over minutes)
  - Cost: pay per ACU-hour used (not provisioned capacity)

Recommended settings:
  min_capacity: 0.5 ACU (minimum — can scale to 0 with auto-pause)
  max_capacity: set to peak workload (start at 4–8 ACU, monitor and adjust)
  auto_pause: enable for dev/test (pauses after 5 minutes of inactivity)
              disable for production (pause/resume adds 20-30 seconds latency)

Key consideration: Serverless v2 does NOT support all features:
  - IAM authentication: supported
  - RDS Proxy: supported
  - Aurora Global Database: supported (ASv2 as secondary)
  - Parallel Query: not supported on ASv2
```

## Aurora Fast Cloning

```sql
-- Aurora database cloning: creates a full copy instantly using copy-on-write
-- From AWS CLI:
-- aws rds restore-db-cluster-to-point-in-time \
--   --source-db-cluster-identifier prod-ecommerce \
--   --db-cluster-identifier staging-ecommerce \
--   --restore-type copy-on-write \
--   --use-latest-restorable-time

-- The clone shares storage with the source until pages diverge
-- No data copying — instant creation regardless of database size
-- Writes to either cluster cause copy-on-write divergence
-- Cost: only pay for diverged (changed) storage blocks
```

## Aurora Global Database

```sql
-- Aurora Global Database: one primary cluster + up to 5 read-only secondary clusters
-- Cross-region replication lag: typically 1-2 seconds
-- Failover to secondary: < 1 minute (manual) or automatic with Global Database health monitoring

-- Check replication lag on a secondary region (run on secondary):
SELECT
  server_id,
  session_id,
  durable_lsn,
  highest_lsn_rcvd,
  feedback_epoch,
  feedback_xmin,
  oldest_read_view_lsn,
  visibility_lag_in_msec
FROM   aurora_global_db_instance_status()
ORDER  BY visibility_lag_in_msec DESC;
```

## Key Parameter Differences from Community PostgreSQL

```sql
-- Check Aurora-specific parameters:
SHOW rds.force_ssl;                    -- SSL enforcement
SHOW rds.logical_replication;         -- Logical replication (must be 1 for logical slots)
SHOW aurora.parallel_query;           -- Aurora Parallel Query (provisioned only)

-- Parameters you CANNOT change on Aurora (managed by AWS):
-- wal_level: always 'logical' (or 'replica') — cannot set to 'minimal'
-- max_wal_senders: managed by Aurora
-- archive_mode: managed by Aurora

-- Recommended Aurora parameter group settings:
-- random_page_cost = 1.1  (Aurora storage has low random I/O cost)
-- effective_cache_size = 75% of instance RAM
-- shared_buffers = 25% of instance RAM (Aurora manages I/O differently)
-- work_mem = RAM / max_connections / 4  (careful — set too high and OOM is possible)
```

## Aurora PostgreSQL Version Compatibility

| Aurora PG Version | Community PG Version | Key Features |
|------------------|---------------------|--------------|
| Aurora PG 14.x   | PostgreSQL 14.x     | Logical replication improvements |
| Aurora PG 15.x   | PostgreSQL 15.x     | MERGE statement, pg_walinspect |
| Aurora PG 16.x   | PostgreSQL 16.x     | Logical replication from standby |
| Aurora PG 17.x   | PostgreSQL 17.x     | Incremental backup, COPY ON_ERROR |

Note: Aurora typically lags community PostgreSQL releases by 3–6 months.

## Why It Matters

- **Storage architecture**: Aurora's shared distributed storage means readers see writes almost immediately (< 100 ms lag). Community PostgreSQL streaming replication has higher lag because full WAL streams must be transferred and applied.
- **Vacuum I/O**: On community PostgreSQL, vacuum reads and writes pages competing with live queries. On Aurora, vacuum writes go to a different I/O path — dramatically reducing vacuum's impact on query latency.
- **Fast clone**: Aurora cloning creates a staging/dev copy of a TB-scale production database in seconds. Community PostgreSQL `pg_dump` + restore would take hours.
- **`aurora_version()` vs `version()`**: Always check both on Aurora. `version()` returns the community PG version; `aurora_version()` returns the Aurora-specific version. Some Aurora-specific extensions and behaviors depend on the Aurora version, not just the PG version.
