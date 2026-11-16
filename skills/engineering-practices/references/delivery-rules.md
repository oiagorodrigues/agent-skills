# Delivery rules, explained

Read this when a rule in the "How to work", "Feature flags and config" or "Commits, PRs and review" sections of `SKILL.md` points here and you need the reasoning or an example. Each rule has the why, a bad and a good example, and its source (the books are in `books.md`).

## Contents

1. Tracer bullet: one thin path end to end first
2. Tidy first, as its own PR
3. Roll out risky changes to a slice first
4. Write an ADR only when it earns one

## 1. Tracer bullet: one thin path end to end first

For work across several layers (UI, API, service, storage), build one thin path that goes through all of them and runs, before filling in any layer. The mismatches between layers (a field name, a date format, an auth rule) show up on the first day instead of at integration, and every later piece extends running code.

Bad: each layer lands complete and alone, and they meet at the end.

```text
PR 1: schema and all twelve report queries
PR 2: the API for all of them
PR 3: the UI, where the date-range format the API expects turns out to differ
```

Good: one field travels the whole path behind the flag, then the slice widens.

```ts
// api: one route
router.get("/reports/sales", requireFlag("sales_report"), async (req, res) => {
  res.json(await salesReport.summary(req.companyId));
});

// service: one real query
export async function summary(companyId: CompanyId): Promise<{ total: string }> {
  return { total: await orders.sumTotals(companyId) };
}

// ui renders report.total; the next PRs add filters, columns and the other queries
```

Source: The Pragmatic Programmer, "Tracer Bullets".

## 2. Tidy first, as its own PR

When a rename, an extract or a move would make a behavior change smaller and easier to review, do the tidying first, in a separate PR that changes no behavior and lands before the behavior change. Propose it to the user and wait for the yes; never fold it into the feature PR or do it on your own initiative. The separate PR is the only form that survives, because a squash merge erases separate commits.

Bad: one PR where the three-line rule change hides among renames and moves.

```text
feat(billing): tax by ship-to state
  40 files changed: billing/utils.py renamed and split, 37 imports updated,
  and somewhere in billing/invoice_total.py the tax line changed
```

Good: two PRs.

```diff
# PR 1, structure only: rename and move, tests unchanged and green
-from billing.utils import calc
+from billing.invoice_total import compute_invoice_total
```

```diff
# PR 2, behavior only: the reviewer reads three lines
-    tax = subtotal * TAX_RATE
+    tax = subtotal * tax_rate_for(invoice.ship_to_state)
```

Source: Tidy First? (Beck).

## 3. Roll out risky changes to a slice first

A risky change (pricing, auth, a data write path, a new dependency in the hot path) goes to a slice first: one internal tenant, a small flag percentage or a canary instance. Before turning it on, name the metric that would show it broke and how long to watch it, and widen only after that metric holds. A full rollout at once turns every bug into an incident for every customer.

Bad: all or nothing.

```python
if flags.is_enabled("new_pricing"):
    return new_price(order)
```

Good: a targeted flag, with the watch plan written in the PR.

```python
if flags.is_enabled("new_pricing", company_id=order.company_id):
    return new_price(order)
```

```text
Rollout: internal test company, then 5% of companies, then all.
Watch for 24 hours at each step: checkout 5xx rate and the count of
price-mismatch log lines for flagged companies. Roll back if either rises.
```

Source: Site Reliability Engineering and The Site Reliability Workbook (Google), canarying releases.

## 4. Write an ADR only when it earns one

An ADR is worth its upkeep only when the decision is hard to reverse, would surprise a future reader, and came from a real trade-off between options; such decisions are usually about structure, contracts, dependencies or non-functional requirements. If any of the three is missing, skip the ADR: an easy-to-reverse or obvious choice belongs in the PR description. An ADR holds the context, the options considered and the consequences. ADRs are append-only: a later decision supersedes one with a new ADR instead of editing it.

Bad: an ADR for a choice that is cheap to undo and surprises nobody.

```markdown
# ADR-014: Use pytest fixtures for order tests
```

Good: hard to reverse (stored data changes), surprising (the rest of the code uses decimals) and chosen between real options.

```markdown
# ADR-015: Store money as integer cents in the payments service

Context: amounts cross three services and two languages; one of them has no decimal type.
Options: decimal strings, integer cents, a money library per service.
Decision: integer cents, with the currency stored next to every amount.
Consequences: every boundary converts; existing decimal columns need a migration.
```

Source: Matt Pocock's domain-modeling skill (MIT, https://github.com/mattpocock/skills), on when a decision deserves an ADR.
