---
name: backend-design
description: Applies senior backend engineering discipline to server-side work. Designs and audits backend components (HTTP endpoints, workers, queue consumers, CLIs, cron jobs, ETL, third-party integrations), reviews schemas and migrations for lock and rollback risk, predicts query plans and missing indexes, and hunts N+1 queries. Carries rules for data modeling, idempotency and side effects, error handling, observability, auth and authorization, multi-tenancy, security, performance, testing and debugging production issues. Use when designing, building or reviewing a backend component, schema, migration or query, when a change touches auth, retries, webhooks, payments or outbound calls, when someone proposes new infrastructure, when a fix for a race, deadlock or Sentry error reaches for a lock, or when something is slow or broken in staging or production. Run as /backend-design <command> [args].
argument-hint: "[design|audit|review-migration|explain-this-query|hunt-n-plus-one] [args]"
---

# Backend design

Workflows and checklists that make backend work start from the data model, failure modes, authorization, idempotency and observability before any code. All paths below are relative to `~/.agents/skills/backend-design/`.

## How to use

Run `/backend-design <command> [args]`:

- `design <what to build>` runs the 6-step design workflow and returns a blueprint, with no code.
- `audit <file or dir>` audits an existing endpoint, worker, consumer, CLI, cron or integration and lists the top 5 fixes.
- `review-migration <file or SQL>` checks a migration for locks, irreversible steps and missing deprecation windows.
- `explain-this-query <SQL, ORM call or file>` predicts the plan, flags missing indexes and gives the exact `CREATE INDEX CONCURRENTLY`.
- `hunt-n-plus-one [path]` scans code for N+1 queries, ranked by confidence, with fixes. The default path is the current directory.

Examples:

- `/backend-design design webhook receiver for Stripe payment events`
- `/backend-design review-migration orders/migrations/0101_add_currency.py`

## Routing

The first word of the arguments ($ARGUMENTS in Claude Code) names the command; read `commands/<cmd>.md` and follow it. In that file, `$ARGUMENTS` means the rest of the arguments after the command name. With no command and no matching topic, show the list under "How to use".

## Topics

When the task is about one of these, read only the matching file:

- Writing any backend component (endpoint, worker, CLI, script, consumer, cron, pipeline, webhook handler, integration), before the first line of code: `skills/think-before-coding/README.md`.
- Creating or changing a schema, entity or ORM model: `skills/data-modeling-discipline/README.md`.
- A new domain concept, a write that changes several rows under one business rule, or a vendor or legacy model entering the code (aggregates, anti-corruption layer, domain names, value objects): `skills/domain-modeling/README.md`.
- Writing, reviewing or running a migration: `skills/migration-safety/README.md`.
- Writing or reviewing a query, ORM call or query builder, pagination, N+1: `skills/query-discipline/README.md`.
- An operation that changes state, charges money, sends a message, calls a third party, emits an event or writes to more than one store: `skills/idempotency-and-side-effects/README.md`.
- Error paths, try/catch, validation at the boundary, retries, timeouts: `skills/error-handling-as-design/README.md`.
- A fix for a race, deadlock, duplicate or Sentry error, or a diff that adds a lock, transaction, signal, `save()` override or serializer write: `skills/anti-patterns/README.md`. A new lock needs its "Adding a lock" defense before any code.
- Logs, metrics, trace IDs and healthchecks for a component: `skills/observability-by-default/README.md`.
- Choosing a database, queue, language, framework, deployment shape or auth scheme: `skills/boring-by-default/README.md`.
- Load, latency budget, caching, connection pools or "make it fast/scale": `skills/performance-and-scaling/README.md`.
- Any diff, new endpoint or change to a backend component, before calling it done: `skills/security-discipline/README.md`.
- Auth flows, permissions, sessions, tokens, OAuth, roles, tenant boundaries, admin paths: `skills/auth-and-authorization/README.md`.
- Something broken, slow, flaky or wrong in staging or production: the `debugging` skill (`~/.agents/skills/debugging/SKILL.md`).
- Writing, reviewing or planning tests, or closing a bug fix: `skills/testing-with-discernment/README.md`.

## Subagents

When a command dispatches agent X (subagent_type `backend-design:X`), spawn a general-purpose subagent whose brief is the body of `agents/X.md` plus the task. In a tool without subagents, follow `agents/X.md` yourself. Tell the subagent that relative paths in the brief are under `~/.agents/skills/backend-design/`.

The same applies when a task matches one of these agents on its own:

- `component-architect`: blueprint for a backend component (dispatched by `design`).
- `schema-reviewer`: review of a CREATE TABLE, ALTER TABLE, ORM model or migration.
- `security-reviewer`: security pass on a diff, file or component before merge.
- `incident-thinker`: likely incident scenarios with detection and recovery, before shipping.
- `incident-investigator`: live investigation of a reported symptom ("it's slow", "we're seeing 500s").
- `boring-tech-advisor`: pushback on a proposal to adopt new infrastructure or tech.

## Checks after writing code

These scripts replace the plugin's write-time hooks. Each one only warns, and it prints nothing when the file is clean or outside its scope.

- After writing or editing a migration file (a path under `migrations/`, `migrate/` or `alembic/`, or a file named like `0001_...`, `V12__...` or `20240101_...`), run `python3 ~/.agents/skills/backend-design/scripts/check_migration.py <path>` and fix what it reports.
- After writing or editing a backend source file (`.py`, `.ts`, `.tsx`, `.js`, `.go`, `.rb`, `.rs`, `.java`, `.kt`, `.cs`, `.php`), run `python3 ~/.agents/skills/backend-design/scripts/check_backend_component.py <path>` and fix what it reports.
- After writing or editing a source or `.sql` file, run `python3 ~/.agents/skills/backend-design/scripts/check_security.py <path>` and fix what it reports.

Each script takes one or more file paths and reads the whole file, so on an existing file it can also flag code you didn't touch. Fix what your change introduced and mention the rest to the user. Test, fixture, `node_modules`, `dist`, `build` and `vendor` paths are skipped. Without arguments, a script reads Claude Code `PreToolUse` hook JSON from stdin, for example `{"tool_name":"Write","tool_input":{"file_path":"/abs/path/x.sql","content":"..."}}`. The migration check matches raw SQL, and it parses Django migrations (`AddField`, `RemoveField`, `AlterField`, `AddIndex`, `RunPython` and the rest) without importing Django. Other ORMs' operations still need the review in `skills/migration-safety/README.md`. `check_migration.py --stdin` checks SQL piped in, such as `python manage.py sqlmigrate <app> <migration>` output.

The scripts need Python 3.8 or newer and only the standard library. They exit 0 after warnings and 1 when a file can't be read.
