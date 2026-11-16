---
name: postgres-best-practices
version: 1.0.0
description: >
  50+ PostgreSQL rules for PostgreSQL 14-17, RDS for PostgreSQL and Aurora PostgreSQL, each with
  a before pattern, a recommended approach and the reason. Covers schema design, data types,
  constraints, indexes (composite, partial, covering, GIN, BRIN), query performance, EXPLAIN
  ANALYZE, pagination, N+1, locking and MVCC, migrations and online DDL, vacuum and bloat,
  connection pooling, roles and row level security. Use when writing, reviewing or tuning SQL,
  a Postgres schema, index or migration, a Django migration or ORM query, reading an EXPLAIN plan, or debugging a slow query.
tags: [postgresql, aurora-postgresql, rds-postgresql, sql, performance, indexing, vacuum]
---

# PostgreSQL Best Practices Skill

This skill teaches the agent how to write, review, and refactor PostgreSQL SQL for correctness, performance, and security. Rules are organized into eight categories. Each rule file contains a bad example, a good example, and an explanation of the performance or correctness impact.

---

## Category 1: Query Optimization (`query-*.md`)

| File | Description |
|------|-------------|
| `query-missing-indexes.md` | Detect and fix sequential scans caused by missing WHERE-clause indexes |
| `query-composite-indexes.md` | Composite index column ordering: equality first, range last, highest selectivity first |
| `query-covering-indexes.md` | Index-only scans via INCLUDE clause (PG 11+) to avoid heap fetches |
| `query-partial-indexes.md` | Partial indexes with WHERE clause for selective data subsets |
| `query-index-types.md` | Choosing B-tree, Hash, GIN, GiST, BRIN, or SP-GiST for each access pattern |
| `query-aggregation-over-join.md` | The silent correctness bug: JOINing two one-to-many tables inflates SUM/AVG without an error |
| `query-pagination.md` | OFFSET-based pagination vs. keyset (cursor) pagination at scale |
| `query-sargable-expressions.md` | Non-sargable predicates (functions, casts, implicit conversions) that prevent index use |
| `query-optimizer-hints.md` | pg_hint_plan, enable_seqscan, plan_cache_mode and when to apply planner overrides |
| `query-statistics.md` | ANALYZE, extended statistics, per-column statistics targets for skewed data |
| `query-or-union.md` | OR across unrelated columns vs. UNION ALL; when bitmap index scan suffices |

---

## Category 2: Connection Management (`conn-*.md`)

| File | Description |
|------|-------------|
| `conn-pgbouncer.md` | pgBouncer connection pooling modes, transaction mode limitations, prepared statement pitfall |
| `conn-rds-proxy.md` | RDS Proxy for Aurora PostgreSQL and RDS PostgreSQL: pooling, fast failover, limitations |
| `conn-connection-limits.md` | max_connections sizing, pg_stat_activity monitoring, pg_terminate_backend |
| `conn-idle-limits.md` | idle_in_transaction_session_timeout to stop idle sessions holding locks |
| `conn-idle-timeouts.md` | idle_in_transaction_session_timeout, statement_timeout, idle_session_timeout (PG 14+) |
| `conn-prepared-statements.md` | PREPARE/EXECUTE/DEALLOCATE, generic vs custom plans, pgBouncer incompatibility |

---

## Category 3: Security (`security-*.md`)

| File | Description |
|------|-------------|
| `security-row-level-security.md` | PostgreSQL Row Level Security policies for tenant isolation and data access control |
| `security-roles-privileges.md` | CREATE ROLE, GRANT, ALTER DEFAULT PRIVILEGES, IAM auth on RDS |
| `security-ssl-tls.md` | sslmode settings, RDS force_ssl, certificate verification, certificate rotation |

---

## Category 4: Schema Design (`schema-*.md`)

| File | Description |
|------|-------------|
| `schema-primary-keys.md` | GENERATED ALWAYS AS IDENTITY vs SERIAL vs UUID; B-tree fragmentation impact |
| `schema-data-types.md` | TEXT vs VARCHAR, NUMERIC for money, TIMESTAMPTZ, BOOLEAN, JSONB vs JSON, arrays |
| `schema-partitioning.md` | Declarative RANGE/LIST/HASH partitioning (PG 10+), partition pruning, pg_partman |
| `schema-online-ddl.md` | DDL locking levels, NOT VALID constraints, CREATE INDEX CONCURRENTLY, pg_repack |
| `schema-generated-columns.md` | GENERATED ALWAYS AS STORED (PG 12+) for computed columns that can be indexed |
| `schema-sequences.md` | Sequences, SERIAL, BIGSERIAL, sequence gaps, exhaustion risk, RDS behavior |
| `schema-roles-privileges.md` | Roles and least-privilege grants for application access, RDS IAM |
| `schema-row-level-security.md` | Row Level Security for tenant isolation in the database |
| `schema-constraints.md` | CHECK, UNIQUE, EXCLUDE, deferrable constraints, NOT VALID + VALIDATE pattern |

---

## Category 5: Locking & MVCC (`lock-*.md`)

| File | Description |
|------|-------------|
| `lock-mvcc.md` | MVCC model, dead tuples, vacuum, transaction ID wraparound — the most critical PG operational risk |
| `lock-deadlock-prevention.md` | Deadlock causes, consistent lock ordering, pg_locks monitoring, Python retry pattern |
| `lock-isolation-levels.md` | READ COMMITTED, REPEATABLE READ, SERIALIZABLE (SSI) and when to use each |
| `lock-advisory-locks.md` | pg_try_advisory_lock for distributed mutex, job locking, rate limiting |
| `lock-skip-locked.md` | SELECT FOR UPDATE SKIP LOCKED for job queues (PG 9.5+) |

Before adding a row, advisory or cache lock in application code, follow "Adding a lock" in `~/.agents/skills/backend-design/skills/anti-patterns/README.md`.

---

## Category 6: Data Patterns (`data-*.md`)

| File | Description |
|------|-------------|
| `data-n-plus-one.md` | N+1 query anti-pattern and batch fetching via JOIN or ANY($1::bigint[]) |
| `data-batch-inserts.md` | Multi-row INSERT vs single-row loop; COPY FROM STDIN for bulk loads |
| `data-keyset-pagination.md` | Keyset/cursor pagination: composite cursors, forward and backward navigation |
| `data-upsert.md` | INSERT ... ON CONFLICT DO UPDATE; EXCLUDED pseudo-table; partial unique index |
| `data-bulk-operations.md` | Batched DELETE, TRUNCATE vs DELETE, COPY TO/FROM, temporary tables for staging |

---

## Category 7: Monitoring (`monitor-*.md`)

| File | Description |
|------|-------------|
| `monitor-pg-stat-statements.md` | pg_stat_statements extension: top queries by total time, mean time, call count |
| `monitor-explain-analyze.md` | EXPLAIN (ANALYZE, BUFFERS), node types, actual vs estimated rows, auto_explain |
| `monitor-autovacuum.md` | Autovacuum monitoring, per-table tuning, XID wraparound detection, pg_stat_progress_vacuum |
| `monitor-bloat.md` | Table and index bloat, pgstattuple, VACUUM FULL, REINDEX CONCURRENTLY, pg_repack |
| `monitor-locks.md` | pg_locks + pg_stat_activity, blocking query detector, pg_blocking_pids(), log_lock_waits |
| `monitor-replication.md` | Streaming replication lag, pg_stat_replication, LSN lag, Aurora replica lag |

---

## Category 8: Advanced / Aurora (`advanced-*.md`)

| File | Description |
|------|-------------|
| `advanced-aurora-postgresql.md` | Aurora PostgreSQL storage layer, Aurora-specific extensions, Serverless v2, Global Database |
| `advanced-rds-postgresql-limitations.md` | What you cannot do on RDS: no superuser, no pg_hba.conf edit, shared_preload_libraries via parameter group |
| `advanced-pg17-features.md` | PG 17 incremental backup, MERGE RETURNING, COPY ON_ERROR, JSON_TABLE, vacuum improvements |
| `advanced-ctes.md` | CTE inlining (PG 12+), MATERIALIZED keyword, recursive CTEs, optimization fence behavior |
| `advanced-window-functions.md` | ROW_NUMBER, RANK, LAG, LEAD, running totals, DISTINCT ON, top-N per group |
| `advanced-jsonb-indexing.md` | JSONB vs JSON, GIN indexes, jsonb_path_ops, functional indexes on JSONB paths |
| `advanced-full-text-search.md` | tsvector/tsquery, GIN index on tsvector, pg_trgm for LIKE/ILIKE, ts_rank scoring |
| `advanced-logical-replication.md` | Publications/subscriptions, row filtering (PG 15+), zero-downtime upgrades, CDC |

---

## Usage Instructions for the Agent

When a user opens or edits a `.sql` file, or asks about PostgreSQL query performance, schema design, or Aurora PostgreSQL behavior:

1. Identify which category (query, schema, lock, data, monitoring, security, connection, advanced) the question falls into.
2. Load the relevant reference file(s) from this skill's `references/` folder.
3. Show the **before pattern** first so the user recognizes it in their own code.
4. Show the **recommended approach** with explanation.
5. Where relevant, quote the **EXPLAIN Notes** section to explain what the optimizer will do.
6. For Aurora PostgreSQL-specific behavior (storage layer, aurora_stat_utils, Serverless v2), always load `advanced-aurora-postgresql.md` or the rule file's **Aurora/RDS Notes** section.
7. For vacuum and bloat issues, always cross-reference `lock-mvcc.md` and `monitor-autovacuum.md` together.
8. Use `$1`, `$2` parameter placeholders (not `?`) in all SQL examples — this is PostgreSQL, not JDBC.
9. If the user's query cannot be improved further, say so — do not invent problems.
