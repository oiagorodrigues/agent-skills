# Mechanism defense

Used by the "Design alternatives" lane and by mode 2 when a reviewer challenges a mechanism. The premise check is adapted from Lauren Tan's pstack `principle-attack-the-premise` (MIT).

## What counts as a risky mechanism

A lock (`select_for_update`, advisory lock, Redis or cache lock, a mutex, `LOCK TABLE`), a cache, a retry or backoff loop, a new table or denormalized column, a signal or hook that fires on save, a background job, a queue, or a feature flag that forks a code path. These fix one symptom and can open a new failure somewhere else, so each needs a reason the simpler options lost.

## Alternatives to check by mechanism

Name at least two for the mechanism the diff adds, including doing nothing new, and say why each loses on this code and this data.

- Lock: a unique constraint or `ON CONFLICT`, a conditional `UPDATE ... WHERE state = X` that checks rows affected, an idempotency key, a retry on serialization or deadlock error with jitter, a smaller transaction, or moving the write so the race can't happen.
- Cache: a missing index or `select_related`, fewer calls per request, precomputing at write time, or accepting the current latency with its measured number.
- Retry: making the operation idempotent first, a dead-letter queue, failing loudly to the caller, or fixing why the call fails.
- New table or column: a field on an existing model, a view or computed query, or the reporting layer.
- Signal or save hook: an explicit call in the service that does the write, so every path that should run it is visible.

Check each against the anti-pattern catalog at `~/.agents/skills/backend-design/skills/anti-patterns/README.md`.

## The whiteboard defense for a lock

A change that adds or widens a lock needs all four, in the PR description or the ticket, before it can merge:

1. The race: the two operations, the interleaving that breaks, and the evidence it happens (Sentry issue, log lines, a reproduction).
2. Alternatives: the options above and why each loses.
3. Lock order: every other code path that locks the same rows or tables (search for `select_for_update`, `.lock(`, raw `FOR UPDATE` on the same models), the order each takes its locks in, and why the new lock can't form a cycle with them. A deadlock in a different path after the fix is the usual failure.
4. Proof: a test or script that reproduces the race on the base branch and passes on the branch, or the reason one can't run and what stands in for it.

A human reviewer must approve the PR as well. An agent review alone never clears a lock change.

## Attack the premise

When the PR is the second or later fix for the same symptom (same Sentry issue, same ticket, an earlier PR that touched the same path for the same error, found with `git log -S` or the ticket's links), every fix so far shares a premise. Write that premise in one sentence ("the deadlock comes from two workers updating the same order"). Then name an observation that would come out differently if it were false (which rows the Sentry events lock, whether the failures cluster on one path or job, whether they started with a deploy) and check it before accepting another fix on the same premise. If the evidence contradicts it, the finding is that the fix treats the wrong cause. If it confirms it, ask whether removing the condition beats compensating for it with a new lock, retry or cleanup job.
