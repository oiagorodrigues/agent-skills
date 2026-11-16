# Specialist checks

How to run each specialist lane once the table in "Specialist checks" says it runs. The rules for each area live in the specialist skill; this file says only which part of it the lane uses and how it hands back.

## The brief

Each specialist is its own subagent, one per specialist, covering every file that triggers it. Its brief holds:

- the diff (or the review bundle), the worktree path at the reviewed SHA, the intent list and the repo rules;
- the trigger: the files and lines, or the impact-analysis item, that made the lead run it;
- the skill to read and the part of it to follow (below);
- the review bar, the likelihood × impact scoring and the limits in "Running tests locally";
- "Report findings only, each with `file:line`, dimension, likelihood × impact, and verified (the command or test that shows it) or unverified. Don't change code."

In a tool without subagents, or when a local-review subagent can't spawn its own, the lead runs the triggered specialists itself, one after another, after the reviewers. Their findings go through Synthesis like any reviewer's.

## security-review

Follow the skill's own instructions for `review-pr`'s security lane (steps 1, 3, 4 only when a manifest or lockfile changed, and 5). When the diff adds an entry point (endpoint, webhook, upload, public page, integration, task fed by outside data, LLM tool, CI workflow, IAM role), run its step 2 threat model as well and put the short table in the report.

## backend-design

Run the matching commands on the changed files. Each is a file under `~/.agents/skills/backend-design/commands/`, so the subagent reads it directly.

- A migration or schema change: `review-migration.md`, then `python3 ~/.agents/skills/backend-design/scripts/check_migration.py <files>`. The script parses Django migrations too (`AddField`, `RemoveField`, `RenameField`, `AlterField`, `AddIndex`, `AddConstraint`, `RunPython`, `RunSQL`). When Django runs, check the exact SQL with `python manage.py sqlmigrate <app> <migration> | python3 ~/.agents/skills/backend-design/scripts/check_migration.py --stdin`.
- A new or changed endpoint, worker, consumer, cron job, CLI or third-party integration: `audit.md`.
- Raw SQL or an ORM query on a large or growing table: `explain-this-query.md`.
- A list endpoint, serializer, template or loop over a queryset: `hunt-n-plus-one.md`, on top of the N+1 check in the Performance lane.
- A Django or DRF view, viewset, serializer, queryset or task that reads or writes company data: `~/.agents/skills/django-expert/references/access-and-performance-review.md` (cross-company access trace, unbounded querysets, missing indexes, write loops).
- Every changed backend file: `python3 ~/.agents/skills/backend-design/scripts/check_security.py <files>` and `check_backend_component.py <files>`. The scripts read whole files, so report only what the diff introduced and confirm each warning in the code before it becomes a finding.

Retries, idempotency, locks and outbound calls are judged by the skill's rules and its anti-pattern catalog; a lock also gets the whiteboard defense from the "Design alternatives" lane.

## system-design

Read `~/.agents/skills/system-design/SKILL.md` and only the topic files it routes to for the building blocks the diff touches (a single-topic read, never the full design orchestrator). Say how the change affects the current architecture (load, consistency, failure modes, the next bottleneck at 10x) and propose a simpler, more modern or faster alternative when one exists, with its trade-off. These are "Design" suggestions, so they never block unless they expose a real defect.

## UI design-system check

1. Find the design system: the workspace values name it and its docs when a workspace skill exists. Otherwise look for tokens, a theme or design docs the way the `design-directions` skill's "Design system" step does (`docs/design*`, `design-system*`, `tokens*`, `tailwind.config*`, `theme.*`, CSS custom properties).
2. Check the changed components and styles against it: a hand-built element where the design system has a component, a hard-coded color, spacing, font size, radius or shadow where a token exists, a new variant or token added outside the design system's own package, a state (hover, focus, disabled, loading, empty, error) the design system defines and the change leaves out.
3. Run the `web-design-guidelines` skill on the changed UI files (it fetches the current rules) and keep only what the diff introduced.

A missing token or component is a repo-rule finding when the repo documents the design system as required, and a Consider or Noted item otherwise.

## perf-review

Run the skill's profiling pass on the changed path only, with the workload the PR claims to speed up or the hot path it changes, and hand back its report format (current time, `file:line`, the fix pattern, expected speedup). Compare base and branch on the same workload. A claimed speedup it can't reproduce is a Verification finding.
