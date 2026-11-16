---
name: brag
description: >-
  Builds the user's worklog and brag document in Notion from what they shipped and decided at work:
  merged PRs (gh CLI), Jira tickets (Atlassian MCP), and Slack decisions (Slack MCP). Reads the job's
  pages, GitHub org, ticket site and repo-to-team map from the workspace skill. Use when the user runs
  /brag, asks to update the worklog or brag document, or wants a summary of work for a period (month,
  quarter, performance review), or a day-by-day summary for time tracking.
---

# Brag

Turn a period of work into two Notion pages:

- **Worklog**: what I delivered each month, grouped by team. Features, fixes customers noticed, migrations, decisions. One line per ticket plus a short note on why it mattered.
- **Brag document**: the few achievements from the worklog that moved something the company cares about (revenue, customers, cost, reliability, team speed). This page feeds performance reviews.

The worklog is not a commit dump. A lint rule change or a small tech-debt cleanup only goes in when it is part of something larger, and even then as a clause, not its own entry.

## Job values

The values below come from the "Values for brag" section of the private workspace skill for the user's job (a `ws-*` skill in `~/.agents/skills`). If more than one workspace skill has that section, ask which job. If none has it, ask the user for the values and offer to save them in that workspace skill.

- The worklog and brag document page URLs.
- The ticket URL pattern (`https://<site>.atlassian.net/browse/<KEY>`).
- The GitHub org and the local folder that holds the job's clones.
- The repo to team map.
- Who reads the pages, who the work benefits, and the placeholders to use instead of customer names.
- Example entries in the house format.
- Where the daily time-tracking summary goes, and what it must leave out.

## Inputs

Ask for the period if the user didn't give one (default: the last full month). The user may also hand over docs, dashboards or Slack threads with impact numbers; use them, and never invent a number.

## Notion pages

Each page has a child page per year (`2026`), and each year has a child page per month (`June`). Fetch the root, then the year, then the month with `notion-fetch`. If the period covers a year or month with no page yet, create it with `notion-create-pages`: a year page under the document's root, a month page under its year, titled like its siblings (`2026`, `July`). Read the existing month before writing so entries aren't duplicated, and add to it with `notion-update-page` instead of rewriting it.

Only write inside these two pages, and only in their year and month pages. Never edit, move or delete anything outside them, or any page in them that doesn't fit the year and month layout, such as a loose month page directly under the root.

Ticket lines link to the ticket URL from the job values; Notion renders Jira links as link previews.

## Repo to team map

Group entries by the team the job values map each repo to. For a repo not in the map, use the Jira project key of the linked ticket (PROJ-93 goes under PROJ). If there is no ticket, ask, then add the repo to the map in the workspace skill.

## Gather

1. **GitHub.** Merged PRs by me in the period, across the whole org, because work lives outside the main repo too:
   ```bash
   gh search prs --owner <org> --author @me --merged --merged-at 2026-09-01..2026-09-30 \
     --json repository,title,url,closedAt,body --limit 200
   ```
   Then check every local repo in the job's clone folder for work that never became a PR:
   ```bash
   git -C <repo> log --author="$(git config user.email)" --since=2026-09-01 --until=2026-10-01 --oneline
   ```
2. **Jira.** Tickets assigned to me and resolved in the period (Atlassian MCP, `searchJiraIssuesUsingJql`):
   `assignee = currentUser() AND resolved >= "2026-09-01" AND resolved < "2026-10-01"`.
   Read the description of each ticket that a PR links to, to learn what problem it solved.
3. **Slack.** Search my messages for decisions and proposals (Slack MCP, `slack_search_public_and_private`, `from:me` plus words like "decided", "proposal", "we'll go with", "RFC"). Keep only threads where a decision landed.

Only include finished work: tickets in Done and merged PRs. Leave out anything in draft, in progress, in review or in UAT, and tickets closed as Won't Do or Duplicate, even when the JQL above returns them.

Group PRs, commits and messages under their Jira ticket. Several PRs for one ticket make one entry.

## Write

Load `/plain-writing` and `/business-first-pitch` before writing anything that goes to Notion: `plain-writing` for the wording, `business-first-pitch` to find each entry's business outcome. Write in first person, past tense, in English.

Worklog month page body (match the existing pages and the examples in the job values; the month name is the page title, not a heading):

```
[PAY]
• PAY-93 Retry card captures that timed out at the bank
    ◦ Customers whose first capture timed out now get charged on the retry instead of seeing a failed order.
• PAY-271 Fix open Dependabot alerts
    ◦ Closed 7 known vulnerabilities in the payment service's dependencies, which keeps us inside the security remediation window.
[CORE]
• CORE-1073 Users getting errors when editing their profile
    ◦ Users can edit their profile again without hitting errors.
```

Both pages are read by the people the job values name (usually leadership, in performance reviews), so every entry has to answer why the work mattered. Before writing, find the reason behind each ticket in its epic, the Slack threads where it was decided (product and rollout channels) and Confluence (RFCs, rollout plans): what problem users had, why the team chose to build, remove or postpone it, and what customer or company outcome it was aiming for. Leave out mechanics a reader at that level doesn't need, such as line counts, PR counts or file names.

No PII or customer identity anywhere on either page: no customer or company names, people's names, emails, IDs or slugs, even when the ticket or Slack thread has them. Use the placeholders from the job values ("a customer", "a customer with 99+ items in the cart") instead.

Every ticket gets a sub-bullet of one to three sentences on what it changed for the business: who benefits (the groups the job values list, such as customers, support, the team, the company) and how. When nothing was measured, describe the intended effect as a plain fact about the change, without labels like "intended impact". No vague filler ("improved the codebase", "more reliable"); name the concrete effect.

Ticket keys are links to the Jira issue. Work without a ticket gets a plain-text title, PR links and the same sub-bullet.

For the brag document, use `business-first-pitch` to frame each achievement by its business outcome: who gained what (customers, revenue, cost, support load, engineering time), how much, and the measured source. One short paragraph per achievement that states the result first, the number and its source, then what I did.

```
• Customers can now download their own sales reports. I built the reporting backend and filters (PROJ-84 to PROJ-94); <N> customers used it in the first month (source: product analytics dashboard).
```

If an achievement has no measured impact yet, write it without a number and tell the user which number would make it stronger.

## Before publishing

Show the user the drafted month for both pages and wait for approval before writing to Notion. After publishing, give the raw URLs of the updated pages, then write the daily time-tracking summary below for the same period without waiting to be asked.

## Daily time-tracking summary

Write this after every publish of the worklog and brag document, and whenever the user asks for a day-by-day summary for time tracking. It goes in chat only, never in Notion. List each day Monday to Friday, built from PR open and merge dates, commit dates, Jira resolution dates and Slack.

- When the summary goes to a system outside the company (the job values say where it goes), leave out internal details: no feature flag names, PR numbers, repo, table, channel or internal tool names. Ticket keys are fine. Unfinished work (open PRs, tickets in review) belongs here too, since it took time that week.
- Every item says what changed for the business (who benefits and how), not only the technical change.
- Each day stays under 1,000 characters, date line included. Count them with a script before sending.
