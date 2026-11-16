# Sources

## Functional requirements come from
Business needs and user stories. In practice: issue tracker (epics, stories, acceptance
criteria), product/PRD docs, wikis, `docs/specs/`, README, API specs (OpenAPI, GraphQL SDL,
proto), e2e and integration tests (the most honest FR record in most repos), feature flags,
admin/CLI surfaces, changelogs, release notes.

## Non-functional requirements come from
Technical constraints, business goals, user expectations. In practice: SLAs and customer
contracts, SLOs/error budgets, dashboards and APM (p50/p95/p99, throughput, error rate,
saturation), error tracker, incident reports and post-mortems, on-call runbooks, load and
soak test results, capacity plans and cloud bills, autoscaling/replica/timeout/retry config,
rate limits, retention and residency rules, auth model, compliance scope (PCI, SOC2, GDPR,
HIPAA), accessibility target, browser/device support matrix.

## Ask the user for what the sweep did not find
One batched request, then start with what you get:
- issue tracker + a link to the current epic/backlog (read access or an export)
- product/architecture docs, ADRs, design docs — where they actually live
- observability: APM, dashboards, log search, error tracker (read-only is enough)
- SLA text, contractual commitments, compliance obligations
- last 3–6 months of incidents/post-mortems, and the on-call rotation's pain list
- available MCP servers / integrations for the above
- who the stakeholders are for Phase 5 questions

## Rank evidence
running code + tests > merged PRs and ADRs > tickets > wiki > slide decks > verbal.
Cite `path:line`, ticket id, dashboard name, or doc + date for every claim. No citation ⇒
mark it `UNVERIFIED`. Requirements you inferred purely from code are `inferred` sourced —
they describe behavior, not intent, and intent is what stakeholders confirm.
