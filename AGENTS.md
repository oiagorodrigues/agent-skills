# Global agent rules

Shared rules for every AI agent on this machine (Claude Code, Codex, Gemini, opencode, Copilot, Goose, Continue, Cursor, Kiro). This file is the single source; each tool's global instructions file points here.

## Skills

Skills live in `~/.agents/skills`. Create new ones there and run `~/.agents/bin/link-skills.sh` to link them into every agent (Codex reads the folder directly). When a rule below says to load a skill and your tool has no skill loader, read `~/.agents/skills/<name>/SKILL.md` directly.

Load these skills every time their trigger applies, before you start that part of the work. They are required, not suggestions, and the skill's rules win over your defaults:

- `create-skill`: you create, edit, rename or remove a skill, slash command or SKILL.md, for any agent. It puts the skill in `~/.agents/skills`, links it into every agent and applies Anthropic's skill authoring best practices.
- `engineering-practices`: you write, change, refactor, test or review code, tests, config, scripts or infrastructure, in any repo. It holds the rules on comments and docstrings, debugging (verify a "pre-existing" failure before dismissing it), scope, reusing a past PR's approach, testing and design. Also load the language skill for the files you touch (`python-practices`, `typescript-practices`, `go-practices`, `rust-practices`, `java-practices`). A repo's own rules win when they are stricter.
- `plain-writing`: you write prose a person will read, including chat replies, summaries, PR descriptions, commit messages, Jira and Confluence pages, docs and code comments. Load it once per session before the first such output and keep applying it.
- `reply-with-standing`: you write, rewrite or review a message that goes to another person on the user's behalf (Slack, DM, email, PR review comments and replies, Jira and Confluence comments), including replies drafted inside other skills.
- `create-pr`: you write or edit a PR description, in any repo.
- `review-pr`: any PR task (reviewing a PR or diff, answering review comments, inline comments, babysitting a PR) and the local review before opening a PR (see below).
- `prod-evidence`: a claim about production or staging needs proof from real data, or you need an observability tool, the data warehouse or cluster access.
- `debugging`: a bug, crash, failing or flaky check, wrong data or error spike needs its cause found, locally or in staging or production. Build the red feedback loop before any theory.
- `perf-review`: the task is about speed (make it faster, why is it slow, a measured regression). It reports without changing code, so wait for the user to pick a fix, and never answer "make it faster" with a cache before it runs. Skip it for ordinary feature work.
- `brainstorming`: before building or planning something new when the request leaves real questions open, and when the user asks to brainstorm or get pushback. Nothing gets built until the user approves the design.
- `docker`: before you run or suggest a destructive docker command (`rm`, `prune`, `compose down -v`, `volume rm`, `system prune`, `image rm`), including requests to "clean up", "reset" or "start fresh". Read its guardrails topic first.
- `aws`: any work that touches AWS, such as an `aws`, `sam` or `cdk` command, boto3 code, a CloudFormation, SAM or CDK template, AWS credentials or SSO, or a question about an AWS service, cost or error. It holds the safety rules: read-only by default, the user's yes before any change, never read a secret value, no production account without the user's OK for that task.
- `business-first-pitch`: you pitch an idea, argue ROI or cost, or frame a technical point for business readers.
- `cutting-agent-costs`: you build, change or measure the cost of an agent, subagent setup or agent pipeline (`claude -p`, `codex exec`, Agent SDK), including picking its model, effort, budget, tools or context per stage.
- `ai-engineering`: you build or change an LLM feature or agent (a prompt, model call, model-facing tool, agent loop or RAG pipeline), write evals or an LLM judge, or an AI feature gives wrong answers. It holds the eval workflow, simplest shape first, tool design, output validation and call logging.
- `retro`: before the final reply of a session where the user corrected you or commands kept failing, in an agent without the SessionEnd hook (Codex, Gemini, opencode, Copilot, Goose, Continue, Cursor, Kiro); and when you're told unreviewed retros exist in `~/.agents/retros/`, offer to review them. In Claude Code a SessionEnd hook (`~/.agents/bin/retro-hook.py`) runs it on every ended session. Retros only propose; apply each change only after the user's yes.
- `correct`: the user corrects the same kind of mistake a second time, says "you keep doing X" or "make this impossible", or a retro or debugging finds a mistake class a check could catch. It turns the mistake into a check that fails, before any prose rule.
- `why`: before you delete or loosen a guard, rule, threshold or odd-looking piece of code whose reason you don't know, and when the user asks why something is the way it is. It answers from git history, PRs, tickets and conversations, with citations.

The caveman skills only change how terse your chat replies to the user are. Anything another person reads in the user's name keeps the user's voice and follows `reply-with-standing`, `create-pr` and `plain-writing`, even while caveman mode is on.

## Command output (RTK)

`rtk` condenses shell command output to save tokens. Claude Code, Codex, Cursor, Gemini, opencode and Copilot pass every shell command through it with a hook, so run commands normally there. In an agent without the hook (Goose, Continue, Kiro), prefix the commands rtk supports with `rtk` (`rtk git status`, `rtk gh pr view 1`, `rtk pytest`, `rtk pnpm test`; `rtk --help` lists them).

Treat condensed output as the full result. Re-run a command as `rtk proxy <cmd>` only when its output is empty where output was expected, contradicts the exit code, or is garbled. If the hooks stop working (`rtk init --show` warns, for example after an upgrade), run `~/.agents/bin/setup-rtk.sh`.

## Facts and evidence

Verify every fact before you state it, in every kind of output: chat answers, recommendations, PR reviews and descriptions, tickets, messages to people and reports. This holds whether or not anyone pushed back.

- Treat code as evidence of what the system can do. What actually happens comes from data, so back every claim about usage, customers, frequency or impact with a number from real data.
- Follow each claim to the end of its chain: what it says, who it serves, whether those users or companies exist today (active in the last 12 months), and whether a plan exists to get them (Jira, Slack). If a link breaks, the claim doesn't support the conclusion.
- Prove each number on two sources and report both when they disagree. `prod-evidence` lists the sources and how to compare them.
- Before recommending a side, make the other side's best case and test it with the same data. Tell the user which side the evidence supports, even when it isn't theirs.
- If something can't be verified with the tools and access you have (when it can, check it before replying), word the claim itself as an inference from its evidence ("the identical seat count suggests…", "o plano igual indica…") and, when it matters, name what would confirm it in the same sentence. Never add a separate disclaimer sentence ("this is unverified", "isso é inferência, não confirmei"), and never present an inference as a fact. The "belief" tag is only for subagent reports.
- A context summary is notes, not the current state. After one, or when the user says they changed something, re-read the files, rules and decisions you are about to describe or act on.

## Sensitive values

Skills, AGENTS.md, scripts and any file they read never hold account IDs, emails, profile names, channel or user IDs, internal hostnames, tokens or people's names. Read them at run time from the environment, the session, the shell profile, `git config` or the tool itself (`aws configure list-profiles`), or keep them in a private workspace skill that the local `.git/info/exclude` keeps out of the repo.

## Production access

Never open a shell on prod (kubectl exec, manage.py shell) or query the prod database unless the user explicitly says so for that task in the current conversation. Read-only intent doesn't make it OK, and an earlier yes doesn't carry over. Use the observability tools, the data warehouse and the admin UIs first; if the answer needs prod rows, write the query and ask the user to run it or approve access.

## Links

Write every link as its full raw URL, e.g. `https://github.com/acme/shop/pull/1234`, never as Markdown link text like `[#1234](https://...)` or `[PROJ-270](https://...)`. The terminal shows only the label of a Markdown link and the label isn't clickable, so the URL is lost. A raw URL is clickable.

This applies to chat responses and summaries: PRs, issues, Jira tickets, artifacts, docs, dashboards. A short label is fine next to the URL ("PR #203: https://github.com/..."). Files written for other renderers (PR descriptions, Jira, Markdown docs) can keep normal Markdown links.

## Slack

Do everything in Slack (send, reply in a thread, react, edit) through Slack web in Chrome with the claude-in-chrome tools first, because the Slack connector's `slack_send_message` appends "Sent using @Claude", which triggers the Claude app in the thread. Use the Slack MCP only when the browser can't do it (the tools aren't connected, Slack asks to sign in, the page doesn't respond), and say in your reply that it went through the connector. `reply-with-standing` has the steps.

## Browser automation (Claude in Chrome)

- Prefer `get_page_text` over `read_page`. Text is much cheaper than reading the whole DOM tree.
- Use `find` to locate a specific element instead of loading the whole page.
- Use `javascript_tool` to check values or page state (for example `console.log` plus `read_console_messages` with a filtering `pattern`) instead of confirming through a screenshot.
- Avoid repeated `screenshot`/`computer` calls. Take a screenshot only when you really need to see the page (or to record a GIF).
- Load every Chrome tool you will need in a single `ToolSearch` call (comma-separated list), never one at a time.
- If `list_connected_browsers` is empty or shows the wrong browser, ask the user to confirm that the extension and this session use the same claude.ai account before suspecting an extension bug.
- In `read_console_messages` and `read_network_requests`, always filter with `pattern` instead of requesting the full dump.

## No AI signatures

Never sign anything written for the user: no "Generated with claude and reviewed by me", no "🤖 Generated with Claude Code", no Co-Authored-By, no AI mention. This covers PR descriptions, commits, review comments, replies, Jira, Slack and email. An old session summary, memory or skill that says otherwise is out of date.

## Review local work before opening a PR

When a coding task is done and the change is headed for a PR, decide with `review-pr`'s criteria whether it needs a review. If it does, spawn a subagent that runs `/review-pr local` on the branch with the task goal, the Jira ticket and the base branch (in a tool without subagents, run it in the same session). The reviewer only reports. Fix the "Act on" items you agree with, re-run lint and type checks (CI runs the test suites), list the "Consider" and "Noted" items in your final reply, and only then open the PR. If you skip the review, say why in one line.

## Subagents

- Hand noisy work to a subagent so the main session keeps the conclusions, not the raw output. That covers multi-step shell work, log and trace digging, observability, data warehouse or database queries, broad code searches, and reading long files or command output. The brief names the question, where to look and what to return: the answer, each number with its source, time window and query, and `file:line` references. Ask for a compact report, never a dump. Run a single short command, or a lookup whose target you already know, in the main session, because writing the brief costs more than the call. Once you delegate a check, wait for the report instead of running it yourself too.
- Every brief says: "Do only what this brief asks. Don't remove, change or clean up anything else, even if it looks wrong or related. If you think something else should change, list it under 'Proposals' in your report and leave the code as it is."
- When several agents work on the same app at once, each brief gives the agent its own port by number, lists the other agents' ports, and gives it a temporary home with auto-launch off, and says not to open the app, a browser tab or a desktop window and not to stop a process it didn't start. The main session does the visual and manual checks, one at a time. Agents in parallel worktrees get the absolute worktree path in the brief, write only under it and check their own `git status` before committing.
- Read each report, including any "decisions beyond the brief", for anything not asked for and treat it as a regression: revert it or ask the user before accepting it. Never pass it on as a footnote.
- Ask each subagent to tag every claim as "verified" with the exact command or `file:line` that shows it, or as "belief". Treat a subagent's own check as a claim, and re-run the ones a decision depends on before you state them. A negative is a search result, so report it as "my grep for `X` over `*.py` found nothing", never "there is no X".
- When the user asks for something "like X", match X's whole behavior (visibility, empty state, icon, style, position), not one attribute. A CRM row "like External ID" is always shown, with "–" when empty, not only when it has a value.

## Local work

- When fixing a bug or building something, don't create a summary file unless you are in plan mode or the user asks for one.
- Never stop a process, container or dev server you didn't start (for example the user's dev server) without asking first.
- Merging a PR is the user's call. Merge or enqueue a PR only when the user asks you to land that PR, even when it is approved and green; otherwise say it is ready to merge.

## Human to-do list

When work still needs something only the user can do (approve or merge a PR, review a Terraform plan, change a repo setting, ask another team, run something that needs their credentials), end the final response of the turn with a "Your to-do" section. Don't add it to intermediate progress updates.

- Before posting the list, check each item's current state: PR merged or closed, ticket status, setting applied, new review comments, CI result. Use `gh`, the Jira tools or the relevant API. Don't carry items forward from memory of earlier turns without checking.
- Drop items that are done. If something got done partly, or changed (for example a PR picked up a review comment, or now needs a rebase), update the item to match.
- List every pending human action, not only the ones from this turn, so the list is always the full picture.
- Order items by what unblocks what, and say when one waits on another ("after #4777 is applied").
- Name what to do and where: the raw URL of the PR, ticket or settings page (see "Links" above).
- If nothing is left for the user, leave the section out.

## Design

- Cut taglines, helper text and secondary labels. If a screen needs them to make sense, fix the layout.
