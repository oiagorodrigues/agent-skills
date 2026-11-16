---
name: harness-architect
description: Builds or audits the Claude Code harness of a project (CLAUDE.md, .claude/settings.json, rules, agents, skills and playbooks, hooks, MCP recommendations). harness-setup scans the target project, interviews the user and runs a 9-phase build, or a shorter lite track for small solo projects, with one subagent per phase and a red-team review after each; it saves state in the target's docs/REQUEST/ folder so a stopped run resumes. audit runs three read-only auditors in parallel (configuration, runtime debt, project-fit drift) and returns one report. Use when the user wants to set up, rebuild, resume or migrate (from Cursor) the Claude Code setup of a repo, wants CLAUDE.md, agents, hooks or permissions designed for a project, or wants an existing harness checked. Only for projects that use Claude Code, since it writes .claude/ files. Run as /harness-architect COMMAND [args].
argument-hint: "[harness-setup|audit|harness-audit|ops-audit|fit-audit|help] [target-path]"
---

# Harness architect

Port of the `harness-architect` Claude Code plugin (Apache-2.0, see `LICENSE`). It builds a Claude Code harness for a target project or audits an existing one. The files it generates are Claude Code files (`CLAUDE.md`, `.claude/`), so use it only on projects that use Claude Code. Most command, agent and playbook text is in Korean, and `harness-setup` replies in Korean by default (its "Language" section).

## How to use

Commands:

- `harness-setup [path]` builds, rebuilds or resumes the harness of a project. This is the main entry point.
- `audit [path]` runs harness-auditor, ops-auditor and fit-auditor in parallel and returns one read-only report graded Critical / High / Medium / Low / Aligned.
- `harness-audit [path]` runs only the configuration audit (file layout, JSON validity, permissions, anti-patterns, agent-to-playbook mapping).
- `ops-audit [path]` runs only the runtime-debt audit (session recovery, retry termination, artifact overwrites, duplicated workflows).
- `fit-audit [path]` runs only the project-fit drift audit (track, archetype, agent count, permission paths, CLAUDE.md identity, MCP and hooks).
- `help` prints the static usage guide and runs nothing.

The `harness-setup` flow:

1. Phase 0 is yours as orchestrator. Collect the target path, pick a request name, detect an earlier run to resume, and run the 9-item interview (A1 to A10 without A4) in three AskUserQuestion calls. Write `docs/<request>/00-target-path.md` and check it with `scripts/validate-phase-artifact.sh`.
2. Phase 1-2 (`phase-setup`) scans the project and writes the base harness. It follows `fresh-setup`, or `cursor-migration` when `.cursor/` exists, or `harness-audit` when `.claude/` exists.
3. After Phase 1-2 you decide the track with the table in `.claude/rules/orchestrator-protocol.md`. The lite track needs all its conditions (solo, web app or CLI, not an agent project, at most 100 source files, simple deploy, single service, no strong scope signals) and the user's confirmation.
4. Full track: 2.5 `phase-domain-research` (optional) → 3-4 `phase-design` → 5 `phase-team` → Scope Confirmation Gate → 6 `phase-skills` → Model Confirmation Gate → 7-8 `phase-hooks` → 9 `phase-validate`, optionally with `security-auditor` running alongside it. It takes 60 minutes or more.
5. Lite track: L `phase-setup-lite` replaces Phases 3-6 → 7-8 `phase-hooks` only when needed → 9 `phase-validate`. It takes 25-35 minutes and can't resume halfway, so a stopped lite run starts over.
6. `red-team-advisor` reviews every phase's output and returns BLOCK / ASK / NOTE items, which you bring to the user.

What `harness-setup` writes into the target project: `CLAUDE.md`, `CLAUDE.local.md`, `.claude/settings.json`, `.claude/settings.local.json`, `.claude/rules/*.md`, `.claude/agents/*.md` (agent projects), `.claude/skills/*/SKILL.md`, `.claude/hooks/*.sh`, `playbooks/*.md`, `.gitignore` entries, and the phase artifacts `docs/<request>/00-target-path.md` to `07-validation-report.md`. MCP servers are only recommended, with config snippets. The audit commands write nothing.

Subagents per run: the full track spawns about 12 to 17 (one worker per phase, a red-team review after each, plus the optional domain research and security audit), and more when a BLOCK sends a phase back (up to 2 reruns per phase). The lite track spawns about 6 to 9. `audit` spawns 3 in parallel, the single audits 1 each, and `help` none.

Examples:

```
/harness-architect harness-setup /Users/me/code/my-app
/harness-architect audit /Users/me/code/my-app
```

## Routing

The first word of the arguments ($ARGUMENTS in Claude Code) names the command; read `commands/<cmd>.md` and follow it. With no command, show the list. With an unknown word, show the list too. Inside a command file, `$ARGUMENTS` means what follows the command word, for example the target path.

Before `harness-setup`, read the four rule files that the plugin expected to be loaded already: `.claude/rules/orchestrator-protocol.md`, `.claude/rules/question-discipline.md`, `.claude/rules/output-quality.md` and `.claude/rules/meta-leakage-guard.md`. Read `.claude/rules/pipeline-review-gate.md` where a file points to it.

## Paths

- `~/.agents/skills/harness-architect` is this skill folder. Expand `~` for tools that need an absolute path. "어시스턴트 프로젝트", "assistant project" and `[Assistant Project Root]` also mean this folder.
- Some files use paths relative to this folder without saying so. These point here: a bare `.claude/rules/<name>.md` for one of the five rules above, any `.claude/templates/...` path, `scripts/<name>` for the scripts listed below, and `playbooks/<name>.md` when `<name>` is one of this folder's playbooks (for example `fresh-setup` or `harness-audit`). Every other `.claude/...`, `CLAUDE.md`, `playbooks/` or `docs/` path points to the target project (`{대상}`, `{target}`, `{대상 프로젝트}`).
- Template skills under `.claude/templates/` are stored as `SKILL.md.template` so this folder holds only one `SKILL.md`. Write them into the target as `SKILL.md`.

## Subagents

When a command dispatches agent X (subagent_type `harness-architect:X` or a plain agent name), spawn a general-purpose subagent whose brief is the body of `agents/X.md` plus the task. In a tool without subagents, follow `agents/X.md` yourself. The files write a dispatch as `Agent(agent: "agents/X.md", ...)`, and that call means the same thing.

- Each agent file's frontmatter names a model (Opus, Sonnet or Haiku). Pass that model family when the spawn tool lets you choose one.
- Only you, the orchestrator, ask the user questions. Subagents return them under `## Escalations`. In a tool without AskUserQuestion, ask in chat with the same options.
- `phase-skills` may fan out with TeamCreate. If its subagent can't spawn agents, it writes the skills one after another.
- Subagents don't see this file, so start each brief with the absolute path of this folder and the path rule from "Paths".
- Add the post-write check below to the brief of every subagent that writes target files.

## Post-write check

The plugin ran `scripts/syntax-check.sh` as a PostToolUse hook on every Write and Edit. Run it yourself instead, right after you or a subagent writes or edits a target file that is under `.claude/`, is a `CLAUDE.md`, or is a phase artifact `docs/<request>/NN-*.md`:

```bash
printf '{"tool_input":{"file_path":"%s"}}' "/absolute/path/to/file" | bash ~/.agents/skills/harness-architect/scripts/syntax-check.sh
```

Exit 2 means a problem, and stderr says which one (invalid JSON, a dangerous `allow` pattern or a missing `deny` list in `settings.json`, an unclosed YAML frontmatter, a file name with shell characters). Fix the file and run the check again. Exit 0 passes. For phase artifacts it also prints structure warnings from `validate-phase-artifact.sh`, which the Phase Gate checks again. The JSON checks use `jq`, or `python3` when `jq` is missing, and are skipped when neither exists.

## Folder contents

- `commands/` holds the six commands above.
- `agents/` holds the 13 subagent briefs (`phase-*`, `red-team-advisor`, `security-auditor`, `harness-auditor`, `ops-auditor`, `fit-auditor`).
- `playbooks/` holds the methods the agents read. `knowledge/` holds Claude Code reference notes and the domain seeds in `knowledge/domains/`. `checklists/` holds the Phase 9 checklists.
- `.claude/rules/` holds the orchestrator rules, and `.claude/templates/` holds the files copied into target projects (intent gate, code researcher, frontend design preset, strict-coding-6step workflow).
- `scripts/` holds `validate-phase-artifact.sh` (with a `.ps1` twin for Windows), `validate-settings.sh`, `validate-meta-leakage.sh` and `syntax-check.sh`. They need bash. `jq` is optional.
