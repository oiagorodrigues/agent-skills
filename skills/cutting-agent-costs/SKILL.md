---
name: cutting-agent-costs
description: Reduces tokens and cost of coding-agent runs and agent pipelines (claude -p, codex exec, opencode run, subagents, Agent SDK) without hurting quality, with numbers measured on this machine. Use when an agent or pipeline is too expensive or starts with too much context, when picking which model or effort to use per stage or task, setting --max-budget-usd or --max-turns, trimming skills, tools or MCP servers per run, structuring prompts for cache hits, designing agent memory or handoffs, deciding what to move into scripts, or measuring cost per stage, agent or PR. Triggers on "reduce tokens", "too expensive", "cost per stage", "which model for", "custo", "economizar tokens", "factory".
---

# Cutting agent costs

Rules for spending fewer tokens without making agents dumber. Measured numbers on this machine are in `references/claude-code-recipe.md`; every external claim has its source in `references/sources.md`.

## 1. Measure before cutting

- Every headless run writes one line to a log: run id, stage, agent, runner, model, effort, input/cache-read/cache-write/output tokens, USD, duration, outcome (passed verify, approved by a person). `claude -p --output-format json` gives `total_cost_usd` and `modelUsage.<model>.costUSD`. These are client-side estimates, not billing.
- The number that matters is cost per merged PR (or per accepted result), including failed runs. Cost per call hides retries.
- Build cost dominates. Optimize the implement/build stage first; planning and QA are cheap.
- Keep 20 to 50 real tasks as an eval set and compare changes on it. Gaps under about 3 points are noise (how to build and label it: `~/.agents/skills/ai-engineering/references/evals.md`).

## 2. Trim startup context

A plain `claude -p` here starts with about 35k tokens before the task. The full recipe and the measured table are in `references/claude-code-recipe.md`. In short:

- Skills: hide personal skills with `skillOverrides: "off"` in a `--settings` file, put the stage's core skill in `--append-system-prompt-file`, and load optional skills as a plugin with `--plugin-dir`. `--disable-slash-commands` removes every skill, including plugin ones.
- MCP: `--strict-mcp-config --mcp-config <file>` with only the servers the stage calls. Prefer a script that fetches the data before the run over an MCP server in context.
- Tools: `--tools` with only what the stage uses. Read-only stages get `Read,Grep,Glob`.
- Settings: `--setting-sources project` drops user hooks, plugins and CLAUDE.md; add back only the hooks you need (rtk) through `--settings`.
- Do not use `--bare`: it skips every hook (rtk included) and does not read OAuth/keychain logins.
- Text-only stages (discovery, refine, PR text) can replace the system prompt with `--system-prompt-file`. Coding stages keep the default.

## 3. Prompt caching

- Order every prompt by how often it changes: tools, system prompt, static repo context, then the task input. Only append. Never put timestamps or run ids in the prefix. Serialize JSON deterministically.
- Things that drop the cache: switching model, changing the tool set or tool order, connecting or disconnecting an MCP server, a different `--system-prompt`, changing effort on older models. Skills injected as messages do not break it.
- Claude Code caches per machine and directory, and sequential sessions share the prefix only when the startup git status matches. Run all stages of one task in the same worktree and commit at the end.
- TTL: with an API key `claude -p` defaults to 5 minutes; set `CLAUDE_CODE_PROMPT_CACHE_TTL=1h` when stages run more than 5 minutes apart. A 1h write costs more than a 5m write, so only use it when there will be a later hit.
- Run the same stage for several tasks back to back so the stage prefix stays warm.
- Single-turn, non-urgent work (classification, summaries, lesson compaction, eval grading) goes to the provider's batch API at about half price. Agent loops cannot use batch.

## 4. Context during a run

- Each stage starts fresh and reads a short handoff file from the previous stage, never the previous transcript.
- Clearing old tool results ("observation masking") is about as good as LLM summarization and costs about half; prefer it before summarizing.
- Exploration goes to a subagent that returns a 1k to 2k token summary.
- Precompute a repo map (structure plus symbols, about 1k tokens) once per commit, and run `rg` on the task keywords before the agent starts. Give the agent the candidate files instead of letting it walk the tree.
- Use an LSP plugin for navigation: one go-to-definition replaces a grep plus several file reads.
- Trim tool output: rtk for shell commands; for tests, pass only failures.
- Before a build stage, write the definition of done (acceptance tests or checks) so the build and verify stages share one contract.

## 5. Memory

- Keep the injected layer tiny (an index of short lines) and load details on demand.
- One writer per memory file. Shared files written by several agents lose writes.
- Let the strongest model write memory; weak models write many low-value notes.
- Store lessons as small itemized deltas ("when X, do Y because Z"), never by rewriting the whole file.
- Run a periodic curation pass that checks lessons against what actually happened, merges duplicates and drops stale ones. Cap each lessons file (about 2 KB).

## 6. Model routing

- Route by fixed rules per stage, not by a learned complexity router. Rule-based complexity routers measured close to chance.
- Strong model where a mistake propagates (plans, a retry after a failed build); mid model for discovery, refinement, test scenarios and the first build attempt; cheap or local model for formatting text and summaries.
- Raise the tier on risk signals found by script (migrations, auth, payments, large diffs), not on the model's own opinion.
- Escalate by restarting from repo state plus a short note. Passing the cheap model's full trajectory to the strong model recovers less than half of the gap.
- Effort is the main dial inside one model: low for subagents and formatting, medium for most coding, high for planning and hard fixes.
- A reviewer from another model family helps in one direction and hurts in the other. Measure it on your eval set before relying on it.
- Fallbacks (`--fallback-model`) handle overload; they are not routing.

## 7. Keep deterministic work out of the model

Scripts do: fetching tickets, building the repo map and candidate file list, creating worktrees and branches, lint, typecheck and selected tests with trimmed output, git commit and push, opening PRs (`gh`), posting ticket comments, validating stage output against a schema (`--json-schema`, `codex exec --output-schema`), counting retries and enforcing gates. Cap automatic fix rounds (2 CI rounds, then a person).

## 8. Budgets

- `--max-budget-usd` and `--max-turns` are safety nets against loops. Set them generously; a tight cap cuts reasoning short and the run stops before finishing. Spend can pass the cap a little, so leave headroom.
- After about 10 runs of a stage, suggest a cap of the stage's p99 cost times 1.2 and report every run that hit the cap. Suggest; never tighten automatically.
- Tune cost with effort and model choice first, caps last.

## 9. Measurement with OpenTelemetry (optional)

Claude Code exports `claude_code.cost.usage` and `claude_code.token.usage` when `CLAUDE_CODE_ENABLE_TELEMETRY=1` and an exporter is set. `OTEL_RESOURCE_ATTRIBUTES=stage=plan,task=ABC-123` tags every metric of that run. Use it when you want dashboards across interactive sessions too; for a pipeline, the per-run JSON log is enough.
