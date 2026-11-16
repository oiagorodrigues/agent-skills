# Terraform and AWS IAM, GitHub Actions, Docker

GitHub Actions threat model and safe patterns adapted from getsentry/skills `gha-security-review` (Apache-2.0, https://github.com/getsentry/skills). Untrusted `github.event` fields from the anthropics/claude-plugins-official `security-guidance` plugin (Apache-2.0, https://github.com/anthropics/claude-plugins-official). Cloud rules adapted from cloudflare/security-audit-skill `CLOUD-AND-DEPLOYMENT.md` (MIT, https://github.com/cloudflare/security-audit-skill).

Before any AWS CLI call, follow the `aws` skill (read-only, the user's yes before changes, no production account without their OK). A review reads code; it doesn't run `terraform plan` or `apply` against real accounts. When an account-level fact decides a finding (an SCP, a bucket policy managed elsewhere, the repo's default token permission), it goes under "Needs validation".

## Contents

- Terraform and AWS IAM
- GitHub Actions
- Docker and Kubernetes

## Terraform and AWS IAM

- Policies with `"Action": "*"` or `"Resource": "*"` on write, IAM, KMS or secrets actions. A broad policy is a finding when something lower-trust can drive it (a workload processing user input, a CI job from a fork, a role others can assume).
- Escalation actions on `*`: `iam:PassRole`, `iam:CreatePolicyVersion`, `iam:AttachRolePolicy`, `iam:PutRolePolicy`, `iam:CreateAccessKey`, `iam:UpdateAssumeRolePolicy`, `lambda:UpdateFunctionCode` combined with `iam:PassRole`, `sts:AssumeRole` on `*`.
- Trust policies: `"Principal": {"AWS": "*"}`, a whole other account without `sts:ExternalId` or source conditions, and GitHub OIDC roles. An OIDC role needs `token.actions.githubusercontent.com:aud` equal to `sts.amazonaws.com` and a `:sub` condition pinned to the repo and a branch or environment (`repo:<org>/<repo>:ref:refs/heads/main`, `repo:<org>/<repo>:environment:production`). A missing `sub` condition or `repo:<org>/*` lets other repos or fork-triggered jobs assume the role.
- S3: public ACLs, `block_public_*` set to false, bucket policies with `"Principal": "*"`, no deny on `aws:SecureTransport = false` for sensitive buckets, object keys without a company prefix when one bucket serves many companies.
- Network: security groups open to `0.0.0.0/0` or `::/0` on admin and data ports (22, 3389, 5432, 6379, 9200), `publicly_accessible = true` on RDS, internal load balancers made internet-facing.
- Secrets: passwords as variable `default` values or in committed `*.tfvars`, outputs carrying secrets without `sensitive = true`, plaintext secrets in Lambda or ECS environment blocks where Secrets Manager or SSM is the pattern, state backends without encryption.
- Encryption and logging: unencrypted RDS, EBS or S3 holding customer data, CloudTrail or access logging turned off by the change.

## GitHub Actions

The attacker is someone without write access: they can open PRs from forks, open issues and comment. Findings that need write access to trigger (`workflow_dispatch` inputs, `push` to protected branches, `schedule`) are out of scope.

Check, for each workflow the diff touches:

1. Pwn request: `pull_request_target` or `workflow_run` that checks out the PR head (`ref: ${{ github.event.pull_request.head.sha }}` or `head.ref`) and then runs anything from it (build, tests, `npm install`, a local action under `./.github/actions/`, a `Makefile`, an AI agent that reads `CLAUDE.md` or `AGENTS.md` from the checkout) while secrets, a write token or OIDC are available.
2. Expression injection: `${{ }}` with attacker-controlled values inside `run:` scripts, and inside `actions/github-script` `script:` (evaluated as JavaScript). Attacker-controlled values include `github.event.issue.title` and `.body`, `github.event.pull_request.title` and `.body`, `github.event.comment.body`, `github.event.review.body`, `github.event.review_comment.body`, `github.event.pages.*.page_name`, `github.event.commits.*.message`, `github.event.head_commit.message`, `github.event.head_commit.author.email` and `.name`, `github.event.commits.*.author.email` and `.name`, `github.event.pull_request.head.ref`, `github.event.pull_request.head.label`, `github.event.pull_request.head.repo.default_branch`, `github.event.client_payload.*` (`repository_dispatch` sets any field), and `github.head_ref`. The fix passes the value through `env:` and uses `"$VAR"` in the script. The same values in `actions/checkout`'s `ref:` are ref injection; a `client_payload.pr_number` must match `^[0-9]+$` before it builds `refs/pull/<n>/head`.
3. Comment-triggered commands without an `author_association` (or team membership) check.
4. Writes of untrusted text to `$GITHUB_ENV`, `$GITHUB_OUTPUT` or `$GITHUB_PATH`, which can set variables like `NODE_OPTIONS` or `LD_PRELOAD` for later steps.
5. Permissions: no top-level `permissions:` block (the default token's scope then depends on a repo setting, so "Needs validation"), `contents: write`, `id-token: write` or `secrets: inherit` on jobs reachable from fork events.
6. Third-party actions on a tag or branch instead of a full commit SHA, in jobs that hold secrets, OIDC, a write token, or release, deploy, package or signing power. First-party `actions/*` and `github/*` on version tags and same-repo local actions aren't pinning findings.
7. Caches and artifacts: a job running untrusted code that writes a cache or artifact later restored and executed by a privileged job (`workflow_run` downloading artifacts from the PR run is the common case).
8. Self-hosted runners used by public-repo workflows that fork PRs can trigger.
9. AI agents in CI (Claude, Codex or similar run on PR or issue content): the content is a prompt-injection channel, so the job needs read-only permissions, no secrets beyond the model key, and a restricted tool list.

Safe and not a finding: `pull_request_target` without checking out PR code, `${{ github.event.pull_request.number }}` and SHAs in `run:`, `${{ secrets.X }}`, expressions in `if:` and in `with:` inputs other than `github-script`'s `script`, and `pull_request` (not `_target`) from forks, which runs with a read-only token and no secrets.

To lint workflows, run `zizmor --offline .github/workflows` (or `uvx zizmor` where it isn't installed). `--offline` keeps zizmor from calling the GitHub API. Treat its output as leads for steps 3 and 5 of the workflow.

## Docker and Kubernetes

- No `USER` line, so the container runs as root.
- Secrets in `ARG`, `ENV`, or files copied into a layer (`.env`, keys). Layers keep them even when a later step deletes the file. Use BuildKit `--mount=type=secret`.
- `.dockerignore` missing `.env`, `.git`, keys and local config while the build uses `COPY . .`.
- Base images on mutable tags (`latest`, `3`) in images that ship. Pin by digest.
- `RUN` steps that pipe a downloaded script into a shell, and `ADD` of a remote URL, without a checksum check.
- Compose files: services bound to `0.0.0.0` with default passwords, `privileged: true`, the Docker socket mounted, `network_mode: host`. If the compose file is only for local development, say so and lower the severity.
- Kubernetes manifests: `privileged`, `hostPath`, `hostNetwork`, added capabilities, `automountServiceAccountToken` left on for pods that don't call the API, secrets in ConfigMaps.
