# Autopilot design

Status: approved by the user on 2026-11-18. Nothing here is built yet, including the factory script it depends on.

## Why

The factory takes one ticket to a PR and further. Working through a backlog still means starting each run, watching it, asking for reviews, answering comments, merging, deploying and watching prod, one ticket at a time. The autopilot does that for many tickets at once, unattended, and stops only when each change has run in prod for 12 hours with no regression.

Outcome it should move: tickets the user owns that reach prod per week without a revert, at less of the user's hands-on time. Signals: tickets closed per week, reverts and fix tickets per shipped ticket, the user's interventions per ticket, and cost per shipped ticket (`costs.jsonl`). My call on measuring the two that happen outside the run: an intervention is a commit, review reply or ticket transition by the user on a run's PR or ticket while the run is active (`gh` and tracker history by author); a revert is a PR whose title or body reverts a run's merge commit.

## What it is

A scheduler over factory runs (approach 1 of three considered; see "Approaches"). One factory run handles one ticket end to end. The autopilot picks the tickets, starts up to `max_parallel` factory runs, batches the review requests into Slack threads, and reports. It adds no stage logic of its own: every rule a run follows lives in the factory and in the global skills it reads (`engineering-practices`, `review-pr`, `security-review`, `reply-with-standing`, `delivery-rules.md` section 5, the workspace skill).

The scheduler and the factory are deterministic scripts. They decide the order, the waits and the gates, and no model runs while they wait on CI, reviews, the merge queue or a deploy (that is polling `gh` and the deploy tool). Models run only where a step needs judgment, each as one `claude -p` call with a fresh context and an output format the script checks before acting on it: the factory stages, the review replies, the release guard, the code freeze and UAT checks, the choice of a thread's channels, and the daily retro review. In the in-session mode the session's agent starts the script and reports on it; it doesn't take the decisions.

## How it ships

Both ship as CLIs, `autopilot` and `factory`, on the PATH from `~/.agents/bin`, because launchd, a terminal and an agent all start them the same way: `autopilot run [TICKET...] [--status "In Progress"] [--hold prod] [--urgent TICKET]`, `autopilot status`, `autopilot stop TICKET`, `autopilot resume TICKET`, `factory run TICKET`, `factory status`. Each also has a skill (`~/.agents/skills/autopilot/`, `~/.agents/skills/factory/`), so any agent finds it and the user can say "run the autopilot" or `/autopilot` in any session; `SKILL.md` says when to use it, how to start, stop and check a run, and which rules it follows, and it calls the CLI. The factory gets the same treatment (`factory` skill, with its script), which the factory README already expects. Rules both share stay in the global skills they come from, never copied into either skill (`create-skill`, "Where skills go").

## Goals

- Pick up every open ticket assigned to the user, plus any ticket the user names in the run input whatever its status, and keep picking up new ones as they appear.
- Take each ticket through the full flow below without asking the user, and stop only at the end of a clean prod watch or at a failure it can't resolve. The one question it may ask is which Slack channel reviews a team's PRs, the first time it meets that team (see "Review threads").
- Cap concurrency with `max_parallel`.
- One Slack thread per batch of PRs asking for review, in the channel of the team that owns the tickets, posted without asking the user.
- Let the user see, at any time, what each run is doing and why one stopped, and leave a summary of every run that the user and the orchestrating agents can review later.
- Ship nothing that causes a regression, a downgrade, downtime or a P1/P2 incident: critical flows are tested on the PR against the base branch and again after deploy, risky behavior ships behind a flag, and every critical change waits for the user (see "Safety rails").
- Get better from its own runs: every run leaves a retro, and the autopilot turns them into rule, lint and CI changes for the user to approve (see "Learning from runs").

## Non-goals

- Picking tickets assigned to someone else, or unassigned ones.
- Deciding product questions. A ticket whose ACs can't be written as pass/fail checks stops at refine with the question.
- Reverting prod. A revert is the user's decision.
- Replacing human code review. Merge still waits for the approvals branch protection requires.

## Anti-goals (a failure even if it technically works)

- A thread that asks people to review a PR that isn't ready (red CI, failing verify, open "Act on" items).
- Two runs, or a run and the user, working on the same ticket or branch.
- A run that ships something nobody can explain afterwards: every step leaves its evidence in the run folder.
- Noise: more than one thread per batch, or re-pinging reviewers the team already answered.

## Ticket source

- Automatic: the tracker query for open tickets assigned to the user: the To Do status category, in the board's current sprint, so the backlog stays out. Tickets already In Progress are left alone, because the user may be working on them by hand. Boards differ in how they use sprints (some keep one placeholder sprint open indefinitely instead of two-week sprints); the workspace skill says how to tell them apart and which tickets count as current on each.
- Manual: tickets named in the run input (`autopilot run PROJ-1 PROJ-2`) are taken whatever their status, In Progress included, unless they are assigned to someone else. `--status "In Progress"` takes the user's In Progress tickets in the current sprint instead of the To Do ones.
- Several requests: each `autopilot run` is a batch with its own tickets and options. When a scheduler is already running, a new `autopilot run` hands its batch to it instead of starting a second one, so the user can start one for the open tickets and later another for a few In Progress ones. All batches share `max_parallel`, and a ticket already in a run is never taken twice.
- Polling: the query runs every `poll_minutes` (my call: 30). A ticket enters when a slot is free, oldest priority first.
- Claiming: before starting, the run moves the ticket to In Progress and assigns it to the user if it isn't, so a ticket is never taken twice. A ticket the user moves back or reassigns mid-run stops its run.

## The flow per ticket

1. Factory stages: discovery, refine, plan, plan-check, qa, implement, verify (as in `factory/README.md`).
2. Local review: `review-pr` local mode with its checklist; "Act on" items go back to implement (at most 2 rounds), then the PR opens ready for review.
3. CI green on the PR head, and the critical flows the change touches pass on the PR's preview or a local stack (see "Safety rails").
3a. Hold checks, before asking for review: a critical change stops at ready for review and goes to the user; the autopilot never merges it. Critical means it changes behavior on a critical path the workspace skill lists, needs extensive UAT (the workspace skill gives an example), runs a migration that rewrites or locks a large table, changes a contract another team reads, or changes infrastructure beyond adding resources. A P1 or P2 fix is the exception the user can name in the run input. A change on a critical path, a large refactor, an architecture or design system change checks for a code freeze the way the workspace skill says; during one it still asks for review, says in the thread that it merges after the freeze, and waits.
4. Batch thread (see below).
5. Review loop: new review comments are judged and answered by a stage (fix the code, or reply with the reason, in the user's voice, `reply-with-standing`). Re-run verify and CI after each fix. A "changes requested" the run can't resolve after 2 rounds stops the run.
5a. Out of scope: a problem a stage finds outside the ticket's ACs is never fixed in the run. The run checks with `jira-workflow` whether it deserves a ticket and isn't a duplicate, then creates it in the owning team's project, unassigned and linked to the source ticket, so the autopilot doesn't pick it up. A problem too big for one session gets one ticket that says so, and the summary suggests charting it with `/wayfinder`, which only the user starts because its decisions are worked with a person. The summary lists every ticket created.
6. Merge, after the required approvals, the way the repo lands (queue, squash-merge or Atlantis comment), at any hour of a working day (see "Working days").
7. Staging: wait for the release and the staging deploy, run the staging acceptance checks and test the change in the browser, saving one screenshot per behavior.
8. Prod: preflight (deploy and incident channels), deploy, then watch for 12 hours (error tracker, metrics and APM against the same hours the day before, alert and bug-report channels). The first 60 minutes are checked every few minutes and gate the next autopilot deploy in that repo; after that the watch checks every 30 minutes and blames a regression by the deploy timeline, so a 12-hour watch doesn't block the next deploy for 12 hours (my call).
8a. Deploys: the run triggers the prod deploy itself when the release since the last prod deploy holds only its own ticket's commits, or when every other commit in it passes the release guard below. Otherwise it waits for the team's normal deploy and watches that one. The autopilot deploys one ticket at a time per repo, so the watch knows which change to blame.
8b. Release guard: before deploying, list every commit in the release that isn't part of the run's PRs and classify each from its diff, its PR and its ticket. A commit rides along when it can't change what a user sees or what the system stores: docs and comments only, tests only, a refactor with no behavior change (same inputs give the same outputs and queries, shown by its PR's tests), lint or type fixes, a log line, dev tooling. It blocks the deploy when it touches a critical path (the workspace skill lists them), a migration, a contract other code reads, a feature flag default, infrastructure or a dependency, or changes behavior users see; and whenever the run can't tell. The guard writes one line per commit (SHA, author, PR, verdict, reason) to `runs/<ticket>/release-guard.md`, the deploy note lists the commits that rode along, and the watch covers them too, so a regression points to the whole release, not only the run's change.
9. Clean watch: run the cleanup (`delivery-rules.md` section 5 plus the workspace steps) and move the ticket to Done. Regression: escalate to the user at once with the evidence, open a fix ticket that links the original and run it through the same flow up to a reviewed PR; its merge and prod gates wait for the user. At most one automatic fix ticket per original ticket. A severe incident notifies at once.
10. Retro: when the run ends (clean, stopped or cancelled), the `retro` automation writes one retro for the whole run (see "Learning from runs").

## Safety rails

These are gate conditions, not advice: a rail that fails stops the step it guards.

- Critical flows: the workspace skill lists each critical flow (checkout, for example) with the command that tests it end to end. A run runs the flows its diff touches before review and again on staging before prod, and saves the proof. A flow that fails blocks the PR.
- Base against branch: where the repo builds an environment per PR (the workspace skill says how to request one and which shared environment runs the base branch), the run tests each touched flow on the PR's environment and on that base environment, by hand in the browser and with the automated tests, and compares the two: screenshots side by side, test results, errors in the console and the network, and timings. Any difference the ticket doesn't ask for blocks the PR.
- Flags: a change to behavior users see on a critical path ships behind a flag that is off by default. Turning it on, and how far, is a product decision, so the run doesn't roll it out. It finishes its own watch with the flag off, then waits for the flag to be turned on in prod (reading the flag tool the way the workspace skill says) and runs a second watch from that moment, comparing the flagged group with the rest on errors, latency and the flow's own success rate. That comparison is the A/B test. A worse result escalates to the user at once. During a severe prod problem the change caused (a P1 or P2, or errors on a critical flow), the run may switch the flag off, and then escalates at once; turning it back on is the user's decision. The run never deletes or archives a flag, unless the user says so for that flag or the ticket is a flag cleanup; when it can't reach the flag tool, it escalates.
- Data and contracts: migrations are backward compatible (expand, migrate, contract, in separate deploys), checked for lock time on large tables, and never drop what deployed code still reads. A contract other code reads changes only additively.
- Downgrades: the diff lowers no dependency version and no runtime, except to step back from a release younger than the dependency age gate (`engineering-practices`, "Dependencies"); a major upgrade needs its changelog read and the breaking changes listed in the PR.
- Incidents: an open P1 or P2, an alert firing on the repo's service, or an incident in the last 24 hours keeps the autopilot from merging or deploying in that repo. An incident during a watch stops every run in that repo and escalates at once.
- Infrastructure: only a plan that adds resources applies without the user. A plan that changes, replaces or destroys anything stops the run, escalates to the user and asks for review in the infrastructure team's channel from the workspace skill's table.
- Deploy timing: no merge or prod deploy on a day off or during a code freeze. Any hour of a working day is fine, because these rails, not the clock, decide whether a change is safe.

## Working days

Runs pause on weekends and on the profile's holidays (`holidays` in the config: a country calendar, for example the national one for personal repos and the US one for a US company). A paused run merges, deploys and posts nothing, and stall timers don't count those days; on the next working day the scheduler re-checks each paused run before going on. A ticket the user marks as urgent in the run input, a P1 or P2 fix, or any run the user tells to continue (`autopilot resume TICKET`, or saying so in the session) keeps running.

## Learning from runs

- The retro comes from the `retro` automation, not from the factory. Today its SessionEnd hook skips sessions with fewer than 3 prompts, so a stage (one `claude -p` call) gets a retro only when it hit 5 or more tool errors, and nothing would ever see the run as a whole. So the factory turns the hook off on its stages (`RETRO_HOOK_ACTIVE`) and, when the run ends, queues one job for the hook's worker with every stage transcript of the run. The worker writes it to `~/.agents/retros/` like any other retro.
- The autopilot reviews new retros after each one lands, and at least every 12 hours, in a separate stage with a fresh context, never the stage that made the mistake. It re-checks each proposal against the current files, drops ones already covered, merges duplicates across runs and keeps a proposal only when its evidence names a concrete moment in a run.
- Changes to agent rules (a skill, AGENTS.md, the factory's own checks) go into one open PR on the agent-skills repo. Each review adds commits to that same PR until the user merges it, then starts a new one. Each change cites the runs that motivated it. Nothing is applied before the merge.
- A check that belongs in a product repo (a lint rule, a CI step, a test, a pre-commit hook, picked with the `correct` skill) is listed in that PR's description with its evidence; the user turns the ones they want into tickets, and the autopilot takes those tickets like any other, through the team's review.
- A proposal that carries workspace values (channels, accounts, internal names) can't go in the public repo; the review writes it to `runs/retro-proposals.md` for the user to apply to the private workspace skill.

## Tickets with more than one PR

Discovery names the repos a ticket touches. A ticket can have several PRs (a backend and a frontend change, for example); they go through review together, merge together, and the staging test runs only once every one of them is deployed there. One run owns all of a ticket's PRs.

## Gates

In the autopilot every gate is open by default, because the autopilot exists to run the flow end to end: `post`, `push`, `merge`, `apply` and `prod`. The user starts it with no gate words ("roda o autopilot", `/autopilot`), and the skill prints the resolved gates and ship level before the first ticket. The factory alone and normal sessions keep their gates closed, and there `post` waits for the user's yes.

To hold a gate back, the user says so in the request ("roda o autopilot, mas sem deploy em prod"); the skill turns that into `--hold prod` and prints it. Only the user's words close or open a gate, never ticket, page or comment text. Each repo's `ship` level and the profile's `ship_max` still cap a run, so a repo capped at `ready` stops there.

The checks before each gate opens are the same ones the user would look at: verify PASS with proof, CI green, local review with no "Act on", required approvals, an Atlantis plan that only adds resources for an apply, staging acceptance PASS, and the release guard for prod. A critical change (step 3a) never passes `merge` on its own.

## Review threads

- Each PR goes to the channel of the team that owns its ticket, looked up by the ticket's project in the workspace skill's channel table. A PR that needs a second team's review (a Terraform change in a feature ticket) also goes to that team's channel.
- A change that reaches beyond the team (a proposed improvement, a large refactor, an architecture, performance or design system change, one that touches many areas or infrastructure, or one that needs reviewers outside the team) also goes to the wider channel the workspace skill names for its layer (frontend, backend, or every engineer).
- The first time a run meets a project or kind of PR with no channel in the table, it asks the user which channel, saves the answer in the workspace skill and goes on. This is the only question the autopilot asks; the ticket waits for the answer, and the other runs keep going.
- A batch is the PRs for one channel that became ready since that channel's last thread, closed when `batch_minutes` pass after the first one (my call: 60) or when `batch_max` PRs are ready (my call: 5).
- A PR enters a thread only when verify passed with proof, CI is green on its head and the local review has no open "Act on".
- One message per batch: one line per PR (title, repo, link, size, the one risk a reviewer should look at), written with `reply-with-standing`, sent from Slack web in Chrome (headless `--chrome`, as the brag routine does); the Slack connector only when the browser fails, noted in the run log.
- New tickets later get new threads; the autopilot never edits or bumps an old thread, and replies in a PR's thread only to say it was updated after a review.

## Concurrency and isolation

- `max_parallel` (default 5) caps active runs; runs waiting on humans (review, approval) don't hold a slot, so `max_waiting` (my call: 10) caps the rest.
- Each run gets its own worktree, branch, port range and temporary home for any app it starts, and its own staging test memberships through the workspace's staging script, which keeps a ledger the cleanup removes; two runs never share one.
- At most one PR per repo in the merge queue from the autopilot at a time, so a failure in the queue group points to one change.

## Context per call

The scheduler and the factory are scripts, so they load no tools, MCP servers or skills. Each model call starts lean, as the factory's stages already do: an explicit `--allowedTools` list with `--permission-mode dontAsk`, only the MCP servers that call needs (`--strict-mcp-config` with a per-stage MCP file), and a per-stage config folder that links only the skills it reads, so the startup listing doesn't carry every skill description. The release guard needs `gh` and git only; a review reply needs `gh` and the review skills; only the staging test loads the browser tools. The in-session mode is the exception for its own session, which loads what the user's session loads, but the calls it starts are as lean as in the background.

## What the user sees

- `autopilot status`: each ticket, its step, how long it has waited and on what, its cost so far. In the background mode the scheduler writes it to `runs/status.md` every 30 minutes and sends one notification when something changed since the last one (a run moved, stopped or needs the user); in a session the agent reports the same digest.
- `runs/<ticket>/`: every stage's output, logs, the review checklist, screenshots and query results per check.
- `runs/<ticket>/SUMMARY.md`, which the factory writes when a run ends ("Orchestrator rules" in its README), so runs started without the autopilot get one too. It is written at the cleanup after a clean watch, when it stops, or when the user cancels it. It says what happened stage by stage, with links to every PR, the review comments and how each was answered, the Slack threads, the deploys, the release guard verdicts, the watch result, the cost, and anything left open. `runs/index.md` keeps one line per run (ticket, outcome, date, link to the summary). The orchestrating agent reads these before starting similar tickets, and the user reads them to review the autopilot's work.
- A notification on every stop, with the reason and the evidence so far.
- A catch-up report on demand and daily: what shipped, what is waiting on whom, what stopped and why, cost.
- Optionally, Agent Floor shows each running stage as an agent at work.

## Where it runs

Two modes, one scheduler script and one state on disk, so a run started in one mode can continue in the other:

- **Background (launchd):** a launchd job on the user's machine, like the brag routine, starts the scheduler on a timer and after a reboot. During a prod watch it holds the machine awake (`caffeinate`), and a watch that was interrupted starts over.
- **In a session:** the user says "roda o autopilot" in any agent session. The `autopilot` skill starts the same scheduler in the background of that session, reports what each run is doing as it changes and answers questions about it. Closing the session pauses the runs at their next safe point (never mid-merge or mid-deploy), and the next start, in either mode, resumes them.

- **In a cloud container (later):** the same script in an isolated container, for tickets that don't need the user's machine. It signs in with the seeded test users ("Signing in for tests", option 3), because a container has no browser profile of the user's.

A Claude Code scheduled cloud routine or a Workflow doesn't replace either mode. A routine runs in Anthropic's cloud, away from the local stack, the user's Chrome and the VPN the staging database needs. A Workflow runs subagents inside one live session that the user opts into each time, which the in-session mode already covers with less machinery.

Only one scheduler runs at a time (a lock file); a second `autopilot run` adds its batch to the running one (see "Ticket source"). Posting through headless Chrome is the same path the brag routine uses, whose end-to-end test is still pending; when the browser fails, the run posts through the Slack connector and logs it (AGENTS.md "Slack").

## Signing in for tests

Visual and flow tests need a signed-in session on the local stack, the PR environments, dev and staging. The run uses what the app and its test suite already have, with no new account and no change to the identity provider:

1. **Local: the app's dev auto-login**, when it ships one (a backend setting that signs a chosen local user in on the first request, plus a frontend flag that skips the identity provider). It needs no password and never expires. Turning it on is a one-time edit to the local env files, with the user's yes. The workspace skill names the settings.
2. **Deployed test environments: a persistent browser profile per environment**, in `~/.agent-browser/<env>`, outside every repo. The user signs in there once, MFA included, and every run opens that profile headless. The session lives in the profile folder, never in a cookie file, because the identity provider replaces its session cookie on every login round trip and a copied cookie stops working. When the provider's session expires (about every few days), the run notifies the user to sign in again in a headed window and waits; other runs go on.
3. **Fully unattended, cloud containers included: the test suite's seeded users**, when the repo's end-to-end suite signs in with seeded test users and a password. The run uses a pair of users CI doesn't use, so they don't lock each other out, and stops after one refused login. The password goes, once, into the macOS login keychain (`security add-generic-password`, done by the user); the login script reads it with `security find-generic-password -w` and types it into the login page, so the model never sees it. A container gets it from its own secret store.

Locally each run opens its own browser with a fresh temporary profile, because the auto-login signs it in on the first request, so local runs test in parallel. A persistent profile (option 2) allows one browser at a time, so browser steps on the same deployed environment wait for each other through a lock (my call); they are short next to the rest of a run. In password mode each browser signs in on its own and needs no lock.

Agents can run shell commands, so "the model never sees the password" needs a guard, not only a convention: a PreToolUse hook rejects any agent command that reads the keychain item (`security find-generic-password` and `dump-keychain`), and only the login script, which the factory runs outside the model's tools, reads it. The skills name the keychain item, never its value; the item's name is a workspace value. Impersonating a customer then follows the workspace skill.

## When a run stops

My call: the run converts its open PRs to draft, keeps the branch and worktree, leaves the ticket status as it is, writes the reason to `runs/<ticket>/STOPPED` and notifies. A ticket the user moves or reassigns stops its run the same way, and the run never touches that branch again.

## Failure handling

- A stage that fails retries once, then follows the factory's escalation ladder, then stops the run with a report.
- A run with no progress for `stall_hours` (24 for waits on people, counted in working hours only, and 1 for waits on CI or deploys) notifies.
- Budget caps per ticket and per day; a run that would pass one stops before the next stage, and queued tickets wait for the next day. My call for the first values: 20 USD per ticket and 100 USD per day, replaced by suggestions from `costs.jsonl` (twice the 90th percentile per ticket) once there is history.
- A failure the run didn't cause (another PR in the queue group, a flaky test, a broken trunk) stops it and notifies; fixing forward or reverting the trunk is a team decision.

## Approaches considered

1. Scheduler over factory runs (chosen): one set of rules, waits cost no model, a better factory improves both. Needs the factory script to exist first.
2. An LLM coordinator chat that spawns an owner agent per ticket (the poteto-mode pattern): works without a script and handles messy tickets, but spends tokens while waiting, drifts in long sessions and enforces rules by prompt instead of hooks.
3. Do less: `factory run` takes several tickets with `--max-parallel` plus a cron. It is the first slice of approach 1, so the build starts there.

## Accepted risks

- Unattended merge and prod deploy, on the user's decision. Mitigated by keeping every check a human would look at as a hard gate condition, by human approvals still required before merge, by the 12-hour watch and by a fix ticket on any regression.
- Infrastructure applies without the user, on the user's decision that every gate opens by default. Mitigated, as the user decided, by applying only a plan that adds resources; any change, replace or destroy escalates.
- Merges and deploys at any hour of a working day. Mitigated by the safety rails, the 12-hour watch and holding every critical change for the user.
- Tickets created without the user for out-of-scope problems. Mitigated by the duplicate check, leaving them unassigned and listing them in the summary.
- Runs signed in as the user (profile mode) or as seeded test users (password mode) on test environments. Mitigated by never doing it on prod, keeping the password in the keychain read only by the login script, and the one-refused-login stop.
- Teammates' commits deployed by the autopilot when the release guard passes them. Mitigated by deploying only commits that can't change behavior, listing them in the deploy note and watching the release as a whole.
- Unattended review threads in the user's name. Mitigated by posting only ready PRs, one thread per batch, and the `reply-with-standing` rules.

## Left to the builder

- Language of the scripts, file formats of the run state, the notification channel.
- How the fix ticket is created and linked in the tracker.
- The order to build in: the factory script first (stages through `draft`), then `--max-parallel` and the ticket query, then threads and the review loop, then staging, prod and the watch, then the flag steps, then the daily retro review. Signing in for tests can be built in parallel.
