# Impact analysis

Used by every review mode: the full PR review, the local review and each babysitting pass with new commits. It traces what the change touches beyond the edited lines, so a regression in a caller, a job, another repo or a customer flow shows up before merge. The method is adapted from pstack's `blast-radius` (a skill by Lauren Tan, MIT, https://github.com/cursor/plugins/tree/main/pstack/skills/blast-radius, read at commit bf0c7cd80abd): listing callers is the easy part, and the job is the breakage a symbol search won't show, plus proof of the one fact the change is safe because of.

## Contents

- Inputs
- 1. Read the change
- 2. Trace outward
- 3. Look where the search stops
- 4. The one fact it's safe because of
- 5. Sort the risks
- Report

## Inputs

The diff (for a babysitting pass, only the commits since the last pass: `git diff <last-sha>..<head>`), the intent list, the worktree path and the workspace values (where local clones live, the GitHub org, shared packages, the ETL whose tables count as a boundary, a repo's own caller table). `scripts/review-bundle.sh` gives the changed symbols and their callers outside the diff as a starting list.

## 1. Read the change

List every symbol the diff adds, changes or deletes: function, class, exception, model field, manager or queryset method, serializer, viewset action, URL, template, component, prop, store field, Celery task, signal receiver, setting, env var, flag. For each, write what it now does differently, including what the diff doesn't spell out: a changed default, ordering or grouping, a new exception or status code, a nullable value, an extra query per row, a write that moved inside or outside a transaction, work that moved from the request to a job or back.

## 2. Trace outward

Cover each kind below. Each item in the report carries a `file:line`, or "none" with the search that was run.

1. Callers. Search the whole repo for every symbol from step 1. Ask of each caller: does it now get a new exception or status code, a changed return type, nullability, default or ordering, extra queries per row, or data it shouldn't see? Does a subclass or sibling path (another endpoint, API version, mode or flow doing the same job) still have the old behavior? Are `mock.patch` targets and fixtures in tests now hiding a changed signature? A caller that breaks is a finding even though its line is outside the diff; anchor the comment on the changed line that causes it. When the workspace values name a repo's own caller table, use it for that repo.
2. Callees. What the changed code now calls that it didn't, or calls differently: new arguments, a call moved into a loop, a callee with side effects (an email, an event, a write, an outbound request) that now runs more often, earlier, or inside a transaction that can roll back after it ran.
3. Paths. Name each entry point that reaches the changed code (route, view, Celery task, management command, consumer, cron job, signal, webhook handler, page or component) and walk one request or job from the entry through the change to its effects. Entry points from `.cartographer/` output (`endpoints.json`, `pipelines.json`, or the readonly cache in `~/.cartographer/`) save time when they exist; `/cartographer map <repo> --readonly` is cheap (about 30 seconds, no subagents) when the repo is large, has no output yet and text search can't find the paths.
4. Shared data. Each table and column, cache key, queue or topic, event, file or bucket key, browser storage key and feature flag the change reads or writes. Find every other reader and writer: search for the model and table name, the cache key prefix, the topic name, the storage key. Ask whether the others now see a different value, a new state, a null, a different format, or a write that lands at a different time (before or after commit, before or after a job reads it).
5. Public contracts. API routes and request and response fields, serializers, GraphQL types, event and topic names and payloads, webhook payloads, CLI commands and flags, config keys, env vars, feature flag names, Celery task names and arguments, URL paths the frontends use, shared package exports (the company's shared packages from the workspace values, shared UI libraries), and database tables and columns another job reads (including reporting tables an ETL reads or writes).
6. Other repos and services. For each contract and shared datum, search the local clones first, in the location the workspace values give: `rg -n "<symbol>" <dirs> --glob '!node_modules' --glob '!*.lock'`. Pull or fetch first if a clone looks stale. Then search GitHub for repos not cloned locally: `gh search code --owner <org> "<symbol>"`. Open each hit and decide whether the change breaks it: removed or renamed field, changed type or nullability, changed default, changed ordering or grouping, new required parameter, changed status code.
7. Background jobs and deploy order. Jobs that call the changed code or read the same data, scheduled jobs, and work in flight during the deploy: a task enqueued by the old code with the old arguments and run by the new code (and the reverse), a migration that runs while the old code still serves, a cache filled by the old code and read by the new.
8. Feature map. When the repo has `docs/feature-map/map.yaml` (see the `feature-map` skill), list the features whose facts point at changed files (`grep -n "<path>" docs/feature-map/map.yaml`), and run `uv run --no-project --with pyyaml python ~/.agents/skills/feature-map/scripts/feature_map.py check` in the worktree. Report the features the change reaches, and each fact it makes stale as a Noted item ("map fact `<id>` needs updating").

## 3. Look where the search stops

A symbol search misses the breakage that matters most. Follow these by hand: the source of a library the change calls, at its pinned version and with any local patch; the JSON an API returns and the code that parses it; a database column another job or service reads; a wire format or bytes another language reads; a feature flag that forks the path; dynamic dispatch (`getattr`, task names as strings, signal receivers, DRF router names, dynamic components, i18n keys, templates that read attributes by name); and code three hops downstream. Work out when things run, too: on commit hooks, unmount and teardown, retries, timeouts.

Three more places a caller search can't reach:

- Neighbors. Code that never calls the change but acts on the same object at runtime: other scripts on the same page, handlers on the same event, hooks, middleware, signals, other writers of the same record. When the change captures or compares state (a snapshot, a baseline, a dirty check, a cache, a diff), list everything else that changes that state and when it runs relative to the capture: on load, after it, on a user action. A neighbor that changes the state after the capture makes the change read the neighbor's work as the user's.
- What the old path got for free. When the change replaces or bypasses a path, or claims to behave like it ("same as a full save", "no behavior change"), list the implicit rules the old path leaned on, such as a framework default for an omitted value, an input the browser never sends, an ORM hook or a validator. Then check each state the old path handled (empty, omitted, disabled, hidden, null, a field with a default and one without) through both paths. Each must come out the same, or the difference goes on the intent list.
- Hand-built inputs. Tests that build the request, event or payload themselves agree with the author's model of the producer, not with the producer. Capture one real input (the rendered page's form data, a real event, a real API response) and compare it with what the tests send. A field that differs is a finding until it's explained.

## 4. The one fact it's safe because of

Most changes that look risky are safe because of a single fact ("this only drops cache entries that are already dead", "no caller passes `None` here"). Find it and spend the time proving it instead of on a long list of maybes. Push it as far down this ladder as is cheap, and say where it stopped:

1. Stated. Worth nothing on its own.
2. Pointed at a real `file:line`, or the library's own source.
3. The failure walked step by step, and it doesn't reach.
4. Ran in a script or test that calls the real code and fails loud if the fact is wrong.
5. Reproduced in the running app.

If it can't be proven, the report says "unproven".

## 5. Sort the risks

Score each risk with likelihood × impact as the review does. Keep confirmed and likely breakages as findings; they go through Synthesis with dimension contract or correctness. List the risks checked and cleared separately, one line each with the search or line that cleared them. A search that finds nothing is an answer; never invent a caller, an API or a consumer.

When the trace shows a trigger the diff alone didn't (a changed helper reached from a webhook handler, a payment flow or a public API), name the specialist check it calls for, so the lead can start it.

## Report

- What the change does, including the part the diff doesn't spell out.
- Areas reached: each feature, module, job, repo or project, with `file:line` or the search that found it.
- Side effects: behavior other code, another service or a user now sees, each with its path from the change.
- Neighbors and old-path rules from step 3, each checked or "none" with the search.
- Breakages: confirmed or likely, each with `file:line` in the affected code (the other repo's path for cross-repo), likelihood × impact, and how it was checked.
- Cleared: what was checked and why it's fine, one line each.
- The safety fact, the ladder step it reached and its proof, or "unproven".
- Specialist triggers found by the trace, if any.

Done when every changed symbol has its outside callers named, every shared datum its other readers and writers, every captured state its other writers, and every contract its consumers, or "none" with the search that was run.
