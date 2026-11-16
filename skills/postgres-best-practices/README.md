# postgresql-best-practices

A curated library of 50+ PostgreSQL performance, security, and schema rules for PostgreSQL 14–17, RDS for PostgreSQL, and Aurora PostgreSQL. Each rule ships with a bad example, a good example, and a concise explanation so that an AI coding agent (Claude Code, Codex, Cursor, Gemini CLI and others) or any developer can apply it immediately.

---

## What It Is

This package is a **skill**: a set of reference files that teach an AI coding agent how to write correct, performant PostgreSQL. Put it where your agent loads skills, or point your project's agent instructions at it, and the agent reviews SQL against the rules.

It is also useful as a standalone reference for DBAs and backend engineers working with:

- PostgreSQL 14, 15, 16, or 17 (community or self-managed)
- Amazon RDS for PostgreSQL
- Amazon Aurora PostgreSQL

---

## Why It Exists

PostgreSQL has a distinct set of performance and operational challenges that generic SQL advice does not cover: MVCC dead-tuple accumulation and autovacuum tuning, GIN indexes for JSONB and trigram searches, the transaction ID wraparound emergency, pgBouncer connection pooling modes that silently break prepared statements, Row Level Security policies, and the differences between community PostgreSQL and the Aurora PostgreSQL storage engine. This library makes those patterns explicit, with runnable SQL that demonstrates both the problem and the fix.

---

## Quick Start

**Step 1 — Clone or copy this folder into your project:**

```bash
git clone https://github.com/your-org/postgresql-best-practices
# or just copy the folder
cp -r postgresql-best-practices /path/to/your/project/
```

**Step 2 — Make the skill visible to your agent.**

Put the folder in your agent's skills directory (for example `~/.agents/skills/` or `~/.claude/skills/`), or add a line to the project's agent instructions file (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md` or a Cursor rule) that tells the agent to apply these rules to SQL.

**Step 3 — Ask your agent to review your query:**

```
Review this query against postgresql-best-practices/references/ and suggest improvements.
```

---

## Folder Layout

| Path | Description |
|------|-------------|
| `README.md` | This file |
| `SKILL.md` | Skill manifest: name, description and rule index |
| `sample/schema.sql` | Reference e-commerce schema used in all examples |
| `sample/bad_queries.sql` | 15 anti-patterns with bad/good/why commentary |
| `references/` | 50+ individual rule files, one topic each |
| `references/_template.md` | Template for writing new rules |
| `references/_contributing.md` | Guide for contributors |

---

## Category Table

| Priority | Category | Files | Covers |
|----------|----------|-------|--------|
| P0 | Query optimization | `query-*.md` (11 files) | Missing indexes, composite indexes, covering indexes, partial indexes, index types, aggregation bugs, pagination, sargable expressions, optimizer hints, statistics, OR vs UNION |
| P0 | Schema design | `schema-*.md` (7 files) | Primary keys, data types, partitioning, online DDL, generated columns, sequences, constraints |
| P0 | Locking & MVCC | `lock-*.md` (5 files) | MVCC model, deadlock prevention, isolation levels, advisory locks, SKIP LOCKED |
| P1 | Connections | `conn-*.md` (5 files) | pgBouncer, RDS Proxy, connection limits, idle timeouts, prepared statements |
| P1 | Data patterns | `data-*.md` (5 files) | N+1 queries, batch inserts, keyset pagination, upsert, bulk operations |
| P1 | Monitoring | `monitor-*.md` (6 files) | pg_stat_statements, EXPLAIN ANALYZE, autovacuum, bloat, locks, replication |
| P1 | Security | `security-*.md` (3 files) | Row Level Security, roles and privileges, SSL/TLS |
| P2 | Advanced / Aurora | `advanced-*.md` (8 files) | Aurora PostgreSQL specifics, RDS limitations, PG 17 features, CTEs, window functions, JSONB indexing, full-text search, logical replication |

---

## Setup in an AI coding agent

1. Copy (or symlink) the folder into your agent's skills directory, globally (for example `~/.agents/skills/` or `~/.claude/skills/`) or per project.
2. The `description` in `SKILL.md` frontmatter tells the agent when to load the skill.
3. To apply the rules every time the agent touches SQL, or Python files with SQL strings or ORM queries, add a line to the project's agent instructions file (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`), or a Cursor rule with a glob such as `**/*.sql` or `**/*.py`.

See `IDE-SETUP-GUIDE.md` for per-tool setup.

---

## How to Add Your Own Rules

1. Copy `references/_template.md` to a new file: `references/my-new-rule.md`
2. Fill in the frontmatter (title, impact, tags, applies_to).
3. Write the Problem, Bad Example, Good Example, Why It Matters, EXPLAIN Notes, and Aurora/RDS Notes sections.
4. Reference the e-commerce schema from `sample/schema.sql` so examples are consistent.
5. Read `references/_contributing.md` for full conventions.

---

## Key Examples Highlighted in This Library

- **LIKE '%term%' vs GIN trigram index** (`advanced-full-text-search.md`, `query-sargable-expressions.md`): `WHERE name LIKE '%acme%'` forces a full sequential scan on every row. `CREATE INDEX ON products USING gin(name gin_trgm_ops)` (with the `pg_trgm` extension) enables a fast GIN index scan. On a 1M-row products table, the difference is seconds vs milliseconds.

- **Table bloat from missing VACUUM tuning** (`lock-mvcc.md`, `monitor-autovacuum.md`, `monitor-bloat.md`): Every UPDATE in PostgreSQL writes a new row version and marks the old version as dead. Without properly tuned autovacuum, these dead tuples accumulate: a table that holds 1M live rows may have 10M dead tuples on disk. Table scans slow down proportionally, and storage grows without bound. The transaction ID wraparound risk (when `age(relfrozenxid)` approaches 2 billion) can force an emergency shutdown of the entire cluster.

- **pgBouncer transaction mode breaking prepared statements** (`conn-pgbouncer.md`, `conn-prepared-statements.md`): An application uses server-side prepared statements (`PREPARE stmt AS SELECT ...`). When pgBouncer is in transaction pooling mode, each transaction may be routed to a different backend connection. The prepared statement is gone on the new connection, and the application gets `ERROR: prepared statement "stmt" does not exist` at runtime. Fix: disable prepared statements in the application driver, or upgrade to pgBouncer 1.21+ which handles this with `server_reset_query`.

- **OFFSET pagination at scale** (`query-pagination.md`, `data-keyset-pagination.md`): `SELECT * FROM orders LIMIT 20 OFFSET 50000` tells PostgreSQL to scan and discard 50,000 rows before returning 20. At page 2,500 that is scanning 50,000 rows every time a user clicks "next page." Keyset pagination with `WHERE id > $1 ORDER BY id LIMIT 20` uses the B-tree index directly and costs the same O(log n) regardless of page depth.

- **Over-join aggregation** (`query-aggregation-over-join.md`): Joining `order_items` and `reviews` in the same query before running `SUM(unit_price * quantity)` produces a Cartesian product of those two one-to-many relations. An order with 3 line items and 4 reviews creates 12 combined rows; `SUM(revenue)` is counted 4 times and is wrong by 4×. No error is raised — the data is silently incorrect. Fix with separate CTEs that aggregate each relation before joining.
