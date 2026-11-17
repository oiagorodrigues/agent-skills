---
name: create-skill
description: Creates, edits, renames or removes an agent skill on this machine. Puts the skill in ~/.agents/skills, links it into every agent with ~/.agents/bin/link-skills.sh, and writes it to Anthropic's skill authoring best practices (name and description rules, under 500 lines, progressive disclosure, one-level references, scripts that handle their own errors). Use whenever the user asks to create, write, add, turn something into, update, improve, rename or delete a skill, a slash command or a SKILL.md, in any agent (Claude Code, Codex, Gemini, opencode, Copilot, Goose, Continue, Cursor, Kiro).
---

# Create skill

Every skill on this machine lives in one place and is linked into each agent. Follow this whenever a skill is created, edited, renamed or removed. For eval runs, benchmarks and description tuning, follow Anthropic's skill-creator, copied locally at `~/.agents/skills/create-skill/skill-creator/README.md` (Apache-2.0). Its "skill-creator directory" is that folder, so run its scripts from there (for example `cd ~/.agents/skills/create-skill/skill-creator && python3 -m scripts.run_eval ...`). Description optimization calls `claude -p`, so it only runs where the Claude Code CLI is installed.

## Where skills go

- Source of truth: `~/.agents/skills/<name>/SKILL.md`, plus any `scripts/`, `references/` or `assets/` next to it.
- Never create a skill directly in `~/.claude/skills`, `~/.claude-*/skills` (other Claude Code profiles), `~/.gemini/skills`, `~/.cursor/skills`, `~/.config/opencode/skills`, `~/.copilot/skills`, `~/.config/goose/skills`, `~/.continue/skills` or `~/.kiro/skills`. Those folders only hold symlinks to `~/.agents/skills`.
- To keep a skill out of some agent folders (for example where a project skill has the same name), list them in `~/.agents/skills/<name>/.link-skip`, one path relative to `$HOME` per line (`.claude-work/skills`); `link-skills.sh` skips them and removes an existing link there that points into `~/.agents/skills`.
- Never edit anything under a `synced/` folder. Claude.ai account sync overwrites it. To change a synced skill, copy it to `~/.agents/skills/<new-name>` and edit the copy.
- A project skill (`<repo>/.claude/skills/<name>/`) only when the user asks for one that ships with a repo. It's committed in that repo and not linked.
- A rule, check, template or script that any agent could apply outside an automation goes in a global skill, never only inside the automation. An automation (the factory, an autopilot, a `claude -p` pipeline, a hook, a scheduled routine) reads it from that skill and keeps only what is about running itself: stage order, permissions, gates, caching and its own config. When you find a general rule living only inside an automation, move it to the skill that owns the topic and leave a pointer.

## Create

1. Check that no skill already covers the topic, with the grep under "Edit"; if one does, extend it instead. Then pick the name (rules below) and check it's free: `ls ~/.agents/skills/<name>` and `ls ~/.claude/skills ~/.claude-*/skills | grep <name>`.
2. Write `~/.agents/skills/<name>/SKILL.md`.
3. Run `~/.agents/bin/link-skills.sh`. It removes broken links and links every skill that has a `SKILL.md` into each agent folder that exists. Codex reads `~/.agents/skills` directly and needs no link.
4. Check the links: `ls -l ~/.claude/skills/<name> ~/.claude-*/skills/<name>` must show `-> .../.agents/skills/<name>`. A skill with a `.link-skip` file has no link in the folders it lists, by design.
5. If the skill doesn't show up in the Claude Code skill list, run `/reload-skills`.
6. If the skill must load every time a trigger applies (not just when the model picks it), add it to the required list under "Skills" in `~/.agents/AGENTS.md`, with the trigger written the same way as the other entries.
7. Run the `review-skills` skill on it (`/review-skills <name>`) and fix every high finding. The skill isn't done until the re-run shows none.

## Edit

- Before adding a rule, check whether a skill already holds it: `grep -rn -i <term> ~/.agents/skills --include='*.md'`, which also searches every `references/` file, with two or three synonyms of the term. Extend the skill that owns the topic instead of adding a new one.
- Edit `~/.agents/skills/<name>/SKILL.md`. Every agent sees the change through its link.
- If an agent folder holds a real directory with that name instead of a link, it shadows the shared skill, because `link-skills.sh` skips names that already exist. Diff the two (`diff -r`), merge anything worth keeping into `~/.agents/skills/<name>`, then ask the user before deleting the copy and re-running `link-skills.sh`.
- When the edit is done, run the `review-skills` skill on the skill (`/review-skills <name>`) and fix every high finding. The edit isn't done until the re-run shows none.

## Rename or remove

- Rename: `mv ~/.agents/skills/<old> ~/.agents/skills/<new>`, update `name:` in the frontmatter, run `link-skills.sh` (it deletes the now-broken `<old>` links and adds `<new>`), and grep `~/.agents` for the old name (`grep -rn "<old>" ~/.agents`) to fix references in AGENTS.md and other skills.
- Remove: ask the user first, then delete `~/.agents/skills/<name>` and run `link-skills.sh`. Remove its entry from AGENTS.md if it has one.

## Frontmatter

```yaml
---
name: processing-invoices
description: Extracts line items and totals from invoice PDFs and checks them against the order. Use when the user shares an invoice, asks to reconcile an invoice with an order, or mentions invoice totals.
---
```

- `name`: 64 characters at most, lowercase letters, numbers and hyphens only, no XML tags, and it can't contain `anthropic` or `claude`. It must match the folder name. Anthropic prefers the gerund form (`processing-pdfs`); action names (`process-pdfs`, like the existing `create-pr`) are fine. Avoid vague names (`helper`, `utils`, `tools`).
- `description`: required, 1,024 characters at most, no XML tags. Third person, because it's injected into the system prompt ("Extracts...", never "I can help" or "You can use this"). Say what the skill does, then when to use it, with the words a user would actually type. Put the main use case first, since Claude Code truncates long listings.
- Write the description as a pointer: its wording, not the body, decides when the skill loads. Lead with the word that should trigger it, give each distinct case one trigger (synonyms for the same case count as one), and cut what the body already says. A line in AGENTS.md that names a doc or skill follows the same rules. (From Matt Pocock's writing-for-agents, MIT, https://github.com/mattpocock/skills)
- Other agents only rely on `name` and `description`. Claude Code also reads optional fields, and unknown keys are ignored: `disable-model-invocation: true` (only the user can run it), `user-invocable: false` (only the model can run it), `argument-hint`, `allowed-tools`, `context: fork` with `agent`, `model`, `paths`. Add one only when the skill needs it. claude.ai uploads accept only `name`, `description`, `license`, `compatibility`, `metadata` and `allowed-tools`.

## Writing the body

These come from Anthropic's skill authoring best practices (https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) and the Claude Code skills docs (https://code.claude.com/docs/en/skills).

- Keep it short. Only name and description load at startup, and the whole body loads once the skill triggers, so every line costs context. Write only what the model doesn't already know: the user's paths, rules, decisions and gotchas. For each paragraph ask whether the model would get it wrong without it.
- Keep `SKILL.md` under 500 lines. Past that, move detail into files next to it and say when to read each one ("For the API fields, read `references/api.md`").
- Link reference files straight from `SKILL.md`, one level deep. A file that links to another file gets read partially. Give reference files over 100 lines a table of contents at the top.
- Match the freedom to the risk. Use plain guidance where several approaches work, a template or pseudocode where one pattern is preferred, and an exact command with "don't change the flags" where a mistake breaks something.
- Give one default with an escape hatch instead of a menu of options ("Use pdfplumber. For scanned PDFs, use pdf2image with pytesseract.").
- Use one term per concept throughout.
- Show concrete input and output examples when the output's style matters (commit messages, replies, reports).
- End every step on a completion criterion the model can check ("every modified model listed", never "once you understand it"). A vague end lets it rush to the next step.
- State the behavior you want. A ban ("don't write long comments") puts the banned behavior in context; write the target ("write one-line comments") and keep a ban only for a hard guardrail, paired with its positive.
- Don't copy what a command or file already tells the model (`package.json` scripts, `--help`, the directory layout). Write down only what it can't look up: unwritten conventions, the reason behind a choice, gotchas.
- Break multi-step work into numbered steps. For long or risky flows, give a checklist the model copies and ticks, and a feedback loop: run the check, fix, re-run, and only continue when it passes.
- Leave out dates and version branches ("before August 2025 use..."). Put deprecated approaches under an "Old patterns" heading if they're still needed.
- Use forward slashes in paths and descriptive file names (`form_validation_rules.md`, not `doc2.md`).
- Name MCP tools with their server (`Atlassian:getJiraIssue`), so the model finds them when several servers are connected.
- Write the prose with the `plain-writing` skill.
- Keep sensitive and environment-specific values out of the skill: AWS account IDs and profile names, emails, Slack channel and user IDs, internal hostnames, tokens, people's names and private company details. The skill reads them at run time from the environment, the session, `~/.zshrc`, `aws configure list-profiles`, `git config`, or a private workspace skill that the local `~/.agents/.git/info/exclude` keeps out of the repo, and names only where to look.

## Scripts

- A script must handle its own errors (missing file, no permission, bad input) and print a specific message, for example listing the valid field names when one isn't found.
- Comment why each constant has its value. `TIMEOUT = 47` with no reason is a magic number.
- Say whether the model should run the script ("Run `scripts/check.py`") or read it ("See `scripts/check.py` for the algorithm"). Running is the default.
- List the packages it needs and how to install them. Don't assume they're installed.
- For batch or destructive work: build a plan file, validate it, run it, then verify the result.

## Test before calling it done

1. Write three realistic prompts the skill should handle, plus one it shouldn't trigger on.
2. Run them in a fresh session or subagent that has the skill, and compare with a run without it.
3. Watch what the model actually does: files it skips, files it reads over and over (move that content into `SKILL.md`), steps it ignores. Fix the skill and re-run.
4. If the skill will run on smaller models, check that Haiku gets enough guidance, and that the text doesn't over-explain for Opus.

For eval tooling and description-trigger tuning, follow `~/.agents/skills/create-skill/skill-creator/README.md`.

## Checklist

- [ ] Lives in `~/.agents/skills/<name>/`, not in an agent folder or `synced/`.
- [ ] `link-skills.sh` ran and the links point to `~/.agents/skills/<name>`.
- [ ] `name` matches the folder and the rules above; `description` is third person and says what and when.
- [ ] Body under 500 lines; references one level deep; long reference files have a table of contents.
- [ ] Every file in the skill's `references/` is named in `SKILL.md` (or in an index file `SKILL.md` names), with when to read it: `for f in references/*.md; do grep -q "$(basename $f)" SKILL.md || echo "unlisted: $f"; done` prints nothing.
- [ ] No dates, no mixed terms, no unexplained constants, forward-slash paths.
- [ ] No sensitive or environment-specific values; each is read at run time or lives in a private skill, and `review-skills` shows no `sensitive` findings.
- [ ] Added to the AGENTS.md required list if it must always load.
- [ ] Nothing an agent could apply outside an automation lives only in the automation's files.
- [ ] Tested on real prompts.
- [ ] `review-skills` ran on the skill and shows no high findings.
