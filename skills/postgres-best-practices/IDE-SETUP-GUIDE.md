# IDE Setup Guide — MySQL & PostgreSQL Best Practices Skills

This guide explains how to use the `mysql-best-practices/` and `postgresql-best-practices/`
skill packages in every major IDE and AI coding tool.

---

## Folder Layout

```
your-project/
├── mysql-best-practices/       ← MySQL 8.0/8.4, RDS for MySQL, Aurora MySQL 3
│   ├── SKILL.md
│   ├── README.md
│   ├── sample/
│   │   ├── schema.sql
│   │   └── bad_queries.sql
│   └── references/             ← 50+ rule files
├── postgresql-best-practices/  ← PostgreSQL 14-17, RDS for PostgreSQL, Aurora PostgreSQL
│   ├── SKILL.md
│   ├── README.md
│   ├── sample/
│   │   ├── schema.sql
│   │   └── bad_queries.sql
│   └── references/             ← 50+ rule files
└── IDE-SETUP-GUIDE.md          ← this file
```

Drop one or both skill folders into your project root, then follow the instructions
for your IDE below.

---

## 1. Agents that load skill folders

Claude Code, Codex, Gemini CLI, opencode, Cursor and other agents that read `SKILL.md` folders pick the skill up from their skills directory (for example `~/.agents/skills/` or `~/.claude/skills/`). The `description` in the `SKILL.md` frontmatter tells the agent when to load it.

To apply the rules every time the agent touches SQL, add a line to the project's agent instructions file (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`) or a Cursor rule. Sections 2 and 4 show examples.

### Verify It Is Working

Ask the agent which skills or files it has loaded (in Claude Code, `/context` lists them).
Then test with:

```
> Review this for performance issues:
  SELECT * FROM orders WHERE YEAR(created_at) = 2024
```

The agent should flag `YEAR()` wrapping an indexed column and suggest the range rewrite.

### One-shot questions from the terminal

```bash
claude -p "What is the minimum MaxConnectionsPercent for db.t3.medium on RDS Proxy?"
codex exec "How does TempTable overflow behave on Aurora MySQL readers?"
gemini -p "Review this PostgreSQL schema for index issues"
```

---

## 2. VS Code

### Option A — Continue.dev (Open Source, Works with Claude / GPT / Ollama)

1. Install the [Continue](https://marketplace.visualstudio.com/items?itemName=Continue.continue) extension.
2. Add the skill folders as doc sources in `.continue/config.json`:

```json
{
  "contextProviders": [
    {
      "name": "folder",
      "params": { "nDirs": 1 }
    }
  ],
  "docs": [
    {
      "title": "MySQL Best Practices",
      "startUrl": "file:///absolute/path/to/your-project/mysql-best-practices/SKILL.md"
    },
    {
      "title": "PostgreSQL Best Practices",
      "startUrl": "file:///absolute/path/to/your-project/postgresql-best-practices/SKILL.md"
    }
  ]
}
```

In Continue chat, use `@MySQL Best Practices` or `@PostgreSQL Best Practices` to
pull the rules into context.

### Option B — GitHub Copilot Chat

Copilot Chat does not load skill folders, but you can reference files directly
in chat with `#file`:

```
@workspace Review this SQL for performance issues.

Context:
#file:mysql-best-practices/references/query-functional-indexes.md
#file:mysql-best-practices/references/query-aggregation-over-join.md
```

Alternatively, open the relevant reference file as an editor tab — Copilot Chat
automatically includes open tabs as context.

### Option C — Cursor

Create a `.cursorrules` file in your project root:

```
When reviewing or writing SQL, apply the rules in:
- mysql-best-practices/references/ for MySQL and Aurora MySQL queries
- postgresql-best-practices/references/ for PostgreSQL and Aurora PostgreSQL queries

Always check:
- query-functional-indexes.md before any WHERE clause that wraps a column in a function
- query-aggregation-over-join.md for any query JOINing multiple one-to-many tables
- query-pagination.md / data-keyset-pagination.md before using OFFSET
- lock-deadlock-prevention.md for any transaction that updates multiple rows
```

In Cursor chat, reference specific rules with `@`:

```
@mysql-best-practices/references/lock-deadlock-prevention.md
Review this transaction for deadlock risk: [paste SQL]
```

---

## 3. JetBrains IDEs (IntelliJ, DataGrip, PyCharm, GoLand, etc.)

### Option A — JetBrains AI Assistant (Built-in)

1. Open any reference file in the editor.
2. In the AI Assistant chat panel, click **Include file in context**.
3. For a persistent setup: **Settings → AI Assistant → Context** and add the
   `references/` folder.

### Option B — DataGrip (Database-Specific Workflow)

DataGrip has built-in EXPLAIN Plan and Query History tools. Complement them with
the skill files:

1. Open `mysql-best-practices/sample/bad_queries.sql` or
   `postgresql-best-practices/sample/bad_queries.sql` as a **Scratch File**
   (`Cmd/Ctrl + Shift + Alt + Insert`).
2. Keep it open as a lookup reference while writing queries.
3. Bookmark the `references/` folder under **Scratches and Consoles** for
   one-click access to any rule.

---

## 4. Claude Code

Since Claude Code has direct file system access, you can reference skill files
in any prompt:

```bash
# Review specific SQL against a rule
> Read mysql-best-practices/references/lock-deadlock-prevention.md and
  review the following transaction for deadlock risk: [paste SQL]

# Broad review of a directory
> Using the rules in mysql-best-practices/references/, review all SQL
  files in src/queries/ for performance issues

# Aurora-specific review
> Apply advanced-aurora-mysql3.md and advanced-aurora-reader.md from
  mysql-best-practices/references/ to review this query: [paste SQL]

# PostgreSQL upsert review
> Read postgresql-best-practices/references/data-upsert.md and check
  whether this insert is race-condition safe: [paste SQL]
```

### Add a CLAUDE.md to Your Project

Create a `CLAUDE.md` file in your project root so Claude Code applies the rules
automatically in every session:

```markdown
# CLAUDE.md

## Database Code Review

When writing or reviewing SQL, apply the rules from:
- `mysql-best-practices/references/` for MySQL, RDS for MySQL, and Aurora MySQL
- `postgresql-best-practices/references/` for PostgreSQL, RDS for PostgreSQL,
  and Aurora PostgreSQL

Always check these rules before generating or reviewing SQL:
- `query-functional-indexes.md` — any WHERE clause that wraps a column in a function
- `query-aggregation-over-join.md` — any query that JOINs multiple one-to-many tables
- `query-pagination.md` / `data-keyset-pagination.md` — any query using OFFSET
- `lock-deadlock-prevention.md` — any transaction that updates multiple rows
- `advanced-aurora-mysql3.md` / `advanced-aurora-postgresql.md` — Aurora deployments
```

---

## 5. Any AI Chat Tool (Claude.ai, ChatGPT, Gemini)

For tools without file system access, paste the relevant reference file contents
directly into your prompt:

```
I need you to review this SQL. Apply these rules:

---
[paste the full contents of query-functional-indexes.md here]
[paste the full contents of query-aggregation-over-join.md here]
---

Query to review:
[your SQL]
```

**For an ongoing session:** paste the contents of `SKILL.md` at the start of the
conversation. This gives the assistant the full rule index. Reference specific
files by name as the conversation continues — the assistant will ask you to paste
them as needed.

---

## 6. Team Setup

### Check In the Skill Folders

```bash
git add mysql-best-practices/ postgresql-best-practices/ IDE-SETUP-GUIDE.md
git commit -m "Add MySQL and PostgreSQL skill packages"
```

Every developer who clones the repo gets the skills and this guide automatically.

### Adding Your Own Rules

```bash
# Copy the template
cp mysql-best-practices/references/_template.md \
   mysql-best-practices/references/query-your-new-rule.md

# Or for PostgreSQL
cp postgresql-best-practices/references/_template.md \
   postgresql-best-practices/references/query-your-new-rule.md
```

Fill in: `title`, `impact`, `bad example`, `good example`, `why it matters`.
Then add a row to the matching category section in `SKILL.md`.
If it is a commonly hit pattern, add it to `sample/bad_queries.sql` too.

The full writing guidelines are in `references/_contributing.md` in each package.

---

## Quick Reference: Which File to Open for What

| You are doing... | MySQL file | PostgreSQL file |
|---|---|---|
| Writing a WHERE clause with a function | `query-functional-indexes.md` | `query-sargable-expressions.md` |
| Paginating a large table | `query-pagination.md` | `data-keyset-pagination.md` |
| JOINing multiple one-to-many + aggregating | `query-aggregation-over-join.md` | `query-aggregation-over-join.md` |
| Writing a multi-row transaction | `lock-deadlock-prevention.md` | `lock-deadlock-prevention.md` |
| Setting up connection pooling | `conn-rds-proxy.md` | `conn-pgbouncer.md` |
| Deploying on Aurora | `advanced-aurora-mysql3.md` | `advanced-aurora-postgresql.md` |
| Designing a new table | `schema-primary-keys.md` + `schema-data-types.md` | `schema-primary-keys.md` + `schema-data-types.md` |
| Upgrading database version | `advanced-mysql84-features.md` | `advanced-pg17-features.md` |
| Query is slower than expected | `monitor-explain-analyze.md` | `monitor-explain-analyze.md` |
| Table growing large / slow scans | `monitor-performance-schema.md` | `monitor-autovacuum.md` + `monitor-bloat.md` |
| Securing a new database user | `security-auth.md` + `security-least-privilege.md` | `security-roles-privileges.md` + `security-ssl-tls.md` |
| Multi-tenant data isolation | *(use RLS at app layer)* | `security-row-level-security.md` |
| Aurora reader query fails | `advanced-aurora-reader.md` | `advanced-aurora-postgresql.md` |
| Bulk loading data | `data-batch-inserts.md` | `data-batch-inserts.md` |
| Checking replication lag | `monitor-replication.md` | `monitor-replication.md` |

---

## Troubleshooting

**Skill not loading**
- Confirm the folder is in the agent's skills directory and `SKILL.md` starts with frontmatter that has `name` and `description`.
- Some agents read skills only at session start, so restart the session after adding it.

**Agent not referencing the right rules**
- Open `SKILL.md` and confirm the rule file names match what is in `references/`.
- Ask the agent which files it loaded (in Claude Code, `/context`).
- For Copilot/Cursor, paste the reference file content directly if `#file` is not working.

**Rules feel generic / not Aurora-specific**
- Explicitly mention the deployment target in your prompt:
  `"This runs on Aurora MySQL 3"` or `"This is RDS for PostgreSQL on db.r6g.large"`.
- Pull in the Aurora-specific files directly:
  `advanced-aurora-mysql3.md`, `advanced-aurora-reader.md`, `advanced-aurora-postgresql.md`.

**Want rules for a language-specific ORM (SQLAlchemy, GORM, ActiveRecord)**
- Add a line to the project's agent instructions file (or a Cursor rule with a
  glob matching your language files, e.g. `**/*.py`, `**/*.go`, `**/*.rb`)
  pointing to the relevant references.
- Add ORM-specific rules to `references/` following the `_template.md` pattern.
