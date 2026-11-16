---
title: "Use Row Level Security to enforce tenant isolation at the database level"
impact: high
tags: [rls, row-level-security, security, multi-tenant, access-control]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Use Row Level Security to enforce tenant isolation at the database level

## Problem

Multi-tenant applications often filter tenant data in application code: `WHERE tenant_id = $current_tenant`. This works until a developer forgets the WHERE clause, a new query path bypasses the filter, or a bug exposes another tenant's data. Row Level Security (RLS) enforces tenant isolation at the database level — the filter is applied automatically for every query, regardless of what the application sends. PostgreSQL's RLS is not available in MySQL, making it a PostgreSQL-specific security advantage.

## Bad Example

```sql
-- BAD: Tenant filtering is application-only — no database enforcement
-- If a developer forgets WHERE tenant_id = $1, all tenants' orders are exposed

-- Application code (Python):
-- tenant_id = get_current_tenant_from_jwt()
-- cur.execute("SELECT id, total_amount FROM orders")  # BUG: forgot WHERE clause
-- All orders for all tenants are returned — security breach

-- Even with the WHERE clause, a query injection or code path bug can bypass it:
-- cur.execute(f"SELECT id FROM orders WHERE status = '{status}'")
-- No tenant_id filter if the developer forgot it or was bypassed
```

## Good Example

```sql
-- GOOD: Enable Row Level Security on the orders table

-- Step 1: Enable RLS on the table
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;

-- Step 2: Force RLS even for the table owner (not just non-owners)
ALTER TABLE orders FORCE ROW LEVEL SECURITY;

-- Step 3: Create a policy using current_setting() for the tenant ID
-- The application must SET app.tenant_id = '42' at the start of each session/transaction
CREATE POLICY tenant_isolation_orders ON orders
  USING (user_id = current_setting('app.tenant_id', true)::bigint);

-- The policy means: for every SELECT/UPDATE/DELETE on orders,
-- PostgreSQL automatically adds: WHERE user_id = current_setting('app.tenant_id')::bigint

-- Step 4: Set the tenant ID in the application at session or transaction start
-- In the application connection setup:
-- SET LOCAL app.tenant_id = '42';   -- transaction-scoped (recommended)
-- SET app.tenant_id = '42';         -- session-scoped

-- Verify: even if application forgets WHERE clause, only tenant's rows are returned
SELECT id, total_amount FROM orders;
-- Automatically returns only orders where user_id = current_setting('app.tenant_id')

-- Step 5: Separate policies for SELECT, INSERT, UPDATE, DELETE if needed
CREATE POLICY tenant_select_orders ON orders
  FOR SELECT
  USING (user_id = current_setting('app.tenant_id', true)::bigint);

CREATE POLICY tenant_insert_orders ON orders
  FOR INSERT
  WITH CHECK (user_id = current_setting('app.tenant_id', true)::bigint);

CREATE POLICY tenant_update_orders ON orders
  FOR UPDATE
  USING (user_id = current_setting('app.tenant_id', true)::bigint)
  WITH CHECK (user_id = current_setting('app.tenant_id', true)::bigint);
```

```sql
-- IMPORTANT: Superuser bypasses RLS by default
-- Create an application role that is NOT a superuser and is NOT BYPASSRLS:
CREATE ROLE app_user LOGIN PASSWORD 'password123';
GRANT SELECT, INSERT, UPDATE, DELETE ON orders TO app_user;
-- app_user is subject to RLS policies (does not have BYPASSRLS privilege)

-- Verify RLS is active:
SELECT tablename, rowsecurity, forcerowsecurity
FROM   pg_tables
WHERE  tablename = 'orders';

-- List current policies:
SELECT policyname, cmd, qual, with_check
FROM   pg_policies
WHERE  tablename = 'orders';
```

```sql
-- Performance consideration: RLS policy predicates must be indexable
-- The policy WHERE clause is appended to every query on the table
-- If user_id is not indexed, every query does a sequential scan

-- Ensure the policy column is indexed:
CREATE INDEX idx_orders_user_id ON orders (user_id);
-- Now every RLS-filtered SELECT on orders uses an index scan
```

## Why It Matters

- **Defense in depth**: Application-level tenant filtering can be bypassed by bugs, injections, or oversight. Database-level RLS cannot be bypassed by application code (unless the role has `BYPASSRLS`).
- **Automatic enforcement**: RLS policies are appended to every query automatically. Developers don't need to remember to add WHERE clauses — the database enforces it.
- **No MySQL equivalent**: MySQL has no native RLS feature. PostgreSQL's RLS is a significant security advantage for multi-tenant SaaS applications.
- **Performance**: RLS adds a predicate to every query. The predicate must be indexable — ensure `idx_orders_user_id` exists. An unindexed RLS predicate causes sequential scans on every query.
- **BYPASSRLS**: The `rds_superuser` role on RDS has `BYPASSRLS`. Admin users and the table owner bypass RLS by default unless `FORCE ROW LEVEL SECURITY` is set.

## Aurora/RDS Notes

- **Aurora PostgreSQL**: RLS works identically on Aurora PostgreSQL as on community PostgreSQL. No Aurora-specific differences.
- **RDS PostgreSQL**: `rds_superuser` has `BYPASSRLS` privilege. Ensure the application uses a non-superuser role that is subject to RLS policies. Check with `\du` in psql or query `pg_roles`.
- **current_setting() with RDS Proxy**: In transaction mode with RDS Proxy, `SET LOCAL app.tenant_id = '42'` (transaction-scoped) is safer than `SET app.tenant_id = '42'` (session-scoped) because transaction-scoped settings are automatically reset when the transaction ends.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | RLS fully available; `current_setting(name, missing_ok)` for safe NULL handling |
| PostgreSQL 15 | Same |
| PostgreSQL 16 | Same |
| PostgreSQL 17 | Same |
| Aurora PostgreSQL | RLS fully supported; same syntax as community PostgreSQL |
