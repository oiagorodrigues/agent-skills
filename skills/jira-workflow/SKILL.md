---
name: jira-workflow
description: Use for any Jira work through the Atlassian MCP. That covers deciding whether something deserves a ticket, drafting and creating a ticket or an epic with its tasks, updating a ticket's description, checking whether a ticket or PR is really related to an issue (not just sharing keywords), linking related tickets, closing an absorbed task as Won't Do, moving status when a PR opens or goes to review, and reading "See checklist below" checklists.
---

# Jira workflow

Workspace values (known transition IDs, the checklist property) come from the workspace's own instructions, or from the "Values for jira-workflow" section of the workspace skill for the repo when one exists.

## Before drafting a ticket

Do all of these first. A ticket filed from code reading or one trace alone is not allowed.

1. Confirm the root cause in the code, at `file:line`.
2. Run `git log -S "<symbol>" -- <paths>` (and `git log -p` on the path) to see whether this is a regression and what the original author meant.
3. Prove it with real data or a real test when it's a bug or a perf problem. Use the `prod-evidence` skill.
4. Search for duplicates and for someone already working on it: `searchJiraIssuesUsingJql` with the key terms, open PRs (`gh pr list --search`), and Slack. Run every hit through "Checking whether a ticket or PR is related" below before calling it a duplicate.
5. Decide whether it deserves a ticket at all. If the fix is small and safe, propose fixing it now instead.

## Epics

Before creating anything, map the dependencies and write an ordered list of tasks. Show it to the user for approval, then create the epic and the tasks in that order.

Split the work into vertical slices. Each task delivers a thin end-to-end path through every layer it needs (schema, API, UI, tests) that can be demoed or tested on its own once done, never one layer per task ("all the models", "all the endpoints"). Put any prefactoring first, then make the first slice a tracer bullet: the thinnest path that runs end to end through every layer the epic touches, so integration problems show up before any layer is filled in. A wide mechanical refactor (a rename or retype across the codebase) is the exception: sequence it as expand, migrate callers in batches, then contract. (From Matt Pocock's to-tickets, MIT, https://github.com/mattpocock/skills)

## Drafting

- Show the skeleton in the chat first: title and description, in English. Wait for approval. One ticket at a time.
- Title: short, in the style of the project's existing tickets (look at a few recent ones).
- Description in bullets: where the problem came from (the Slack thread, ticket or alert, linked), what was found, links to code, PRs, dashboards and traces, and a table of results when there are numbers.
- Apply the `plain-writing` skill.

## Updating

- Rewrite the description to reflect the current state. Don't append "Update:" blocks.
- Cross-link related tickets (`createIssueLink`), only after each one passes the check below.
- When one task is absorbed by another, add a comment on it that links to the ticket that took it over, then move it to Won't Do.
- Comments follow the `reply-with-standing` skill: 250 characters or less, URLs not counted, with no background the reader already has.

## Checking whether a ticket or PR is related

Every skill that cites a ticket, PR or Slack thread as related, a duplicate, history, evidence or a PR's intent runs this check first. A search hit or a ticket a PR tags is a lead, not a relation: PRs often tag a ticket because it shares a word or two with the real issue ("invoice", "sync", "export", "credit"), and the ticket turns out to be about something else.

1. Read each candidate in full before judging it. For a ticket: description, acceptance criteria, checklist, comments, linked issues and the PRs linked to it. For a PR: description and diff, not only the title or branch name. For a Slack thread: the whole thread.
2. Compare it with the issue on substance. Count it as related only when it matches on at least one of these, and say which: the same symptom or behavior, the same code path (files, functions, endpoints, tables), the same entity or customer data, or the same cause. Shared words, the same feature area or the same team don't count.
3. Classify each one:
   - Same issue: it describes this exact problem or change. Treat it as the duplicate or the source of intent.
   - Related: it shares a cause, code path or data with this issue but is a different problem. Cite it with one line on what it shares.
   - Unrelated: it only shares words. Drop it.
   - Unclear: say "possibly related, unverified" and what would settle it (a file to read, a person to ask, a query to run). Never present it as related.
4. When a PR tags a ticket that its diff doesn't address, report the mismatch ("the PR tags TICKET-1, which asks for X; the diff does Y"), don't build the PR's intent or acceptance criteria from that ticket, and search for the right one.
5. In the output, list what you dropped and why in one line each ("TICKET-2: about the CSV export's date format, not the sync job"), so the user sees the check happened.

## Status

- Opening a PR for a ticket: assign it to the user and move it to In Progress.
- PR ready for review: move it to In Review.
- Done: leave it to the user unless they ask.

Transition IDs: use the ones the workspace values list. For any other status, look the ID up with `getTransitionsForJiraIssue`, since IDs differ between workflows.

## Checklists

When a description says "See checklist below", read the items with `getJiraIssue` and `properties: ["<checklist property>"]`, using the property the workspace values name. When the property doesn't carry a checked or unchecked state per item, don't report which items are done.
