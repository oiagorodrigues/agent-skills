---
name: local-emulator
description: Runs AWS Emulator (aws/aws-emulator, AWS's local emulator of the AWS APIs) in Docker on this Mac with telemetry off, and points the AWS CLI, boto3, the JS SDK v3, SAM and CDK at it. Use when testing code against AWS services locally or in CI without an AWS account, in projects that don't name another emulator.
---

# Local AWS Emulator

AWS Emulator serves the AWS APIs on `https://127.0.0.1:9297` from memory, as one account (`000000000000`). Use it to test code that calls AWS without touching a real account. Docs: https://docs.aws.amazon.com/emulator/latest/userguide/what-is-service.html

If the workspace, repo or its docs say to use another emulator (for example LocalStack, `moto` or a `docker-compose` service), use that one and skip this topic.

Requests to the emulator don't reach AWS, so the Safety rules' yes-before-a-write rule doesn't apply to them. It applies again the moment a command could reach a real account: check `AWS_ENDPOINT_URL` is set in the same command or script before any write.

## Start and stop

The launcher is `~/.agents/bin/aws-emulator`. It runs the pinned image `aws-emulator:<version>` as container `aws-emulator-<port>`, published on `127.0.0.1` only, with telemetry off three ways (`~/.aws/emulator/config.toml` with `[telemetry] enabled = false`, `EMULATOR_TELEMETRY=off`, `--telemetry off`).

```bash
aws-emulator start        # waits for the health check, prints the telemetry line
aws-emulator status       # container and health
aws-emulator logs
aws-emulator stop         # SIGTERM: the emulator deletes its keys and cert; all resources are gone
aws-emulator build [ver]  # rebuild; verifies AWS's GPG signature on the package before installing
```

`start 9300` runs a second emulator on another port. Each run makes new keys and a new certificate in `~/.aws/emulator/<port>/`. State lives in memory, so restart for a clean slate. Check that the startup line says `telemetry: disabled`.

## Point clients at it

Set these in the same command or script that runs the code, never in a shell profile. They replace your AWS config and credentials for that process only. Use the emulator's own keys: with auth on (the default), dummy keys like `test` get `AccessDenied`.

```bash
E=~/.aws/emulator/9297
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_PROFILE
export AWS_ENDPOINT_URL=https://127.0.0.1:9297 \
  AWS_SHARED_CREDENTIALS_FILE=$E/emulator_credentials AWS_CONFIG_FILE=$E/config \
  AWS_CA_BUNDLE=$E/ca.pem AWS_EC2_METADATA_DISABLED=true \
  AWS_DISABLE_HOST_PREFIX_INJECTION=true AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1
aws sts get-caller-identity   # Account must be 000000000000; your own account ID means it hit AWS
```

- AWS CLI and boto3: the variables above are enough. `AWS_CA_BUNDLE` trusts the emulator's certificate; skip `--no-verify-ssl`.
- JS SDK v3 (Node): also `export NODE_EXTRA_CA_CERTS=$E/ca.pem`, and create clients with `disableHostPrefix: true`.
- Keep `127.0.0.1` in the endpoint, never `localhost`: with a host name, the JS, Java and Go SDKs put S3 bucket names in the host and the request misses the emulator. S3 Control can't be reached at all.
- SAM CLI: the same variables plus `SAM_CLI_TELEMETRY=0`; `sam deploy` then creates the stack in the emulator. The emulator docs don't cover SAM; this was checked by deploying an SQS queue.
- CDK CLI: the same variables plus `NODE_EXTRA_CA_CERTS=$E/ca.pem` and `CDK_DISABLE_CLI_TELEMETRY=true`; `cdk bootstrap aws://000000000000/us-east-1` works. The emulator docs don't cover CDK, and its fidelity docs say CloudFormation, CDK and Terraform support varies by service.
- Java, Rust, .NET: see the per-SDK table at https://docs.aws.amazon.com/emulator/latest/userguide/point-sdk-to-emulator.html#point-sdk-ca

Use one region per emulator; it doesn't separate resources by region or account.

## Check fidelity before relying on a service

1. List the AWS operations the workflow calls.
2. Find their fidelity tests in `manifest.jsonl` in https://github.com/aws/aws-emulator-evaluation-suite.
3. Read the service's score for the installed version: `gh release view v<version> -R aws/aws-emulator` (the scores are in its `scores.json.gz` asset). Compare scores only across the same fidelity-test version.
4. For operations no test covers, run the same test against the emulator and against a sandbox AWS account (a real-account run follows the Safety rules) and compare.

An unimplemented operation returns HTTP 501 `NotImplemented`. Control-plane calls (create, describe, update, delete) match AWS more closely than data-plane calls. Details: https://docs.aws.amazon.com/emulator/latest/userguide/check-project.html

## Security

Don't use the emulator to test security. It never denies a request signed with its own keys and doesn't evaluate IAM, bucket or KMS key policies the way AWS does, so test those on real AWS. Keep real credentials and real data out of it. Function code it runs isn't isolated from this machine. Keep auth on (no `--auth off`).

Security fixes ship only in the latest release. To upgrade, read the release notes, then `aws-emulator build <version>` and update `VERSION_DEFAULT` in the launcher.
