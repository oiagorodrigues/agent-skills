# Clarifying questions — the last step

This document is a reconstruction. Boundaries, intent, and priority are **not** inferable
from a codebase, and assuming them is how onboarding produces confident wrong architecture.
Say that to the user, plainly, once.

## Rules
- Max 10, ranked by what they change.
- One line each. Closed or multiple-choice where possible.
- Each names the assumption it kills and what breaks if the assumption is wrong.
- Only genuine ambiguity: contradictory sources, an unmeasurable Must, an undocumented
  behavior with real blast radius, an unowned boundary, a target with no business reason.
  Anything the repo answers is not a question.
- Name a likely stakeholder per question (PO, tech lead, SRE/on-call, security, finance).

## Format
`Q3 (PO) — Is guest checkout in scope, or is an account required? Assumed account-required
from routes/checkout.js:41; if wrong, FR-08/09 and the session model change.`

## Then
List the assumptions you shipped the doc under, in one block, so a stakeholder can confirm
or knock them down in a single pass. Mark the doc's status line `DRAFT — unconfirmed` until
someone does.
