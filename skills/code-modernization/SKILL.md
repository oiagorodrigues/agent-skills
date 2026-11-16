---
name: code-modernization
description: Modernizes legacy codebases (COBOL, legacy Java/C++/.NET, monolith web apps) through a gated workflow of preflight, assess, map, extract-rules, brief, then reimagine, transform or uplift, then harden and status. Produces an assessment, an interactive topology map, business rules as Given/When/Then cards, a phased modernization brief, rewritten or version-bumped code with behavior-equivalence tests, and a reviewed security patch for the legacy code. Use when the user wants to understand, plan or migrate a legacy system, rewrite one module to a new stack, rebuild a system on a new architecture, bump a stack version (.NET Framework to .NET 8, Java 8 to 17, Spring Boot 2 to 3), or security-harden legacy code before a migration. Run as /code-modernization COMMAND [args], where COMMAND is preflight, assess, map, extract-rules, brief, reimagine, transform, uplift, harden or status.
argument-hint: <preflight|assess|map|extract-rules|brief|reimagine|transform|uplift|harden|status> <system-dir> [args]
---

# Code modernization

This skill takes a legacy system through discovery, a human-approved plan and then the rewrite, so code is never changed before it is understood and every change ships with tests that prove behavior didn't drift. It is a port of Anthropic's `code-modernization` Claude Code plugin (Apache-2.0, see `LICENSE`). Each command is a standalone step that writes its own artifacts, so the user can stop, review and resume at any point.

## How to use

Run the commands in this order. `status` works at any point.

```
preflight -> assess -> map -> extract-rules -> brief -> (reimagine | transform | uplift) -> harden
```

| Command | Arguments | What it does |
|---|---|---|
| `preflight` | `<system-dir> [target-stack]` | Asks the user five questions the code can't answer, then checks tools, build toolchain, missing sources and scope boundary. Writes `PREFLIGHT.md`. |
| `assess` | `<system-dir> [--show-secrets]` or `--portfolio <parent-dir>` | Inventory, complexity, tech debt, security posture and a relative COCOMO size index. Writes `ASSESSMENT.md` and `ARCHITECTURE.mmd`, or `analysis/portfolio.html` for a portfolio. |
| `map` | `<system-dir>` | Call graph, data lineage, entry points and persona flows. Writes `topology.json`, an interactive `TOPOLOGY.html` and small `.mmd` diagrams. |
| `extract-rules` | `<system-dir> [module-pattern]` | Mines business rules into Rule Cards with `file:line` citations. Writes `BUSINESS_RULES.md` and `DATA_OBJECTS.md`. |
| `brief` | `<system-dir> [target-stack]` | Turns discovery into a phased plan with a behavior contract and an approval block, then stops until the user approves. Writes `MODERNIZATION_BRIEF.md`. |
| `reimagine` | `<system-dir> <target-vision>` | Greenfield rebuild from the extracted spec, with two approval checkpoints. Scaffolds services with acceptance tests. |
| `transform` | `<system-dir> <module> <target-stack>` | Rewrites one module to a new stack after an approved plan, with characterization tests first. Writes `TRANSFORMATION_NOTES.md`. |
| `uplift` | `<system-dir> <source-version> <target-version> [project-pattern]` | Same-stack version bump with the smallest diffs that build, pilot unit first, then batched fan-out. Writes `DELTA_CATALOG.md`, `BASELINE.md`, `PLAYBOOK.md` and `UPLIFT_NOTES.md`. |
| `harden` | `<system-dir> [--show-secrets]` | Security scan of the legacy code and a reviewed remediation patch the user applies. Writes `SECURITY_FINDINGS.md` and `security_remediation.patch`. |
| `status` | `<system-dir>` | Read-only report of which artifacts exist, which are stale, secrets hygiene and the next command to run. |

Pick the build command by how much of the code survives:

- `transform` rewrites one module at a time into a different stack (COBOL to Java), strangler-fig style, while the legacy system keeps running.
- `reimagine` rebuilds the whole system on a new architecture from the extracted rules and interfaces, so the legacy code becomes the spec and stops being the template.
- `uplift` keeps the code and bumps it to a newer version of the same stack (.NET Framework 4.8 to .NET 8). If the delta catalog shows most of the code has to change anyway, it stops and recommends `transform` or `reimagine`.

`assess` and `brief` both recommend one of the three, and `brief` names the command for each phase.

Every command expects the code at `legacy/<system-dir>/` under the current project. If it lives elsewhere, symlink it (`mkdir -p legacy && ln -s /path/to/code legacy/billing`). Outputs go to:

- `analysis/<system-dir>/` for discovery artifacts, the brief, the delta catalog, the playbook and security findings.
- `modernized/<system-dir>/<module>/` for `transform`, `modernized/<system-dir>-reimagined/` for `reimagine` and `modernized/<system-dir>-uplifted/` for `uplift`.
- `SECRETS.local.md` and `*.local.patch`, gitignored inside `analysis/`, or under `~/.modernize/<system-dir>/` when the project isn't a git repo.

No command edits `legacy/`. `README.md` in this folder has a `.claude/settings.json` that enforces that and the safety notes on untrusted code and secrets.

Examples:

```
/code-modernization assess billing
/code-modernization uplift billing ".NET Framework 4.8" ".NET 8" "src/Billing.*"
```

## Routing

The first word of the arguments (`$ARGUMENTS` in Claude Code) names the command; read `commands/<cmd>.md` and follow it. With no command, or one that isn't in the table above, show the table and stop.

Inside a command file, `$ARGUMENTS` means everything after the command name, and `$1`, `$2`, ... are the words of that remainder. For `/code-modernization transform billing interest-calc java-spring`, `$1` is `billing`, `$2` is `interest-calc` and `$3` is `java-spring`. Treat a quoted value as one word.

Paths in the command files (`agents/`, `workflows/`, `assets/`) are relative to this skill folder, `~/.agents/skills/code-modernization`. When a command mentions "the plugin README", read `README.md` in this folder.

## Subagents

When a command or workflow dispatches agent X (for example "spawn the **legacy-analyst** subagent"), spawn a general-purpose subagent whose brief is the body of `agents/X.md` plus the task. In a tool without subagents, follow `agents/X.md` yourself.

Each agent file lists its allowed tools in its frontmatter. Put that list in the brief as an instruction ("Use only these tools: ..."), because a general-purpose subagent doesn't enforce it.

| Agent | Tools | Used by |
|---|---|---|
| `legacy-analyst` | Read, Glob, Grep, Bash (read-only) | assess, extract-rules, reimagine |
| `business-rules-extractor` | Read, Glob, Grep, Bash (read-only) | extract-rules, reimagine |
| `security-auditor` | Read, Glob, Grep, Bash (read-only) | assess, harden |
| `architecture-critic` | Read, Glob, Grep, Bash (read-only) | reimagine, transform, uplift |
| `version-delta-analyst` | Read, Glob, Grep, Bash (read-only) | brief, uplift |
| `test-engineer` | Read, Write, Edit, Glob, Grep, Bash | transform, uplift |
| `scaffolder` | Read, Glob, Grep, Write, Edit, Bash | reimagine |
| `uplift-migrator` | Read, Glob, Grep, Write, Edit, Bash | uplift |

## Workflow tool

Five commands prefer the Claude Code Workflow tool and run a script from `workflows/`: `assess --portfolio`, `extract-rules`, `harden`, `reimagine` (Phase E) and `uplift` (Steps 3 and 5b). Pass `scriptPath` as an absolute path, with `~` expanded to the home directory. The scripts run each agent as `general-purpose` and tell it to read its `agents/X.md` file first.

When the Workflow tool isn't available, use the command's own fallback (the section marked "Fallback" or "Method B"), which spawns the subagents directly as described above.
