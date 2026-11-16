# Non-functional requirements

NFRs are **how well** the system does it. They shape the architecture; FRs ride on top.
They are hard to measure, need real technical expertise to state, and stay ambiguous — and
therefore unmet — until someone attaches a number.

## Make the subjective measurable
`<attribute> of <scope> <operator> <number><unit> at <load>, measured by <source> over <window>`

| Vague | Measurable |
|---|---|
| "fast" | checkout p95 < 300 ms at 200 rps, APM, 30-day |
| "highly available" | 99.9% monthly on the order API, excl. planned windows |
| "scalable" | 10k concurrent sessions, < 5 min to add capacity |
| "secure" | no criticals in SCA; auth on every non-public route; PII encrypted at rest |
| "maintainable" | new endpoint shippable in < 1 day; p95 CI < 10 min |

## Attributes to sweep for
Performance (latency, throughput, batch window) · availability + RTO/RPO · scalability +
capacity headroom · reliability (error budget, retry/idempotency, queue depth) · security +
privacy · compliance + data residency/retention · observability (what is actually alerted) ·
maintainability + deployability (lead time, change-fail rate) · cost per unit of work ·
portability/compatibility · usability + accessibility · i18n/l10n.

## For each NFR record
Current measured value and where it came from · the target · **where it is enforced**
(timeout, rate limiter, autoscaler, index, cache, circuit breaker, CDN, alert — or `none`)
· blast radius if it is missed. A target nothing enforces is an aspiration; say so.

## Cost discipline
Over-engineering an NFR is expensive: five nines is exponentially more complex and costly
than three. Align each target with an actual business need — a contract, a real user
expectation, a revenue or compliance consequence. Flag both directions:
`gold-plated` (target far above need, paid for in complexity) and `under-served`
(a Must with no enforcement and no alert). Note the trade-off each target forces
(latency vs consistency, cost vs redundancy, throughput vs durability).
