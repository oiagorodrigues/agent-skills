---
name: feature-map
description: Builds and maintains a feature map of a product, so agents stop guessing how it works. Each feature lists its entry points (routes, pages, CLI commands, jobs), the steps of its flow, the data it reads and writes, the systems it calls, and the commands to run and inspect it, and every fact links to the lines of code it came from, pinned to the commit where it was last checked. Use when the user asks for a feature map or a map of the product, asks how a feature works end to end, wants agents onboarded to a repo, or asks to check or update an existing map.
---

# Feature map

A feature map is a list of facts grouped by feature. Each fact is one claim plus the lines of code or config it came from, pinned to the commit where someone last confirmed it. Agents read it to find where a feature starts, what it touches and how to run it, and check any claim by opening its link.

`map.yaml` is the only source. `scripts/feature_map.py` (paths here are relative to `~/.agents/skills/feature-map/`) checks each fact against the code, stamps facts you confirmed, and renders `README.md` plus an optional architecture diagram. Run it as `uv run --no-project --with pyyaml python ~/.agents/skills/feature-map/scripts/feature_map.py <check|stamp|render>`; `--help` lists the flags.

The map stays at the level of features and flows. File structure, imports, classes, hot spots and the glossary belong to the `cartographer` skill; this skill reads its output and never rebuilds it.

## map.yaml

Default location `docs/feature-map/map.yaml` in the repo; `--map` points elsewhere.

```yaml
title: Shop feature map
intro: How the shop works, feature by feature.   # optional; shown at the top of README.md
repo: https://github.com/acme/shop      # optional; turns links into commit permalinks
sources:                                # where this project keeps product knowledge
  - docs: docs/product/
  - github-issues: acme/shop
diagram:                                # optional render_diagram.py spec (nodes, groups, edges)
  nodes: [{id: buyers, label: Buyers, kind: people, row: 0, public: true}, {id: api, label: Shop API, kind: compute, row: 1}]
  edges: [{from: buyers, to: api, label: https, public: true}]
features:
  - id: checkout
    name: Checkout
    summary: A buyer pays for a cart and gets an order.
    docs: [https://github.com/acme/shop/issues/412]
    facts:
      - id: checkout-route
        kind: entry                     # entry | step | data | call | control | command
        claim: POST /api/checkout starts checkout.
        source: {path: shop/api/routes.py, anchor: "def checkout(", lines: 14}
      - id: checkout-e2e
        kind: command
        command: make e2e-checkout
        claim: Runs checkout end to end against the local stack.
        source: {path: Makefile, anchor: "e2e-checkout:", lines: 3}
      - id: refund-window
        kind: control
        claim: Refunds are allowed for 30 days.
        url: https://notion.so/acme/refund-policy   # a fact no repo holds; never checked
```

`stamp` writes each fact's `verified` commit; never type it by hand. It also rewrites the file, so keep notes in `intro` or `summary`, not in YAML comments.

## Build a map

1. **Read what already exists.** Look for `.cartographer/` in the repo, then for the readonly cache with `grep -l "<absolute repo path>" ~/.cartographer/*/_project.txt` (the matching file's folder holds the output). From it take `endpoints.md` and `endpoints.json` (entry points), `pipelines.json` (what each entry point calls), `GLOSSARY.md` or `glossary.md` (feature and domain names) and `hotspots.md` (features that change most, so check them first). With no output and more than about 30 source files, run `/cartographer map <repo> --readonly` first (about 30 seconds, no subagents). Done when you have a list of entry points with file:line.
2. **List the features** as a user or operator would name them, from the product sources (next section) and the entry points. Every entry point belongs to one feature or to a "not mapped" list you show the user. Agree on the list with the user before writing facts. Done when each feature has an id, a name and a one-sentence summary.
3. **Write the facts for each feature** by the fact rules below: its entry points, the steps of its flow in the order a request travels, the data it reads and writes, the systems it calls, its controls (sign-in, permissions, validation, webhook checks), and at least one `command` fact that runs or inspects it (a test target, a CLI subcommand, a dev-server URL, a log query). Read the code for each fact, then `stamp <id>`. Done when `check` prints no `unverified` line.
4. **Draw the diagram** only when the product has three or more components that talk over a network. Write the `diagram` block by the rules in `~/.agents/skills/system-design/topics/architecture-diagram/README.md` (spec format, kinds and colors, layout), then `render`. Fix every warning it prints and look at `feature-map.svg`. Done when render prints no warning.
5. **Have an agent that did not write the facts open every link** and check each claim against the lines it shows. Rewrite, split or delete each flagged fact, then stamp again. Done when that agent flags nothing.
6. **Point readers at it**: one line in the repo's `AGENTS.md` or `CLAUDE.md` saying where the map is and to run `check` before trusting a fact. If the team keeps a wiki, add a page that only links the README; a copy of the facts there would go stale with nothing to check it.

## Product sources

Record in `sources` what the project uses, so the next run searches the same places. Search each source for every feature name, then read the code; where a source and the code disagree, the code wins and the fact says what the code does.

| Source | How to search |
|---|---|
| docs folder | `grep -ril "<feature>" <folder>` |
| GitHub issues and PRs | `gh issue list -R <owner/repo> --search "<feature>" --state all`, `gh pr list -R <owner/repo> --search "<feature>" --state merged` |
| Notion | `Notion:notion-search` with the feature name |
| Confluence | `Atlassian:searchConfluenceUsingCql` with `text ~ "<feature>" AND type = page`, scoped to the spaces listed in `sources` |
| Jira | `Atlassian:searchJiraIssuesUsingJql` with `text ~ "<feature>"`, scoped to the project keys listed in `sources` |

When a source isn't connected, say which one in your report and go on with the rest. A setting that lives only in a dashboard (an identity provider option, a cloud console change) becomes a `url` fact pointing at the page or ticket that records it.

## Fact rules

- **One fact, one link.** A claim the linked lines cannot show gets reworded or split. "All", "every" and "only" can never be shown by one span, so don't claim them.
- **Anchor on a line that names the thing**: a `def`, a `class`, a route path, a Terraform `resource`, a Makefile target, a setting name. It must match exactly one line in the file and hold no version number, or every bump breaks it.
- **`lines` must cover every value the claim states**, or a change to that value goes unflagged.
- **A fact lives in one feature.** When two features share a step, put the fact in the feature that owns the code and name it from the other feature's summary.
- **Put known gaps in the tracker.** The map says what the code does today.

## Keep it true

- `check` exits 1 and prints each fact that is `changed`, `missing`, `ambiguous` or `unverified`. For each: read the code and `git diff <verified>..HEAD -- <path>`; if the claim holds, `stamp` it; if not, rewrite the claim (and `lines`), then stamp; if the thing is gone, delete the fact; for `missing` or `ambiguous`, fix `source.path` or `source.anchor` first. Stamp only facts whose code you read. Then `render`.
- For CI, copy `scripts/feature_map.py` into the map's folder (CI can't read `~/.agents`) and run `check` on each pull request, plus `render` followed by `git diff --exit-code docs/feature-map/` so a stale README fails too.
- `check` sees only what is in the repo. A `url` fact, or a setting someone changes by hand in a console, is never checked; review those when the page they cite changes.
