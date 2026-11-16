---
name: prod-evidence
description: Use whenever a claim about production or staging needs proof from real data instead of an assumption. Covers Datadog APM, RUM, logs and deploys, Sentry errors, trace span analysis, data warehouse and staging database queries, proving a number on two sources, calling a CI failure flaky, and when prod shell, kubectl or database access is allowed (only when the user says so). Sets how to report the result, always with numbers, the time window, the query used and a direct link. Use it from triage, Jira tickets, PR reviews, incident work and perf investigations.
---

# Prod evidence

Confirm with real data. Never assume how production behaves from reading code or one trace.

Workspace values (data sources and how to reach them, Datadog retention, cluster limits, SQL rules for the user's client) come from the workspace's own instructions, or from the "Values for prod-evidence" section of the workspace skill for the repo when one exists.

## Datadog

Follow the Datadog MCP's own setup first: load the matching Datadog skill (`load_datadog_skill`, `list_datadog_skills`) and read data through `execute_code`.

- APM keeps data for as long as the workspace values say. Query by `resource_name` (the endpoint or task), not by service alone, so the numbers belong to the code path in question.
- RUM keeps data for as long as the workspace values say. Use it for views and users per company: how many customers hit a page and how often.
- Errors: use RUM errors and Sentry together, and line them up with deploys (Datadog deployment events, `get_change_stories`, merged PRs and release tags). An error that starts at a deploy points to that deploy's PRs.

## Trace spans

Before calling a span the dominant cost, add up the spans of that kind in the trace. If the sum is larger than the trace's wall-clock time, those spans run async or concurrently and don't block the request, so cutting them won't make it faster by that amount.

For ranking slow paths and confirming an N+1, follow the `perf-review` skill.

## CI failures

Call a failure flaky only when its stack trace matches the CI failure exactly. A similar error in a different place is a different failure, so find its cause.

## Production access

Never run `kubectl exec`, open a shell (`manage.py shell`, `psql`) or query the prod database unless the user explicitly says so in this conversation, for this task. Read-only intent doesn't make it OK, and approval given in an earlier conversation or for another task doesn't carry over. Get prod evidence from Datadog, Sentry, the prod data source the workspace values name or the feature flag tool first. When the answer needs prod rows those can't give, write the query and hand it to the user to run, or ask them for access.

## Shell on staging or prod

On prod, these rules apply only after the user's go-ahead (see "Production access").

- Read-only. No writes, migrations, deletes or management commands that change data.
- Confirm the environment before running anything (`kubectl config current-context`, the host, the database name).
- Always pass `--context` explicitly on `kubectl`. Never rely on the current context.
- Check field and table names before querying (model definition, `\d table`, a one-row select) so the query doesn't fail or, worse, return the wrong thing.
- Check what each cluster lets you do before planning a shell. The workspace values list the known limits (for example `pods/exec` denied) and how to reach the database instead.

## Database and warehouse

Prove every number on two sources. Run the query yourself, then confirm it on a second source: for business data, the two sources the workspace values name (for example a prod warehouse and a staging database), or Sentry and Datadog for errors and traffic. When the sources disagree, report both numbers and explain the gap before drawing a conclusion.

- **Staging database:** connect the way the workspace values say. Never print, read or copy credential files, and never put credentials in a command, env var or file. Never turn off a read-only setting, never use `BEGIN READ WRITE`, and run only `SELECT`s.
- **A copy of prod data** (the workspace values say whether staging holds one): check `MAX(created_on)` to see how old the copy is. Because this is real customer data, report counts and aggregates only, with no names, emails, addresses or other personal fields in the output.
- **Prod warehouse** (connection and schemas in the workspace values): when staging holds a prod copy, run the same query on staging and in the warehouse and compare the results. They should match to within the rows created since the staging copy and staging's own test rows. Explain any larger gap before you use either number.
- **Prod SQL for the user to run:** follow the table prefix and the syntax limits the workspace values give for the user's client.
- Count active entities in a recent window (last 12 months), not all-time totals. A table with 4,800 rows and none from the last two years points to a feature nobody uses.
- Code shows what the system can do; whether anyone uses it comes from data. Follow the claim to the customers it serves and check they exist today: a validator that supports a country means nothing when the data shows no orders from that country in years.

## Reporting

Every finding carries:

- The number (counts, p50/p95/p99, error rate, rows, bytes).
- The time window it covers.
- The query used, copied as run.
- A direct link to the Datadog view, trace, Sentry issue or CI log.

If the data can't be reached (no access, data past retention), say so and say what was checked instead. Don't fill the gap with a guess.
