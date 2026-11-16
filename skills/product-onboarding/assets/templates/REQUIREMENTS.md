# <Product> — reconstructed requirements

**Status: DRAFT — unconfirmed.** Reconstructed from code and documents on <date> by
onboarding sweep. Not authoritative until stakeholders confirm the Assumptions and answer
the Open questions below.

Sources read: <docs, tracker, dashboards, SLA, incidents>  ·  Not available: <gaps>

## 1. What the system is
Three lines max: the domain, the actors, the money/value path.

## 2. Functional requirements

Status: `implemented` `partial` `drifted` `missing` `undocumented` `UNVERIFIED`
MoSCoW: `M` `S` `C` `W`

| ID | Requirement | Actor | Source | Code evidence | Test | Status | MoSCoW |
|----|-------------|-------|--------|---------------|------|--------|--------|
| FR-01 | A buyer can cancel an order while status = PENDING; stock returns, auth voided | buyer | docs/specs/03-orders.md:44 | routes/orders.js:88 → services/order.js:cancel | test/orders.test.js:cancel-pending | implemented | M |
| FR-02 | <one verb, one actor, one testable outcome> | <role> | <doc:line / TICKET-123 / inferred> | <path:line, or NONE> | <test:name / none> | <status> | <M> |

## 3. Non-functional requirements

Every target carries a number, a unit, and a measurement window.

| ID | Attribute | Target | Measured | Source | Enforced at | Status | MoSCoW |
|----|-----------|--------|----------|--------|-------------|--------|--------|
| NFR-01 | Checkout latency | p95 < 300 ms at 200 rps | p95 412 ms (APM, 30d) | SLA §4 | none | drifted | M |
| NFR-02 | Order API availability | 99.9% monthly, excl. planned | 99.94% (90d) | contract | 3 replicas + HC | implemented | M |

### Cost check
`gold-plated` (target above business need) and `under-served` (Must with no enforcement),
one line each with the trade-off it forces.

## 4. Drift

| Requirement | Doc says (date) | Code does | Superseding decision | Verdict |
|-------------|-----------------|-----------|----------------------|---------|
| FR-07 | doc:12 (2024-03) | path:line | commit abc123 / ADR-4 / none | doc stale / code regressed / undecided |

## 5. Component map
Which part of the backend answers for which FRs — one line per component, IDs listed.
Note anything owning requirements it should not.

## 6. Risks and first suggestions
Ranked. Each: the requirement it threatens, the evidence, the smallest fix. No redesigns.

## Assumptions
Numbered, one line each. What I assumed, and what changes if it is wrong.

## Open questions
`Q1 (stakeholder) — <question> Assumed <X> from <evidence>; if wrong, <impact>.`
