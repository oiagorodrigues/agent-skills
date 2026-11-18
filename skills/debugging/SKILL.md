---
name: debugging
description: Debugging method for a bug, failure, crash, flaky test, wrong data or error spike, local or in staging or production. Builds a tight pass/fail loop that goes red on the reported symptom before any theory, then reproduces and minimizes, ranks falsifiable hypotheses, instruments one variable at a time, fixes with a regression test and cleans up. Covers active incidents (mitigate first). Use when the user says debug, diagnose, "it's broken", "it doesn't work", "why is this failing", reports a 500 or a wrong value, or a check keeps failing after a fix.
---

# Debugging

Method adapted from Matt Pocock's diagnosing-bugs (MIT, https://github.com/mattpocock/skills), merged with the rules from the old backend-design debugging-discipline topic. For "it's slow" with no error, use `perf-review` instead. For hunting latent state bugs with no reported symptom, use `hunting-bugs`.

The rules in `engineering-practices` still apply: fix the root cause, never call a failure "pre-existing" without proving it on the base branch, and stop after about three fix attempts on changed hypotheses. Production shells and prod database queries need the user's explicit yes for this task (AGENTS.md); get production data through `prod-evidence`.

When the user says they can't reproduce a result you reported (a bug on the base branch, a fix that works), re-run it yourself first, on the exact branch, commit and container they use, and report what you saw. Say which commit and container your earlier run used. The new run decides; don't defend the earlier result.

## Phase 0: Mode and symptom

1. **Active incident** (customers hurt right now): stop the bleeding first (roll back, flag off, block the traffic), capture state before any restart (logs, metrics, traces), tell people, and root-cause after. Propose the mitigation to the user; don't run it on shared environments yourself.
2. **Stable bug**: define the symptom in two sentences: when it started, who sees it, what fraction, the exact behavior and the expected behavior. If you can't, gather that first. `references/symptoms-and-biases.md` maps each kind of symptom to where it shows up.

## Phase 1: Build a feedback loop

This is the skill. With a tight pass/fail signal that goes red on this bug, bisection, hypotheses and instrumentation just consume it. Without one, reading code won't find the cause. Spend most of the effort here.

Ways to build one, roughly in order:

1. A failing test at whatever seam reaches the bug (unit, integration, e2e).
2. curl or an HTTP script against the running dev server.
3. A CLI or management command with a fixture input, diffed against a known-good output.
4. A browser script that drives the UI and asserts on DOM, console or network: `agent-browser`, or `claude-in-chrome` when it needs the user's session.
5. A replay of a captured request, payload or event log through the code path in isolation.
6. A throwaway harness: the smallest part of the system that hits the code path with one call.
7. A property or fuzz loop for "sometimes wrong": many random inputs, look for the failure (Hypothesis in Python, fast-check in TS, proptest or `cargo +nightly fuzz run <target>` in Rust, jqwik in Java).
8. A bisection harness when it broke between two known states: `git bisect run <script>`.
9. A differential run: same input through the old and new version (or two configs), diff the outputs.
10. Last resort, a human in the loop: numbered steps the user runs, pasting back exactly what they saw.

Tighten it: faster (narrow scope, skip setup), sharper (assert the exact symptom, not "didn't crash"), deterministic (pin time, seed randomness, isolate network). For flaky bugs, aim for a higher reproduction rate (loop it 100 times, parallelize, add stress); 50% is debuggable, 1% isn't.

Redact secrets in everything you show: build the loop against env vars, and quote only the lines of a capture that carry the signal.

If you can't build a loop, stop and say so: list what you tried and ask for access to the environment that reproduces it, a redacted capture (HAR, log dump, recording with timestamps), or permission for temporary instrumentation.

**Done when** you can name one command you've already run (show it and its redacted output) that drives the real code path, asserts the user's exact symptom, gives the same verdict every run, takes seconds and runs unattended. Reading code to build a theory before this command exists is the failure this skill prevents.

## Phase 2: Reproduce and minimize

Run the loop and watch it go red. Check that it's the failure the user described, not a nearby one, and capture the exact symptom (error text, wrong value, timing).

Then cut inputs, callers, config, data and steps one at a time, re-running after each cut. **Done when** every remaining element is load-bearing: removing any one turns the loop green.

## Phase 3: Hypothesize

Write 3 to 5 ranked hypotheses before testing any. Each states a prediction: "If X is the cause, changing Y makes the bug disappear." A hypothesis without a prediction gets sharpened or dropped. Show the ranked list to the user; they often know what changed. Keep going with your ranking if they're away.

Check the instrument before trusting a reading: what would this tool show if the system were healthy? If the same thing, it can't support the conclusion (a lagging index, a runner that collected zero tests).

**Attack the premise.** When two fixes that share one premise have failed the same check, suspect the premise, not the fixes. Don't start a third fix until you have done this:

1. Write the premise in one sentence: the belief every failed fix assumed.
2. Test it directly with an observation that would come out differently if it were false, and make that check rerunnable. Look at how the failures are distributed (which records, actors, hosts or code paths always land on the losing side), not only how large they are.
3. If the evidence contradicts it, the cause is elsewhere: look for what the failures share that the premise didn't predict. If it confirms it, ask the next "why"; the earlier fixes may have treated a consequence.
4. Remove the condition that puts one side on the losing end instead of adding a mechanism that cleans up after it.

From pstack's principle-attack-the-premise (Lauren Tan, MIT, https://github.com/cursor/plugins/tree/main/pstack) and the "Attack the Premise" rule in Robert C. Martin's ub-mode (MIT, https://github.com/unclebob/ub-mode).

## Phase 4: Instrument

Each probe maps to one prediction. Change one variable at a time. Prefer a debugger or REPL (`python manage.py shell` or the repo's REPL, inside its container when it runs in one; `breakpoint()` in Python, `node --inspect-brk` or `vitest --inspect-brk --no-file-parallelism` for Node and Vitest, `rust-lldb` with `RUST_BACKTRACE=1` for Rust, `-agentlib:jdwp=transport=dt_socket,server=y,suspend=n,address=*:5005` for a JVM), then targeted logs at the boundaries that separate hypotheses. Tag every debug log with a unique prefix such as `[DEBUG-a4f2]` so cleanup is one grep.

## Phase 5: Fix and regression test

Write the regression test before the fix, at a seam that exercises the real bug pattern. If the only seam is too shallow to reproduce the chain that caused it, say so: that's a design finding, not a reason to write a test that gives false confidence.

1. Turn the minimized repro into a failing test and watch it fail (negative control per `engineering-practices`).
2. Apply the fix and watch it pass.
3. Re-run the Phase 1 loop against the original, un-minimized scenario.

## Phase 6: Clean up

- [ ] The Phase 1 loop no longer reproduces the bug.
- [ ] The regression test passes, or the missing seam is written down.
- [ ] Every `[DEBUG-...]` line is gone (grep the prefix) and throwaway scripts are deleted.
- [ ] The cause that turned out right is stated in the PR description, so the next person learns it.

If the cause is a mistake that has happened before (the same misuse of an API, the same missing guard, the same wrong command), offer to run `correct` so a type, lint or test makes it impossible next time.
