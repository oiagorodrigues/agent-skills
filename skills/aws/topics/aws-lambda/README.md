---
name: aws-lambda
description: "Design, build, deploy, test, and debug serverless applications with AWS Lambda. Triggers on phrases like: Lambda function, event source, serverless application, API Gateway, EventBridge, Step Functions, serverless API, event-driven architecture, Lambda trigger. For deploying non-serverless apps to AWS, use deploy-on-aws plugin instead."
argument-hint: "[what are you building?]"
---

# AWS Lambda Serverless Development

Design, build, deploy, and debug serverless applications with AWS serverless services. This topic gives serverless development guidance and runs the SAM CLI, CDK CLI and AWS CLI from the shell (the MCP tool mapping is in `~/.agents/skills/aws/SKILL.md`, "Tools").

Use SAM CLI for project initialization and deployment, Lambda Web Adapter for web applications, or Event Source Mappings for event-driven architectures. AWS handles infrastructure provisioning, scaling, and monitoring automatically.

**Key capabilities:**

- **SAM CLI Integration**: Initialize, build, deploy, and test serverless applications
- **Web Application Deployment**: Deploy full-stack applications with Lambda Web Adapter
- **Event Source Mappings**: Configure Lambda triggers for DynamoDB, Kinesis, SQS, Kafka
- **Lambda durable functions**: Resilient multi-step applications with checkpointing — see the [durable-functions skill](../aws-lambda-durable-functions/) for guidance
- **Lambda Managed Instances**: Run Lambda on dedicated EC2 instances with managed lifecycle — see the [managed-instances skill](../aws-lambda-managed-instances/) for evaluation, configuration, and migration guidance
- **Schema Management**: Type-safe EventBridge integration with schema registry
- **Observability**: CloudWatch logs, metrics, and X-Ray tracing
- **Performance Optimization**: Right-sizing, cost optimization, and troubleshooting

## When to Load Reference Files

Load the appropriate reference file based on what the user is working on:

- **Getting started**, **what to build**, **project type decision**, or **working with existing projects** -> see [references/getting-started.md](references/getting-started.md)
- **SAM**, **CDK**, **deployment**, **IaC templates**, **CDK constructs**, or **CI/CD pipelines** -> see the [aws-serverless-deployment skill](../aws-serverless-deployment/) (separate topic)
- **Web app deployment**, **Lambda Web Adapter**, **API endpoints**, **CORS**, **authentication**, **custom domains**, or **sam local start-api** -> see [references/web-app-deployment.md](references/web-app-deployment.md)
- **Event sources**, **DynamoDB Streams**, **Kinesis**, **SQS**, **Kafka**, **S3 notifications**, or **SNS** -> see [references/event-sources.md](references/event-sources.md)
- **EventBridge**, **event bus**, **event patterns**, **event design**, **Pipes**, or **schema registry** -> see [references/event-driven-architecture.md](references/event-driven-architecture.md)
- **Durable functions**, **checkpointing**, **replay model**, **saga pattern**, or **long-running Lambda workflows** -> see the [durable-functions skill](../aws-lambda-durable-functions/) (separate topic with full SDK reference, testing, and deployment guides)
- **Lambda Managed Instances**, **LMI**, **capacity providers**, **multi-concurrency**, **EC2-backed Lambda**, **cold start elimination**, or **Lambda cost optimization with Reserved Instances** -> see the [managed-instances skill](../aws-lambda-managed-instances/) (separate skill in this plugin for evaluation, configuration, and migration)
- **Orchestration**, **workflows**, or **Durable Functions vs Step Functions** -> see [references/orchestration-and-workflows.md](references/orchestration-and-workflows.md)
- **Step Functions**, **ASL**, **state machines**, **JSONata**, **Distributed Map**, **SDK integrations**, **TestState API**, **mocking service integrations**, or **state machine unit tests** -> see the [aws-step-functions skill](../aws-step-functions/) for comprehensive guidance
- **Observability**, **logging**, **tracing**, **metrics**, **alarms**, or **dashboards** -> see [references/observability.md](references/observability.md)
- **Optimization**, **cold starts**, **memory tuning**, **cost**, or **streaming** -> see [references/optimization.md](references/optimization.md)
- **Powertools**, **idempotency**, **feature flags**, **parameters**, **parser**, **batch processing**, or **data masking** -> see [references/powertools.md](references/powertools.md)
- **Troubleshooting**, **errors**, **debugging**, or **deployment failures** -> see [references/troubleshooting.md](references/troubleshooting.md)

## Best Practices

### Project Setup

- Do: Use `sam init` or `cdk init` with an appropriate template for your use case
- Do: Set global defaults for timeout, memory, runtime, and tracing (`Globals` in SAM, construct props in CDK)
- Do: Use AWS Lambda Powertools for structured logging, tracing, metrics (EMF), idempotency, and batch processing — available for Python, TypeScript, Java, and .NET
- Don't: Copy-paste templates from the internet without understanding the resource configuration
- Don't: Use the same memory and timeout values for all functions regardless of workload

### Security

- Do: Follow least-privilege IAM policies scoped to specific resources and actions
- Do: Write event source mapping IAM policies from the per-source permission list in the Lambda docs (see `secure_esm_*` in `~/.agents/skills/aws/SKILL.md`, "Tools")
- Do: Store secrets in AWS Secrets Manager or SSM Parameter Store, never in environment variables
- Do: Use VPC endpoints instead of NAT Gateways for AWS service access when possible
- Do: Enable Amazon GuardDuty Lambda Protection to monitor function network activity for threats (cryptocurrency mining, data exfiltration, C2 callbacks)
- Don't: Use wildcard (`*`) resource ARNs or actions in IAM policies
- Don't: Hardcode credentials or secrets in application code or templates
- Don't: Store user data or sensitive information in module-level variables — execution environments can be reused across different callers

### Idempotency

- Do: Write idempotent function code — Lambda delivers events **at least once**, so duplicate invocations must be safe
- Do: Use the AWS Lambda Powertools Idempotency utility (backed by DynamoDB) for critical operations
- Do: Validate and deduplicate events at the start of the handler before performing side effects
- Don't: Assume an event will only ever be processed once

For topic-specific best practices, see the dedicated guide files in the reference table above.

## Lambda Limits Quick Reference

Limits that developers commonly hit:

| Resource                                     | Limit                               |
| -------------------------------------------- | ----------------------------------- |
| Function timeout                             | 900 seconds (15 minutes)            |
| Memory                                       | 128 MB – 10,240 MB                  |
| 1 vCPU equivalent                            | 1,769 MB memory                     |
| Synchronous payload (request + response)     | 6 MB each                           |
| Async invocation payload                     | 1 MB                                |
| Streamed response                            | 200 MB                              |
| Deployment package (.zip, uncompressed)      | 250 MB                              |
| Deployment package (.zip upload, compressed) | 50 MB                               |
| Container image                              | 10 GB                               |
| Layers per function                          | 5                                   |
| Environment variables (aggregate)            | 4 KB                                |
| `/tmp` ephemeral storage                     | 512 MB – 10,240 MB                  |
| Account concurrent executions (default)      | 1,000 (requestable increase)        |
| Burst scaling rate                           | 1,000 new executions per 10 seconds |

Check Service Quotas for your account limits: `aws lambda get-account-settings`

## Troubleshooting Quick Reference

| Error                               | Cause                          | Solution                                                                                                                                        |
| ----------------------------------- | ------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `Build Failed`                      | Missing dependencies           | Run `sam build --use-container`                                                                                                      |
| `Stack is in ROLLBACK_COMPLETE`     | Previous deploy failed         | Delete stack with `aws cloudformation delete-stack`, redeploy                                                                                   |
| `IteratorAge` increasing            | Stream consumer falling behind | Increase `ParallelizationFactor` and `BatchSize`. See [optimization.md](references/optimization.md)                                                                            |
| EventBridge events silently dropped | No DLQ, retries exhausted      | Add `RetryPolicy` + `DeadLetterConfig` to rule target                                                                                           |
| Step Functions failing silently     | No retry on Task state         | Add `Retry` with `Lambda.ServiceException`, `Lambda.AWSLambdaException`                                                                         |
| Durable Function not resuming       | Missing IAM permissions        | Add `lambda:CheckpointDurableExecution` and `lambda:GetDurableExecutionState` — see [durable-functions skill](../aws-lambda-durable-functions/) |

For detailed troubleshooting, see [references/troubleshooting.md](references/troubleshooting.md).

## Configuration

### AWS CLI Setup

This skill requires that AWS credentials are configured on the host machine:

**Verify access**: Run `aws sts get-caller-identity` to confirm credentials are valid

### SAM CLI Setup

1. **Install SAM CLI**: Follow the [SAM CLI installation guide](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
2. **Verify**: Run `sam --version`

### Container Runtime Setup

1. **Install a Docker compatible container runtime**: Required for `sam local invoke` and container-based builds
2. **Verify**: Use an appropriate command such as `docker --version` or `finch --version`

### CLI access

Commands run through the SAM CLI, CDK CLI and AWS CLI (mapping in `~/.agents/skills/aws/SKILL.md`, "Tools"). Local commands (`sam init`, `sam build`, `sam validate --lint`, `sam local invoke`, `cdk synth`) need no approval. Anything that changes an account (`sam deploy`, `sam delete`, `cdk deploy`, `cdk destroy`) needs the user's explicit yes for that command, with account, region and stack named. Lambda and API Gateway logs (`sam logs`, `aws logs tail`) can hold customer data, so read them only when the task needs them and the user agreed to that account.

### SAM template validation (replaces the plugin hook)

After every edit to a `template.yaml` or `template.yml`, run `sam validate --template <file> --lint` (local cfn-lint check, no AWS call) and fix what it reports before moving on. If `sam` is missing, say so and skip the check.

## Language selection

Default: TypeScript

Override syntax:

- "use Python" → Generate Python code
- "use JavaScript" → Generate JavaScript code

When not specified, ALWAYS use TypeScript

## IaC framework selection

Default: CDK

Override syntax:

- "use CloudFormation" → Generate YAML templates
- "use SAM" → Generate YAML templates

When not specified, ALWAYS use CDK

### SAM or CDK CLI missing

- If `sam` (or `cdk`) is missing, say so and give the install command from `~/.agents/skills/aws/SKILL.md` ("Tools"); don't install it without the user's yes
- Continue with the guidance that needs no CLI (templates, code, reviews) meanwhile

## Resources

- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)
- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [AWS Lambda Powertools](https://docs.aws.amazon.com/powertools/)
- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
