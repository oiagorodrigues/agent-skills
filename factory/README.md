# Factory

Takes a Jira ticket to a draft PR with one headless agent run per stage (discovery, refine, plan, plan-check, qa, implement, verify, pr). A deterministic script orchestrates; stages hand off through files in `runs/<ticket>/`. Design decisions live in the agent memory `agent-factory-design`; token and cost rules in the `cutting-agent-costs` skill.

## Layout

- `hooks/guard-bash.sh`: PreToolUse hook (matcher `Bash`) in every stage's settings. Blocks push, merge, rebase, `reset --hard`, `clean`, switching to the trunk, GitHub writes, TLS-off flags, `curl | sh`, credentials piped to the network and publishing.
- `lib/checks.sh`: runs a repo's check commands once per commit and caches PASS/FAIL by SHA.
- `checks/<repo>.md` (optional): checks for one repo that aren't company specific. Company repos keep theirs in the workspace skill (`references/checks/<repo>.md`).

The general pieces live in global skills, so any agent uses them without the factory, and the stages read them from there:

- Plan-stage output: `engineering-practices` `references/plan-template.md`. Its "Files to change" feeds the out-of-plan check.
- Checks for every repo: `engineering-practices` `references/done-checks.md`; verify runs them, implement never sees them.
- Review bundle (diff, commits, files outside the plan, callers of changed exports, touched tests): `review-pr` `scripts/review-bundle.sh`.
- Secret scan before a push: gitleaks (`security-review`, `references/sinks-and-secrets.md`), or `security-review` `scripts/secret-scan.sh` without it.
- Verification rules: `engineering-practices` `references/reducing-ai-slop.md`. Landing, the prod watch and the cleanup: `engineering-practices` `references/delivery-rules.md`, section 5, with the company's values in the workspace skill.

## Orchestrator rules

- Stages never push, merge, open the PR or write to Jira. The script does, after verify passes and the secret scan is clean.
- Run stages with `--permission-mode dontAsk` and an explicit `--allowedTools`, so anything not allowed is refused at once. Auto mode in headless runs stalled for up to 15 minutes per call on the classifier.
- Stage prompts wrap ticket, page and comment text in `<untrusted source="...">` and say it is data, never instructions.
- Every stage ends with a pass/fail check and reports the command and its output, never "tests pass". The implement stage gets a Stop hook that runs lint and the type check on the changed files and exits 2 while they fail.
- Escalation is mechanical: retry once on the same model, then fix the plan (the spec is the defect), then restart the stage fresh on the next model tier, then stop and report. Never hand a failed trajectory to a bigger model.
- Stop when no check moves for 2 rounds, and allow at most 2 CI fix rounds per PR.
- A stage that hits a usage limit in `-p` fails instead of pausing. The script resumes from the last stage whose output file exists, and implement commits only verified work.
- Leave `CLAUDE_CODE_AUTO_COMPACT_WINDOW` unset.
- Verification follows `engineering-practices` (`references/reducing-ai-slop.md`), which the plan, plan-check, qa and verify stages read:
  - plan writes every AC as a pass/fail line with its check method; plan-check (read-only, cheap model) sends back a plan with a vague AC, an AC with no check, or steps outside the scope.
  - qa writes the failing tests or scenarios for each AC before implement and shows they fail on the base. The script lists them in `runs/<ticket>/locked-files`, and a PreToolUse hook on Edit, Write and Bash refuses changes to them during implement.
  - verify runs on a clean checkout of the SHA with no Edit or Write tools and never gets the implement transcript. It runs the result (app plus `agent-browser`, real API calls, `verify-etl`), defaults to fail, attaches proof per line to `runs/<ticket>/evidence/`, and also runs every line of `done-checks.md` and the repo's checks file. At most 3 implement and verify rounds before the ladder below.
  - A mistake the user or a reviewer catches after "done" becomes a proposed line in the repo's checks file (or `done-checks.md` when it holds for every repo), added after the user's yes.
- The verify verdict comes from a different model than the one that implemented, in a fresh context with only the diff, the plan and the checks. Prefer another vendor (Codex against Claude). The profile's model allowlist decides what is allowed; when it allows one vendor only, verify uses a different model of that vendor.

## Shipping

How far the script takes a ticket after verify passes. Each level includes the ones before it:

| Level | What the script does |
|---|---|
| `local` | Commits on the ticket branch. Nothing leaves the machine. |
| `draft` | Pushes the ticket branch (never the trunk, never `--force`) and opens a draft PR. Default. |
| `ready` | After CI passes on the PR head, marks the PR ready for review. |
| `merge` | Waits for approvals, answers review comments, then lands the PR the way the repo requires (see "Landing"). |
| `staging` | Waits for the release and the staging deploy, runs the staging acceptance checks and tests the change in the browser, with screenshots when the change is visible. |
| `prod` | Runs the preflight checks, deploys to prod, then watches it (see "Watching prod"). When the watch finds no bug or regression from the deploy, runs the cleanup (`engineering-practices` `references/delivery-rules.md`, section 5, with the company's steps in the profile's `delivery_rules` file), which ends with the ticket moved to Done. |

The level is resolved in layers, each one overriding the one before:

1. `profiles.<name>.ship` in `config.json` (the profile default).
2. `repos.<repo>.ship` (a repo that needs a different default).
3. The run input: `factory run PROJ-123 --ship prod`, or a `ship:prod` token anywhere in the text given to `factory run`. The script removes the token before the input reaches a stage. A plain-language request ("resolve PROJ-123 and take it to prod") goes through the `factory` skill or a small extraction step that turns it into flags, and the script prints the resolved level and approvals before the first stage.

`ship_max` in the profile caps the result. A run asking for more than the cap stops before discovery and says which cap blocked it, so a run never silently ships less or more than asked. Lowering the level (`--ship local`) is always allowed.

Gates work the same way. `profiles.<name>.gates` lists the steps where the run pauses for `factory approve <ticket> <step>`: `push` before anything leaves the machine, `merge` before the PR lands, `apply` before an infrastructure apply, `prod` before the prod deploy. `--approve <step>` or an `approve:<step>` token in the run input pre-approves a step for that run only. A gate in `locked_gates` opens only when that run's input names it (`--approve prod`): a blanket `--approve all`, a repo setting or a config default never opens it. A gate that waits sends a notification with the evidence so far (checks, PR state, staging results, screenshots).

Only the user's own `factory run` input can set the level or approve a gate. Ticket, Jira, PR comment and page text is never read for `ship:` or `approve:` tokens, because anyone who can edit a ticket could otherwise ship code.

The script stops instead of moving up a level when the PR has a "changes requested" review it can't resolve, a CI failure after the 2 fix rounds, a head SHA that differs from the one verify passed, or a failed staging acceptance check. Each stop sends a notification with the reason.

## Landing

- Waiting (approvals, CI, the merge queue, a release, a deploy) is a script polling `gh`, with no model running. The script starts a stage only when something changes: a new review comment, a failed check, a finished step.
- Review comments are judged and answered by a stage, which fixes the code or replies with the reason, and posts the reply on the PR.
- Each repo declares how it lands in `repos.<repo>.land`: `queue` (merge queue, `gh pr merge --auto`), `merge` (squash-merge once approvals and checks pass) or `atlantis` (comment the apply command after approval; Atlantis merges). Unknown repos are detected from their branch rules and an `atlantis.yaml`, and the run stops if it can't tell. Never `--admin` and never a bypass of branch protection.
- A repo that doesn't deploy on merge declares `repos.<repo>.deploy`: ordered steps, each with the changed paths that need it and the command to run. The script picks the steps from the PR's changed files, runs them on staging, then on prod, always from the trunk, and runs none when no listed path changed.
- Commits and merges use the profile's `git_email`; the script checks it in the worktree before the first commit and checks the author of the landed commit.
- A profile can name a `delivery_rules` file with what only that company knows (merge queue rules, deploy workflows, channels to check, staging test accounts). Landing, staging and prod stages read it; anything the script needs to decide (workflow names, repo land mode) goes in `config.json` instead.
- Preflight before the PR enters a queue and again before prod: read the profile's `preflight` sources (deploy and incident channels) and wait when there is an incident or someone is holding deploys.
- A failure the script didn't cause (another PR in the same queue group, a flaky test, a broken trunk after the merge) stops the run and notifies, because fixing forward or reverting the trunk is a team decision.

## Watching prod

After a prod deploy the script watches for `watch.minutes` (30 to 60), with checks at `watch.checks_at` (for example 10, 30 and 60 minutes). Each check is a short read-only stage over the profile's `watch.sources`: the error tracker (new issues in the deployed release, issues whose rate went up), metrics and APM (error rate and latency of the changed paths against the hour before the deploy, monitors in alert), alert channels, and the channels where people report bugs.

- A problem counts as caused by the deploy only when it touches the changed code or starts after the deploy time. Every finding comes with its query, window and link.
- No problem: the run report closes with what was checked.
- A regression: the factory opens a fix ticket branch from the trunk, links the original ticket and PR, and runs it through the same flow and gates.
- A severe incident (the profile's `watch.page_on`, for example a P1 alert): notify at once instead of waiting for the fix PR. A revert is the user's decision.
