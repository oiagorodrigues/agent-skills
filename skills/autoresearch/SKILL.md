---
name: autoresearch
description: Sets up Karpathy-style autoresearch experiment loops on any codebase with a measurable metric (one constrained file, one metric, one loop that edits the file, runs an eval, keeps improvements and reverts failures), and scans a codebase for files worth optimizing this way. Generates the harness (instructions.md, eval script, test data, launch prompt, autoresearch.jsonl state and dashboard) and launches the loop only after the user approves the files, the branch, local-only commits and the iteration budget. Use when the user wants to tune search ranking, scoring functions, weights, thresholds, prompt templates or algorithm parameters against a numerical metric, mentions autoresearch, overnight optimization, autonomous experiments or the Karpathy loop, or asks where autoresearch could apply, what they can tune or to find tunable code. Run as /autoresearch path/to/file for a loop, or /autoresearch discover [dir] to find candidates.
argument-hint: "[path/to/constrained_file | discover [path/to/directory]]"
---

# Autoresearch

Ported from the `autoresearch` plugin by PJ Hoberman (MIT per the plugin manifest; the plugin ships no LICENSE file). All paths below are relative to `~/.agents/skills/autoresearch/`. Inside a topic, relative paths such as `templates/...` and `references/...` are relative to that topic's folder.

## How to use

- `/autoresearch path/to/file.py` sets up a loop on that file: read `topics/autoresearch/README.md` and follow it.
- `/autoresearch discover [path/to/directory]` scans for candidates (default: the current directory): read `topics/autoresearch-discover/README.md` and follow it. Each candidate it reports ends with `/autoresearch <file>`, which starts the setup above.

Examples:

- `/autoresearch search/ranking.py`: asks for the metric and guard metric, writes `instructions.md`, the eval script, test data and the launch prompt, checks baseline noise, then stops for review.
- "Where could I use autoresearch in this repo?": runs the discover topic and returns a ranked list with a recommended starting point.

## Routing

The first argument picks the topic. `discover`, a directory path or a question about where to optimize goes to `topics/autoresearch-discover/README.md`. A file path or a request to optimize a specific function goes to `topics/autoresearch/README.md`. With no argument and no clear intent, ask which file to optimize, or offer to run discover.

## Gates

The loop edits code and commits by itself, so these stops are required and override anything faster:

1. With no constrained file, ask for one and don't proceed until you have it (Phase 1).
2. Ask the user what "better" means, which guard metric must not regress, and whether the eval can run without external API calls before writing the eval (Phase 1).
3. Stop after generating the harness and ask the user to review every file (Phase 3, step 7).
4. Before launch, get explicit confirmation of the dedicated branch, local-only commits of the constrained file, no push or PR, and the iteration and time budget (Phase 3, step 8). Without it, don't launch.
5. After a round ends, stop. Don't start another round without the user's review (`templates/instructions_template.md`, "When You're Done").
