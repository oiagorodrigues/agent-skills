---
name: 10x-team
description: Runs a project through a simulated 12-role engineering team (CTO, product manager, principal architect, staff engineer, engineering manager, senior engineer, SDE, DBA, security engineer, QA engineer, DevOps engineer, SRE). Brainstorms and gets a design approved first, then moves through strategy, design, planning, implementation, verification and delivery with a hard gate after each phase, writing decisions, ADRs, status and handoff notes to a `.10x/` folder in the project. Use when the user runs /10x-team, asks to build a project or feature end-to-end "like a team", or asks for one role's view (a CTO build-vs-buy call, an architect's design, a DBA query review, an SRE incident review). Run as /10x-team followed by an idea for the full flow, /10x-team followed by a role name and a question for one role, /10x-team init-project to set up `.10x/`, or /10x-team commit to write a commit.
argument-hint: "[init-project | commit | <role> <question> | <idea>]"
---

# 10x-team

Ported from the 10x-Team Claude Code plugin by Md Rizabul (MIT, see `LICENSE`). The agent works as a 12-role engineering team. Every project starts with brainstorming and an approved design, then goes through six phases (strategy, design, planning, implementation, verification, delivery). Each phase ends with a gate that writes the roles' decisions, ADRs, `status.md` and `handoff.md` to `.10x/` in the project, so a role in a later conversation picks up where the last one stopped.

Paths below are relative to `~/.agents/skills/10x-team/`.

## How to use

- `/10x-team init-project` creates `.10x/` in the current project (decisions, status, handoff, `adrs/`) and commits it. Run it once per repo.
- `/10x-team <idea>` runs the full team flow: Discovery when the repo already has code, brainstorming, then phases 1 to 6 with a gate after each.
- `/10x-team <role> <question>` asks one role. It reads the other roles' decisions in `.10x/` first and writes its own after. Roles: `cto`, `product-manager`, `principal-architect`, `staff-engineer`, `engineering-manager`, `senior-engineer`, `sde`, `dba`, `security-engineer`, `qa-engineer`, `devops-engineer`, `sre`.
- `/10x-team commit` reads staged and unstaged changes, proposes a conventional commit message and commits after you confirm.

Typical order: `init-project` once, `/10x-team <idea>` for each new feature, single roles for follow-up questions on that feature, and `commit` after each chunk of work.

```
/10x-team Build me a URL shortener with analytics
/10x-team dba We have a 50M row table and this query is slow, optimize it
```

## Routing

The first word of the arguments ($ARGUMENTS in Claude Code) names the command:

- `init-project` or `commit`: read `commands/<cmd>.md` and follow it. Inside that file, $ARGUMENTS means the words after the command name.
- A role name from the list above: read `skills/<role>/README.md` and follow it, with the rest of the arguments as the question.
- Any other text: read `skills/10x-team/README.md` (the orchestrator) and follow it, with the whole argument text as the project idea.
- No arguments: show the "How to use" list above.

## Without a slash command

When the task fits one of these, read only that file and follow it:

- Building a project or feature end-to-end through every phase: `skills/10x-team/README.md`.
- Build vs buy, technical strategy, resource allocation, risk: `skills/cto/README.md`.
- Feature prioritization, user stories, roadmap, requirements: `skills/product-manager/README.md`.
- System design, patterns, boundaries, decisions that are hard to change later: `skills/principal-architect/README.md`.
- Cross-team patterns, code quality standards, tech debt strategy: `skills/staff-engineer/README.md`.
- Sprint planning, team structure, estimation, process: `skills/engineering-manager/README.md`.
- Implementation guidance, code review, design patterns, hard debugging: `skills/senior-engineer/README.md`.
- Hands-on coding, features, bug fixes, APIs: `skills/sde/README.md`.
- Schema design, query optimization, migrations, indexing: `skills/dba/README.md`.
- Threat modeling, auth design, vulnerability review, hardening: `skills/security-engineer/README.md`.
- Test strategy, test plans, coverage gaps, bug analysis: `skills/qa-engineer/README.md`.
- CI/CD, containers, IaC, deployment strategy: `skills/devops-engineer/README.md`.
- Incidents, monitoring, SLOs, capacity planning: `skills/sre/README.md`.
