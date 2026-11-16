---
name: security-review
description: Local, stack-aware security review of a diff, PR, branch or feature, separate from Claude Code's built-in /security-review command. Use when reviewing a diff or PR for security, doing a security pass before a release, or adding auth, input handling, uploads, secrets, webhooks, payments, LLM tools or dependencies. Covers Django and DRF (company isolation, IDOR, serializers, raw SQL, CSRF, uploads, Celery, admin), Vue and TypeScript SPAs, Node and Nuxt, Java, Rust, Python services, Terraform and AWS IAM, GitHub Actions, Docker, secrets, PII in logs, LLM and agent features, and new or changed dependencies. Proves each finding with an exploit path and reports severity with file:line, without changing code. For a full-repository audit, use security-audit.
---

# Security review

Find vulnerabilities an attacker can reach in the code under review, prove each one, and report it with severity and `file:line`. The review only reports. Change code only when the user asks for fixes after reading the report.

## Scope

- Report on what was asked: a diff, a PR, named files or a feature. Research the whole repo (callers, base classes, settings, middleware, other services) before calling anything a finding.
- A pre-release pass reviews the diff from the last release tag to the release branch, plus every dependency and config change in it.
- A full-repository audit is a different job. Use the `security-audit` skill (Cloudflare's multi-phase workflow). In full audit mode it writes its run files to `~/security-audit-skill/<repo>/run-<N>` unless the user names another directory outside the repo.
- Inside `review-pr`'s security lane, run steps 1, 2 (only when the diff adds an entry point), 3, 4 (only when a manifest or lockfile changed) and 5, and hand findings back in that skill's format.

## Workflow

Copy this checklist into your notes and tick each step:

```
- [ ] 1. Scope: every changed file mapped to a reference
- [ ] 2. Threat model: only when the change adds an entry point
- [ ] 3. Per-stack review: each candidate traced from source to sink
- [ ] 4. Dependency check: only when a manifest or lockfile changed
- [ ] 5. Validation: each candidate proven, moved to "Needs validation" or dropped
- [ ] 6. Report
```

### 1. Scope

List the changed files (`git diff --name-status <base>...HEAD`) and read the reference for each stack:

| Changed files | Read |
|---|---|
| Django or DRF views, serializers, models, permissions, `urls.py`, `tasks.py`, `admin.py`, settings | `references/django-drf.md`, plus `~/.agents/skills/django-expert/references/access-and-performance-review.md` ("Access review") for every endpoint, task or export that touches company data |
| `.vue`, SPA `.ts`/`.js`, Nuxt `server/`, Node services | `references/web-frontend-and-node.md` |
| Python services outside Django (FastAPI, Flask, ETL, Lambdas), Java (`.java`, `pom.xml`, Gradle), Rust (`.rs`) | `references/services-python-java.md` |
| `*.tf`, IAM JSON, `Dockerfile`, compose files, Kubernetes manifests, `.github/workflows/`, `action.yml` | `references/infrastructure-and-ci.md` |
| Prompts, LLM client calls, tool or function definitions, MCP servers and clients, agent loops | `references/llm-and-agents.md` |
| `package.json`, `pnpm-lock.yaml`, `package-lock.json`, `pyproject.toml`, `uv.lock`, `poetry.lock`, `requirements*.txt`, `pom.xml`, Gradle files, `Cargo.toml`, `Cargo.lock` | `references/dependencies.md` |
| Every diff | `references/sinks-and-secrets.md` (grep list for dangerous sinks, secrets and PII in logs) |

Done when every changed file has a reference, or is marked out of scope (tests, docs, generated code) with the reason.

### 2. Threat model for new surfaces

When the change adds an entry point (a new endpoint, webhook, upload, public page, integration, Celery task fed by outside data, LLM tool, CI workflow or IAM role), follow `references/threat-model.md` and put its short table in the report. Skip this step for changes inside surfaces that already exist.

### 3. Per-stack review

For each candidate, trace from the source (where attacker input enters) to the sink (where it does harm), with `file:line` at each hop. Settings, environment variables, constants and admin-only configuration are server-controlled, so they aren't attacker input. Framework protections are real controls (Django and Vue auto-escaping, ORM parameterization, DRF CSRF on session auth): check that they apply before flagging. Done when each candidate has a full trace or a named gap in it.

### 4. Dependency check

When a manifest or lockfile changed, follow `references/dependencies.md`. On a private repo, ask the user before running anything that sends dependency names to a public service (OSV, deps.dev, pip-audit's default PyPI lookup, vendor scanners), because that call discloses the repo's dependency list to a third party. The reference lists which command sends what to whom, and an offline option.

### 5. Validate each finding

A candidate becomes a finding only when you can state all five:

1. Attacker: who and with what starting access (anonymous, any logged-in user, a user of another company, a fork PR author, the author of a document an LLM reads).
2. Entry point: the route, task, message, workflow trigger or file, with `file:line`.
3. Path: each hop to the sink with `file:line`, the control that should stop it, and why it doesn't.
4. Result: what the attacker gets (another company's orders, code execution, a CI token, a user's session).
5. Proof: a reproduction, preferably run. A failing test (two companies, the second one's user requests the first one's object), a request sequence against a local server, or the exact payload.

Run code only locally with dummy data, under these limits: never against staging or production, never with real credentials, no new package installs, no network calls from the code under test. If the proof needs any of those, write the reproduction as steps and move the candidate to "Needs validation" with the exact missing fact ("whether ALB strips `X-Forwarded-Host`").

Drop these, or list them under "Hardening" when a fix is cheap:

- A missing best practice with no reachable impact.
- A missing layer when another layer already blocks the attack.
- Self-impact (a user attacking their own data or session).
- An attack that needs access the attacker would need to have already (repo write access for a workflow, Django admin for an admin-only form).

Done when each candidate is a finding with all five parts, a "Needs validation" item with its settling fact, or dropped.

### 6. Report

Severity follows the proof, never the pattern:

- Critical: unauthenticated code execution, full data-store access, takeover of any account, a live production secret in the repo.
- High: auth bypass, cross-company read or write, stored XSS that other users see, authenticated code execution, secret theft from a fork PR.
- Medium: a real boundary violation with a narrow blast radius or uncommon preconditions (CSRF on a state change, reflected XSS, an open redirect in the login flow).
- Low: disclosure of non-secret internals, or an attack that needs sustained effort for little gain.

A fix must enforce the rule in code (a scoped queryset, a permission class, a sanitizer). A comment such as "callers must check access" is never a fix.

````markdown
## Security review: <PR, branch or feature>

Scope: `<base>...<head>`, 14 files. Stacks: Django/DRF, Vue. Dependency check: ran `pnpm audit --prod` (2 new packages, no advisories).

### Findings

#### [SEC-1] Any buyer can read another company's order (high)
- Location: `orders/views.py:72`
- Attacker: logged-in user of any buyer company
- Path: `orders/urls.py:40` routes to `OrderViewSet.retrieve`; `get_queryset` returns `Order.objects.all()` (`orders/views.py:72`); `permission_classes` is only `IsAuthenticated` (`orders/views.py:65`)
- Result: reads any company's order, line items and prices by ID
- Proof: `test_other_company_cannot_retrieve_order` returns 200 on this branch, 404 expected
- Fix: filter `get_queryset` by the requesting company on the buyer or seller side, and keep the test

### Needs validation
#### [VERIFY-1] <title>
- Location: `file:line`
- Open fact: <what decides it> and how to check it

### Hardening
- <one line each, no reachable impact today>

### Checked and clear
- <what you checked that had no finding>
````

Zero findings is a valid result. Say what you checked.

## Sources

- getsentry/skills `security-review`, `django-access-review` and `gha-security-review` (Apache-2.0, https://github.com/getsentry/skills): attacker- versus server-controlled input, framework-mitigated patterns, the confidence split behind "Needs validation", the GitHub Actions threat model and safe patterns. Sentry's material in turn draws on the OWASP Cheat Sheet Series (CC BY-SA 4.0).
- cloudflare/security-audit-skill (MIT, https://github.com/cloudflare/security-audit-skill): the boundary-and-result gate, "Needs validation" discipline, limits on running target code, severity anchors and the LLM attack classes.
- openai/skills `security-threat-model` (Apache-2.0, https://github.com/openai/skills): the threat-model steps.
- trailofbits/skills `supply-chain-risk-auditor` (CC-BY-SA-4.0, https://github.com/trailofbits/skills): dependency risk criteria. `references/dependencies.md` adapts it and is shared under CC-BY-SA-4.0.
- anthropics/claude-plugins-official `security-guidance` (Apache-2.0, https://github.com/anthropics/claude-plugins-official): the sink list in `references/sinks-and-secrets.md`.
