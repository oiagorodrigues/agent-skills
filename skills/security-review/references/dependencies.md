# Dependency check

Risk criteria and reporting rules adapted from trailofbits/skills `supply-chain-risk-auditor` (CC-BY-SA-4.0, https://github.com/trailofbits/skills). Because of that license, this file is shared under CC-BY-SA-4.0 (https://creativecommons.org/licenses/by-sa/4.0/). pnpm settings come from pnpm's supply-chain security docs; tool flags were checked against each tool's own docs.

## Contents

- What leaves the machine
- 1. Read the lockfile diff
- 2. Vet each new or changed package
- 3. Advisory sweep
- 4. Pinning and install policy
- 5. Report

## What leaves the machine

| Command | Sends | To |
|---|---|---|
| `pnpm audit`, `npm audit` | Dependency tree with versions | The configured npm registry, which already serves those packages |
| `npm audit signatures`, `npm view` | Package names and versions | The npm registry |
| `uvx pip-audit` (default `-s pypi`) | Every package name and version | PyPI's JSON API |
| `uvx pip-audit -s osv`, `osv-scanner` online | Every package name and version | api.osv.dev |
| deps.dev, GitHub advisory API, Socket, Snyk and similar | Package names and versions | That vendor |
| `cargo audit`, `cargo deny check advisories` | Nothing from the project; they `git fetch` the public RustSec advisory database and check `Cargo.lock` locally | github.com |
| `osv-scanner --offline` after the databases are downloaded | Nothing; per its docs it sends no project or dependency information | None |

On a private repo, ask the user before any row that goes to a third party, and say which list would leave the machine. `uvx` and `pnpm dlx` download the tool itself from PyPI or npm, which reveals only the tool's name.

## 1. Read the lockfile diff

```bash
git diff <base>...HEAD -- '*package.json' '*pnpm-lock.yaml' '*package-lock.json' '*pyproject.toml' '*uv.lock' '*poetry.lock' '*requirements*.txt' '*pom.xml' '*build.gradle*' '*gradle.lockfile' '*Cargo.toml' '*Cargo.lock'
```

List:

- Every added package, direct or transitive, and every version change, with old and new versions.
- Sources that aren't the normal registry: git URLs, tarball URLs, local paths, a changed `resolved` URL or registry, a removed `integrity` or hash.
- A manifest change without a matching lockfile change, which means CI resolves versions at install time.
- New entries in pnpm's build-script allowlist (`allowBuilds`, or `onlyBuiltDependencies` in older pnpm) or `dangerouslyAllowAllBuilds`, which let install scripts run.

Use `pnpm why <pkg>`, `npm explain <pkg>` `uv tree --invert --package <pkg>` or `cargo tree -i <pkg>` to find which direct dependency pulled in a new transitive one.

Done when every added or changed package is in the list with its source.

## 2. Vet each new or changed package

For each new direct dependency and each version jump of a direct dependency, check:

- Advisories at the resolved version (step 3).
- Maintenance: date of the last release, archived or deprecated repository, unanswered security issues.
- Maintainers: a single maintainer, or a recent change of owner or publisher.
- Name: a typosquat of a popular package (swapped or doubled letters, `-js` or `-py` suffixes, scope confusion such as `@acme/x` against `acme-x`), and dependency confusion, where an internal package name also exists on the public registry and the resolver could pick the public one.
- Install-time code: npm `preinstall`, `install` or `postinstall` scripts and `binding.gyp`; Python packages published only as an sdist with a `setup.py`; Rust `build.rs` scripts and proc-macro crates, which run at compile time.
- Provenance: npm attestations (`dist.attestations`), PyPI trusted publishing.
- Release age against the policy in step 4. A version a few days old is where most malicious publishes get caught.
- Need: whether the standard library or an existing dependency already does the job, and how many transitive packages it adds.

```bash
npm view <pkg>@<version> time maintainers repository scripts dist.attestations --json
curl -s https://pypi.org/pypi/<pkg>/<version>/json | jq '{project_urls: .info.project_urls, files: [.urls[].packagetype], uploaded: [.urls[].upload_time_iso_8601]}'
```

Report figures as measured. Data a registry doesn't publish (PyPI has no maintainer ACL) is "unassessed", not a risk and not a pass.

## 3. Advisory sweep

Run what fits the repo, after the privacy check above:

- pnpm: `pnpm audit --prod`, adding `--json` for details. npm: `npm audit --omit=dev`.
- npm signatures and provenance, in npm projects with `node_modules` installed: `npm audit signatures`.
- uv projects: `uv export --frozen --no-hashes --format requirements.txt -o <scratch>/requirements.txt`, then `uvx pip-audit --no-deps --disable-pip -r <scratch>/requirements.txt`. Write the export to the session scratchpad, not the repo.
- Plain requirements files: `uvx pip-audit --no-deps --disable-pip -r requirements.txt` when every line is pinned.
- Rust: `cargo audit` reads `Cargo.lock`. On an untrusted checkout, run `cargo audit --file <repo>/Cargo.lock` from outside the repo, because Cargo reads config from the current directory. When the repo has a `deny.toml`, `cargo deny check advisories bans sources` also checks banned crates and non-crates.io sources.
- Poetry, Maven, Gradle and mixed repos, or any private repo where the user declined third-party lookups: `osv-scanner` in offline mode. Download the databases once with `osv-scanner --offline-vulnerabilities --download-offline-databases <dir>`, then scan with `osv-scanner --offline <dir>`. `--offline-vulnerabilities` alone can still query deps.dev for manifests without a lockfile (Maven `pom.xml`), which is why the scan itself uses `--offline`.

A scanner that reads only the first YAML document of pnpm's two-document `pnpm-lock.yaml` reports zero dependencies and zero advisories without failing. Check the count of scanned packages before calling a result clean.

An advisory becomes a finding when the vulnerable code is reachable from how the project uses the package (the affected function is called, the affected parser gets untrusted input) or when the advisory applies regardless of use (malicious package, install-time code). Otherwise list it under "Hardening" with its upgrade path, noting whether the fix is a patch release or a major version away.

## 4. Pinning and install policy

- npm: the user's `~/.npmrc` sets `save-exact=true` and `min-release-age=7` (days). That file is per machine, so CI and other developers don't get it; a repo-level `.npmrc` does.
- pnpm: `minimumReleaseAge` in `pnpm-workspace.yaml` is in minutes, and pnpm's docs give 1440 (one day) as the default; `10080` waits a week. `trustPolicy: no-downgrade` blocks a version whose publish trust is lower than earlier releases. A diff that lowers either, or adds broad excludes, needs a reason.
- uv: `exclude-newer` accepts a duration such as `"7 days"` in `[tool.uv]` or `uv.toml`.
- Ranges (`^`, `~`, `*`, `latest`, `>=` without an upper bound) in a direct dependency added by the diff, when the repo otherwise pins exact versions.
- CI installs from the lockfile: `pnpm install --frozen-lockfile`, `npm ci`, `uv sync --locked`, `poetry install` with a committed `poetry.lock`, `cargo build --locked`.

## 5. Report

Put dependency findings in the main report with the same five parts as code findings. Add a line to the report header with what ran, how many packages each tool scanned, and what was skipped and why ("pip-audit skipped: private repo, user declined PyPI lookup"). "No advisories" covers only what was scanned.
