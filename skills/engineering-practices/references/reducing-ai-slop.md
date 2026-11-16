# Reducing AI slop

Read this when you build or review an agent workflow (a pipeline of `claude -p` stages, subagents, a verify or QA step), write acceptance criteria for agent work, or when agent-written code keeps needing the same fixes. It holds two sources: Lauren Tan's (poteto) seven steps against AI slop, and a set of rules for verification loops.

## Poteto's seven steps

From her talk, as summarized by The Turing Post: https://x.com/TheTuringPost/status/2120607968408531110. Her code and principles are in pstack (MIT, https://github.com/cursor/plugins/tree/main/pstack).

1. Clean the code agents learn from, because agents follow the patterns already in the repo.
2. Turn every correction into a check. When you fix the same mistake by hand twice, write a lint rule, a type or a test that catches it next time.
3. Remove opportunities for mistakes. Her team, for example, restricts `useEffect` and enforces import boundaries.
4. Give agents a way to run and inspect the product: CLIs, and a feature map that says where each feature lives and how to reach it.
5. Review evidence as well as diffs. Ask for screenshots, videos, command output and test runs that show the change working.
6. Spend most tokens on verification: property-based tests, and TLA+ specs for the critical parts.
7. Automate only once the loop is reliable. Automating a loop that produces slop produces more slop, faster.

She says her team ships about 11,000 PRs a month with a revert rate around 0.5%. Those are her numbers, not measured here.

## Verification engineering

From https://x.com/distortgeekin/status/2120856919359258814.

- The agent that made the change never grades its own work. A separate verifier checks it.
- Write the acceptance criteria first, in a `CHECKS.md` (or the ticket's acceptance criteria), before the maker starts.
- The verifier answers "no" by default and attaches proof (a command and its output, a screenshot, a test run) for every "yes".
- Allow at most three maker-verifier rounds. After the third failure, stop and escalate to a person with what was tried.
- Each mistake caught by hand adds one line to `CHECKS.md`, so the verifier catches it next time.

How to apply it in a pipeline of agent stages:

- Every acceptance criterion is one line that passes or fails and names its check: `POST /orders with an empty cart → 400 {"cart": "empty"} · check: curl against the local API`. "Works correctly" or "handles errors" can't fail, so a plan with one goes back. If the criteria can't be written, the task isn't ready for an agent.
- Check the plan before any code. A short read-only step passes the plan only when every criterion has a check, the files to change cover every criterion, and no step leaves the scope. A wrong plan found here costs one cheap call instead of an implement run.
- The tests that grade the change come from a step other than the one writing the code, because a wrong idea passes its own tests. That step writes them first and shows they fail on the base. The implementer can't edit them (a hook refuses it); a wrong test goes back to the step that wrote it. The verifier checks they are unchanged and now pass.
- The verifier is a different model in a fresh context. It gets the criteria, `CHECKS.md`, the commit SHA and the check output, never the maker's transcript, reasoning or summary. It has no edit tools, works on a clean checkout of that SHA, and binds its verdict to it.
- The verifier tests the result instead of reading the code: it starts the app and drives the changed flow (`agent-browser`), makes the real API calls, recomputes numbers from the source. Reading code only tells it where to look.
- Keep `CHECKS.md` outside what the maker receives, one file per repo plus one for all repos. The one for all repos is `done-checks.md` next to this file; a repo's own file lives in the workspace skill (`references/checks/<repo>.md`).

| Symptom | Missing check |
|---|---|
| Says done and isn't | Criteria written before the work |
| Tests pass, feature broken | Tests written by another step |
| Looks right, numbers wrong | Recompute from the source |
| Works for the agent, not the user | Verifier read the code instead of using the result |
| Same mistake every week | A line in `CHECKS.md` |
| You still read everything | Proof attached to each pass |

## How this maps to the local rules

- Step 2 and the `CHECKS.md` rule are the "turn each repeated correction into a rule" line in `engineering-practices` and the `correct` skill.
- Step 5 matches "Verify before claiming done" and the negative-control rule in `engineering-practices`.
- The tests written by another step and locked against the maker are the stricter form of "every behavior change ships with a test that fails if the change is reverted".
- The three-round limit matches the "about three fix attempts" rule in `engineering-practices`.
