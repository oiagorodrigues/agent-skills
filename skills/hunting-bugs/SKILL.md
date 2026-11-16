---
name: hunting-bugs
description: "Hunts hidden bugs that no one has reported yet, in implicit state machines: state that lives in flags, nullable timestamps, status strings and related rows that are written from many places with no single table of allowed transitions. Spiders a repo, module or feature with parallel subagents, rebuilds each machine's states and transitions, and reports reachable illegal states, missing guards, stuck states, double or out-of-order events and races, with a short list plus a detailed doc. Report only, changes nothing. Use when the user runs /hunting-bugs, asks to find implicit state machines or hidden state bugs, or asks why a record ended up in an impossible or stuck state. Also used for one machine at a time from code review and triage."
argument-hint: "[repo | path | feature | model or field name]"
metadata:
  source: "David K (@DavidKPiano) post on X, Nov 9 2026, https://x.com/DavidKPiano/status/2119788094434038264, plus a sweep prompt the user shared"
---

# Implicit state machines

A state machine is any logic of the form "when we're in this state and this event happens, we move to that state". Explicit ones are easy to read: a `switch` or reducer, a transition table, an enum with one function that moves between values, or a library like XState. An implicit one has the same logic spread across the code, so nobody can list which transitions exist. That's where bugs hide: the storage allows states the product never meant to allow, tests cover the paths the author thought of, and a review approves each piece because each piece looks fine on its own.

This skill finds those machines, rebuilds their transition tables and checks them for bugs. It reports and doesn't change code.

## What an implicit machine looks like

Look for one thing whose "where is it now" answer depends on several values or is written from several places:

- Booleans that combine: `is_paid` and `is_shipped`, `isLoading`, `isError` and `data`. Two booleans allow four states even when the product has three.
- Nullable fields read as state: `shipped_at is not None`, `cancelled_by`, `deleted_at`, an empty `external_id` meaning "not synced yet".
- A status string or enum assigned in many files, with no function that checks the current value before changing it.
- State split across rows or systems: an order status plus its payment row, a local record plus a third-party status from a webhook, a DB value plus a cache or a client store.
- Async flow state: Celery chains and retries, webhooks, polling, timers, debounced requests, optimistic UI updates, route and modal state on the frontend.

## Two modes

- **Sweep**: the argument is a repo, a large module or nothing (use the current repo). Run the whole flow below.
- **One machine**: called from a review, a triage or a question about one model or field. Skip the fan-out and run "Check one machine" on that machine, then report its findings in the caller's format.

## Sweep

### 1. Map the areas

List the top-level areas of the target (Django apps, services, packages, frontend feature folders) and the stateful code in each. Quick signals to search with `rg`:

- Status and state fields: `status`, `state`, `stage`, `phase`, `step`, model `choices`, `TextChoices`, TypeScript string unions, Java enums with `@Enumerated`, Rust enums.
- Writes: `.status =`, `update(status=`, `bulk_update`, `save(update_fields=`, `setState`, store mutations and Pinia `$patch`, `ref(false)`/`useState(false)` pairs, Java `setStatus(`, Rust `.status =` and `AtomicBool` stores.
- Flags and markers: `is_*`, `has_*`, `*_at`, `*_by`, `Option<DateTime<...>>` fields, `loading`, `pending`, `submitted`.
- Event sources: Celery tasks, signals, webhooks, management commands, admin actions, data migrations, consumers, Spring `@Scheduled`, `@KafkaListener`, `@EventListener` and `@Async` methods, spawned Tokio tasks.

Group the areas into at most 8 batches of similar size.

### 2. Spider in parallel

Spawn one subagent per batch, all in the same message so they run at once (in a tool without subagents, do the batches one after another). Give each one this brief, filled in:

```
Find every implicit state machine in <paths> of <repo> at <checkout path>.
Definition: <paste the first paragraph and "What an implicit machine looks like" from this skill>.
For each machine, run "Check one machine" from <path to this SKILL.md> and return:
- name, and the files that matter most (file:line)
- the state variables and the states the code means to allow
- the transition table: from state, event, guard, to state, file:line
- each suspected bug: which question from the check found it, the steps that reach it, file:line, and whether you proved it (test, repro) or only read it in code
Skip machines that are already explicit and fully guarded, listing them in one line each.
Read-only: don't edit code, don't query production data, don't run full test suites (one targeted test file at a time is fine).
Do only what this brief asks. Don't remove, change or clean up anything else, even if it looks wrong or related. If you think something else should change, list it under 'Proposals' in your report and leave the code as it is.
Return a compact report, not file dumps.
```

### 3. Judge the findings

The lead (you) judges every finding; don't pass subagent output on as-is.

1. Merge machines that two batches found from different ends (an order status written by the API and by a Celery task is one machine).
2. Re-read the code for each suspected bug and trace the exact path that reaches it. Drop the ones that a guard, constraint or lock elsewhere already prevents, with one line on why.
3. Prove what you can: a failing test or a local repro for the transition, and for "does this happen in production" a count of records in the illegal state through the `prod-evidence` skill (Sigma or Datadog first; production database or shell only when the user says so for this task).
4. Score each one likelihood × impact (1 to 10 each), as in the `review-pr` skill.
5. Put each in one bucket:
   - **Bug**: proved by a test, a repro or real data.
   - **Needs thought**: reachable in code but not proved, or it needs a product decision about which states are legal.
   - **Fine**: explicit enough, or the illegal state can't cause harm. One line each.

### 4. Report

In chat, a short list with one entry per machine that has a Bug or Needs thought item, highest score first:

- Title, then one or two sentences on the machine and what goes wrong.
- The most important files (`file:line`).
- Bucket and score.

Write the details to a Markdown file in the scratchpad (`hunting-bugs-<repo>-<date>.md`) and give its full path. For each machine it holds the state variables, the transition table, every finding with its steps to reach it, the evidence or "read from code only", the score and a fix direction. If the user wants to share it, publish it as an Artifact.

## Check one machine

1. **Name the state.** List every variable that together answers "where is it now": status fields, booleans, nullable timestamps, related rows, external status, cache keys, client store fields, URL or route.
2. **Legal versus representable.** Write the states the product means to allow (from the enum, docs, ticket or tests). Then count the combinations the storage allows. Every combination outside the legal list is a candidate illegal state.
3. **Find every writer.** Search the whole repo, and other repos per the cross-repo check in `review-pr`, for every place that writes any of those variables: views, serializers that accept the field, services, Celery tasks, signals, webhooks, admin actions, management commands, data migrations, `queryset.update()` and `bulk_update` (which skip `save()` and signals), and frontend optimistic updates.
4. **Build the table.** One row per transition: from state, event, guard, to state, `file:line`. A writer with no guard on the from-state is a transition from every state.
5. **Ask each question:**
   - Can any write path reach an illegal state from step 2?
   - Is there a transition the product forbids that a writer allows (cancel after shipped, edit after submit)?
   - Is a state stuck, with no way out, or dead, with no way in? What happens to a record when the process dies halfway through a transition?
   - What happens when the same event arrives twice: double click, retried task, duplicated webhook, replayed message?
   - What happens when two events arrive at once? A read, then a check, then a write, with no lock or conditional update, is a race.
   - What happens when events arrive out of order: a late webhook, a slow response landing after the user navigated away, a retry finishing after a cancel?
   - Does a sibling path (admin, bulk update, another API version, a backfill) skip the guard the main path has?
   - Do side effects tied to a transition (email, charge, inventory, event publish) run when the transition didn't happen, or run twice?
   - Do readers assume a subset of states (`if paid ... else` treated as pending), so a new or illegal state falls into the wrong branch?
6. **Verify** each suspect as in step 3 of "Judge the findings", or mark it "read from code only".

## Fix directions

Put these in the report; don't apply them unless the user asks.

- Replace combining booleans and nullable markers with one status field whose values are the legal states.
- Move every transition into one function that checks the from-state and rejects the rest, and make other writers call it.
- Make the write conditional on the from-state (`filter(pk=..., status=FROM).update(status=TO)` and check the row count, or `select_for_update`) to close races.
- Add a database check constraint for combinations that must never exist.
- Make repeated events safe with an idempotency key or a processed-event record.
- In Rust, make the states an enum whose variants carry their own data, or typestate structs, so an illegal combination doesn't compile.
- On the frontend, use one status value or a discriminated union instead of separate `loading`, `error` and `data` flags, and ignore responses that belong to a previous state.
