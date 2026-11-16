---
name: review-pr
description: "Use for any pull request review work: reviewing a whole PR, a branch diff or a feature; reviewing, answering or resolving review comments; writing inline comments; babysitting a PR (watching CI and new comments until it merges); and reviewing the user's own branch before opening a PR. Run as `/review-pr <pr-url>`, or `/review-pr local` for a branch with no PR yet. Builds the PR's intent from its description and Jira ticket, runs a reviewer panel sized by diff size and risk, checks the company's other repos for regressions, and leaves the review pending on GitHub for the user to submit. Not for writing PR descriptions; use `create-pr`."
metadata:
  source: "Full-review flow based on Lauren Tan's pstack `interrogate` and `blast-radius` (MIT), the premise check from pstack `principle-attack-the-premise` (MIT), the code smell baseline and scope-creep check from Matt Pocock's `code-review` (MIT), plus house rules."
---

# IR Code Reviewer

One skill for all PR review work; PR descriptions follow the `create-pr` skill. Pick the mode that matches the request, then follow the shared rules below. Every mode uses the review bar, the cross-repo impact check and the writing rules.

Review like a staff or principal engineer: hold a strong opinion and let the evidence set it, following "Facts and evidence" in `~/.agents/AGENTS.md`. The evidence is a metric, a query count, an `EXPLAIN` plan, a reproduction, a failing test, or a check against a known pattern or anti-pattern. Who wrote the code or the comment, and how sure they sound, don't count. The same scrutiny applies to the author's code, to a reviewer's comment, to the user's own branch and to code the agent wrote. A pattern that already exists in the codebase only shows that someone used it before. When the evidence shows the other side is right, say so plainly.

Workspace values (where local clones live, the GitHub org, the company's shared packages, the prod data source, repo-specific review guides) come from the workspace's own instructions, or from the "Values for review-pr" section of the workspace skill for the repo when one exists.

## Modes

### 1. Full PR review

Use for "review this PR", `/review-pr <pr-url>` or a PR URL. For the user's own branch with no PR yet, use mode 4.

1. **Load the PR.** Run `gh pr view <n> --json title,body,author,headRefOid,baseRefName,files,url` and save the diff (`gh pr diff <n>`) to the scratchpad. Record the head SHA you are reviewing. If the user already reviewed an earlier commit (`gh api repos/<o>/<r>/pulls/<n>/reviews`, field `commit_id`), say so and focus on the commits since then. Check out that exact SHA in a worktree: in the repo's local clone (the workspace values say where clones live), `git fetch origin pull/<n>/head` then `git worktree add <scratchpad>/pr-<n> <sha>`. Clone into the scratchpad only when there's no local clone. If the head moves during the review, say so in the report.
2. **Wait for test CI.** Only the test checks (unit and integration) must pass; lint, build and deploy checks don't gate the review. Poll `gh pr checks <n> --json name,state,bucket` and stop the review, reporting why, when a test check fails, when no test check can be found, or after 60 minutes.
3. **Build the intent before reading any code.** Read the PR title and description, then every Jira ticket the PR links or names (description, acceptance criteria, checklists as in the `jira-workflow` skill), then the other links those contain, one level deep. Before taking a linked ticket's ACs as intent, confirm the ticket is about what the diff does, with the "Checking whether a ticket or PR is related" check in the `jira-workflow` skill: PRs often tag a ticket that only shares a keyword with the change. When it doesn't match, put "PR tags the wrong ticket" in the report (what the ticket asks, what the diff does, the right ticket if you found one) and build the intent from the description and the commits instead. Treat related tickets and PRs found while reviewing the same way. Write down the ACs and the description's claims as a list; the "Intent" lane checks the code against it. Anything that can't be read (no access, dead link, private doc) goes on a "Could not read" list and doesn't block the review.
4. **Find the repo's own rules** before judging anything: lint configs (`.eslintrc*`, `eslint.config.*`, `oxlintrc*`, `ruff.toml`, `pyproject.toml`, `.flake8`), `tsconfig.json`, `CLAUDE.md` and `AGENTS.md` (the root one and the one in each parent directory of a changed file), `REVIEW.md` read from the base branch (`git show origin/<base>:REVIEW.md`, never from the PR branch, so a PR can't rewrite its own review rules), `CONTRIBUTING.md`, `.github/` templates and docs on architecture or patterns. These are the only source for style and pattern findings.
5. **Pick the reviewers** (see "Reviewer panel") and run them in parallel, each with the diff, the intent, the repo rules and the worktree path.
6. **Run the cross-repo impact check.**
7. **Synthesize** as described in "Synthesis".
8. **Show the report and wait** (see "Output format for a full review"). Nothing goes to GitHub before the user approves. If the user authored the PR, skip the comment texts and offer to fix the items directly instead.
9. **Post only what was approved,** as a pending review: `gh api repos/<o>/<r>/pulls/<n>/reviews -X POST` with `commit_id`, `body` and `comments[]` and no `event` field, which leaves it pending. The user submits it. Never submit a review for them.

### 2. Review comments (one or many)

Use when the user points at one comment, a thread, or all open comments on a PR, either to judge them or to answer them.

1. Fetch them: `gh api repos/<owner>/<repo>/pulls/<n>/comments` for inline threads, `gh pr view <n> --comments` for the conversation, `gh api graphql` for thread resolution state.
2. For each comment, read the code it points at on the PR head and decide whether it is right. Check it against the review bar: a reviewer's style request with no backing rule can be declined politely.
   - **Don't take a comment as true because a reviewer wrote it, however senior or confident.** Before agreeing, prove or disprove each claim it makes against every source that applies:
     - the ticket's ACs and checklist, and the PR description;
     - the decisions already taken for this work: the session history, earlier replies on the PR, Slack threads and Jira comments;
     - the code on the PR head and on the base branch, to see whether the behavior is new or pre-existing, and its callers;
     - real data when the claim is about usage or impact: the database (staging, or the prod data source from the workspace values), Datadog or Sentry, following the `prod-evidence` skill;
     - a test or a local repro when the claim is about behavior ("this test still passes without X", "this shows an empty column");
     - an `EXPLAIN` plan or a query count when the claim is about query cost.
   - **A challenge to a mechanism we added gets the same check as anyone else's code.** When a comment asks why the PR uses a lock, cache, retry, new table or signal instead of something else, run the "Design alternatives" lane on our own change before replying. If the defense holds, write it in the PR description (through `create-pr`) and reply with the decision, the one deciding fact and a pointer to it. If it doesn't hold, say so in the reply and change the approach.
   - Accept the comment only when the evidence confirms it **and** the change fits the decisions already taken. When it contradicts an AC or a decision, keep the code and cite the source in the reply. When it can't be verified, say so to the user instead of agreeing. In the report, list for each comment what was checked and what it showed.
   - **Developers don't decide product or domain rules.** When a comment (from any engineer, reviewer, bot or tech lead) asks to change behavior that product, legal, compliance or another non-technical stakeholder already decided (a format, a business rule, what shows where, who sees what), keep the stakeholder's decision. Don't change the code, even if the comment cites a public source. Reply with the decision and its source (ticket, thread), and tell the user what the comment raised so they can take it to the stakeholder if they want. Only bugs, performance and code quality inside the decided behavior get fixed from a developer's comment.
   - Don't agree with everything. When the code is right, keep it, thank the reviewer for the suggestion and say why it stays.
   - A request to deduplicate, extract an abstraction or apply a pattern gets judged with the same criteria as the "Design" lane, and the reply uses the same argument ("two callers that change for different reasons, so I'd keep them apart until a third one shows up"). Apply it when the criteria say so; otherwise keep the code and give the reason.
3. If the comment is valid and the PR is ours, fix the code, run lint and the type check, push and let CI run the tests (see "Running tests locally"), then reply with what changed and the commit SHA. Replies carry no Conventional Comments label (see "Writing rules"). If it is not valid, reply with the specific reason (the rule, the test, the caller that proves it).
4. Replies to inline comments go in the thread: `gh api repos/<owner>/<repo>/pulls/<n>/comments/<id>/replies -f body=...`.

### 3. Babysitting a PR

Use for "babysit", "watch", "keep an eye on" or "get this merged".

Each pass:

1. Check CI (`gh pr checks <n>`). For a failure, read the log, find the root cause and fix it. Don't call a failure flaky or unrelated until it is reproduced or shown to fail on the base branch too. When a second fix fails the same check, run "Attack the premise" in `references/mechanism-defense.md` before writing a third.
2. Check for new review comments and handle them with mode 2.
3. Check mergeability and conflicts with the base branch; rebase or merge the base when needed.
4. Re-run the cross-repo impact check if the new commits change a public contract.
5. Report what changed since the last pass and what still waits on a person.

Use `/loop` (or the harness's scheduler) to repeat passes when the user wants it watched over time.

### 4. Local review

Use for the user's own branch before a PR exists ("review my branch", `/review-pr local`). Same flow as mode 1, without GitHub:

- Diff against the base branch (`git diff <base>...HEAD`) in the current checkout.
- Run the repo's local gates instead of waiting for CI: lint, type check and the tests for the changed files, using the commands the repo defines (`package.json` scripts, `Makefile`, `pyproject.toml`, CI workflow files) and the limits in "Running tests locally". A failing gate is reported as a finding with its output.
- Build the intent the same way, before reading code: the Jira ticket the branch names (ACs and checklist, after the same relatedness check), the draft PR description if there is one, and `git log <base>..HEAD`.
- For a change a user or another service can see, exercise it (start the app and drive the flow, call the endpoint, run the job) and attach the proof per AC; a reading of the code is not a pass.
- End with the report only. Don't post anything and don't fix anything unless the user asks.

When a coding task is done and the change is headed for a PR, decide whether it needs this review first:

- Review it when the change alters behavior: logic, queries, API or event contracts, migrations, permissions, background jobs, or UI state and data fetching. Always review a change that touches a risk area (listed under "Reviewer panel"), whatever its size.
- Skip it when nothing a user or another service sees can change: docs, comments, copy or text fixes, formatting, lockfile or generated-file updates, a version bump with no code change, or a change the user said to ship without review. Say in one line that you skipped the review and why.

To run it, spawn a subagent with this mode on the branch and give it the task goal, the Jira ticket and the base branch, never your reasoning or a summary of what you did, so it judges the result rather than the story. If it can't spawn its own reviewers, it runs Reviewer A itself. In a tool without subagents, run this mode in the same session. The reviewer only reports. Then fix the "Act on" items you agree with, re-run lint and the type check, and list the "Consider" and "Noted" items in your final reply for the user to decide. Open the PR only after that.

## Review bar

Comment only on things that cause a bug, a regression, a security problem, data loss or a broken contract, or that break a rule the repo already defines and you can point to.

- A style or pattern finding needs a source: a lint rule, a TypeScript compiler option, a documented project convention or an established pattern in the surrounding code. Cite it in the comment. If there is no source, don't comment.
- Don't ask for renames, reordering, extra comments, trailing commas, formatting, alternative but equivalent approaches, or "I would have done it differently" changes. Formatting belongs to the formatter. Asking which alternatives were weighed for a risky mechanism (the "Design alternatives" lane) is a different question and stays in scope.
- A small issue becomes worth a comment only when it breaks something: a missing comma that makes JSON invalid, a typo in a migration column name, a wrong import that fails at runtime.
- Missing tests are a finding only when the change alters behavior that nothing tests and a regression there would hurt.
- When unsure whether something is a real problem, check it (run the test, read the caller, query the data) instead of posting a speculative comment. If it can't be checked, ask a question instead of requesting a change.
- A finding about behavior cites the `file:line` that proves it. Inferring behavior from a function or variable name doesn't count.
- Skip generated files, lockfiles and vendored code, and anything lint, the formatter or the type check in CI already enforces.
- Fewer, correct comments beat many weak ones. A review with zero findings is a valid result.
- Two exceptions are never blocking and never required: "Design" lane suggestions (DRY, abstractions, patterns) and a PR description that doesn't match the code. Post them as `suggestion (non-blocking)` or `note:` only when the gain is concrete, with the principle and the `file:line` evidence that make it apply here.

### Likelihood times impact

Score every bug or code change finding from 1 to 10 on two axes: how often it would happen (likelihood) and how bad it would be when it does (impact). Multiply them.

- Below 5: leave the code alone and don't ask for a change in the PR. Propose it as an issue (a Jira ticket through the `jira-workflow` skill, or a GitHub issue where the repo uses them) with the scenario and both scores. File it once the user approves, and link the issue in the review.
- 5 or more: report it as a finding as usual.

Show both scores and the product next to each finding and each filed issue, for example `likelihood 2 × impact 2 = 4`, so the reader can challenge the rating.

## Dependency age gates

A PR that adds an exception to a dependency age gate (pnpm `minimumReleaseAgeExclude`, a Renovate `minimumReleaseAge` override or any equivalent) goes in Act on, even when the exception is for a security fix. The rule lives in the `engineering-practices` skill.

## Running tests locally

When the PR is the user's own (fixes for review comments, a rebase or a merge of the base, any follow-up commit), don't run test suites or spec files locally. Run lint and the type check on the changed files, push, and let CI run the tests. Report "tests: left to CI" with the pushed SHA, and check the CI result before calling the fix done.

Never run a heavy test suite (a full integration or e2e suite) inside Docker, and never start several Node processes to run tests: no two suites at the same time, no suite per reviewer, and no suite in the background while installs, builds or other tests run. Run one targeted spec file at a time (for example `vitest run <spec>`) and leave full suites to CI. This applies to the lead and to every reviewer, so put it in each reviewer's brief.

## Cross-repo impact check

A change in one repo can break another. Before finishing a review (or before opening our own PR), search the other company repos for anything that depends on what the diff changes.

1. List what the diff changes at a boundary: API routes, request and response fields, serializers, GraphQL types, event or topic names and payloads, database tables and columns (including reporting tables an ETL reads or writes), shared package exports (the company's shared packages named in the workspace values, shared UI libraries), env vars, feature flag names, Celery task names, URL paths used by the frontends.
2. Search local clones first, in the location the workspace values give. Use `rg -n "<symbol>" <dirs> --glob '!node_modules' --glob '!*.lock'`. Pull or fetch first if a clone looks stale.
3. Search GitHub for repos not cloned locally: `gh search code --owner <org> "<symbol>"`.
4. For each hit, open the file and decide whether the change breaks it: removed or renamed field, changed type or nullability, changed default, changed ordering or grouping, new required parameter, changed status code.
5. Report only confirmed or likely breakages with the file path and line in the other repo. If nothing depends on the change, say which symbols were searched in one line.

## Reviewer panel

Size the panel by the diff and its risk. Risk areas: auth and permissions, payments, money and tax math, migrations, order state transitions, a lock added or widened (`select_for_update`, advisory locks, a wider `atomic`), shared querysets or serializers, shared UI components.

- Under 300 changed lines and no risk area: Reviewer A only, on Opus at medium effort.
- Otherwise: Reviewer A on Opus at high effort, plus Reviewer B on Sonnet at medium effort.

The value of B is a second model's view, not more effort. Don't raise B's effort; that was tried and the extra cost didn't pay off. Each reviewer covers every review lane below and applies the review bar before reporting. Record each reviewer's tokens and duration for the report. In a harness without model choice, run Reviewer A only and say so in the report.

Each reviewer's brief includes this, from pstack `interrogate`: "Try to break this change. Back each correctness finding with a run against the real code (a failing test, a repro script, or command output that shows the wrong behavior) and report the command, its output and the output the intent requires. A finding you didn't run is reported as unverified."

### Optional lanes in a Claude Code session

Only when this runs inside Claude Code; in any other agent, skip them and say so in the Cost line.

- `/code-review low <PR#|origin/<base>...HEAD>` as a cheap third opinion on a risk-area diff. Treat its output as one more reviewer's findings: they go through Synthesis like the others. Never pass `--comment` or `--fix`.
- For a large diff in a risk area, suggest the user run `/code-review ultra <PR#>` (cloud review, 5 to 15 minutes, 3 free runs per account, then about $5 to $25 each). Claude can't start it. Never use `--post`, because that post signs "Generated by Claude Code".

### Optional council with another vendor's model

Run it when the user asks for it or the diff is in a risk area, unless the repo's AGENTS.md or CLAUDE.md, or a workspace skill, limits which models may see its code. When it does, skip the council: the A and B panel above covers the same ground with allowed models.

1. Run another vendor's model as Reviewer C on the same diff, intent and brief (for example `codex exec` in the worktree, read-only).
2. Give each reviewer the findings of the others and ask it to confirm or refute each one with evidence.
3. Stop when they agree or after two rounds. Agreed findings go through Synthesis as usual; findings they still disagree on become open questions.

## Review lanes

Every reviewer covers these.

Always:
1. General correctness: logic errors, regressions, behavior that doesn't match the ticket, missing tests on changed behavior.
2. Verification: are the PR's claims backed by evidence (tests run, numbers measured, repro shown)? What wasn't verified? Check perf, flakiness and production-behavior claims with the `prod-evidence` skill.
3. Security (`security-review` skill): trust boundaries, authn/authz, injection, secrets in code or logs, data exposure.
4. Intent: check the code against the list from "Build the intent". For each AC, find the code and the test that meet it. Code that misses or contradicts an AC goes in Act on and can block. Code that does more than the ACs ask is fine and doesn't block, unless the extra behavior breaks something on its own. Code that differs from the PR description doesn't block either: ask for the description to be updated in a non-blocking note.
   - A test only meets an AC when it checks what the AC claims. A test that only asserts the code didn't throw, allows a wider tolerance than the AC, or asserts against a mock of the behavior it should test leaves that AC untested.
   - Diff the branch's test files against the base (`git diff <base>...HEAD`) for weakening: loosened assertions, widened tolerances, new skips or todos, deleted cases. Weakening goes in Act on.
   - Scope creep: list each behavior the diff adds that no AC or description line asked for, with the hunk. It stays non-blocking as above, and goes in Consider when it carries its own risk (a new mechanism, a contract change) so the author can split it into its own PR, or in Noted otherwise.
5. Performance: on every review, check the diff against the fix patterns in the `perf-review` skill (its "Match each spot to one case" list) without running its full profiling pass. Run that pass only when the diff changes a hot path (a list endpoint, checkout, a job over many rows) and a workload can run. On backend code always look for N+1: queries or remote calls inside loops, serializers, templates or properties that read related objects without `select_related`/`prefetch_related`, and per-row lookups in list endpoints. Confirm with a query count on the changed path (`CaptureQueriesContext`, `assertNumQueries` or `django_assert_num_queries`) at two list sizes when a test can run, and report the counts.
6. Design: repetition, abstractions, separation of concerns and the patterns the surrounding code already uses, judged by the "Design and architecture" and "Comments and docstrings" rules in the `engineering-practices` skill and never enforced as rules. Cite the neighboring code when the PR departs from it. A comment or docstring that restates the code gets deleted before pushing in our own code, and suggested as non-blocking on someone else's PR.
   - Check the diff against the code smell baseline in `references/code-smells.md` (Fowler's smells, each a judgment call that the repo's own rules override).
   - Judge cleanups (dead code, needless nesting, redundant abstractions, unclear names) with the rules in the `code-simplifier` skill. The review only reports them as Design findings; in `local` mode the main session can then run `code-simplifier` on the changed files to apply the ones the user accepts.
7. Callers ("network effects"): follow every caller of the touched code, not only the code around it in the same file. List each function, class, exception, model field, manager or queryset method, serializer, viewset action, template, component, prop, store field and Celery task the diff adds or changes, then search the whole repo (and the other repos, per "Cross-repo impact check") for its callers. Ask of each caller: does it now get a new exception or status code, a changed return type, nullability, default or ordering, extra queries per row, or data it shouldn't see? Does a subclass or sibling path (another endpoint, API version, mode or flow doing the same job) still have the old behavior? Are `mock.patch` targets and fixtures in tests now hiding a changed signature? A caller that breaks is a finding even though its line is outside the diff; anchor the comment on the changed line that causes it. The lane is done when every symbol has its outside callers named in the report, or "none" with the search that was run. When the workspace values name a repo's own caller table, use it for that repo.
   - From pstack `blast-radius`: look where a symbol search stops (the library's source at its pinned version, JSON an API returns, a DB column another job reads, a feature flag, a consumer three hops away). Then name the one fact the change is safe because of ("this only drops cache entries that are already dead") and push it as far down this ladder as is cheap: stated, pointed at a `file:line`, failure walked step by step, ran in a script or test against the real code, reproduced in the running app. The report says the fact and the step it reached, or "unproven".
8. Base comparison: for each behavior the diff changes, compare what the base branch does with what the branch does for the same input, and report the difference as "on `main` X returns 200; with this change it returns 400". Look for inputs that worked on the base and now fail, inputs that failed and still fail through a sibling path (the same bug in neighboring fields or endpoints), and guards that skip the changed code (a service that ignores a field when another one is sent). Check this by running the PR's new tests, or a request, against the base checkout: a new test that also passes on the base proves nothing about the change. When the PR description claims "nothing that works today breaks" or "no behavior change", try to falsify it this way before accepting it.
9. Design alternatives: for each risky mechanism the diff adds or widens (a lock, a cache, a retry, a new table or column, a signal or save hook, a background job or queue), find which alternatives the author weighed and why they lost, in the PR description, the ticket or the commits. Following an existing pattern doesn't count as a reason. Read `references/mechanism-defense.md` for the alternatives per mechanism, the lock defense and the premise check, and compare the mechanism with the anti-pattern catalog at `~/.agents/skills/backend-design/skills/anti-patterns/README.md` (for serializer writes, `save()` overrides and signals, entries D2, D4 and D5).
   - No alternatives named: a finding in Consider, asking which ones were weighed and naming the two the reference suggests for this mechanism.
   - A lock with no whiteboard defense (the race, the alternatives, the lock order against every other path that locks the same rows, and a reproduction): Act on, tagged correctness, because a lock in the wrong order trades one deadlock for another. Say in the report that a human reviewer must approve it too.
   - The second or later fix for the same symptom: run "Attack the premise" from the reference and report the premise and what the check showed.

When the diff touches frontend code (`*.js`, `*.ts`, `*.tsx`, `*.vue`, components, routing, client data fetching, styling): add a frontend lane. Use `vue-router-best-practices`, `web-design-guidelines` or `frontend-design` when relevant. Check rendering and state regressions, loading and error states, cache invalidation and request/response assumptions.

When the diff touches backend code (Django, Node services, SQL, migrations, jobs, auth): add a backend lane. Use `django-expert` or `postgres-best-practices` when relevant. Check validation, authz, transactions, races, idempotency, query correctness and performance, and API contract compatibility. Run the matching `backend-design` commands on the changed files (each is a file under `~/.agents/skills/backend-design/commands/`, so a reviewer subagent can read it directly):
- A migration or schema change: `review-migration.md`, then `python3 ~/.agents/skills/backend-design/scripts/check_migration.py <files>`. The script parses Django migrations too (`AddField`, `RemoveField`, `RenameField`, `AlterField`, `AddIndex`, `AddConstraint`, `RunPython`, `RunSQL`). When Django runs, check the exact SQL with `python manage.py sqlmigrate <app> <migration> | python3 ~/.agents/skills/backend-design/scripts/check_migration.py --stdin`.
- A new or changed endpoint, worker, consumer, cron job, CLI or third-party integration: `audit.md`.
- Raw SQL or an ORM query on a large or growing table: `explain-this-query.md`.
- A list endpoint, serializer, template or loop over a queryset: `hunt-n-plus-one.md`, on top of the N+1 check in the Performance lane.
- A Django or DRF view, viewset, serializer, queryset or task that reads or writes company data: `~/.agents/skills/django-expert/references/access-and-performance-review.md` (cross-company access trace, unbounded querysets, missing indexes, write loops).
- Every changed backend file: `python3 ~/.agents/skills/backend-design/scripts/check_security.py <files>` and `check_backend_component.py <files>`. The scripts read whole files, so report only what the diff introduced and confirm each warning in the code before it becomes a finding.

When the diff changes how parts of the system work together (a new service, queue, cache, table or index on a hot path, background job, external call, cross-service contract, or a data volume or traffic pattern that grows), add a system-design lane. Read `~/.agents/skills/system-design/SKILL.md` and the topic files it routes to for each building block the diff touches. Say how the change affects the current architecture (load, consistency, failure modes, the next bottleneck at 10x), and propose a simpler, more modern or faster alternative when one exists, with its trade-off. These are "Design" suggestions, so they never block unless they expose a real defect.

When the diff adds or changes a status or state field, a flag that gates behavior, or a write to one, run "Check one machine" from the `hunting-bugs` skill on that machine only.

## Synthesis

The lead (you, not a reviewer) judges every finding. Don't merge reviewer output as-is.

1. Deduplicate across reviewers. A finding both reviewers raised independently is stronger evidence.
2. Re-check each finding against the code at the reviewed SHA and the review bar. Score likelihood × impact.
3. Verify independently: for each candidate Act on and Consider finding on a risk-area diff, start a fresh-context subagent with only the finding, the SHA and the worktree path, told to refute it. A finding it refutes drops to Consider or Dismissed.
4. Put each in one bucket:
   - **Act on**: verified, scores 5 or more. Should block or change the PR.
   - **Consider**: scores 5 or more but unverified, or a judgment call the author should weigh.
   - **Noted**: real but scores below 5, or a pre-existing bug the PR neither introduces nor worsens (never Act on). Proposed as an issue to file (see "Likelihood times impact"), filed only once the user approves.
   - **Dismissed**: fails the review bar or is wrong. One line on why, so the user can overrule it.
5. Tag each with its dimension: correctness, intent, security, performance, design, contract (cross-repo), data or migration, tests, or repo rule. Design findings and description mismatches go in Consider or Noted, never Act on. The one exception is a lock with no whiteboard defense, which is tagged correctness (lane 9).
6. Turn conflicts the evidence can't settle into open questions.

## Writing rules

- Load the `plain-writing` skill before writing a PR description, a review body, an inline comment or a reply. Apply it to every piece of text that will be posted.
- Comments are short: what breaks, under which input or state, and the fix if it is clear. Cite the rule or the caller when there is one. Use a GitHub `suggestion` block when the fix is a few lines.
- Hard limit: at most 2 short sentences and 250 characters per inline comment, reply or review body (URLs and the `suggestion` block not counted), plus an optional `suggestion` block. Add at most one link, and only when it is the evidence. Don't restate context the author already knows (what the PR does, how deploys work). Review bodies get one sentence or none.
- Start every new review comment (a finding opened on someone's PR) with a Conventional Comments label (https://conventionalcomments.org) in bold: `**issue (blocking):**`, `**suggestion (non-blocking):**`, `**question (non-blocking):**`, `**nitpick (non-blocking):**`, `**note:**`, `**praise:**`. Use `(blocking)` only for findings in the Act on bucket.
- Never put a Conventional Comments label (or any bold label like `**note:**` or `**fixed:**`) on a reply to a comment, even when the comment you answer has one. A reply is plain prose, in the voice of the `reply-with-standing` skill: say what changed and the commit, or why not, and the one ask if there is one.
- Before posting, re-fetch every other reviewer's comments, including ones added while the review ran. Drop any finding someone already raised, and don't repost a finding whose earlier thread was resolved or answered with a reason; read those replies first. When yours adds something to their point (a different fix, a missed consequence), reply in their thread in one or two sentences instead of opening a new comment.
- Show the drafts to the user and post only after they approve. Replies and comments may go out directly if the user already said to post, but a full review always stays pending for the user to submit.

## Output format for a full review

1. Verdict: approve, comment or request changes, in one line with the reason, and the SHA reviewed.
2. Numbered items grouped by bucket (Act on, Consider, Noted, Dismissed), highest score first. Each one: `file:line`, dimension, the likelihood × impact score, what breaks and when, whether it is verified and how (command, test or caller read), and the fix if clear. For Act on and Consider, add the inline comment in English, ready to post. Skip comment texts when the user authored the PR.
3. Cross-repo impact: affected repos with file and line, or the one-line "searched X, Y, Z; no consumers" note.
4. Open questions.
5. Could not read: each link or source the intent step couldn't open.
6. Cost: reviewers used (model and effort), tokens and duration for each.

The user approves by item number ("post 1, 3, 4"). Post those and nothing else. If there are no findings, say so and name any residual risk or verification gap.

Keep the chat report short as well: one or two lines per item, Dismissed items as a single list line each, and no section for something with nothing to say.

## Don't skip

Don't skip the intent, performance, callers, security, verification or design alternatives lanes or the cross-repo check because the diff is small, looks like a refactor or seems to touch only one layer. Small diffs break other repos too.
