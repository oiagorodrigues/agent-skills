---
title: "Use roles and least-privilege grants for application database access"
impact: high
tags: [security, roles, privileges, grant, least-privilege, rds-iam]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Use roles and least-privilege grants for application database access

## Problem

Granting `ALL` privileges to application users is a common shortcut that violates the principle of least privilege. If the application's database credentials are compromised, an attacker has full read-write-drop access to all tables. Separate roles (read-only, read-write, admin) with minimal required privileges limit blast radius and make auditing easier.

## Bad Example

```sql
-- BAD: Single application user with ALL privileges on everything
CREATE USER app_user WITH PASSWORD 'password123';
GRANT ALL PRIVILEGES ON DATABASE ecommerce TO app_user;
GRANT ALL ON ALL TABLES IN SCHEMA public TO app_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO app_user;

-- Problems:
-- 1. app_user can DROP tables, ALTER schemas, CREATE users
-- 2. A compromised credential = full database access
-- 3. No separation between read and write operations
-- 4. Future tables are not automatically covered (no DEFAULT PRIVILEGES)
```

## Good Example

```sql
-- GOOD: Separate roles with minimal required privileges

-- 1. Create roles (groups of privileges, no LOGIN)
CREATE ROLE ecommerce_readonly  NOLOGIN;
CREATE ROLE ecommerce_readwrite NOLOGIN;
CREATE ROLE ecommerce_admin     NOLOGIN;

-- 2. Grant privileges to roles
-- Read-only role: SELECT only
GRANT CONNECT ON DATABASE ecommerce TO ecommerce_readonly;
GRANT USAGE ON SCHEMA public TO ecommerce_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO ecommerce_readonly;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO ecommerce_readonly;

-- Read-write role: SELECT, INSERT, UPDATE, DELETE (no DROP, no DDL)
GRANT CONNECT ON DATABASE ecommerce TO ecommerce_readwrite;
GRANT USAGE ON SCHEMA public TO ecommerce_readwrite;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO ecommerce_readwrite;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO ecommerce_readwrite;

-- Admin role: everything the app may need for migrations
GRANT CONNECT ON DATABASE ecommerce TO ecommerce_admin;
GRANT CREATE ON DATABASE ecommerce TO ecommerce_admin;
GRANT ALL ON SCHEMA public TO ecommerce_admin;
GRANT ALL ON ALL TABLES IN SCHEMA public TO ecommerce_admin;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO ecommerce_admin;

-- 3. Set DEFAULT PRIVILEGES so future tables are covered automatically
-- Without this, newly created tables don't inherit the grants above
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT ON TABLES TO ecommerce_readonly;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ecommerce_readwrite;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO ecommerce_readonly, ecommerce_readwrite;

-- 4. Create login users and assign them to roles
CREATE USER app_user  WITH PASSWORD 'password123' NOINHERIT;
CREATE USER api_ro    WITH PASSWORD 'password123' NOINHERIT;
CREATE USER migrator  WITH PASSWORD 'password123' NOINHERIT;

GRANT ecommerce_readwrite TO app_user;
GRANT ecommerce_readonly  TO api_ro;
GRANT ecommerce_admin     TO migrator;

-- 5. Application user explicitly sets role to activate inherited privileges
-- (NOINHERIT means role must be explicitly SET ROLE)
-- Or use INHERIT (default) to automatically inherit privileges
CREATE USER app_user WITH PASSWORD 'password123';  -- INHERIT is default
GRANT ecommerce_readwrite TO app_user;
-- Now app_user automatically has readwrite privileges without SET ROLE
```

```sql
-- IAM Authentication for RDS PostgreSQL and Aurora PostgreSQL
-- Grant the rds_iam role to the user:
CREATE USER app_iam_user WITH PASSWORD 'placeholder';
GRANT rds_iam TO app_iam_user;
-- The user can now authenticate using an IAM token instead of a password

-- Generate token (AWS CLI):
-- aws rds generate-db-auth-token \
--   --hostname mydb.xxxx.us-east-1.rds.amazonaws.com \
--   --port 5432 --region us-east-1 --username app_iam_user

-- Connect with token as password (token valid for 15 minutes)
```

```sql
-- Review current privileges:
-- Table-level privileges:
SELECT grantee, table_name, privilege_type
FROM   information_schema.role_table_grants
WHERE  table_schema = 'public'
ORDER  BY grantee, table_name;

-- Role memberships:
SELECT r.rolname AS role, m.rolname AS member
FROM   pg_auth_members am
JOIN   pg_roles r ON r.oid = am.roleid
JOIN   pg_roles m ON m.oid = am.member
ORDER  BY r.rolname, m.rolname;
```

## Why It Matters

- **Blast radius**: If `app_user` credentials are leaked and the role has `ALL` privileges, an attacker can read, modify, or drop any table. A read-only credential only exposes reads.
- **No MySQL GRANT ALL equivalent**: PostgreSQL's role system is more flexible than MySQL's. Roles are first-class objects that can be nested, activated with `SET ROLE`, and assigned granularly at the schema level.
- **`ALTER DEFAULT PRIVILEGES`**: Critical for ensuring future tables (created by migrations) inherit the grants. Without it, a new table is only accessible to the owner and superusers until explicitly granted.
- **IAM authentication on RDS**: Using IAM tokens instead of static passwords means credentials rotate automatically (tokens expire in 15 minutes) and are managed by AWS IAM policies rather than in-database password storage.

## Aurora/RDS Notes

- **RDS PostgreSQL / Aurora PostgreSQL**: The master user is `rds_superuser`, not a true PostgreSQL superuser. The `rds_superuser` role grants most superuser-like privileges but not OS-level operations.
- **IAM authentication**: Available on both RDS and Aurora PostgreSQL. Requires `rds.force_ssl = 1` and IAM policy `rds-db:connect`. Strongly recommended for Lambda and ECS workloads.
- **No `pg_hba.conf` direct edit on RDS**: Use the `rds.force_ssl` parameter and connection parameter groups to control host-based authentication. IAM auth replaces the need for `pg_hba.conf` `hostssl` entries for most use cases.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | `CREATE ROLE`, `GRANT`, `ALTER DEFAULT PRIVILEGES` unchanged |
| PostgreSQL 15 | Non-superuser `CREATE` privilege on public schema removed by default (`pg_public` schema security hardening) |
| PostgreSQL 16 | `pg_use_reserved_connections` role added |
| PostgreSQL 17 | Same |
| Aurora PostgreSQL | `rds_superuser` role; `rds_iam` for IAM auth; same privilege syntax |
