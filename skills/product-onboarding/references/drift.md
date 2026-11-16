# Reconcile documents against the code

Every requirement found in a doc, story, or spec gets compared to what the code does. Docs
rot; code ships. Neither is automatically right — intent lives in docs, truth lives in code.

## Status vocabulary (validator enforces these)
- `implemented` — code matches the documented behavior.
- `partial` — some conditions, cases, or edges missing.
- `drifted` — code does something different from the doc.
- `missing` — documented, never built (or removed).
- `undocumented` — code does it, no doc or story says it should.
- `UNVERIFIED` — claimed somewhere, could not be confirmed either way.

## Deciding which artifact is current
When doc and code disagree, look for a **registered change** before calling it rot:
```bash
git log --follow -5 -- <file>                 # when did behavior last change, and why
git log -S'<symbol or string>' --oneline      # the commit that introduced/removed it
git log --since=<doc date> --oneline -- docs/ # was the doc superseded
```
Then check ADRs, changelogs, release notes, ticket/PR history, and migration files for a
decision that supersedes the doc. Newest *decision* wins, not the newest file mtime.
If no registered change exists, the drift is unintentional — that is a finding, and often
the most valuable thing this exercise produces.

## Record per drift
what the doc says (`doc:line`, date) · what the code does (`path:line`) · the superseding
evidence, if any (commit/ADR/ticket) · verdict: doc stale, code regressed, or undecided.
Undecided goes straight into Phase 5 questions. Do not fix the code; do not rewrite the
other team's docs. Report.
