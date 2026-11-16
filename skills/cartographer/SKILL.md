---
name: cartographer
description: Maps and audits large codebases (hundreds of files, several integrations). Builds a dependency, call and class graph with SVG diagrams over every file type (Vue, Ruby, Java, Kotlin, Rust, PHP and styles included), ranks git hot spots and files that change together, drafts a domain glossary, traces pipelines and API endpoints, splits the repo into segments, sends each segment to one of 19 specialist reviewer subagents in waves of up to 5, then writes a P0-P3 refactor backlog and can apply fixes behind a confirmation gate. Run as /cartographer <command> [project-path]; commands are audit (full pipeline with review subagents) and map (graph and diagrams only, no subagents). Use when the user asks to map out, audit or review a whole project, find hot spots, duplication or naming drift across a repo, build a domain glossary, build a UML or call graph of a project, or understand the structure of a large codebase. Skip it for projects under about 30 files.
argument-hint: "audit|map [project-path]"
---

# Cartographer

Cartographer maps a codebase with deterministic Python scripts (dependency, call and class graph, pipeline and endpoint traces, segments, review waves, specialist matching), then has specialist subagents review each segment and turns their reports into a ranked refactor backlog. Fixes are optional and only run after you approve them.

## How to use

- `/cartographer map [path]` runs only the scripted phases and writes the graph, SVG diagrams, file inventory, hot spots, glossary draft, endpoint cards, segments and wave plan to `<path>/.cartographer/`. It spawns no subagents and takes about 30 seconds for 300 files. Add `--readonly` to write to `~/.cartographer/<hash>/` instead of the repo.
- `/cartographer audit [path]` runs the full flow and stops at each gate for your answer: scope and clarifying questions, then the scripted phases, gate A (confirm segments), gate B (confirm specialists and cost), review subagents, synthesis and `FINAL_REPORT.md` plus `backlog.md`, gate D (pick fixes), and the optional fix phase.

Start with `map` to see the segments and diagrams for free, then run `audit` when you want the review. Examples:

```
/cartographer map <repo-path>
/cartographer audit .
```

Cost: an audit spawns one review subagent per segment (about 40K tokens each, by the plugin's own estimate), so a repo with 20 segments means about 20 subagents. Gate B shows the count and lets you cut it ("top N", "skip generalist", "stop"). The fix phase spawns one more subagent per approved backlog item.

## Signals beyond the graph

All three come from the scripted phases, so `map` produces them too.

- File inventory (`project-map.json` → `inventory`, `stats.inventory_by_lang`). Every text file git lists, with language, size and line count, so JSON, YAML, SQL, Terraform and docs are counted even without a parser. Files with an import parser (Python, JS/TS, Vue `<script>` blocks, Go, Ruby, Java, Kotlin, Rust, PHP, CSS/SCSS/Less, HTML) also join the graph and the segments. Binaries and vendor or build folders are skipped; lockfiles are listed as `lockfile` and left out of hot spots. To parse a new language, add a regex parser in `scripts/map_project.py` and its extension to `SUPPORTED_EXT`.
- Git hot spots (`hotspots.md`, `hotspots.json`, and `hotspots` in `project-map.json` and `synthesis.md`). Per file over the last 12 months: commits, authors, churn and a score of commits x indentation complexity, plus temporal coupling (pairs that keep changing in the same commits, with or without an import between them). Set `CARTOGRAPHER_HOTSPOT_MONTHS` to change the window. Without git or history the files say why and the pipeline goes on; a shallow clone gets a warning. From Matt Pocock's improve-codebase-architecture (MIT, https://github.com/mattpocock/skills).
- Domain glossary (`glossary.md`, `glossary.json`). Built in two steps. A script lists terms from class, type and enum names, enum values, tables, models, routes and frequent identifier words, each with file:line, usage count and a meaning from a docstring, comment or enum values, else "to define", and flags names that may be one concept. The script finds terms reliably but can't say what most of them mean, so in an audit one subagent then runs `skills/cartographer/prompts/glossary.md` to define them and settle the flags, writing `GLOSSARY.md` in the output folder. From Matt Pocock's domain-modeling (MIT).

## Routing

The first word of the arguments ($ARGUMENTS in Claude Code) names the command; read `commands/<cmd>.md` and follow it. With no command, show the list above. In the command files, `$1` means the first argument after the command name (the project path).

When the task is about mapping, auditing or reviewing a whole codebase without a command, read `skills/cartographer/README.md`.

## Paths

All paths here are relative to `~/.agents/skills/cartographer/`. Inside `skills/cartographer/README.md` and its prompts, `prompts/` means `skills/cartographer/prompts/`, while `scripts/`, `agents/` and `run_pipeline.sh` are at this skill's root. `.cartographer/` is the output folder inside the project being mapped.

## Subagents

When a command dispatches a reviewer (for example `backend-api-reviewer`, assigned in `wave_plan.json`), spawn a general-purpose subagent whose brief is `skills/cartographer/prompts/specialist_base.md`, then the body of `agents/<reviewer>.md`, then the segment metadata from the README's Phase 4. Fix subagents in Phase 7 get `skills/cartographer/prompts/fix_agent.md` plus the backlog item. In a tool without subagents, follow those files yourself, one segment or fix at a time.

## Requirements

Run the scripts as `uv run --no-project --with pathspec --with networkx --with rapidfuzz python scripts/<script>.py`, which brings the optional deps without a global pip; `run_pipeline.sh` does this and falls back to `python3` with a printed note when uv is missing. Without `pathspec` the mapper ignores the project's `.gitignore`, and without the other two the scripts use slower stdlib fallbacks. Graphviz (`brew install graphviz`) renders the dependency, class, pipeline and endpoint graphs to SVG; without it they are written as `.dot` files. The segment overview `segments.svg` comes from the system-design skill's renderer, `~/.agents/skills/system-design/topics/architecture-diagram/scripts/render_diagram.py`. Hot spots need `git` on the PATH and the project inside a work tree. `scripts/install_specialist.py` runs `npx skills add` and only does so with `--execute --allow-skill-install`.
