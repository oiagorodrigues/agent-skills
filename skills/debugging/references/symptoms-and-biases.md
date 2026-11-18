# Symptoms, biases and anti-patterns

From the old backend-design debugging-discipline topic. Read it in Phase 0 to turn a vague report into a symptom and find where it shows up, and in Phase 3 to check your hypotheses against the usual biases.

## Define The Symptom

The first wrong move is treating a vague report as a fact. "It's slow" is not a symptom. Get specific:

- **When did it start?** A timestamp turns into a deploy window, a config change, a third-party announcement, a spike.
- **Who sees it?** All users, one tenant, one role, one region, one device. Specificity narrows the hypothesis space.
- **What fraction?** 100%, 1%, intermittent. "Intermittent" means there is a discriminator you have not found.
- **What is the exact behavior?** Returns 500, hangs, returns the wrong data, returns the right data late. Each one points at a different layer.
- **What is the expected behavior?** Sometimes the bug is in the expectation.

If you cannot answer those in two sentences, the report is not a bug report; it is a request to do the report yourself.

## Where Before What

Before "what is wrong", answer "where would I see it".

- **Latency issue**: APM traces, slow query log, DB CPU, p95/p99 histograms, third-party latency. See `~/.agents/skills/backend-design/skills/observability-by-default/README.md`; for production data use `prod-evidence`.
- **Error spike**: error rate by route, exception breakdown, recent deploy diff.
- **Wrong data**: which row, which write changed it, which job processed it, which user did it. Reconstruct the timeline.
- **Crash / OOM**: pod events, GC logs, heap dump, dmesg / kernel logs.
- **Intermittent**: per-instance metrics (one bad host), per-tenant (one specific data shape), time-of-day (cron interference).

A senior debugger has a map of where each kind of symptom is visible. Build that map first, run queries second.

## Bias Killers

The mistakes that come for everyone:

- **Pattern matching ("we saw this last week, must be the same").** Often wrong, always lazy. Treat each incident fresh, then check the resemblance.
- **"It cannot be X".** Look anyway. Especially the things that "cannot" go wrong are the things nobody checks.
- **"Obviously it is the cache."** Obvious is an instinct; instincts are wrong half the time. Verify before fixing.
- **Confirmation bias.** You see what supports your theory; you skim past what does not. Read the data, not your theory.
- **Survivor bias.** "All the requests I see succeed." Yes, because the failing ones do not reach your log.
- **The first-thing-that-changed**. The deploy was 10 minutes ago, so it is the deploy. Sometimes. Often something else changed in the same window. Check.
- **Trusting the instrument.** Before believing a reading, ask what the tool would show if the system were healthy. If the answer is "the same thing", it cannot support the conclusion. A lagging index, a service listed before it sends any data and a runner that collected zero tests all look like answers.

## Anti-Patterns

- **Changing things at random.** "Let me try this" without a hypothesis. You make more states to debug, not fewer.
- **Pushing fixes without a reproduction.** You may be lucky and resolve the symptom; you do not know what you actually did.
- **Restarting first.** Restart hides the evidence. Restart only after capturing state.
- **Blaming the network.** It is occasionally the network. Most of the time, the network is fine and the timeout is wrong.
- **Stopping at the first plausible explanation.** A wrong root cause is worse than no root cause; you ship a misfix.
- **Explaining a wrong number instead of doubting its inputs.** Tracing how a formula produced a surprising total proves the formula, not the data. Check that the records behind it are plausible first (`prod-evidence`, "Plausibility before explanation").
- **A third fix on the same premise.** After two failed fixes that rest on one assumption, test the assumption itself before trying again. Every new attempt needs a changed hypothesis; the same idea retried only adds states to debug.
- **"Works on my machine" as a verdict.** It works on your machine because your state is different. Find the state difference.
- **Big-bang fix.** Multiple unrelated changes in one PR after an incident. If one of them is wrong, you do not know which.
- **Skipping the postmortem.** The incident is the data; the postmortem is the learning. Skip the postmortem, repeat the incident.
