---
title: "Choose PostgreSQL data types that match the data's semantics"
impact: high
tags: [data-types, schema-design, timestamptz, numeric, jsonb, text, boolean]
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Choose PostgreSQL data types that match the data's semantics

## Problem

Using the wrong data type causes precision loss (FLOAT for money), silent timezone bugs (TIMESTAMP without timezone), wasted storage (VARCHAR(n) constraints where TEXT suffices), inability to query efficiently (JSON instead of JSONB), and data integrity risks (SMALLINT for boolean, comma-separated strings instead of arrays). PostgreSQL's rich type system — including TIMESTAMPTZ, NUMERIC, JSONB, arrays, INET, and CIDR — eliminates most of these problems when used correctly.

## Bad Example

```sql
-- BAD: FLOAT for money — precision errors are inevitable
CREATE TABLE invoices (
  id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  amount FLOAT  NOT NULL   -- 0.1 + 0.2 = 0.30000000000000004 in IEEE 754
);

-- BAD: TIMESTAMP without timezone — ambiguous in distributed systems
CREATE TABLE orders (
  id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()  -- Which timezone is NOW() in?
);
-- When the database server or application changes timezone, historical timestamps
-- are misinterpreted. A "10:00 AM order" may mean different things.

-- BAD: VARCHAR(255) everywhere — cargo-culted from MySQL
-- In PostgreSQL, TEXT and VARCHAR(n) have identical performance.
-- VARCHAR(n) only adds a CHECK constraint on length — use TEXT unless you need the constraint.
CREATE TABLE users (
  email    VARCHAR(255) NOT NULL,   -- VARCHAR(255) = TEXT + length check, not faster
  username VARCHAR(100) NOT NULL    -- Use TEXT; add CHECK if you need max length
);

-- BAD: JSON instead of JSONB for queried data
-- JSON stores raw text — no GIN indexing, slower operator access
CREATE TABLE products (
  attributes JSON  -- cannot use @>, ?, or GIN index
);

-- BAD: SMALLINT for boolean
CREATE TABLE products (
  is_active SMALLINT NOT NULL DEFAULT 1   -- 0/1 convention — not type-safe
);

-- BAD: Comma-separated strings instead of arrays
CREATE TABLE products (
  tags TEXT NOT NULL DEFAULT ''   -- 'electronics,wireless,bluetooth'
  -- Cannot index efficiently, cannot query for a single tag, no referential integrity
);
```

## Good Example

```sql
-- GOOD: NUMERIC(10,2) for money — exact decimal arithmetic
CREATE TABLE invoices (
  id     BIGINT         GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  amount NUMERIC(10,2)  NOT NULL CHECK (amount >= 0)
  -- NUMERIC stores exact decimal values; 0.10 + 0.20 = 0.30 exactly
);

-- GOOD: TIMESTAMPTZ for all timestamps — timezone-aware
CREATE TABLE orders (
  id         BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
  -- PostgreSQL stores TIMESTAMPTZ as UTC internally.
  -- NOW() always returns the current time in UTC, converted to the session timezone.
  -- Consistent across all timezones, DST changes, and server migrations.
);

-- GOOD: TEXT for variable-length strings (no artificial length limit)
-- Add CHECK constraint only when you need to enforce a maximum length
CREATE TABLE users (
  email    TEXT NOT NULL CHECK (LENGTH(email) <= 255),
  username TEXT NOT NULL CHECK (LENGTH(username) BETWEEN 3 AND 50)
  -- TEXT and VARCHAR(n) have identical storage and performance in PostgreSQL
);

-- GOOD: JSONB for queryable JSON data
CREATE TABLE products (
  attributes JSONB NOT NULL DEFAULT '{}'
  -- JSONB: binary format, supports GIN indexing, @>, ?, @@ operators
  -- CREATE INDEX ON products USING gin(attributes);
);

-- GOOD: BOOLEAN for boolean flags
CREATE TABLE products (
  is_active BOOLEAN NOT NULL DEFAULT TRUE
  -- TRUE/FALSE literals, not 0/1; enforces boolean semantics at DB level
);

-- GOOD: TEXT[] arrays instead of comma-separated strings
CREATE TABLE products (
  tags TEXT[] NOT NULL DEFAULT '{}'
  -- Queryable with ANY(), @>, &&, GIN index
  -- CREATE INDEX ON products USING gin(tags);
  -- WHERE 'wireless' = ANY(tags)
  -- WHERE tags @> ARRAY['wireless', 'bluetooth']
);

-- GOOD: INET and CIDR for IP addresses
CREATE TABLE access_logs (
  id         BIGINT  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  client_ip  INET    NOT NULL,   -- stores IPv4 or IPv6, supports subnet operators
  network    CIDR    DEFAULT NULL
  -- WHERE client_ip << '192.168.0.0/16'  (subnet containment)
);
```

### Data Type Reference

| Use Case | Bad Type | Good Type | Why |
|----------|----------|-----------|-----|
| Money / prices | `FLOAT`, `DOUBLE PRECISION` | `NUMERIC(10,2)` | Exact decimal arithmetic |
| Wall-clock timestamps | `TIMESTAMP` | `TIMESTAMPTZ` | Timezone-aware, stored as UTC |
| Short strings | `VARCHAR(255)` | `TEXT` or `TEXT + CHECK` | No performance difference in PG |
| Queryable JSON | `JSON` | `JSONB` | GIN indexing, faster operators |
| Boolean flags | `SMALLINT`, `INT` | `BOOLEAN` | Type-safe, explicit semantics |
| Multi-value strings | `TEXT` (CSV) | `TEXT[]` array | GIN-indexable, queryable |
| IP addresses | `TEXT` | `INET` / `CIDR` | Subnet operators, validation |
| Enum-like values | `TEXT` (unconstrained) | `TEXT + CHECK` or `CREATE TYPE ... AS ENUM` | Data validation |

## Why It Matters

- **FLOAT precision loss**: `SELECT 0.1::float + 0.2::float` returns `0.30000000000000004`. In financial calculations this accumulates over millions of rows. `NUMERIC` is exact.
- **TIMESTAMP timezone bugs**: A `TIMESTAMP` column stores a time value with no timezone information. `2024-06-15 10:00:00` is ambiguous — is that UTC or ET? When servers or clients change timezone, historical data is misread. `TIMESTAMPTZ` stores UTC and converts to the session timezone on retrieval — always unambiguous.
- **TEXT vs VARCHAR(n)**: In PostgreSQL, `TEXT` and `VARCHAR(n)` use the same underlying storage (varlena) and have identical performance. `VARCHAR(255)` only adds a length check, not performance. Use `TEXT` for flexibility; add `CHECK (LENGTH(col) <= n)` if you need the constraint.
- **JSONB vs JSON**: JSON stores text verbatim and re-parses on every access. JSONB stores a parsed binary representation — access to individual keys is faster, and GIN indexes enable containment queries. There is no reason to use JSON for queried data.

## Aurora/RDS Notes

- **Aurora PostgreSQL**: All PostgreSQL data types are fully supported on Aurora. JSONB GIN indexes are replicated to Aurora reader nodes.
- **RDS PostgreSQL**: Same as community PostgreSQL. `pg_trgm` and array GIN indexes behave identically.

## Version Notes

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | All types listed above available |
| PostgreSQL 15 | `pg_public` schema changes — `TEXT` column creation behavior unchanged |
| PostgreSQL 16 | Same |
| PostgreSQL 17 | Same; `JSON_TABLE()` function added for SQL/JSON |
| Aurora PostgreSQL | All types fully supported |
