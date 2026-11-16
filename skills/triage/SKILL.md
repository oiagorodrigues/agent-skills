---
name: triage
description: Use when the user shares a link to a GitHub issue, Jira ticket or Slack thread that describes a customer, product or GTM question or a reported issue, and wants it triaged and answered. Finds the answer or the cause in the code and production data, proposes a fix when there is one, and drafts a short plain-English reply to post back in the same place. Triggers on /triage, "triage this", "answer this thread", "can you look at this ticket/issue". For a ticket or PR that proposes work (a feature, a change, a planned fix) and needs its product, business or cross-repo impact assessed, use product-lens instead.
---

# Triage issue

Take a link, work out what the person is really asking, find the answer in the code and the data, and reply in the thread in words a CS rep or account manager understands.

Workspace values (where local clones live, the GitHub org, how removed code is recorded) come from the workspace's own instructions, or from the workspace skill for the repo when one exists: its "Values for triage" section and its repo routing.

## 1. Read the source

Fetch everything at the link, not only the first message.

| Link | How to read it |
|------|----------------|
| Slack thread | Slack MCP `slack_read_thread` with `message_ts` set to the parent message. The URL holds the channel ID and the message (`p1712345678123456` is `1712345678.123456`); if it also has `thread_ts=`, that is the parent. Read attached files and canvases too. |
| Jira ticket | Atlassian MCP `getJiraIssue`, plus comments, linked issues and remote links. Read checklists as the `jira-workflow` skill says. |
| GitHub issue | `gh issue view <n> -R <org>/<repo> --comments`. |

Then write down, for yourself:

- The type: customer question, product question, GTM question (pricing, packaging, what we can promise a prospect), or a reported issue (bug, data looks wrong, something broke).
- The actual question in one sentence. People often ask for a solution ("can we turn off X?") when they need an answer to a problem ("why is X showing for this buyer?"). Answer the problem.
- The specifics: customer or company name, IDs, order or product numbers, environment, dates, screenshots, error text.
- Who asked, and who will read the reply.

If the thread already has an accepted answer, say so and stop.

## 2. Check the codebase in depth

Every claim in the reply must trace back to code, data or a doc you looked at. Don't answer from memory of how the product "usually" works.

1. Find the code that owns the behavior. Search the local clones (the workspace values say where they live) with `rg -n "<term>" --glob '!node_modules' --glob '!*.lock'`, starting from UI labels, error text, API paths or field names in the report. Use `gh search code --owner <org> "<term>"` for repos not cloned locally. Pull first if a clone looks stale.
2. Follow it end to end: UI component, API call, view or serializer, model, task or event, and any other service it calls. Read the permission checks, feature flags, settings and defaults on that path, since many "bugs" are a flag or a config.
3. Check recent changes on that path: `git log -p --since=<date the problem started> -- <paths>` and `gh pr list -R <org>/<repo> --state merged --search "<term>"`. A problem that started on a date usually matches a deploy.
4. For a reported issue, a perf complaint, a CI failure or any claim about how production behaves, load the `prod-evidence` skill and confirm it with real data: Datadog APM, RUM and logs, Sentry errors lined up with deploys, read-only shell when needed. Follow its rules for spans, perf and calling something flaky.
5. Look for history: Jira (`searchJiraIssuesUsingJql` with the key terms) and Slack search for the same question or bug. Link a duplicate instead of re-solving it. A keyword hit isn't history yet: read every candidate ticket, PR and thread in full and run the "Checking whether a ticket or PR is related" check in the `jira-workflow` skill before citing it. The same goes for the PRs found in step 3 and for the tickets those PRs tag, which are often tagged by a shared word.
6. When a route, page, task, flag or field named in the report isn't in the code, don't conclude it never existed. Find when and why it left: `git log -S "<name>"` (and `-G` for a path pattern) on the default branch of every repo that could have held it, then the PR that removed it, then Jira (`searchJiraIssuesUsingJql` with the name and the PR's ticket). When the workspace values name a program that removes unused code, search where it records each removal too.
7. When the sweep spans several repos, run parallel `Explore` agents, one per repo or area, and give each the question, the search terms and what you've already ruled out.
8. When the report is a record stuck in a state or in a combination that shouldn't exist, run "Check one machine" from the `hunting-bugs` skill on it.

Never change production data and never post anything while checking. If the answer depends on one customer's data or settings and the code alone can't tell, ask the user to check it (or to hijack the account on staging) instead of guessing.

## 3. Decide the answer

Reach one of these outcomes, with evidence:

- **Answered**: the question has a factual answer (how it works, whether it's supported, what the customer should do).
- **Expected behavior**: the system does what the code intends. Say what it does and why, and the workaround if there is one.
- **Bug found**: name the cause (`file:line`), when it started (PR or commit, found with `git log -S`) and who is affected, with the numbers from `prod-evidence`. A bug read from code alone isn't found yet; prove it first. Propose the fix as a short outline. Don't write the fix unless the user asks; offer to open a PR.
- **Config or data problem**: a flag, setting or record is wrong. Say which one and who can change it.
- **Can't tell yet**: say exactly what is missing (an order ID, a time, a screenshot) and ask for that one thing.

Rate your confidence (high, medium, low). If it's low, the reply asks a question or says what you're checking next, and doesn't state a guess as fact.

## 4. Write the reply

Load the `plain-writing` skill and apply it to the reply.

Draft the reply with the `reply-with-standing` skill, following its rules for a non-technical or skimming reader, since the asker is usually CS, support or an account manager. On top of those rules:

- Plain English for a non-engineer. No file paths, function names, stack traces or internal jargon in the reply. Those go in the triage notes for the user.
- Describe a technical cause by its effect on the business, not by the metric: "reports for large sellers fail overnight, so they get yesterday's numbers" instead of "the export job times out" or "the endpoint takes 40s". Latency, throughput and error rates stay in the triage notes.
- Add at most one link when it helps the reader act: the ticket you filed, the PR with the fix, or a help-center article. Never a Datadog, Sentry or admin link the reader can't open.

Example:

```
This is expected. A customer only sees a supplier's products once the supplier adds them as a customer, so Acme won't see them until then. The supplier can do that under Customers.
```

## 5. Show it, then post

Show the user, in the terminal:

1. Type and the question in one sentence.
2. Outcome and confidence.
3. Evidence: `file:line` references, PRs and related tickets (each with one line on what it shares with this issue, plus the candidates dropped as unrelated and why), plus each data finding reported the `prod-evidence` way (number, time window, query, link). This detail stays in the notes, not in the reply.
4. Proposed fix, if any.
5. The draft reply and its character count.
6. "If they ask": two or three one-line follow-ups for the likely next questions, each with its evidence, so the next answer is ready without another investigation.
7. The DM draft, when someone outside the thread needs to confirm something.

Posting is visible to other people, so wait for the user's go-ahead before posting, unless they already said to post. Then reply in the same place:

- Slack: send it from Slack web in Chrome, as `reply-with-standing` describes (the connector's `slack_send_message` appends "Sent using @Claude"). Open the parent message's link, reply in its thread, not in the channel, and give the user the reply link. If the browser can't do it, send it with `slack_send_message` and `thread_ts` set to the parent message, and say it went through the connector; in a Slack Connect channel, where the MCP can't post, give the user the reply to paste.
- Jira: `addCommentToJiraIssue`.
- GitHub: `gh issue comment <n> -R <org>/<repo> --body "<reply>"`.

After posting, give the user the raw URL of the reply or the thread.

If the triage found a bug or a gap with no ticket yet, load the `jira-workflow` skill and follow it: it decides whether a ticket is worth it (or a fix now), checks for duplicates and drafts the ticket for approval. If the user then opens a fix PR, it also owns the status moves.
