---
name: data-pipeline-builder
description: Reviews and writes dbt models and Airflow DAGs so they are tested, documented and safe to rerun. A bundled Python script flags dbt models with no tests, docs or unique key test, sources without freshness, SELECT * outside staging and hardcoded schema.table names, plus Airflow DAGs with no retries, catchup left on, import-time work, credentials in code, datetime.now() or bare except. Use when writing or reviewing dbt models or Airflow DAGs, adding schema tests and docs, or chasing missing retries, unsafe backfills or loads that double data on rerun. Run as /data-pipeline-builder pipeline-check with an optional folder, or /data-pipeline-builder pipeline-new followed by a description of the model or DAG.
argument-hint: "[pipeline-check [folder] | pipeline-new <description>]"
---

# data-pipeline-builder

Ported from the Data Pipeline Builder plugin by Stefan Petrovici (MIT, see `LICENSE`). A text-based Python script checks dbt projects and Airflow DAG files, and the guidance covers dbt layers and schema tests, materializations, DAG defaults, idempotent loads and data quality checks. It reads local files only and never connects to a warehouse. It needs Python 3; `dbt` is optional, for parsing and building models.

Paths below are relative to `~/.agents/skills/data-pipeline-builder/`.

## How to use

- `/data-pipeline-builder pipeline-check [folder]` runs the checker on a folder (the current one by default) and confirms each finding in context.
- `/data-pipeline-builder pipeline-new <description>` writes a new dbt model or Airflow DAG with tests, in the project's style.

Typical order: run `pipeline-check` on the repo and fix the high and medium findings, then use `pipeline-new` for each new model or DAG.

```
/data-pipeline-builder pipeline-check analytics
/data-pipeline-builder pipeline-new daily revenue per customer from stg_orders
```

## Routing

The first word of the arguments ($ARGUMENTS in Claude Code) names the command; read `commands/<cmd>.md` and follow it. Inside that file, $ARGUMENTS means the words after the command name. With no command, show the "How to use" list above.

## Without a slash command

When the task is writing or reviewing dbt models or Airflow DAGs (tests, docs, retries, backfills, idempotent loads, data quality checks), read `skills/data-pipeline-builder/README.md` and follow it.
