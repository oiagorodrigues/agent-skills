---
name: why
description: "Explains why code, a rule, a threshold or a design is the way it is, by sending parallel read-only investigators through git history and blame, PRs and review comments, Jira, Confluence, Slack and, for defensive code, Sentry and Datadog, then returning a cited answer that separates what the record says from what is inferred and what is unknown. Use when the user asks \"why does X work this way\", \"why did we pick Y\", \"where did this number come from\", \"is this still needed\", wants the history behind code before changing or deleting it, or asks for the rationale behind a past decision."
---

# Why

Adapted from Lauren Tan's why in pstack (MIT, https://github.com/cursor/plugins/tree/main/pstack), with our sources and our subagent rules. Code shows what it does; the reason lives in commits, PRs, tickets, docs and conversations, all incomplete. This skill finds that record and says honestly how much of the answer it supports.

Everything here is read-only. Investigators read git, GitHub, Jira, Confluence, Slack, Sentry, Datadog and Sigma; nobody comments, posts, edits, transitions a ticket or commits. If the answer suggests a change, the report says so and stops.

For what code does at runtime, read the code or use `debugging`. For a reported problem in a ticket or thread, use `triage`. For a whole-repo map, use `cartographer`.

Load the workspace skill for the repo first, when one exists, for the GitHub org, clone paths and the prod warehouse connection.

## 1. Pin the target and the question

The target is a piece of code, a pattern, a feature or a named decision. The question is a rationale, a trade-off, an edge case, an external constraint, a magic number, or "is this dead". If the target is vague, pick the best reading from the conversation, state it in one line and go on.

When the user embeds a guess ("I assume it's for performance"), treat it as one hypothesis to test, never the answer.

## 2. Build the code anchor

Before spawning anyone, collect the seed context yourself:

```bash
git blame -L <start>,<end> <file>                       # last touch per line
git log --follow --oneline -- <file> | head -30         # history through renames, PR numbers in subjects
git log -S '<exact string or number>' --oneline -- <file>   # when this text appeared or vanished
git log -1 --format=%B <commit>                         # PR number and ticket keys in the message
gh pr view <n> -R <org>/<repo> --json title,body,author,mergedAt,closingIssuesReferences,comments,reviews
```

The anchor is: file paths with line ranges, key symbols, the commits that introduced and last changed the target (not only the most recent), PR numbers and Jira keys. **Done when** you have the introducing commit and its PR, or know the target predates the history (squashed import, copied file).

If the introducing PR body or a code comment already answers the question in full, answer inline from it and say which sources you skipped and why. That should be rare.

## 3. Spawn the investigators

One subagent per source, all in one message so they run in parallel, each owning exactly one source. Give each the brief in `references/investigator-brief.md` with its source section, the code anchor and the question. Run them one step cheaper than the session (`effort: "lower"`), since each is a bounded search.

| Source | Spawn when | Best at |
|---|---|---|
| Source control (git, `gh`, comments, tests, ADRs) | Always | The rationale written during review |
| Jira (Atlassian MCP) | Always when the anchor has a ticket key, else when the target is product behavior | The product or business reason |
| Confluence (Atlassian MCP) | Feature or design decisions | Design docs written before the code |
| Slack (Slack MCP) | Always unless the record is already complete | Discussion that never reached a doc |
| Sentry | The target is defensive (a guard, retry, timeout, null check, rate limit, try/except) | The errors that motivated the defense |
| Datadog | Timeouts, retries, limits, queues, anything reacting to load | The runtime signal behind the code |
| Prod warehouse | Thresholds, flags, data rules, "is this still used" | How often the case happens in real data |

Skip a source only with a written reason that goes in "Sources consulted": the tool isn't connected or authenticated (a gap, not a choice), or the source provably can't hold the answer (a build script has no runtime errors to find in Sentry). "Probably irrelevant" isn't a reason.

## 4. Synthesize

Do it yourself, or hand it to one subagent when the findings are long. Follow `references/epistemics.md` (confidence tiers and phrasing) and use the output format in `references/synthesis.md`. Spot-check every citation a conclusion rests on by opening it; a subagent's claim is a claim until you see the source.

## 5. Present

Give the synthesized answer with raw URLs for PRs, tickets, docs and threads (AGENTS.md "Links"). Don't strengthen the confidence language while editing. If the question was a step toward changing the code, end with the Preserve / Change / Avoid / Risk list from `references/synthesis.md`.

**Done when** every claim sits in one confidence tier with its citation, "What we don't know" names concrete gaps, and every source is listed as searched or skipped with a reason.

## Failure modes

- Recency bias: the last commit is often a rename or a reformat. Trace back to the commit that introduced the behavior.
- Code as evidence of its own intent: "the author chose X" is an observation about code, not a reason.
- Filling a gap with a plausible story. "We searched A, B and C and found nothing" is a useful answer; it tells the user to ask a person, and names who (the PR author, the ticket reporter).
