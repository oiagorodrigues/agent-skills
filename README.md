# ~/.agents

One set of rules and skills for every coding agent on the machine: Claude Code, Codex, Gemini CLI, opencode, GitHub Copilot CLI, Goose, Continue, Cursor and Kiro. `AGENTS.md` holds the global rules, `skills/` holds the skills, and each agent's own config points back here, so a change in this folder reaches all of them.

## Layout

| Path | What it is |
| --- | --- |
| `AGENTS.md` | Global rules for every agent. Each agent's global instructions file imports or links it. |
| `skills/` | The skills, one folder each with a `SKILL.md`. This folder is the source of truth; agents get symlinks to it. |
| `bin/install.sh` | Puts the repo at `~/.agents` and sets up a machine: checks tools, writes the `AGENTS.md` pointers, installs the third-party skills, links the skills, and adds hooks when asked. |
| `bin/fetch-third-party.sh` | Installs the files listed in `third-party.tsv` from upstream at their pinned commits. `install.sh` runs it. |
| `third-party.tsv` | Third-party skill files that aren't committed here, each with its upstream repo, pinned commit and license. |
| `bin/link-skills.sh` | Links every skill into each agent's skills folder and removes broken links. A skill can stay out of an agent with a `.link-skip` file. |
| `bin/setup-rtk.sh` | Installs or repairs the RTK command-output hooks in every agent that supports them. |
| `bin/retro-hook.py` | Claude Code SessionStart and SessionEnd hook that runs the `retro` skill on ended sessions and writes to `retros/`. |
| `factory/` | Parts of a planned `factory` CLI that takes a Jira ticket to a draft PR with one headless agent run per stage. See `factory/README.md`. |
| `retros/` | Generated session retros. Ignored by git. |
| `.skill-lock.json` | Lock file of the `npx skills` CLI for the skills installed from GitHub with it. |

## Quick install

The skills, the hooks and `link-skills.sh` all read `~/.agents`, so the repo always ends up at that path. Clone it anywhere and run its installer, which puts it there:

```sh
git clone https://github.com/<owner>/agent-skills.git /tmp/agents-src
/tmp/agents-src/bin/install.sh --dry-run    # see what it would do
/tmp/agents-src/bin/install.sh              # place ~/.agents, pointers, skill links
~/.agents/bin/install.sh --hooks --rtk
```

Or run it in one line without a clone. The script clones `AGENTS_REPO_URL` to a temp folder, runs from there and deletes the temp folder when it finishes:

```sh
AGENTS_REPO_URL=https://github.com/<owner>/agent-skills.git \
  bash -c "$(curl -fsSL https://raw.githubusercontent.com/<owner>/agent-skills/main/bin/install.sh)"
```

The repo is `agent-skills`; it isn't published yet, so replace `<owner>` with the GitHub owner once it is. Run from a clone, the script takes the URL from the clone's `origin`, and `AGENTS_REPO_URL` overrides it.

What happens to `~/.agents` depends on what is already there:

| `~/.agents` | What the installer does |
| --- | --- |
| Missing | Clones the repo there, with `origin` set to the repo URL. |
| A checkout of this repo | Asks whether to pull, and pulls fast-forward only. |
| A folder that isn't a git checkout, or a checkout of another repo | Lists the files only in the repo, the files only in `~/.agents` and the files in both that differ, then asks `Merge? [y/N]`. |

A merge adds only the missing files and never overwrites or deletes a local file. It then makes `~/.agents` a checkout of the repo by moving a fresh clone's `.git` into it, so `git -C ~/.agents status` shows your local changes as modified or untracked files. A `.git` that was already there moves to `~/.agents.git.bak.<timestamp>`. Answering no changes nothing.

Options:

- `--dry-run` prints every step and changes nothing. When `~/.agents` is missing it stops after saying it would clone, and when it needs a merge it prints the full file summary and stops. Without `--dry-run`, the merge summary shows the first 40 entries of each list.
- `--yes` (or `-y`) answers yes to the pull and merge questions.
- `--install-tools` installs the missing required and recommended tools with Homebrew. Add `--all-tools` for the optional ones.
- `--hooks` adds the retro hooks to `settings.json` in each Claude Code profile (`~/.claude`, `~/.claude-*` and `$CLAUDE_CONFIG_DIR`).
- `--rtk` runs `bin/setup-rtk.sh`.

The script is safe to re-run. It backs up any agent config file it changes to `<file>.bak.<timestamp>`, keeps your own content in instruction files and only appends the pointer, and exits 1 when something needs your attention.

Install and start each agent once before running it, because the script only sets up agents whose config folder exists. Cursor keeps user rules in its settings, so the script prints the line to paste into Settings > Rules > User Rules.

### Private skills and files

Company-only workspace skills stay in `~/.agents` on the machine that has them and are listed in that clone's `.git/info/exclude`, which git never commits, so their names don't reach the repo either. Do the same for a `.link-skip` file that names local profile folders. `link-skills.sh` still links an excluded skill like any other. `.gitignore` keeps out what every machine generates: `/retros/`, `factory/config.json` (the working factory config; `factory/config.example.json` holds the same structure with placeholder values) and `/agents/`. To keep another skill private, add `skills/<name>/` to `.git/info/exclude`.

### Installing with `npx skills`

The skills follow the `skills/<name>/SKILL.md` layout that the skills CLI reads (`.skill-lock.json` records the same `skillPath` shape for skills installed from other repos), so `npx skills add <owner>/agent-skills` can pick skills from this repo. It copies only the skills, though, without `AGENTS.md`, the pointers or the hooks, and many skills read files under `~/.agents`, so use `bin/install.sh` for the full setup.

## How the pointers work

| Agent | File | Pointer |
| --- | --- | --- |
| Claude Code | `~/.claude/CLAUDE.md` (and every other profile folder) | `@~/.agents/AGENTS.md` import |
| Codex | `~/.codex/AGENTS.md` | A sentence telling it to read `~/.agents/AGENTS.md` |
| Gemini CLI | `~/.gemini/GEMINI.md` | `@/Users/<you>/.agents/AGENTS.md` import |
| opencode | `~/.config/opencode/AGENTS.md` | Symlink to `AGENTS.md` |
| Copilot CLI | `~/.copilot/copilot-instructions.md` | Symlink to `AGENTS.md` |
| Goose | `~/.config/goose/.goosehints` | Symlink to `AGENTS.md` |
| Continue | `~/.continue/rules/global-agent-rules.md` | Symlink to `AGENTS.md` |
| Kiro | `~/.kiro/steering/global-agent-rules.md` | Symlink to `AGENTS.md` |
| Cursor | Settings > Rules > User Rules | Pasted by hand |

When one of the symlink files already exists with your own content, the script appends the sentence instead of replacing the file.

## How skill linking works

`bin/link-skills.sh` goes through the skills folder of each agent that exists (`~/.claude/skills`, every `~/.claude-*/skills` profile, `~/.gemini/skills`, `~/.cursor/skills`, `~/.config/opencode/skills`, `~/.copilot/skills`, `~/.config/goose/skills`, `~/.continue/skills`, `~/.kiro/skills`). For each one it deletes broken symlinks, then links every `skills/<name>` that has a `SKILL.md` and isn't there yet. It never touches a real folder or a link that points somewhere else, so a project or plugin skill with the same name wins.

Codex reads `~/.agents/skills` directly and gets no links.

To keep a skill out of an agent, add a `.link-skip` file to the skill folder with one path per line, relative to `$HOME` (for example `.claude-work/skills`). The next run removes that agent's link to it.

After adding, renaming or removing a skill, run `~/.agents/bin/link-skills.sh`. The `create-skill` skill does this for you.

## Skills

### Engineering

- `engineering-practices`: house rules for writing, changing, testing and reviewing code in any stack.
- `python-practices`, `typescript-practices`, `go-practices`, `rust-practices`, `java-practices`: per-language checks and gotchas (frameworks, ORMs, mutation testing), loaded with engineering-practices.
- `debugging`: finds the cause of a bug, crash, flaky test or error spike from a pass/fail loop.
- `hunting-bugs`: looks for unreported bugs in implicit state machines (flags, timestamps, status strings).
- `perf-review`: report-only performance review with measured times and one fix per hot spot.
- `code-simplifier`: simplifies recent code without changing what it does.
- `improve-codebase-architecture`: finds shallow modules and proposes deeper ones.
- `prototype`: throwaway code that answers one design question.
- `why`: explains why code or a rule is the way it is from git history, PRs and tickets.
- `cartographer`: maps and audits a large codebase with graphs, hot spots and a refactor backlog.
- `feature-map`: builds and maintains a feature map of a product (entry points, flow, data, commands).
- `code-modernization`: gated workflow for legacy rewrites and version uplifts.
- `codebase-requirements-analyst`: extracts business rules and requirements from existing code.
- `product-onboarding`: reconstructs a product's requirements to get up to speed on it.

### Review

- `review-pr`: full PR review flow, review comments, babysitting a PR and the local pre-PR review.
- `caveman-review`: one-line review comments for chat summaries.
- `product-lens`: reads a change as a PM, CTO and GTM team would.
- `web-design-guidelines`: checks UI code against the Web Interface Guidelines.

### Security

- `security-review`: stack-aware security review of a diff, PR or feature.
- `security-audit`: full-repository vulnerability review.
- `auth0`: adds Auth0 authentication and configures Auth0 features.
- `reverse-engineer-anything`: reverse engineers binaries, apps, firmware and web targets with REA.

### Backend and data

- `backend-design`: designs and audits endpoints, workers, schemas, migrations and queries.
- `system-design`: backend and distributed-system design from requirements and numbers.
- `django-expert`: Django models, views, serializers, ORM and migrations.
- `async-python-patterns`: asyncio and async/await patterns.
- `postgres-best-practices`: PostgreSQL rules for schema, types, indexes and queries (RDS and Aurora too).
- `data-pipeline-builder`: reviews and writes dbt models and Airflow DAGs.

### Frontend

- `frontend-design`: production-grade web UI with a distinct look.
- `design-directions`: 2 or 3 responsive visual directions for a product.
- `vue-best-practices`, `vue-pinia-best-practices`, `vue-router-best-practices`, `vue-testing-best-practices`: Vue 3, Pinia, Vue Router and Vue testing.
- `vitest`: Vitest tests, mocks and coverage.
- `pnpm`: pnpm commands, workspaces, catalogs and patches.
- `i18n`: keeps every user-facing string translated in every locale.
- `modern-web-guidance`: Chrome's modern web platform guides and Manifest V3 extensions.
- `site-seo-aeo-audit`: SEO and AI-answer visibility audit of a site (written in Portuguese).
- `agent-browser`: drives Chrome from the shell with the agent-browser CLI.

### AI and agents

- `ai-engineering`: LLM features and agents built around evals (error analysis, binary checks, validated judges), output validation and call logging.
- `ai-integration-architect`: designs and scaffolds AI integrations (MCP, RAG, event-driven, agentic).
- `agent-guardrails`: what an agent may do alone and where a person must approve.
- `harness-architect`: builds or audits a project's Claude Code harness.
- `cutting-agent-costs`: cuts tokens and cost of agent runs and pipelines.
- `autoresearch`: Karpathy-style experiment loops on a measurable metric.
- `typesafe-ai`: TypeSafe AI primitives for typed judgments in code.
- `handoff`: compacts a session into a document another agent can act on.
- `watch-video`: frame and transcript pipeline for the `/watch-video` command.

### Writing

- `plain-writing`: checklist of AI-writing tells, plus the author's own voice.
- `reply-with-standing`: drafts and checks messages sent to people on the user's behalf.
- `business-first-pitch`: turns a technical idea into a business case with ROI.
- `explain`: re-explains the last message in plain words.
- `interactive-docs`: self-contained interactive HTML docs for a project.
- `caveman`, `caveman-commit`, `caveman-compress`, `caveman-help`: terse chat replies, terse commit messages and compressed memory files.

### Workflow, Jira and PRs

- `brainstorming`: questions a new idea and gets a design approved before building.
- `create-pr`: writes and edits PR descriptions in the house format.
- `git-commit`: conventional commit messages with staging.
- `jira-workflow`: tickets, epics, links and status changes through the Atlassian MCP.
- `triage`: answers a customer, product or GTM question from a ticket or thread.
- `to-questionnaire`: turns an open decision into a questionnaire for one person.
- `business-requirements-analyst`: requirements gathering for a new project or idea.
- `10x-team`: runs a project through a simulated 12-role engineering team.

### Infra and cloud

- `aws`: AWS CLI, SAM and CDK work, read-only by default, plus a local emulator topic.
- `docker`: Dockerfiles, Compose, Docker sandboxes and safe Docker commands.
- `prod-evidence`: proves production claims with Datadog, Sentry and warehouse data.
- `self-improve`: turns a project's Sentry and Datadog telemetry into a ranked fix list.
- `vercel-troubleshooter`: diagnoses a Vercel site that is down or unreachable.

### Meta

- `create-skill`: creates, edits and removes skills here and links them.
- `review-skills`: reviews skills for cost, security and trigger quality.
- `find-skills`: finds and installs skills from the open ecosystem.
- `agent-instructions-optimizer`: slims down oversized CLAUDE.md and AGENTS.md files.
- `correct`: turns a repeated agent mistake into a rule that enforces itself.
- `retro`: reviews an agent session and proposes fixes to rules and skills.

## Before pushing this repo

Run `gitleaks git ~/.agents --no-banner --redact` and check that it reports no leaks. A finding confirmed as a false positive (a placeholder in vendored docs, a public key fingerprint) goes in the allowlist in `.gitleaks.toml`, by path or pattern, because a `.gitleaksignore` fingerprint includes the commit SHA and stops matching after a history rewrite. `review-skills` (`check_skill.py --sensitive`) catches the values gitleaks doesn't look for: account IDs, emails, channel IDs and internal hostnames.

## Tools to install

Required tools are needed by `install.sh` and the hooks. Recommended tools are used by many skills. Optional tools are used by one or two skills, which say so when the tool is missing. `bin/install.sh` checks all of them.

| Tool | Used by | Level | Install |
| --- | --- | --- | --- |
| git | everything | required | `xcode-select --install` or `brew install git` |
| python3 | `retro-hook.py`, `install.sh`, skill scripts | required | `brew install python` |
| rtk | `AGENTS.md` command-output rule, `setup-rtk.sh`, cutting-agent-costs | recommended | `brew install rtk` |
| gh | create-pr, review-pr, triage, why, jira-workflow, find-skills | recommended | `brew install gh` |
| jq | `setup-rtk.sh`, aws, auth0, security-review, vercel-troubleshooter | recommended | `brew install jq` |
| uv | cartographer, review-skills, security-review, aws, autoresearch | recommended | `brew install uv` |
| node | auth0, harness-architect, find-skills, npx-based steps | recommended | `brew install node` |
| gitleaks | security-review, engineering-practices done checks, scanning this repo before a push | recommended | `brew install gitleaks`, or without installing: `docker run --rm -v "$PWD:/repo:ro" ghcr.io/gitleaks/gitleaks:v8.30.1 git /repo --redact` |
| claude | `retro-hook.py` worker, review-skills, create-skill evals | optional | https://docs.claude.com/en/docs/claude-code |
| pnpm | pnpm, engineering-practices, security-review | optional | `brew install pnpm` |
| graphviz (`dot`) | cartographer diagrams | optional | `brew install graphviz` |
| agent-browser | agent-browser | optional | `brew install agent-browser` (the skill pins a version with `npm i -g agent-browser@<version>`) |
| osv-scanner | security-review | optional | `brew install osv-scanner` |
| zizmor | security-review | optional | `brew install zizmor` or `uvx zizmor` |
| pip-audit | security-review, code-modernization | optional | none, runs with `uvx pip-audit` |
| codex | review-pr, cutting-agent-costs | optional | `brew install --cask codex` |
| aws | aws, prod-evidence, security-review | optional | `brew install awscli` |
| sam | aws | optional | `brew install aws-sam-cli` |
| cdk | aws | optional | `brew install aws-cdk` |
| docker | docker, debugging, backend-design | optional | `brew install --cask docker-desktop` |
| yt-dlp, ffmpeg | watch-video | optional | `brew install yt-dlp ffmpeg` |
| auth0 | auth0 | optional | `brew tap auth0/auth0-cli && brew install auth0` |
| Stryker | typescript-practices (mutation testing, JS and TS) | optional, one-off, no install | `pnpm dlx` command in typescript-practices |
| mutmut | python-practices (mutation testing, Python) | optional, one-off, no install | `uv run --with mutmut mutmut run`, or pip from a wheel cache in a one-off container (python-practices) |
| Atlassian MCP | jira-workflow, triage, brag, why, reply-with-standing | optional | claude.ai connector or `claude mcp add` |
| Slack MCP | triage, brag, why, reply-with-standing, self-improve | optional | claude.ai connector |
| Sentry MCP | prod-evidence, self-improve, triage | optional | Sentry plugin or claude.ai connector |
| Datadog MCP | prod-evidence, self-improve, hunting-bugs | optional | Datadog plugin |
| Sigma MCP | prod-evidence (warehouse queries), why, hunting-bugs | optional | claude.ai connector |
| Notion MCP | brag | optional | claude.ai connector |

## Third-party skills

These skills are copies or adaptations of other people's work. Each keeps its license file where the source shipped one.

The ones used as upstream ships them aren't committed here. `third-party.tsv` lists each of their paths with the upstream git URL, the pinned commit, the path inside that repo and the license, and `.gitignore` keeps those paths out of the repo. `bin/install.sh` installs them by running `bin/fetch-third-party.sh`, which you can also run alone with `--dry-run` or `--yes`. For each line it clones the repo without file contents (`git clone --filter=blob:none --no-checkout`), checks that the pinned commit resolves to the same SHA, fetches only the blobs under that path and copies the path into place. It never runs anything from the download. It records each install in `.third-party-state/` and skips a path that still matches its record. When a path's files differ from both its record and the pinned commit, it lists the files that differ and leaves the path alone unless you pass `--yes`.

Put local rules for these skills in `AGENTS.md`, because an edited copy blocks the next install. To move to a newer upstream version, change the commit in `third-party.tsv` and re-run `bin/fetch-third-party.sh`. The built CLI files of modern-web-guidance (`modern-web.mjs`, `search.mjs`, the guide index and the search vectors) ship only in the npm package, so they stay committed in `vendor/`, while its guides and MiniLM model come from GitHub.

| Skill | Source | License |
| --- | --- | --- |
| 10x-team | 10x-Team Claude Code plugin by Md Rizabul | MIT (`LICENSE`) |
| agent-guardrails | agent-guardrails plugin by Sergey Skripko | MIT (`LICENSE`) |
| agent-instructions-optimizer | claude-md-optimizer plugin v2.2.0 by Will Smith | MIT per the plugin manifest, no license file |
| ai-integration-architect | ai-integration-architect plugin by Pedro Barros | MIT per the plugin manifest, no license file |
| auth0 | Auth0 agent skills | Apache-2.0 (frontmatter, no license file) |
| autoresearch | autoresearch plugin by PJ Hoberman | MIT per the plugin manifest, no license file |
| aws | AWS aws-core and aws-serverless plugins and aws/agent-toolkit-for-aws | Apache-2.0 (`LICENSE`, `NOTICE`) |
| backend-design | sheitabrk and contributors | MIT (`LICENSE`) |
| brainstorming | obra/superpowers by Jesse Vincent, via claude-code-templates | MIT (`LICENSE`) |
| business-requirements-analyst | github.com/gmdaos | MIT (frontmatter) |
| cartographer | Roei Michael | MIT (`LICENSE`) |
| caveman, caveman-commit, caveman-compress, caveman-help, caveman-review | https://github.com/JuliusBrussee/caveman, installed from `third-party.tsv` | MIT (upstream `LICENSE`) |
| code-modernization | Anthropic code-modernization plugin | Apache-2.0 (`LICENSE`) |
| code-simplifier | Anthropic code-simplifier agent | Apache-2.0 (`LICENSE`) |
| correct, why | Lauren Tan's pstack, https://github.com/cursor/plugins/tree/main/pstack | MIT |
| create-skill (`skill-creator/`) | Anthropic skill-creator | Apache-2.0 (`skill-creator/LICENSE.txt`) |
| data-pipeline-builder | Data Pipeline Builder plugin by Stefan Petrovici | MIT (`LICENSE`) |
| debugging, handoff, improve-codebase-architecture, prototype, to-questionnaire | Matt Pocock, https://github.com/mattpocock/skills | MIT |
| docker | Docker docker-skills plugin | Apache-2.0 (`LICENSE`) |
| explain, find-skills, i18n | zizi-skills by Zia Saidi, https://github.com/ziazon/zizi-skills | MIT (`LICENSE`, `THIRD_PARTY_NOTICES.md`) |
| frontend-design | Anthropic | Apache-2.0 (`LICENSE.txt`) |
| git-commit | not recorded | MIT (frontmatter) |
| harness-architect | ClaudeCode-Harness-Setup-Assistant, https://github.com/leee880619-commits/ClaudeCode-Harness-Setup-Assistant | Apache-2.0 (`LICENSE`) |
| interactive-docs | interactive-docs plugin by Bhargava Ganti | MIT (`LICENSE`) |
| review-pr, retro, plain-writing | adapted in part from pstack (Lauren Tan), Matt Pocock's skills and blader/humanizer | MIT |
| plain-writing | Wikipedia "Signs of AI writing" | CC BY-SA 4.0 for any text taken from Wikipedia |
| modern-web-guidance | Google Chrome modern-web-guidance plugin 0.0.197, partly installed from `third-party.tsv` | Apache-2.0 (`LICENSE`, `vendor/.../THIRD_PARTY_NOTICES`) |
| pnpm, vitest | Anthony Fu, https://github.com/antfu/skills | see upstream |
| review-skills (`scripts/scan_skill.py`) | Sentry skill-scanner, https://github.com/getsentry/skills | Apache-2.0 (`NOTICE`, `scripts/LICENSE-scan_skill`) |
| security-audit | Cloudflare | MIT (`LICENSE`) |
| system-design | system-design-skills plugin by Proyecto 26 | MIT (`LICENSE`) |
| typesafe-ai | https://github.com/typesafe-ai/skills (in `.skill-lock.json`) | MIT (`LICENSE`) |
| vue-best-practices, vue-pinia-best-practices, vue-router-best-practices, vue-testing-best-practices | github.com/vuejs-ai (hyf0, SerKo) | MIT (`LICENSE.md`) |
| watch-video | Ketan; scripts from https://github.com/bradautomates/claude-video | MIT (`LICENSE`, `THIRD_PARTY_NOTICES.md`) |
| web-design-guidelines | Vercel | not recorded |

The source of async-python-patterns, django-expert, postgres-best-practices, reverse-engineer-anything, site-seo-aeo-audit, vercel-troubleshooter, codebase-requirements-analyst, product-onboarding and agent-browser isn't recorded in their folders.
