#!/usr/bin/env bash
# Cheap, language-agnostic inventory. Names of things only — read the files you need after.
set -uo pipefail
cd "${CLAUDE_PROJECT_DIR:-$PWD}" || exit 1
p() { printf '\n== %s ==\n' "$1"; }
ls_f() { git ls-files 2>/dev/null || find . -type f -not -path './.git/*' -not -path '*/node_modules/*'; }
X='--exclude-dir=node_modules --exclude-dir=.git --exclude-dir=dist --exclude-dir=build --exclude-dir=vendor --exclude-dir=target --exclude-dir=.venv --exclude-dir=coverage --exclude-dir=generated --exclude-dir=.next --exclude-dir=__pycache__'
g() { grep $X "$@" 2>/dev/null; }

p "repo";        git log --oneline -5 2>/dev/null; git ls-files 2>/dev/null | wc -l | sed 's/^/files: /'
p "manifests";   ls package.json pyproject.toml go.mod Cargo.toml pom.xml build.gradle Gemfile composer.json 2>/dev/null
p "docs";        ls_f | grep -Ei '(^|/)(docs?|adr|rfc|specs?|wiki)/|README|CHANGELOG|ARCHITECTURE|DECISION' | head -60
p "requirements-ish"; g -rlEi 'user stor|acceptance criteri|as a .*i want|must (have|support)|shall ' --include='*.md' --include='*.txt' . 2>/dev/null | head -30
p "api surface"; g -rnE "(app|router|r)\.(get|post|put|patch|delete)\(|@(Get|Post|Put|Patch|Delete|RequestMapping)|def (get|post|put|delete)|path\(|route\(" --include='*.js' --include='*.ts' --include='*.py' --include='*.go' --include='*.java' --include='*.rb' . 2>/dev/null | head -60
p "api specs";   ls_f | grep -Ei 'openapi|swagger|\.proto$|schema\.graphql|asyncapi' | head -20
p "async work";  g -rlEi 'cron|schedule|worker|consumer|queue|kafka|sqs|rabbit|bull|celery' --include='*.js' --include='*.ts' --include='*.py' --include='*.go' --include='*.yml' --include='*.yaml' . 2>/dev/null | head -25
p "data model";  ls_f | grep -Ei 'schema\.prisma|migrations?/|\.sql$|models?\.(py|rb|go|ts|js)$' | head -30
p "tests";       ls_f | grep -Ei '(test|spec|e2e|cypress|playwright)' | head -40
p "nfr signals"; ls_f | grep -Ei 'slo|sla|budget|loadtest|k6|jmeter|gatling|locust|benchmark|dashboard|alert|grafana|prometheus|datadog|runbook|incident|postmortem|post-mortem|oncall|on-call|threat|compliance|soc2|gdpr|pci' | head -40
p "ops config";  ls_f | grep -Ei 'dockerfile|docker-compose|\.tf$|k8s|kubernetes|helm|\.github/workflows|nginx|terraform|serverless' | head -30
p "runtime knobs"; g -rnEi 'timeout|retry|rate.?limit|circuit|replicas|maxPool|cache|ttl' --include='*.yml' --include='*.yaml' --include='*.tf' --include='*.json' --include='*.env*' . 2>/dev/null | head -30
p "env contract"; ls .env.example .env.sample 2>/dev/null && grep -hE '^[A-Z_]+=' .env.example .env.sample 2>/dev/null | cut -d= -f1 | head -40
