---
name: self-improve
description: Turns a project's production telemetry into a ranked fix list. Given a project folder, it finds the project's Sentry projects and Datadog services, analyzes the last 24 hours (or a given window) of errors, logs, traces, RUM and monitors, maps findings to code in that folder, and publishes the report as an Artifact. Use when the user runs /self-improve PATH, asks for an improvement report, or wants to know what is broken or slow in a project from its logs.
disable-model-invocation: true
argument-hint: <project-path> [--window 24h]
---

# Self-improve

Read what the program's telemetry says about the last day, find what is broken, where users struggle and what wastes resources, and hand back a fix list ranked by impact. This skill is read-only: it never edits code, resolves or mutes Sentry issues, changes Datadog monitors or writes anywhere except the report.

## Inputs

- **Project folder** (required): the first argument, e.g. `/self-improve ~/code/myapp`. If none is given, ask for it. Don't fall back to the current directory silently.
- **Window** (optional): `24h` by default. Accept `--window 7d` or plain wording like "past week".

## 1. Identify the project in Sentry and Datadog

Work out the names the project uses in each tool from the folder itself, before querying anything:

- Sentry: grep the folder for `SENTRY_DSN`, `sentry.properties`, `.sentryclirc`, `sentry.init`/`Sentry.init`, `sentry_sdk.init`, and Helm/Terraform values that set the DSN or project slug.
- Datadog: grep for `DD_SERVICE`, `DD_ENV`, `service:` tags in `datadog.yaml`, Helm values, Dockerfiles, `ddtrace` config, and RUM `applicationId`/`service` in frontend init code.
- Fall back to the repo or package name (`package.json`, `pyproject.toml`, `go.mod`, git remote).

Then confirm the names exist: Sentry `find_organizations` and `find_projects`, Datadog `search_datadog_entities` or a service-scoped log query. If several candidates match, or none, ask the user which to use. Default to the production environment unless the user names another.

If either MCP server is missing or fails to connect, say so in the report and continue with the other one. If both are unavailable, stop and tell the user.

## 2. Collect from Sentry

Load the Sentry tools with ToolSearch (`mcp__sentry__*`). For the window:

- Unresolved issues seen in the window, sorted by event count and by users affected (`search_issues`). Note which are new (first seen inside the window) and which are regressions.
- Error volume by issue and release (`search_errors`), to catch spikes tied to a deploy.
- Slow or failing transactions (`search_traces`) and, if the project has them, session replays with errors or rage clicks (`search_replays`).
- For the top 3 to 5 issues by impact, fetch the full event (`get_sentry_resource`) to get the stack trace. Use `analyze_issue_with_seer` only on the top one or two, since it is slow.

## 3. Collect from Datadog

Follow the Datadog MCP server instructions: load the matching Datadog skills first (`load_datadog_skill` for `datadog/logs`, `datadog/traces`, `datadog/rum` as relevant, alongside `list_datadog_skills`), and prefer `execute_code` for the reads so one script can pull and aggregate several sources.

- Logs at `status:error` and `status:warn` for the service, grouped by message pattern with counts (`analyze_datadog_logs` or the SDK equivalent). Look for repeated retries, timeouts, swallowed exceptions and noisy logs that cost money without telling anyone anything.
- APM: endpoints by error rate, p95/p99 latency and request count; slow DB queries and N+1 patterns in spans.
- RUM (frontend projects): JS errors, rage and dead clicks, slow views, frustrated sessions.
- Monitors currently alerting or that flapped in the window, and any incidents touching the service.
- Deploys or change events in the window (`get_change_stories`), so spikes can be tied to a release.

## 4. Correlate and map to code

- Merge findings that describe the same problem across tools (a Sentry issue, its error logs and the failing endpoint in APM are one finding, not three).
- For each finding, locate the code in the project folder from the stack frames, logger names, route or span names. Cite `path:line`. Read the code before proposing a fix; don't propose fixes from the stack trace alone.
- Check `git log` on the file to see whether a recent commit lines up with when the problem started.

## 4b. Find existing discussions in Slack

If a Slack connector is available (`mcp__claude_ai_Slack__*` via ToolSearch), search it for each finding before ranking, so the report links the conversation people already had instead of presenting a known problem as new. Skip this step in one line if Slack isn't connected.

- Search with the specific identifiers first: Sentry issue IDs (`MARKETPLACE-DF2`), error messages, exception names, endpoint paths, monitor names and IDs, release versions. Fall back to plain descriptions ("checkout slow", "502 during deploy") only if those find nothing.
- Search public and private channels you can read, and limit results to the last 90 days unless the problem is older.
- Read the thread before linking it. Link it only when it is about the same problem, and note in one sentence what it says: who raised it, whether someone owns it, whether a ticket or fix exists, or whether it was dismissed.
- Add the thread link to the finding's evidence, and when a thread shows the problem is already owned or being fixed, say so in the finding's actions instead of proposing duplicate work.
- Never post, react or reply in Slack. This step only reads.

## 5. Rank

Sort by estimated impact, highest first. Estimate impact from users or requests affected per day, severity (data loss or failed checkout beats a cosmetic error), and trend (new or growing beats flat). Put the numbers behind each estimate in the finding. Group each finding as one of:

- **Broken behavior**: errors, failed requests, wrong results.
- **User friction**: slow pages, rage clicks, retries the user sees, confusing error states.
- **Inefficiency**: wasted queries, excessive logging, retries that never succeed, oversized payloads.

Also check whether the telemetry is good enough to reconstruct what a user experienced. If it isn't (no request IDs in logs, errors without context, missing spans around key operations, no RUM), add an "Instrumentation gaps" section with specific logging to add: replaying what the user did, meaningful internal operations, and visible outcomes.

## 6. Publish the report as an Artifact

Call the Artifact tool with `action: "quickstart"` and `intent: "other"` first, and follow what it says (load `artifact-design`, follow the page contract). Title it `Self-improve: <project> <YYYY-MM-DD>`.

You must load the `plain-writing` skill before writing any of the report and apply it to every sentence.

Name the repo or service with every release version, error, status code, metric and code path, including in the opening paragraph, so a reader never has to guess which project a number belongs to. When the symptom shows in one project and the cause is in another (for example frontend users seeing 5xx from a backend deploy), name both. Link every release version to its release page (find it with `gh release view <tag> -R <owner>/<repo> --json url`); if no release exists for the tag, link the tag or commit instead.

Keep the report clear, concise and short. A reader should know what to fix first within a minute. Cap it at the 10 highest-impact findings and drop anything without numbers or a code location. Each finding answers four things in a sentence or two each:

- **What**: the problem as the user or system sees it, with the numbers (events, users, requests, latency) and its trend.
- **Why**: the root cause in the code, with `path:line`, and why it matters (who is affected, what it costs).
- **How**: the fix, in a few sentences or a short diff sketch.
- **Actions**: the concrete next steps, each one a task someone can pick up (change X in `path`, add a test for Y, add a log field Z, open a ticket for team W).

The page holds:

1. One short paragraph: the window, sources checked, and the top two or three problems with their numbers.
2. The ranked fix list. Each finding has a title, category and impact estimate, the what, why, how and actions above, and evidence as raw URLs (Sentry issue, Datadog log query, trace or monitor).
3. Instrumentation gaps, if any.
4. Sources that were unavailable or returned nothing, in one line each.

Use one file path per project in the scratchpad (`self-improve-<project>.html`) so a later run on the same day republishes to the same URL instead of creating a new one.

## 7. Reply

End with the Artifact URL (raw URL) and the top three findings in one line each. Don't repeat the full report in chat.
