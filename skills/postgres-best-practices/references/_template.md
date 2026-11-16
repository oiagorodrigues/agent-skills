---
title: "Rule Title"
impact: critical|high|medium|low
tags: []
applies_to: [postgresql-14, postgresql-15, postgresql-16, postgresql-17, aurora-postgresql, rds-postgresql]
---

# Rule Title

## Problem

Describe the anti-pattern in one to three sentences. What does the developer typically write, and why is it problematic? State the performance or correctness impact concisely (e.g., "causes a sequential scan", "silently returns wrong data", "holds locks for the full transaction duration", "causes dead-tuple accumulation").

## Bad Example

```sql
-- Context: what this query is trying to do
SELECT ...
FROM   ...
WHERE  ...;
```

Explain in one or two sentences why this specific example is bad. Reference the column, index, or setting involved.

## Good Example

```sql
-- Context: the corrected approach
SELECT ...
FROM   ...
WHERE  ...;
```

Explain why this is better. If there is more than one acceptable fix, list them in order of preference.

## Why It Matters

- **Performance impact**: Quantify if possible (e.g., "changes from Seq Scan to Index Scan in EXPLAIN", "reduces rows examined from 1M to 50").
- **Correctness impact**: Does the bad example return wrong data silently?
- **Operational impact**: Does it hold locks, block DDL, cause replication lag, accumulate dead tuples?
- **At scale**: How does the problem grow as the table grows?

## EXPLAIN Notes

```sql
-- Run EXPLAIN (ANALYZE, BUFFERS) on the bad query to observe:
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT ...;
-- Expected bad output:
--   Seq Scan on orders          ← full sequential scan
--   rows=1000000                ← all rows examined
--   Buffers: shared read=50000  ← many buffer misses

-- Run EXPLAIN (ANALYZE, BUFFERS) on the good query to observe:
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT ...;
-- Expected good output:
--   Index Scan using idx_... on orders  ← index used
--   rows=50                             ← estimated rows examined
--   Buffers: shared hit=3               ← served from buffer cache
```

Key node types to look for in this rule:

| Query | Node Type | Rows | Notes |
|-------|-----------|------|-------|
| Bad   | Seq Scan  | 1000000 | Full table scan |
| Good  | Index Scan | 50 | B-tree index lookup |

## Aurora/RDS Notes

*(Include this section only when behavior differs from community PostgreSQL.)*

- **Aurora PostgreSQL**: Describe any Aurora-specific behavior, storage layer impact, or limitation.
- **RDS PostgreSQL**: Describe any RDS-specific parameter or restriction (parameter groups, rds_superuser, etc.).
- **RDS Proxy**: If relevant, note proxy behavior (e.g., prepared statements in transaction mode).

## Version Notes

*(Include this section only when behavior differs across PostgreSQL versions.)*

| Version | Behavior |
|---------|----------|
| PostgreSQL 14 | ... |
| PostgreSQL 15 | ... |
| PostgreSQL 16 | ... |
| PostgreSQL 17 | ... |
| Aurora PostgreSQL | ... |
