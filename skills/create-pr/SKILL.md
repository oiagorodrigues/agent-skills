---
name: create-pr
description: Use every time a pull request description is written or changed, in any repo and any agent. Covers opening a PR (`gh pr create`), rewriting or fixing an existing description (`gh pr edit`), and drafting one for the user to paste. Applies the house format (ticket link, why the change, special things to note, change outline), plain-writing rules, linking rules for every referenced resource, and a 1,000 to 2,000 character limit.
---

# Create PR

Write a PR description a reviewer reads in under a minute and comes away knowing what changed, why, and what to watch for. The diff already shows the mechanics, so the description carries the reason and the risk.

## Before writing

1. Load the `plain-writing` skill and apply it to every sentence, including the title and the commit message.
2. Gather the facts: the diff (`git diff <base>...HEAD` or `gh pr diff <n>`), the Jira ticket (from the branch name, commits or the user), related PRs, and how the change was verified. Before linking a ticket or a related PR, read it and confirm the diff addresses it, with the "Checking whether a ticket or PR is related" check in the `jira-workflow` skill. Never tag a ticket picked from a keyword search; if the branch's ticket doesn't match the diff, tell the user instead of linking it.
3. Write as the author ("I removed", "this PR deletes"), following the "Write as the author" section of `plain-writing`.

## Format

In the examples, `<org>` is the GitHub org and `<site>.atlassian.net` the Jira site. Both come from the workspace skill for the repo, when one exists; otherwise take the org from `gh repo view --json owner` and the site from the ticket link.

````markdown
[PROJ-123](https://<site>.atlassian.net/browse/PROJ-123) · follows [repo#123](https://github.com/<org>/repo/pull/123)

## Why the change

Two to four sentences in plain English: what was wrong or missing, as a user or operator saw it, and what this PR does about it.

## Special things to note

- Only what a reviewer needs to review safely: a behavior that looks wrong but is expected, a number that changes and why, a risky part of the Terraform plan, a known gap left for a follow-up, a required merge or deploy order.
- One line on reversibility and blast radius: a two-way door (undo with a revert or by turning a flag off) or a one-way door (a data migration, a public API change, deleted data), and what it can break (callers, other repos, customers).

## Change outline

```diff
service/handler
- old call or resource
+ new call or resource
```

How it was verified, in one or two sentences with the real numbers: tests run and passing, before/after counts on real data.
````

### Change outline

A short diff or pseudo-code block showing the shape of the change (call flow, query shape, schema change). Not a file-by-file list. Always tag the fence with a language so GitHub highlights it: `diff` for an outline of `+`/`-` lines, otherwise the code's language (`python`, `ts`, `hcl`, `sql`).

For UI or UX changes, add one screenshot or a GIF of five seconds or less here instead of describing the UI in words. Use before/after images side by side when the change is visual.

## Links

Every resource the description mentions gets a Markdown link, so a reviewer can jump to it in one click:

- Jira ticket, always, when one exists: `[PROJ-123](https://<site>.atlassian.net/browse/PROJ-123)`.
- PRs in the same repo: `[#4797](https://github.com/<org>/<repo>/pull/4797)`. PRs in other repos: `[other-repo#2921](https://github.com/<org>/other-repo/pull/2921)`. Link every mention, including repeats in later sections.
- Commits: `` [`d711108`](https://github.com/<org>/<repo>/commit/<full-sha>) ``.
- Code: link the file or line range on the PR's head commit, `` [`path/file.py#L10-L20`](https://github.com/<org>/<repo>/blob/<sha>/path/file.py#L10-L20) ``. Use a commit SHA, not a branch name, so the link doesn't drift.
- Docs, Confluence, Slack threads, Datadog dashboards, Sentry issues: link the exact page, not the space or home.

Don't write a reference a reader would have to search for. If the URL can't be found, ask the user or drop the reference.

## Length

Keep the body between 1,000 and 2,000 characters, not counting blocks bots append, because long descriptions don't get read. Check with `wc -c` before posting. If it runs long, cut the change outline first, then the notes. If it runs short, the "why" is probably missing a fact the reviewer needs.

## Rules

- Title: a conventional-commit prefix and a plain summary of the outcome (`chore: remove Knock data-engineering infrastructure`).
- Drop "Special things to note" when there is nothing a reviewer must know.
- The one-way or two-way door line comes from Matt Pocock's pr skill (MIT, https://github.com/mattpocock/skills). Write "one-way door" plainly when it is one, so the reviewer slows down.
- No headings beyond these three, no tables, no restating the diff file by file, no long verification write-ups.
- Point to a ticket or doc for background instead of retelling it.
- Show the draft to the user before creating or editing the PR, unless they already said to post.
- Always open the PR as a draft (`gh pr create --draft`) unless the user says to open it ready for review.
- Before opening or pushing, read the diff for any change the task doesn't need (a drive-by fix, a refactor of shared code, a file outside the feature). Revert it. Keep it only with a concrete reason, and then leave an inline PR comment on that line saying why it's in this PR (`gh api repos/<owner>/<repo>/pulls/<n>/comments` with `path`, `line` and `commit_id`).
