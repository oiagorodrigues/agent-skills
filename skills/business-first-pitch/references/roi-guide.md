# ROI without fiction — quick reference

## Measure business value in four separate buckets

| Bucket | Examples | Can count as ROI? |
| --- | --- | --- |
| Cash savings / avoided spending | Reduced infra bills, tool licenses canceled, contractor spending no longer required | Yes, if demonstrably realized |
| Risk-adjusted avoided loss | Reduced expected cost of incidents, outages, penalties (frequency × impact) | Yes, but clearly label estimate/uncertainty |
| Capacity freed | Fewer manual steps, fewer on-call hours, faster processing | Only monetize with evidence of avoided spend or incremental contribution; otherwise report hours |
| Strategic / nonfinancial | Better customer experience, trust, agility, availability, employee satisfaction | Track separately unless credible economic causality is established |

Don't double-count: a recovery hour cannot simultaneously be counted as reduced payroll, new sales and avoided contractor expense unless truly independent. Gross revenue is not profit; if modeling new sales use **incremental contribution margin**, not the entire sale amount.

## Core formulas — same currency and horizon

For a 12-month, steady-state illustrative model:

- `Annual gross quantifiable benefit = annual cash savings + annual validated capacity value + annual expected losses avoided + annual incremental contribution profit`
- `Annual ongoing incremental cost = extra cloud / infrastructure + tools + operations + support + maintenance + human review` (net of *existing* operating costs already counted as savings)
- `Total Year-1 costs = one-time implementation / migration / training / dual-running costs + annual ongoing incremental cost`
- `Year-1 net value = gross Year-1 benefits - Year-1 costs`
- `Year-1 ROI = Year-1 net value / Total Year-1 costs × 100%`, only if total costs > 0
- `Simple payback (months) = 12 × one-time costs / (annual gross quantifiable benefits - annual ongoing incremental costs)`, only if positive annual net recurring benefits, benefits accrue evenly, and no ramp-up. Otherwise payback not estimated.
- When costs decrease relative to current state, represent avoided costs on benefit side, and avoid counting them twice.

This is a simple directional ROI, **not** discounted NPV/IRR or financial forecast. If rollout ramps or changes risk over time, use a monthly cash-flow model instead; don't present simple payback as precise.

## Evidence hierarchy

1. Actual invoices / incident logs / customer behavior / support data / work hours measured.
2. Short PoC or controlled pilot, with agreed success criteria.
3. Credible comparable benchmarks, explicitly labeled non-transferable assumptions.
4. Expert estimates, clearly labeled assumptions.
5. No evidence: do not calculate a numerical ROI.

For three scenarios, vary only explicitly stated assumptions and show the differences. Don't attach made-up probabilities or precise percentages to low-confidence estimates.

## Reliability / external reporting example — needed baseline

- Reports/month; P50/P95 report wait; incident or error counts/month; retry rates; affected customers.
- Does the delay cause support tickets, refunds, contractual breaches, overtime, lost contribution profit, or measurable churn? How much, based on data?
- Engineering build hours × loaded cost, AWS/infra ongoing delta, parallel run, observability, maintenance, failure modes, rollout risk.
- Pilot success: measure improvement in P95 and failures without unacceptable cost, operational or delivery impact.
- With no validated financial consequence, lead with **risk/reliability and time saved**, and state ROI pending evidence.

## Questions to ask in discovery (pick one, not all)

- "What is this problem costing the business today, even if roughly?"
- "What would you need to see to prioritize this over our planned roadmap?"
- "Which customers or operational workflows actually feel this pain?"
- "What pilot result would make a rollout worthwhile?"

## Source principles

- AWS Well-Architected: quantify business value, not only cost savings: https://docs.aws.amazon.com/wellarchitected/latest/framework/cost_cloud_financial_management_quantify_value.html
- AWS Cloud Value Framework: TCO, staff productivity, operational resilience, business agility: https://aws.amazon.com/economics/
- AWS directional business case: TCO, ROI, NPV, payback when sufficient input exists: https://docs.aws.amazon.com/prescriptive-guidance/latest/application-portfolio-assessment-guide/directional-business-case.html
