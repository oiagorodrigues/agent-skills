---
name: product-onboarding
description: Onboard onto an unfamiliar product by reconstructing its requirements. Sweeps the codebase, reads docs/user stories/specs for functional requirements (what it does), reads SLAs/metrics/incident and ops reports for non-functional requirements (how well it does), reconciles both against the code to find drift, classifies with MoSCoW, and ends with short clarifying questions for stakeholders. Use when joining a new codebase/team/product, when asked "what does this system do", for a requirements or capability audit, or before proposing architecture, performance, or system-design changes. Triggers on /product-onboarding, "onboard me", "reverse-engineer the requirements", "FR/NFR audit".
---

# Product Onboarding — requirements first

Output: `docs/onboarding/REQUIREMENTS.md` — the blueprint every later architectural
decision is argued from. Nothing else is written.

**Prime directive: evidence or nothing.** Every requirement carries a source and a code
location, or it is marked `UNVERIFIED`. Never state what the system does from the shape of
a folder name. Invented requirements are worse than missing ones.

**Second directive: NFRs are load-bearing.** NFRs dictate the architecture; FRs are built
on top. Find the NFRs before proposing anything.

**Discovery is read-only.** No product code, config, or migration is edited during this
skill. The write fence enforces it (Setup below).

---

## Setup (once per repo)

```bash
~/.agents/skills/product-onboarding/assets/bin/install-hooks.sh   # write fence + doc validator
```
Enforced programmatically, not by good intentions:
- `guard-write.sh` — during onboarding only `docs/onboarding/**` is writable.
- `validate-requirements.sh` — rejects a FR row with no source/evidence, a NFR target with
  no number, a bad status or MoSCoW value, or a doc with no open questions.

It seeds `docs/onboarding/REQUIREMENTS.md` from the template; replace the example rows.
When the user approves real changes, lift the fence with `install-hooks.sh --end`.

## Phase 0 — Inventory sources, then ask for the rest

```bash
~/.agents/skills/product-onboarding/assets/bin/sweep.sh    # docs, stories, routes, jobs, tests, deps, SLOs
```
Read `references/sources.md`. Whatever the sweep did not find, request in **one** batched
question — issue tracker / user stories, product or architecture docs, observability
(APM, dashboards, error tracker), SLA or contract text, incident and on-call reports,
relevant MCP servers or read credentials. Proceed with what you get; mark the gaps.
Never ask what the filesystem already answers.

## Phase 1 — Functional requirements

`references/functional.md`. Extract FRs from docs, stories, specs, tests. One verb, one
actor, one testable outcome. Map each to the component that implements it.

## Phase 2 — Non-functional requirements

`references/nonfunctional.md`. Extract NFRs from SLAs, metrics, ops reports, load tests,
infra config, and technical constraints. Turn each subjective attribute into a number with
a unit and a measurement window. Record where it is enforced — and whether it is enforced.

## Phase 3 — Reconcile against the code

`references/drift.md`. For every requirement found in a document or story, compare it to
the codebase: complied, changed, silently dropped, or never built. When they disagree,
date the evidence (git log, ADRs, changelogs, ticket history) to decide which artifact is
current — the newest *registered decision* wins, not the loudest document.

## Phase 4 — Classify and cost

MoSCoW every requirement (Must / Should / Could / Won't) so trade-offs are deliberate.
Flag any NFR whose target exceeds business need — five nines costs exponentially more than
three and each extra nine buys less. Flag the reverse too: an unenforced Must.

## Phase 5 — Clarifying questions (always last)

`references/questions.md`. Write ≤10 questions, one line each, each naming the assumption
it would kill. State plainly in the report and to the user: **confirm these with
stakeholders before treating any of this as settled** — the doc is reconstruction, not
authority, and boundaries and intent are not inferable from code.

---

## Report

Fill `assets/templates/REQUIREMENTS.md`. Tables only, no prose padding. The validator hook
must pass before you report done. Say what you could not see and why.
