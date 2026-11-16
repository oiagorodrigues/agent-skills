# Contributing Guide

This document explains how to write a new rule for `postgresql-best-practices/references/`. Follow these conventions to keep the library consistent and useful.

---

## How to Write a New Rule

1. **Copy the template**: `cp references/_template.md references/my-new-rule.md`
2. **Choose a file name** following the naming conventions below.
3. **Fill in all required frontmatter fields**.
4. **Write the Problem section** — one paragraph maximum.
5. **Write the Bad Example** — runnable PostgreSQL SQL that references the e-commerce schema where possible.
6. **Write the Good Example** — the corrected SQL.
7. **Write Why It Matters** — at least one bullet must quantify the impact.
8. **Write EXPLAIN Notes** — show the `EXPLAIN (ANALYZE, BUFFERS)` output difference between bad and good.
9. **Add Aurora/RDS Notes only if the behavior differs** from community PostgreSQL.
10. **Add Version Notes only if the behavior differs** across PostgreSQL versions (14, 15, 16, 17).

---

## File Naming Conventions

Files are named `<category>-<topic>.md` using kebab-case. Categories:

| Prefix | Category |
|--------|----------|
| `query-` | Query optimization (indexes, predicates, aggregation, pagination) |
| `schema-` | Schema design (data types, DDL, partitioning, constraints) |
| `lock-` | Locking, MVCC, and transactions (deadlocks, isolation, advisory locks) |
| `conn-` | Connection management (pgBouncer, RDS Proxy, timeouts) |
| `data-` | Data access patterns (N+1, batch inserts, upsert) |
| `monitor-` | Monitoring and observability |
| `security-` | Authentication, authorization, Row Level Security |
| `advanced-` | Aurora-specific, RDS-specific, version-specific advanced topics |

Examples:
- `query-missing-indexes.md` ✓
- `missingIndexes.md` ✗ (camelCase not allowed)
- `general-tips.md` ✗ (no matching category prefix)

---

## Frontmatter Fields

```yaml
---
title: "Short, descriptive rule name"              # Required. Under 60 characters.
impact: critical|high|medium|low                   # Required. See impact levels below.
tags: [keyword1, keyword2]                         # Required. At least 2 tags.
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---
```

### Impact Levels

| Level | Meaning |
|-------|---------|
| `critical` | Causes correctness errors, sequential scans that appear in production immediately, or operational risk (XID wraparound, connection exhaustion) |
| `high` | Significant performance degradation at moderate scale (>100k rows), security risk, or DDL that blocks production traffic |
| `medium` | Performance issue that becomes noticeable at large scale, or operational friction |
| `low` | Style or hygiene issue; negligible performance impact |

---

## SQL Conventions

- **Use the e-commerce schema** (`sample/schema.sql`): tables `users`, `products`, `categories`, `orders`, `order_items`, `reviews`. Do not invent new table names.
- **SQL must be runnable PostgreSQL**: No MySQL-isms. No `AUTO_INCREMENT`, `TINYINT`, `UNSIGNED`, `ON UPDATE CURRENT_TIMESTAMP`, `ENGINE=InnoDB`, or `?` placeholders.
- **Parameter placeholders**: Use `$1`, `$2`, `$3` — the PostgreSQL protocol wire format. Never use `?` (that is JDBC/MySQL).
- **Primary keys**: Use `BIGINT GENERATED ALWAYS AS IDENTITY` — the SQL standard form introduced in PostgreSQL 10. Do not use `SERIAL` in new examples (it is legacy).
- **Timestamps**: Use `TIMESTAMPTZ` (timezone-aware). Never use bare `TIMESTAMP` for wall-clock time.
- **Money/prices**: Use `NUMERIC(10,2)`. Never use `FLOAT` or `DOUBLE PRECISION` for currency.
- **Credentials**: Use `app_user` as the user and `password123` as the placeholder password in any `CREATE USER` or `GRANT` examples. Never use real credentials.
- **Uppercase SQL keywords**: `SELECT`, `FROM`, `WHERE`, `JOIN`, `GROUP BY`, etc.
- **Version-specific SQL**: Add a comment `-- PostgreSQL 11+` or `-- Aurora PostgreSQL only` on the line if the syntax does not work on all supported versions.
- **Extension prerequisites**: If an example requires an extension, include `CREATE EXTENSION IF NOT EXISTS extension_name;` at the top of the code block.

---

## How to Write EXPLAIN Notes

Always use `EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)` — this is PostgreSQL's most informative form. For write queries where you don't want to execute the write, wrap in a transaction and roll back:

```sql
BEGIN;
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
DELETE FROM order_items WHERE created_at < NOW() - INTERVAL '2 years';
ROLLBACK;
```

Key node types to document:

| Node | Meaning |
|------|---------|
| `Seq Scan` | Full sequential table scan — usually bad |
| `Index Scan` | B-tree index lookup + heap fetch |
| `Index Only Scan` | Index lookup with no heap fetch — best case |
| `Bitmap Index Scan` + `Bitmap Heap Scan` | Used for OR predicates or loose range scans |
| `Hash Join` | Efficient for large unsorted inputs |
| `Merge Join` | Efficient when both inputs are already sorted |
| `Nested Loop` | Good for small outer input + indexed inner; bad for large outer |
| `Hash Aggregate` | GROUP BY with hash table |
| `Sort` | Explicit sort step — check if an index can eliminate it |

Key metrics to document:

- **actual rows vs estimated rows**: Large discrepancy means stale statistics → run `ANALYZE`.
- **Buffers: shared hit vs shared read**: `shared read` means disk I/O (buffer cache miss); `shared hit` means served from RAM.
- **actual time**: Wall-clock time for that node. Look for nodes with disproportionate time.

Provide a table like this:

```markdown
| Query | Node | Rows (estimated) | Buffers | Notes |
|-------|------|-----------------|---------|-------|
| Bad   | Seq Scan on orders | 4987234 | shared read=50000 | Full table scan |
| Good  | Index Scan using idx_orders_status | 1024 | shared hit=3 | Index lookup |
```

---

## What Makes a Good Rule vs. a Vague Tip

### Good rule ✓
- Has a specific bad pattern that can be recognized in code (e.g., `WHERE EXTRACT(year FROM created_at) = ...`)
- Has a specific fix that can be applied mechanically
- Quantifies the impact (e.g., "changes from Seq Scan to Index Scan")
- The bad example would compile and run on PostgreSQL 14+ — it just runs poorly
- References the e-commerce schema tables

### Vague tip ✗
- "Always use indexes" — too general, not actionable
- "Avoid slow queries" — no specific pattern
- Bad example that would produce a syntax error
- Good example that requires infrastructure the reader doesn't have
- MySQL syntax in a PostgreSQL rule file (`AUTO_INCREMENT`, `?` placeholders, `SHOW TABLES`, etc.)

---

## How to Test a Rule

1. Load `sample/schema.sql` into a test PostgreSQL 14+ instance (or Aurora PostgreSQL).
2. Insert at least 50k rows into the relevant table:
   ```sql
   INSERT INTO orders (user_id, status, total_amount)
   SELECT (random() * 999 + 1)::bigint,
          (ARRAY['pending','paid','delivered'])[floor(random()*3+1)],
          (random() * 500)::numeric(12,2)
   FROM generate_series(1, 100000);
   ```
3. Run `EXPLAIN (ANALYZE, BUFFERS)` on the bad query and confirm the expected bad behavior (Seq Scan, high buffer reads, etc.).
4. Apply the fix (create the index, rewrite the query).
5. Run `EXPLAIN (ANALYZE, BUFFERS)` on the good query and confirm the expected good behavior.
6. For Aurora-specific rules, test on an Aurora PostgreSQL cluster (writer + reader) and note differences.

---

## Review Checklist

Before submitting a new rule, verify:

- [ ] File name follows `<category>-<topic>.md` convention
- [ ] All frontmatter fields are filled in
- [ ] Bad example is runnable PostgreSQL SQL (no MySQL-isms, no `?` placeholders)
- [ ] Good example is runnable PostgreSQL SQL
- [ ] `$1`, `$2` used for parameter placeholders (not `?`)
- [ ] `TIMESTAMPTZ` used for timestamps (not bare `TIMESTAMP`)
- [ ] `NUMERIC` used for money (not `FLOAT`)
- [ ] `BIGINT GENERATED ALWAYS AS IDENTITY` used for PKs in new table definitions
- [ ] Why It Matters has at least one quantified bullet
- [ ] EXPLAIN Notes shows the actual output difference using `EXPLAIN (ANALYZE, BUFFERS)`
- [ ] No real credentials anywhere in the file
- [ ] Aurora/RDS Notes section present if behavior differs from community PostgreSQL
- [ ] File has been spell-checked
