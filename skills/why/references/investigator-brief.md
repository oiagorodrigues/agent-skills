# Investigator brief

Adapted from pstack's why (Lauren Tan, MIT, https://github.com/cursor/plugins/tree/main/pstack). Paste the shared part, then only the section for this investigator's source, then the code anchor and the question.

## Shared part

You are investigating why a piece of code is the way it is. Other investigators search other sources in parallel and someone else writes the answer, so go deep on your source only and gather evidence; don't write the conclusion.

- Read-only. Don't comment, post, react, edit, transition, create or commit anything, in any tool. Do only what this brief asks. If you think something else should change, list it under "Proposals" in your report.
- Cast a wide net, then read each hit in full (the whole PR with review comments, the whole ticket with comments and parent, the whole thread). The answer is often in a comment.
- Follow links within your source only. Record a lead into another source under "Leads" instead of chasing it.
- Quote verbatim with the exact location (PR number, ticket key, URL, commit hash, `file:line`), author and date.
- Record every query you ran, including the empty ones. An empty search is a finding.
- A commit that changes `limit = 50` to `limit = 100` shows the change, not the reason. Claim intent only where someone wrote it.
- When items disagree, record both. The contradiction is often the most useful finding.
- Tag each finding "verified" (with the command, URL or `file:line`) or "belief".

Return, in this order: Source; What I searched (queries verbatim); Direct evidence (quote, location, author and date, one line on relevance); Indirect evidence (what it is, where, what it suggests, other readings); Contradictions; Gaps; Leads for other sources; Proposals.

## Source control

```bash
git log --follow -p -- <file>                  # full history through renames
git log -S '<exact text>' -- <file>            # commits that added or removed this text
git log -G '<regex>' -- <file>
git show <hash>                                # one commit with its co-changed files
rg -n -C2 '(TODO|FIXME|HACK|XXX|NOTE)' <file>
rg -l '<symbol>' --glob '*test*'               # tests often encode the motivating edge case
rg -l -i 'architecture decision|ADR' --glob '*.md'
gh pr view <n> -R <org>/<repo> --comments
gh api repos/<org>/<repo>/pulls/<n>/comments   # inline review comments
gh pr list -R <org>/<repo> --state merged --search '<term>'
gh search code --owner <org> '<symbol>'        # other repos that depend on it
```

Look for reverts followed by "re-apply with...", commits that say "fix for incident" or "add defensive check", and CHANGELOG or release notes.

## Jira (Atlassian MCP)

1. Fetch every ticket key from the anchor first (`Atlassian:getJiraIssue`), with comments, then its parent and epic, and linked issues (`Atlassian:getJiraIssueRemoteIssueLinks` for linked PRs and docs).
2. Search by the feature name, the symbol and business terms with `Atlassian:searchJiraIssuesUsingJql` (`text ~ "<term>" ORDER BY created ASC`), trying several phrasings and the window around the introducing commit.
3. Labels, components and fix versions hint at the kind of reason (customer request, compliance, incident follow-up).
4. Before using a ticket found by keyword, check it is really about this code, as `jira-workflow` describes ("Checking whether a ticket or PR is related"); a shared keyword proves nothing.

## Confluence (Atlassian MCP)

Search with `Atlassian:searchConfluenceUsingCql` (`text ~ "<term>"`) and `Atlassian:search` for the feature, the ticket key and the PR URL; open hits with `Atlassian:getConfluencePage` and read their comments. Specs are often written before the code and never updated, so compare dates with the PR and say when the doc describes a plan that changed. When several drafts exist, find the final or latest one.

## Slack (Slack MCP)

1. Search for the PR URL or `pull/<n>`, the ticket key, and the error string the code handles, with `Slack:slack_search_public_and_private`.
2. Search messages from the PR author in the weeks around the merge date.
3. For defensive code, search incident channels around the date the code appeared.
4. Always open the whole thread (`Slack:slack_read_thread`); one message out of context misleads. A joke isn't a decision. Note the retention cliff if nothing exists before some date, and that DMs may be invisible.

If the Slack MCP isn't authenticated, stop and report the gap; never fill it.

## Sentry

For a guard, retry or try/except: search issues and events for the exception type, the error message and the function name (`Sentry:search_issues`, `Sentry:search_errors`), and compare first-seen dates with the commit that added the defense. Report whether the error still happens today (count, window, query), since that answers "is this still needed".

## Datadog

For timeouts, retries, limits and queues: look for monitors, dashboards and incidents around the introducing commit's date, and the current value of the metric the code reacts to. Load Datadog's own skill guides first, as its MCP instructions say. A metric shows someone measured something, not that the code exists because of it; compare dates. Note retention gaps (the workspace values give Datadog's retention).

## Sigma (data warehouse)

For a threshold, flag or data rule: query how many rows hit the case today and when it last happened, following `prod-evidence` (two sources, the window and the query in the report). Report counts and aggregates only, never personal fields.
