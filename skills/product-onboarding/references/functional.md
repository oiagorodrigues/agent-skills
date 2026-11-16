# Functional requirements

FRs are the system's **verbs**: actions a user can take, tasks the system must perform.
They tell developers what to build and testers what to validate.

## Shape
`<actor> can <verb> <object> [under <condition>] → <observable outcome>`

- Objective and testable. If you cannot write a pass/fail check for it, it is not an FR yet.
- One behavior per FR. Split anything joined by "and".
- No implementation in the statement (that goes in the mapping column).
- Include the negative rules that are really behavior: validation, authorization,
  idempotency, what happens on conflict or failure.

Bad: "the system handles orders properly".
Good: `FR-12 A buyer can cancel an order while status = PENDING; stock is returned and the
payment authorization is voided.`

## Extraction order
1. API surface — routes/handlers/CLI/queue consumers = the capability list.
2. E2E + integration tests — asserted behavior, already testable.
3. Stories and acceptance criteria — intent and edge cases.
4. Domain model + invariants (schema constraints, state machines).
5. Scheduled jobs, webhooks, events — behavior with no user in front of it.

## Map every FR to code
For each FR record the owning component and the entry point, e.g.
`POST /orders/:id/cancel → routes/orders.js:88 → services/order.js:cancel → repo/order.js`.
This is the point of the exercise: it tells an architect which part of the backend answers
for which behavior, and where a change lands. Unmapped FR ⇒ status `missing` or
`UNVERIFIED`, never a silent pass.

## Also record
Actor/role · trigger · preconditions · failure behavior · the test that proves it
(`test/path:name`, or `none` — "no test" is a finding worth reporting).
