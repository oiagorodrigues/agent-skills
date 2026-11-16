---
title: "Enforce SSL/TLS with certificate verification for PostgreSQL connections"
impact: high
tags: [ssl, tls, security, encryption, rds, certificates]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Enforce SSL/TLS with certificate verification for PostgreSQL connections

## Problem

PostgreSQL supports SSL/TLS for encrypted connections, but the default `sslmode=prefer` in many drivers falls back to unencrypted connections if SSL negotiation fails — providing false security. In production, all connections should use `sslmode=require` or `sslmode=verify-full`. Without certificate verification, connections are encrypted but vulnerable to man-in-the-middle attacks. RDS and Aurora PostgreSQL support and encourage SSL with their own CA bundle.

## Bad Example

```python
# BAD: sslmode=disable — completely unencrypted connection in production
import psycopg2

conn = psycopg2.connect(
    host='mydb.xxxx.us-east-1.rds.amazonaws.com',
    dbname='ecommerce',
    user='app_user',
    password='password123',
    sslmode='disable'    # NEVER in production — all data transmitted in plaintext
)
```

```python
# BAD: sslmode=prefer — falls back to unencrypted if SSL negotiation fails
conn = psycopg2.connect(
    host='mydb.xxxx.us-east-1.rds.amazonaws.com',
    dbname='ecommerce',
    user='app_user',
    password='password123',
    sslmode='prefer'     # silently falls back to no encryption
)
```

## Good Example

```python
# GOOD: sslmode=verify-full — encrypted AND certificate verified
# Download the RDS CA bundle: https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem
import psycopg2

conn = psycopg2.connect(
    host='mydb.xxxx.us-east-1.rds.amazonaws.com',
    dbname='ecommerce',
    user='app_user',
    password='password123',
    sslmode='verify-full',
    sslrootcert='/etc/ssl/certs/rds-ca-bundle.pem'
)
```

```python
# GOOD: asyncpg with SSL verification
import asyncpg, ssl

ssl_context = ssl.create_default_context(
    cafile='/etc/ssl/certs/rds-ca-bundle.pem'
)
ssl_context.check_hostname = True
ssl_context.verify_mode = ssl.CERT_REQUIRED

conn = await asyncpg.connect(
    host='mydb.xxxx.us-east-1.rds.amazonaws.com',
    database='ecommerce',
    user='app_user',
    password='password123',
    ssl=ssl_context
)
```

```bash
# Download the AWS RDS CA bundle (includes all regional CAs):
curl -o /etc/ssl/certs/rds-ca-bundle.pem \
  https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem

# Verify connection certificate from command line:
psql "host=mydb.xxxx.us-east-1.rds.amazonaws.com \
      dbname=ecommerce user=app_user sslmode=verify-full \
      sslrootcert=/etc/ssl/certs/rds-ca-bundle.pem"
```

```sql
-- Server-side: enforce SSL for all connections (community PostgreSQL)
-- In postgresql.conf:
-- ssl = on
-- ssl_cert_file = 'server.crt'
-- ssl_key_file  = 'server.key'
-- ssl_ca_file   = 'root.crt'

-- In pg_hba.conf (enforce SSL for the app user from any host):
-- hostssl  ecommerce  app_user  0.0.0.0/0  scram-sha-256

-- Reject non-SSL connections entirely:
-- host     ecommerce  app_user  0.0.0.0/0  reject
-- hostssl  ecommerce  app_user  0.0.0.0/0  scram-sha-256
```

```sql
-- Check current SSL status for the connection:
SELECT ssl, version, cipher, bits
FROM   pg_stat_ssl
WHERE  pid = pg_backend_pid();

-- Check which connections are using SSL:
SELECT pid, usename, application_name, client_addr, ssl, version, cipher
FROM   pg_stat_ssl
JOIN   pg_stat_activity USING (pid)
ORDER  BY ssl ASC;  -- non-SSL connections first
```

### sslmode Values Reference

| sslmode | Encrypted? | Certificate Verified? | Use Case |
|---------|-----------|----------------------|----------|
| `disable` | No | No | Development only — NEVER production |
| `allow` | If server requires | No | Backward compatibility only |
| `prefer` | If possible | No | Default in many drivers — risky |
| `require` | Yes | No (MITM possible) | Encrypted but no cert check |
| `verify-ca` | Yes | CA verified | Encrypted + CA checked (not hostname) |
| `verify-full` | Yes | CA + hostname verified | **Recommended for production** |

## Why It Matters

- **Data in transit**: Without SSL, all query results, including passwords, PII, financial data, and API keys stored in the database, are transmitted in plaintext over the network.
- **`sslmode=prefer` false security**: Developers see no error with `prefer` but the connection silently downgrade to plaintext if SSL negotiation fails (e.g., misconfigured server). Production connections must use `require` or `verify-full`.
- **Certificate rotation**: AWS periodically rotates RDS CA certificates. Download the `global-bundle.pem` (combines all regional CAs) rather than individual regional bundles to avoid certificate rotation disruptions.
- **RDS force_ssl**: On RDS, setting `rds.force_ssl = 1` in the parameter group rejects all non-SSL connections at the server level — a defense-in-depth measure even if individual connections use `sslmode=require`.

## Aurora/RDS Notes

- **RDS PostgreSQL**: Set `rds.force_ssl = 1` in the parameter group to reject non-SSL connections. This applies to all users and databases on the instance.
- **Aurora PostgreSQL**: Same — `rds.force_ssl = 1` is available and recommended. SSL is required if using RDS Proxy (Proxy always requires SSL).
- **CA bundle for RDS**: Download from `https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem`. This bundle includes the `rds-ca-rsa2048-g1` CA used by recent RDS and Aurora instances.
- **Certificate rotation**: AWS rotates RDS certificates periodically. Subscribe to AWS Health events for the `AWS_RDS_CA_ROTATION` event. Use the `global-bundle.pem` to include both old and new CA certificates during rotation.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | TLS 1.3 supported; `ssl_min_protocol_version = 'TLSv1.2'` recommended |
| PostgreSQL 15 | Same |
| PostgreSQL 16 | Same |
| PostgreSQL 17 | Same |
| Aurora PostgreSQL | SSL required for RDS Proxy; `rds.force_ssl` parameter available |
