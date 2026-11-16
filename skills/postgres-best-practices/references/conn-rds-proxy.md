---
title: "Use RDS Proxy for Aurora PostgreSQL connection pooling and failover"
impact: high
tags: [rds-proxy, connection-pooling, aurora, lambda, failover, connections]
applies_to: [aurora-postgresql, rds-postgresql]
---

# Use RDS Proxy for Aurora PostgreSQL connection pooling and failover

## Problem

Applications connecting directly to Aurora PostgreSQL or RDS PostgreSQL face two problems at scale: (1) connection exhaustion — Lambda functions or microservices can create thousands of short-lived connections that exceed `max_connections`, and (2) slow failover — direct connections to the writer endpoint must reconnect after an Aurora failover (30–60 seconds). RDS Proxy solves both: it pools connections to Aurora and maintains persistent server-side connections through failover events.

## Bad Example

```python
# BAD: Lambda function connecting directly to Aurora PostgreSQL
# Each Lambda invocation creates a new connection.
# 1,000 concurrent Lambdas = 1,000 new connections to Aurora.
# Aurora db.r6g.large max_connections ≈ 1,700 — easily exhausted.

import psycopg2

def handler(event, context):
    # New connection on every invocation — never reused between Lambda cold starts
    conn = psycopg2.connect(
        host='mydb.cluster-xxxxx.us-east-1.rds.amazonaws.com',
        port=5432,
        dbname='ecommerce',
        user='app_user',
        password='password123'
    )
    cur = conn.cursor()
    cur.execute("SELECT id FROM orders WHERE status = 'pending' LIMIT 10")
    rows = cur.fetchall()
    conn.close()
    return rows
```

```sql
-- On Aurora: check current connection count
SELECT COUNT(*) AS connections, state
FROM   pg_stat_activity
GROUP  BY state
ORDER  BY connections DESC;
```

## Good Example

```python
# GOOD: Connect through RDS Proxy endpoint
# RDS Proxy multiplexes 1,000 Lambda connections into ~50 Aurora connections
# Proxy handles Aurora failover transparently — no reconnection logic needed

import psycopg2
import boto3

def handler(event, context):
    conn = psycopg2.connect(
        host='mydb.proxy-xxxxx.us-east-1.rds.amazonaws.com',   # Proxy endpoint
        port=5432,
        dbname='ecommerce',
        user='app_user',
        password='password123',
        sslmode='verify-full',    # RDS Proxy requires SSL
        sslrootcert='/var/task/rds-ca-bundle.pem'
    )
    cur = conn.cursor()
    cur.execute("SELECT id FROM orders WHERE status = %s LIMIT 10", ('pending',))
    rows = cur.fetchall()
    conn.close()
    return rows
```

```hcl
# Terraform: RDS Proxy configuration for Aurora PostgreSQL
resource "aws_db_proxy" "ecommerce_proxy" {
  name                   = "ecommerce-proxy"
  debug_logging          = false
  engine_family          = "POSTGRESQL"
  idle_client_timeout    = 1800
  require_tls            = true
  role_arn               = aws_iam_role.rds_proxy_role.arn
  vpc_security_group_ids = [aws_security_group.proxy_sg.id]
  vpc_subnet_ids         = aws_subnet.private[*].id

  auth {
    auth_scheme = "SECRETS"
    description = "App user credentials"
    iam_auth    = "DISABLED"
    secret_arn  = aws_secretsmanager_secret.db_credentials.arn
  }
}

resource "aws_db_proxy_default_target_group" "ecommerce" {
  db_proxy_name = aws_db_proxy.ecommerce_proxy.name

  connection_pool_config {
    connection_borrow_timeout    = 120
    max_connections_percent      = 70   # Use at most 70% of max_connections
    max_idle_connections_percent = 50
  }
}

resource "aws_db_proxy_target" "aurora_cluster" {
  db_cluster_identifier = aws_rds_cluster.ecommerce.id
  db_proxy_name         = aws_db_proxy.ecommerce_proxy.name
  target_group_name     = aws_db_proxy_default_target_group.ecommerce.name
}
```

```python
# GOOD: Python retry pattern for Aurora failover through RDS Proxy
# RDS Proxy holds client connections during failover — retry with exponential backoff
import psycopg2
import time

def execute_with_retry(query, params=None, max_retries=3):
    for attempt in range(max_retries):
        try:
            conn = psycopg2.connect(
                host='mydb.proxy-xxxxx.us-east-1.rds.amazonaws.com',
                port=5432, dbname='ecommerce',
                user='app_user', password='password123',
                sslmode='require',
                connect_timeout=10
            )
            cur = conn.cursor()
            cur.execute(query, params)
            result = cur.fetchall()
            conn.commit()
            conn.close()
            return result
        except psycopg2.OperationalError as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)   # 1s, 2s, 4s
                continue
            raise
```

### RDS Proxy Limitations

```
RDS Proxy does NOT support:
  - LISTEN / NOTIFY           (publish/subscribe messaging)
  - Session-level SET state   (SET search_path persists on server conn, not client)
  - Multi-statement strings   ("SELECT 1; SELECT 2" in one call)
  - pg_advisory_lock          (session-scoped advisory locks won't survive proxy reset)
  - COPY TO/FROM STDIN        (binary protocol not supported through proxy)
  - Cancel queries            (pg_cancel_backend not routable through proxy)

RDS Proxy DOES support:
  - Protocol-level prepared statements (parameterized queries)
  - Transactions (BEGIN/COMMIT/ROLLBACK)
  - SSL/TLS (required)
  - IAM authentication
```

## Why It Matters

- **Connection multiplexing**: RDS Proxy multiplexes thousands of client connections into a small pool of server connections. 1,000 Lambda connections → 50 Aurora server connections.
- **Fast failover**: RDS Proxy detects Aurora writer failover in seconds (vs 30–60 seconds for direct DNS failover). Client connections are held by the proxy and resumed on the new writer without reconnect errors.
- **Managed service**: No EC2 instance to maintain. Proxy is Multi-AZ, highly available, and scales automatically.
- **`MaxConnectionsPercent`**: Controls what fraction of `max_connections` the proxy may use. Set to 70–80% to reserve capacity for superuser and monitoring connections.
- **`IdleClientTimeout`**: Closes client connections that have been idle for the configured duration. Prevents Lambda-style connection leaks.

## Aurora/RDS Notes

- **Aurora PostgreSQL**: RDS Proxy is the recommended pooling solution for Aurora. It is Aurora-aware — it knows which instance is the current writer and routes write connections correctly after failover.
- **RDS PostgreSQL (non-Aurora)**: RDS Proxy works for RDS PostgreSQL too but does not provide the same failover benefits as Aurora (RDS failover involves DNS propagation, which proxy helps with but cannot fully hide).
- **IAM Authentication**: RDS Proxy supports IAM database authentication. Generate a token with `aws rds generate-db-auth-token` and use it instead of a password. Token validity: 15 minutes.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14–17 | RDS Proxy supported on all versions on RDS/Aurora |
| Aurora PostgreSQL 14+ | RDS Proxy supported; failover handled transparently |
