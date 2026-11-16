---
name: aws
description: Works with AWS from the shell through the AWS CLI, SAM CLI and CDK CLI, read-only by default and with the user's explicit yes before any change. Has 45 topics, ported from AWS's plugins without their MCP servers, covering IAM, CloudFormation, CDK, Lambda, API Gateway, Step Functions, SAM deployment, ECS/EKS/ECR, EC2, databases (RDS, Aurora, DynamoDB, ElastiCache), networking (Route 53, CloudFront, WAF, VPC), S3 and storage, SQS/SNS/EventBridge/Kinesis, CloudWatch observability, Bedrock and SageMaker, Cognito auth, Secrets Manager, security services, cost and billing with a read-only cost audit, a local AWS Emulator for testing without an account, SDK usage (boto3, JS v3, Swift) and Well-Architected reviews, plus any other AWS service through `aws SERVICE help`. Use when the user asks about or works with anything on AWS, such as an aws CLI command, boto3 code, a CloudFormation, SAM or CDK template, a Lambda, queue or bucket, an AWS bill, an IAM policy, an AWS error, or AWS credentials, `aws login` and SSO.
---

# AWS

AWS's own agent guidance, ported from the `aws-core` (1.2.0) and `aws-serverless` (1.3.0) plugins and eleven specialized skills from `aws/agent-toolkit-for-aws` by Amazon Web Services (Apache-2.0, see `LICENSE` and `NOTICE`) and split into topics, plus `aws-cost-audit` from `aboudjem/aws-cost-audit-skill` (MIT, see `topics/aws-cost-audit/LICENSE`). The plugins called AWS through two MCP servers; this port uses the CLIs instead. All paths below are relative to `~/.agents/skills/aws/`. Inside a topic, "this skill" means that topic and a relative path resolves from the topic's folder.

The rules in this file win over anything a topic says. Topics were written for an agent with its own sandboxed AWS access, so some of them run `aws sts get-caller-identity`, `aws login` or account reads without asking; here those follow the Safety rules below.

## Safety: read before running any command

1. **Read-only by default.** Run only operations that read: `describe-*`, `list-*`, `get-*` (except the secret reads in rule 3), `search-*`, `lookup-*`, `query`/`scan` reads, `logs tail`, `cloudwatch get-metric-data`, `cloudformation describe-events`, `s3 ls`. A few reads cost money or leave state behind: Cost Explorer charges per request, Athena `start-query-execution` and Logs Insights `start-query` bill per data scanned and write results, so say so before running them.
2. **Every change needs the user's explicit yes in chat, for that command.** Before running it, state the account ID, profile, region, the resources it touches and the exact command, then wait. This covers any `create-*`, `update-*`, `delete-*`, `put-*`, `modify-*`, `attach-*`/`detach-*`, `tag-*`, `start-*`/`stop-*`, `terminate-*`, `reboot-*`, `run-instances`, `lambda invoke` (it runs code), `sqs send-message`, `sns publish`, `s3 cp/mv/rm/sync` to S3, `cloudformation create-change-set`/`execute-change-set`/`deploy`, `sam deploy`/`sam delete`/`sam sync`, `cdk bootstrap`/`deploy`/`destroy`, `terraform apply`/`destroy`, and any script that calls them. A yes covers that one command, not the next one. Where a resource is managed by Terraform, CloudFormation or CDK, change the code instead of the live resource, because a CLI write leaves drift.
3. **Never fetch secret values.** Don't run `aws secretsmanager get-secret-value` or `batch-get-secret-value`, SDK `GetSecretValue` calls, `curl` to the Secrets Manager Agent on `localhost:2773`, `ssm get-parameter(s) --with-decryption`, `aws configure export-credentials` or `aws configure get aws_secret_access_key`. Don't print commands whose output holds credentials (`sts assume-role`, `sts get-session-token`, `ecr get-login-password`, `codeartifact get-authorization-token`); pipe them straight into the consumer. Lambda and ECS reads return environment variables that often hold secrets, so add `--query` to leave `Environment` out. To pass a secret to a command, use `asm-exec` from `topics/aws-secrets-manager/README.md`.
4. **Know the account before the first call.** Start with local checks that make no AWS request: `echo "$AWS_PROFILE $AWS_REGION"`, `aws configure list`, `aws configure list-profiles`. `aws sts get-caller-identity` is a credentialed call, so if the user hasn't named a profile, ask which profile and account to use before running it. Pass `--profile` and `--region` on every command and tell the user which account ID the identity call returned.
5. **Production accounts follow `~/.agents/AGENTS.md`, "Production access".** Make no call against a production account, read-only or not, unless the user explicitly OKs it for this task in the current conversation; an earlier yes doesn't carry over. Look at Datadog, Sentry and Sigma first (`prod-evidence` skill). Treat an account as production when its profile or alias contains `prod`, when the user says so, or when it hosts production (the workspace skill, when one exists, says where its Terraform roots are). When unsure, ask.
6. **Credentials come only from a login the user runs.** The user runs `aws login` or `aws sso login --profile <name>` in their terminal (in Claude Code, `! aws sso login --profile <name>`); see `topics/signing-in-to-aws/README.md`. Never run a login yourself, never ask for access keys in chat, never write keys to `~/.aws/credentials`, `.env` or any other file, and never run `aws configure set aws_access_key_id`. If you find long-lived keys (`AKIA...`) in use, point it out.

## How to use

1. Apply the Safety rules above.
2. Match the task to a topic below and read only that topic's `README.md`. Each topic links its own references, assets and scripts; open them when the topic says to. Many links inside a topic's `references/` are relative to the topic folder, not to the file, so resolve `references/...` and `assets/...` from `topics/<topic>/`. When a task spans two topics, read both.
3. Run AWS calls with the CLIs listed under "Tools". Where a topic names an MCP tool, use the CLI equivalent from the mapping table.

Examples:

- "Why is my SQS-triggered Lambda falling behind?": read `topics/aws-lambda/README.md`, then its `references/troubleshooting.md`.
- "Review this CloudFormation template before we deploy": read `topics/aws-cloudformation/README.md` and its pre-deploy validation reference.
- "How much are we spending on NAT gateways?": read `topics/aws-billing-and-cost-management/README.md`.

## Topics

From aws-core:

- Bedrock models, Knowledge Bases, Agents, Guardrails, AgentCore: `topics/amazon-bedrock/README.md`.
- SageMaker training, fine-tuning, model selection, evaluation, endpoints: `topics/aws-ai-ml/README.md`.
- Cognito user and identity pools, app sign-in, OAuth/OIDC: `topics/aws-auth/README.md`.
- Costs, budgets, Savings Plans, rightsizing, CUR with Athena, pricing: `topics/aws-billing-and-cost-management/README.md`.
- AWS Blocks infrastructure-from-code apps: `topics/aws-blocks/README.md`.
- CDK in TypeScript or Python (synth, diff, deploy, bootstrap, errors): `topics/aws-cdk/README.md`.
- CloudFormation templates, cfn-lint, cfn-guard, pre-deploy validation, failed stacks: `topics/aws-cloudformation/README.md`.
- EC2 instances, launch templates, Auto Scaling, Spot, IMDSv2: `topics/aws-compute/README.md`.
- EKS, ECS, Fargate, ECR, Karpenter, load balancer controller: `topics/aws-containers/README.md`.
- Choosing or operating any AWS database (router): `topics/aws-database/README.md`.
- CodePipeline, CodeBuild, CodeDeploy, CodeArtifact: `topics/aws-deployment/README.md`.
- IAM policies, trust policies, STS, Organizations, policy generation: `topics/aws-iam/README.md`.
- SQS, SNS, EventBridge, Kinesis, Firehose, MQ, MSK patterns (router): `topics/aws-messaging-and-streaming/README.md`.
- Route 53, CloudFront, Transit Gateway, Direct Connect, VPN, WAF, Shield (router): `topics/aws-networking/README.md`.
- CloudWatch logs, metrics, alarms, Logs Insights, X-Ray, CloudTrail, ADOT, CloudWatch Omni: `topics/aws-observability/README.md`.
- AWS SDK for JavaScript v3: `topics/aws-sdk-js-v3-usage/README.md`.
- boto3 and botocore code: `topics/aws-sdk-python-usage/README.md`.
- AWS SDK for Swift: `topics/aws-sdk-swift-usage/README.md`.
- Secrets in commands, `asm-exec`, `{{resolve:secretsmanager:...}}`: `topics/aws-secrets-manager/README.md`.
- GuardDuty, Inspector, Security Hub, Macie, Detective, Security Lake, coverage and cost advice: `topics/aws-security/README.md`.
- Serverless architecture choices: Lambda form factor, orchestration, event routing (router): `topics/aws-serverless/README.md`.
- S3, EFS, FSx, EBS, storage classes, storage cost: `topics/aws-storage/README.md`.
- Well-Architected Framework review of a workload: `topics/aws-well-architected-review/README.md`.
- Migrating a web app to AWS with Launch with AWS: `topics/launch-with-aws/README.md`.
- Missing or expired credentials, `aws login`, SSO: `topics/signing-in-to-aws/README.md`.

From aws-serverless:

- Lambda functions, event sources, Lambda Web Adapter, Lambda troubleshooting: `topics/aws-lambda/README.md`.
- API Gateway REST, HTTP and WebSocket APIs: `topics/api-gateway/README.md`.
- Step Functions state machines, ASL, JSONata: `topics/aws-step-functions/README.md`.
- SAM and CDK projects and deployment for serverless apps: `topics/aws-serverless-deployment/README.md`.
- Lambda durable functions (checkpoint and replay): `topics/aws-lambda-durable-functions/README.md`.
- Lambda Managed Instances (capacity providers): `topics/aws-lambda-managed-instances/README.md`.
- Lambda MicroVMs (Firecracker, suspend and resume): `topics/aws-lambda-microvms/README.md`.

From the specialized skills in `aws/agent-toolkit-for-aws`. To size a resource family in the account at hand, count it with a read under the Safety rules: `aws rds describe-db-instances`, `aws dynamodb list-tables`, `aws elasticache describe-cache-clusters`, `aws route53 list-hosted-zones` (records: `list-resource-record-sets`), `aws cloudfront list-distributions`, `aws wafv2 list-web-acls --scope REGIONAL` (and `--scope CLOUDFRONT --region us-east-1`), `aws ec2 describe-vpc-peering-connections`, `aws ec2 describe-vpc-endpoints`, `aws events list-event-buses`. The workspace skill for the repo, when one exists, may hold the counts from the company's Terraform.

- RDS for PostgreSQL, MySQL or MariaDB: creating an instance, upgrade planning and prechecks, RI vs Database Savings Plans, RDS Proxy, Blue/Green: `topics/rds-oss/README.md`.
- Aurora PostgreSQL clusters: express create, ACU sizing, I/O-Optimized, commitment pricing, upgrades: `topics/amazon-aurora-postgresql/README.md`.
- DynamoDB tables: access patterns, keys and GSIs, Streams, Global Tables, vector search, bulk loads, hot partitions, cost estimates: `topics/amazon-dynamodb/README.md`.
- ElastiCache for Valkey, Redis or Memcached: setup, connectivity, monitoring, cost, migration, Redis to Valkey: `topics/amazon-elasticache/README.md`.
- Route 53 hosted zones, records, health checks, routing policies, Resolver, DNS Firewall: `topics/route53/README.md`.
- CloudFront distributions: caching, OAC, certificates, signed URLs, observability: `topics/cloudfront/README.md`.
- WAF web ACLs: managed rules, rate-based rules, Bot and Fraud Control, logging, client IP behind a CDN: `topics/waf/README.md`.
- VPC peering connections, cross-VPC routes and DNS: `topics/connecting-vpcs-with-peering/README.md`.
- VPC gateway and interface endpoints (PrivateLink) for S3, DynamoDB and other services: `topics/configuring-vpc-endpoints-for-private-aws-service-access/README.md`.
- EventBridge custom event buses on the new `eventsv2` API: publishing, subscribers, filters, replay, delivery debugging. Classic `events` rules and buses go to `topics/aws-messaging-and-streaming/README.md`; check which kind the account's bus is (`aws events list-event-buses`) before choosing: `topics/amazon-eventbridge-event-bus/README.md`.
- S3 bucket security audits and fixes: Block Public Access, bucket policies, encryption, access logging: `topics/securing-s3-buckets/README.md`.

From `aboudjem/aws-cost-audit-skill`:

- A full cost audit of an account: idle and orphaned resources, rightsizing, Savings Plans and RI coverage, NAT, data transfer, S3 and log costs, with live-verified prices and a savings report. Questions about one bill line, budgets or pricing stay in `topics/aws-billing-and-cost-management/README.md`: `topics/aws-cost-audit/README.md`.

Local:

- Testing against AWS APIs locally with AWS Emulator (Docker, telemetry off) and pointing the CLI, SDKs, SAM or CDK at it, unless the repo names another emulator: `topics/local-emulator/README.md`.

## Tools

The machine has the AWS CLI v2 (`/opt/homebrew/bin/aws`) and the SAM CLI (`/usr/local/bin/sam`, which bundles cfn-lint for `sam validate --lint`), plus `uv`/`uvx`, `pipx` and `jq`. These are missing; give the install command and install only after the user's yes:

| CLI | Used by | Install |
|---|---|---|
| `cdk` | aws-cdk, aws-serverless-deployment | `brew install aws-cdk` (or `npm install -g aws-cdk`; `npx aws-cdk` runs it without installing) |
| `cfn-lint` | aws-cloudformation | `brew install cfn-lint` (or `pipx install cfn-lint`, `uv tool install cfn-lint`) |
| `cfn-guard` | aws-cloudformation | `brew install cloudformation-guard` |
| `awscurl` | CloudWatch PromQL HTTP API in aws-observability | `uvx awscurl --service monitoring --profile <p> --region <r> '<url>'` runs it without installing |

### MCP tool to CLI mapping

Topics were written for two MCP servers: `aws-mcp` (the AWS MCP Server, tools named `aws___*`) and `aws-serverless-mcp`. Use these instead. Every row follows the Safety rules.

| MCP tool | Use instead |
|---|---|
| `call_aws` / `aws___call_aws` | `aws <service> <operation> --profile <p> --region <r>` in the shell. `file://` inputs work. |
| `suggest_aws_commands` | `aws <service> help`, `aws <service> <operation> help`, `aws <service> <operation> --generate-cli-skeleton` (all local). |
| `aws___search_documentation` | The web search tool with `site:docs.aws.amazon.com <terms>`. |
| `aws___read_documentation` | The web fetch tool on the `docs.aws.amazon.com` `.html` page. |
| `aws___retrieve_skill` | Read `topics/<skill>/README.md`; for a skill that isn't ported, see "Skills a topic names that aren't ported". |
| `aws___run_script` | Write the Python script to the scratchpad and run `uv run --with boto3 python <script>.py` (pass `--profile`/region into the boto3 session). Pure math on fetched data needs no AWS access. |
| `aws___list_regions`, `aws___get_regional_availability` | The "AWS Services by Region" and service endpoints pages on aws.amazon.com and docs.aws.amazon.com; `aws account list-regions` or `aws ssm get-parameters-by-path --path /aws/service/global-infrastructure/services/<svc>/regions` are credentialed reads. |
| `aws___get_presigned_url` | `aws s3 presign s3://<bucket>/<key> --expires-in <s>` for downloads; uploads are `aws s3 cp` (a write). |
| `aws___get_tasks` | Not needed; local scripts run in the foreground. |
| `sam_init` | `sam init --name <app> --runtime <rt> --app-template <t> --dependency-manager <m> --no-interactive` |
| `sam_build` | `sam build` (`--use-container` for native dependencies) |
| `sam_local_invoke` | `sam local invoke <Function> --event <file>`; make events with `sam local generate-event <service> <event>` |
| `sam_deploy` | `sam deploy` (`--guided` the first time, `--config-env <env>`); a write. |
| `sam_logs` | `sam logs --stack-name <s> --name <Function> [--tail]` or `aws logs tail /aws/lambda/<fn> --since 1h`; logs can hold customer data. |
| `get_metrics` | `aws cloudwatch get-metric-data` on `AWS/Lambda` (`Invocations`, `Errors`, `Duration`, `Throttles`, `ConcurrentExecutions`, `IteratorAge`), `AWS/ApiGateway`, `AWS/SQS`; memory from the `REPORT` log lines or Lambda Insights. |
| `get_lambda_guidance`, `get_iac_guidance`, `deploy_serverless_app_help`, `webapp_deployment_help` | The matching topic (`aws-lambda`, `aws-serverless`, `aws-serverless-deployment`) and the Lambda, SAM and CDK developer guides. |
| `get_lambda_event_schemas` | `sam local generate-event <service> <event>` (local) and the event examples in the Lambda developer guide. |
| `get_serverless_templates` | `sam init` app templates, and Serverless Land patterns (serverlessland.com/patterns, github.com/aws-samples/serverless-patterns) through the web fetch tool. |
| `list_registries`, `search_schema`, `describe_schema` | `aws schemas list-registries`, `aws schemas search-schemas --registry-name <r> --keywords <k>`, `aws schemas describe-schema --registry-name <r> --schema-name <n>` |
| `esm_guidance`, `esm_optimize` | `topics/aws-lambda/references/event-sources.md` and `optimization.md`, plus `aws lambda list-event-source-mappings` / `get-event-source-mapping` and the source's lag metrics. |
| `esm_kafka_troubleshoot` | The Kafka section of `topics/aws-lambda/references/troubleshooting.md`, the ESM's `StateTransitionReason`, `aws kafka describe-cluster-v2`, `aws ec2 describe-security-groups`. |
| `secure_esm_sqs_policy`, `secure_esm_kinesis_policy`, `secure_esm_dynamodb_policy`, `secure_esm_msk_policy` | Write the execution-role policy from the per-source permission list in the Lambda developer guide, scoped to the one queue, stream, table or cluster ARN. |
| `deploy_webapp` | A SAM template with Lambda Web Adapter (see `topics/aws-lambda/references/web-app-deployment.md`), then `sam build` and `sam deploy`. |
| `update_webapp_frontend` | `aws s3 sync <dist> s3://<bucket>` and `aws cloudfront create-invalidation --distribution-id <id> --paths '/*'` (both writes). |
| `configure_domain` | `aws acm request-certificate`, `aws apigatewayv2 create-domain-name` and `create-api-mapping`, `aws route53 change-resource-record-sets` (all writes), or the same resources in the template. |

### Plugin hooks

- aws-core's `PreToolUse` hook (`secret-safety.py`) blocked secret reads. Safety rule 3 replaces it. The checker is kept at `scripts/secret-safety.py`, but it does nothing unless someone wires it as a `PreToolUse` hook on `Bash`.
- aws-serverless's `PostToolUse` hook ran `sam validate` after edits to `template.yaml` or `template.yml`. Do it as a step: after each edit to a SAM template, run `sam validate --template <file> --lint` (local) and fix what it reports.

## Skills a topic names that aren't ported

Topics route to more AWS skills than this port holds, such as `amazon-aurora-mysql`, `shieldadvanced`, `transitgateway`, `connecting-lambda-to-api-gateway` or `setting-up-cloudwatch-observability`. When a topic names a skill, first check for `topics/<skill>/README.md`: some topics still say a skill isn't ported (`aws-networking`, `aws-serverless`) although it now is, and the local topic wins. They live in the public repo `aws/agent-toolkit-for-aws`, under `skills/specialized-skills/<category>/<skill>/`. Reading them is a public GitHub read, so it needs no approval:

```bash
gh api 'repos/aws/agent-toolkit-for-aws/git/trees/main?recursive=1' --jq '.tree[].path' | grep '/<skill>/SKILL.md$'
gh api repos/aws/agent-toolkit-for-aws/contents/<path-from-above> -H 'Accept: application/vnd.github.raw'
```

Fetch a reference it cites the same way, with the path relative to that skill's folder. Apply this file's Safety rules and the MCP mapping to whatever it says. If the skill isn't in that repo, say so and answer from the topic and the AWS docs.

## Services without a topic

For any other AWS service:

1. Find the operation locally: `aws help` lists services, `aws <service> help` lists operations, `aws <service> <operation> help` shows parameters and output, and `aws <service> <operation> --generate-cli-skeleton input` prints the request shape. None of these call AWS.
2. Read the service's docs on docs.aws.amazon.com (user guide, API reference, quotas and pricing pages) with the web fetch tool, and the CLI reference at `https://docs.aws.amazon.com/cli/latest/reference/<service>/<operation>.html`.
3. Classify the operation by its verb under Safety rules 1 and 2 before running it. Where a service offers `--dry-run` (EC2), use it to check permissions before asking for a write.
4. Keep output small with `--query`, `--output json` and `--max-items`, and leave secrets and environment variables out of it.
