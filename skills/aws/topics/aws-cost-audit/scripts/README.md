# aws-cost-audit scripts

Generic, account-agnostic helper scripts for auditing and reducing AWS spend.

Every script here is read-only against AWS and has no `--apply` flag. The upstream
mutating scripts (`set-log-retention.sh`, `gp2-to-gp3.sh`,
`delete-unattached-ebs.sh`) aren't ported: a change is a command you propose and run
only after the user's yes, per the Safety rules in `~/.agents/skills/aws/SKILL.md`.
`_lib.sh` still carries the upstream `--apply`/`confirm` helpers, which no ported
script calls.

Nothing here hardcodes an account id, region, ARN, resource id, or a dollar
price. Region is resolved from `--region`, then `$AWS_REGION`, then
`$AWS_DEFAULT_REGION`, then `aws configure get region`, if none is set the
script stops and tells you to set one. Prices are always looked up **live** from
the AWS Price List Query API (see `verify-price.sh`), never assumed.

## Requirements

- AWS CLI v2, configured with credentials for the account you want to audit.
- `jq` recommended (scripts degrade to raw JSON without it). The one exception is
  `findings-validate.sh`, which needs `jq` to do its job and exits 2 saying so rather
  than reporting a file as valid when it could not check it.
- IAM permissions: read-only `Describe*`/`List*`/`Get*` for the services you
  scan, `ce:Get*` for the baseline, and `pricing:GetProducts` for price lookups.
- No `--profile` flag: run each script as `AWS_PROFILE=<profile> bash <script>`.

## Scripts

| Script | What it does | Mutates? | Savings lever | Risk | Rollback |
|---|---|---|---|---|---|
| `doctor.sh` | Preflight check: aws CLI, credentials, `jq`, region resolution, writable output dir, and (opt-in) whether Cost Explorer answers | No (read-only) | Stops you burning a run on a broken environment | None | N/A (read-only) |
| `00-baseline.sh` | Cost Explorer total, by-service, by-region, by-usage-type, 90d daily trend, 30d forecast → JSON | No (read-only) | Establishes the spend picture so you target the biggest line items | None | N/A (read-only) |
| `inventory-regions.sh` | Loops `describe-regions` and runs read-only inventory per region (EC2, EBS, snapshots, EIPs, ELB, TGs, NAT, RDS, ElastiCache, log groups) | No (read-only) | Finds resources you forgot in other regions | None | N/A (read-only) |
| `find-idle.sh` | Candidate table: unassociated EIPs, unattached EBS, idle ALBs/empty TGs, never-expire log groups, gp2 volumes | No (read-only) | Pinpoints concrete waste to act on | None | N/A (read-only) |
| `verify-price.sh` | Live unit price from `pricing get-products` for a service-code + region-code + filters | No (read-only) | Proves savings math with real, current prices (no guessing) | None | N/A (read-only) |
| `findings-validate.sh` | Checks a `findings.json` file against the contract in `../references/output-and-reporting.md` (jq) | No (read-only) | Lets two audits be diffed instead of re-read | None | N/A (read-only) |

Shared helpers live in `_lib.sh` (sourced, not run directly).

### Cost Explorer requests are counted and capped

AWS bills every Cost Explorer API request, and every page of a paginated result is its own
request. `_lib.sh` wraps them: `ce_call` passes `--no-paginate` and counts one request per call,
`ce_paged_call` walks the pages itself so every billed page is counted, and the run stops asking
once it reaches `AWS_COST_AUDIT_CE_BUDGET` (default 50). `ce_report` prints the count and the
estimated spend at the end of `00-baseline.sh`. The per-request price is not written into any
script: it is read from `../references/pricing-verification.md`, which carries the figure with its
AWS source URL. The counter covers what these scripts issue; an `aws ce` command you run yourself
is billed the same way but is invisible to it.

## Suggested workflow

1. `doctor.sh`, confirm the environment can run an audit at all. Add
   `--check-cost-explorer` to also probe Cost Explorer, which makes one billed
   request.
2. `00-baseline.sh --output <out>`, snapshot current spend (billed Cost Explorer requests).
3. `inventory-regions.sh --output <out>`, sweep every region.
4. `find-idle.sh --region <region> --output <out>`, list candidates per region.
5. `verify-price.sh --service-code AmazonEC2 --region-code <region> ...`, confirm the live price before you size any savings claim.
6. For each change worth making, propose the exact command (rollback step first, such as a
   snapshot) and run it only after the user's yes.

## Constraints

- **Never touch production without proof it is safe and the user's OK.** Confirm via
  metrics, owners, and dependency checks that a resource is genuinely idle before
  proposing to delete or modify it. The finder scripts surface *candidates*, not
  verdicts.
- **Law 1, never assume a price.** Verify it live for your exact region and
  usage type with `verify-price.sh` (or the service's pricing page) before
  claiming a dollar amount.
- **Reversibility first.** Propose a snapshot before any delete and record the prior
  state (retention, volume type) before any modify, so the rollback is a known command.

## Output

By default scripts write to `./cost-audit-out` (override with `--output` or
`$OUT_DIR`). Point it at the session scratchpad or a temp dir, never the user's repo.
