# Epistemics

Adapted from pstack's why (Lauren Tan, MIT, https://github.com/cursor/plugins/tree/main/pstack). How to grade evidence about intent and how to word each grade.

## Confidence tiers

Every claim sits in exactly one tier. The tier sets its section in the output and its wording.

1. **Direct.** Someone wrote down why: a PR description ("this fixes pagination for users with more than 1,000 items"), a ticket ("Acme needs this for their security review"), a code comment ("clamp to 100 because the upstream API rejects larger values"), a design doc, or the author in Slack. Wording: plain and cited. "This exists because X (PR #123)."
2. **Supported.** Several indirect items converge and none states it: the PR title says "improve performance", the ticket has a perf label and the same week's commits touch the same hot path. Wording: confident but shown as derived, listing each item. "The evidence points to X: A, B and C."
3. **Inferred.** A reasonable reading nothing states: merged the same day an incident channel lit up, so likely a hotfix. Wording: hedged, with the chain visible. "Given A and B, C seems likely because D."
4. **Speculative.** Plausible on thin evidence, with other explanations fitting as well. Wording: "One possibility is X, but we found no record of it." It belongs under competing hypotheses.
5. **Unknown.** Searched and not found. Wording names what was searched: "Jira for 'rate limit' and 'throttle' in ENG since 2022, the 6 PRs that touched the file, and Slack for the PR URL found no rationale."

## Wording rules

- "Because", "the reason is", "was designed to", "fixes", "the team decided" claim intent or a group decision. Use them only next to a Direct or Supported citation.
- Hedges ("appears to", "likely", "suggests", "is consistent with") mark interpretation. Use them in the inferred section.
- Drop "obviously", "clearly", "of course", "just" and "I think"; each hides how strong the evidence is.

## Traps

- Rationalization: code that makes sense today may have been written for reasons that no longer apply, or that were wrong then. A consistent pattern can be copy-paste.
- Absence of evidence: "nobody mentioned security" doesn't mean security wasn't a concern.
- The user's guess: check it like any other hypothesis and say plainly when the evidence doesn't support it.
- Contradictions: when the ticket says "compliance" and the PR says "tech debt cleanup", show both with citations. Both may be true, or one may be wrong; the user decides.

## Before finalizing

- Every claim in "What we found" has a citation, or it moves to inferred or hypotheses.
- Each claim's wording matches its tier.
- No code is cited as evidence of its own intent.
- "What we don't know" is present and concrete. An empty one is suspicious.
