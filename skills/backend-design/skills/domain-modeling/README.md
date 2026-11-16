---
name: domain-modeling
description: Use when a change adds or reshapes a domain concept, writes several rows under one business rule, or brings a third-party or legacy model into the code, in a Django and Postgres codebase. Sets the aggregate as the transaction and lock boundary, puts an anti-corruption layer at integrations, takes names from the domain glossary, says when a value needs its own type, and lists the DDD patterns to leave out.
---

# Domain modeling

Tactical domain-driven design (Evans, Vernon, Khononov), cut to the parts that change how Django and Postgres code is written. Paths are relative to `~/.agents/skills/`.

## Aggregate: one transaction, one lock

Name the invariant a write protects and the smallest set of rows it spans. That set is the aggregate: one parent row (the root) and the child rows only it owns.

- One transaction changes one aggregate, through one service function that starts from the root and checks the invariant before commit.
- Serialize writers on the root row (guarded update, version column or lock on the parent), never on a child, so every writer of the aggregate waits on the same row. This is the "lock parents before children" rule in `backend-design/skills/anti-patterns/README.md`.
- Only the root's service writes its children. Another app that calls `LineItem.objects.filter(...).update(...)` bypasses the invariant.
- Other aggregates are referenced by id and change after commit (`transaction.on_commit`, a task, an outbox event). When a rule really needs two aggregates in one transaction, say why in the PR and take their locks in the order the anti-patterns file lists.

Example: "an order's total equals the sum of its line items" spans `Order` and `OrderLineItem`. `add_line_item(order_id, ...)` runs `Order.objects.filter(pk=order_id, version=v).update(version=F("version") + 1)`, inserts the line and recomputes the total in one `atomic` block. Updating the buyer's `last_ordered_at` or a reporting row is another aggregate, so it runs in `on_commit`.

## Anti-corruption layer at integrations

Translate a vendor's or legacy system's model into your own types in one adapter module at the boundary. Domain code never branches on the vendor's field names, status strings or error codes, and an unknown vendor value raises in the adapter instead of mapping to a default.

Example: the payment provider returns `{"status": "requires_capture"}`. `payments/adapters/provider.py` maps it to `PaymentStatus.AUTHORIZED` and raises `UnknownProviderStatus` for anything it doesn't list, and the order service only ever sees `PaymentStatus`. A vendor upgrade then changes one file.

## Ubiquitous language in code

Name models, functions, API fields and tests with the domain term from the repo's glossary (`GLOSSARY.md`, or cartographer's `glossary.md`), or the word product and support use when there is no glossary. When code and business use different words for one thing, keep the code's existing term and tell the user about the mismatch instead of adding a third word.

When a term is fuzzy, ask which concept it means, test it with an edge-case scenario and check what the code does (from Matt Pocock's domain-modeling, MIT, https://github.com/mattpocock/skills).

Example: product says "buyer" and the model is `Customer`. A new field named `client_id` makes three words for one thing; name it `customer_id` and report the buyer/customer mismatch.

## Value objects

Give a value its own small immutable type only when it carries a rule: money with a currency, a quantity with a unit, a date range whose end follows its start, an identifier with a format. The type validates when it's built, so an invalid value can't exist. A plain id or a free-text name stays a primitive. The review-side smell is Primitive Obsession in `review-pr/references/code-smells.md`.

Example: `Money(amount: Decimal, currency: str)` as a frozen dataclass whose `__add__` raises on a currency mismatch, stored as `amount numeric(12, 2)` and `currency char(3)` columns, so `subtotal + tax` can't add dollars to euros.

## When not to use DDD patterns

- The Django model and its manager are the repository. Don't add a repository class per aggregate or map models to separate domain entities: it doubles every field and hides the `select_related` and `prefetch_related` calls that keep queries fast.
- No ports-and-adapters layer inside a Django app. The anti-corruption layer sits only at an external boundary.
- A bounded context stays a Django app or module inside the monolith, with a service interface. Splitting one into its own service has to pass `backend-design/skills/boring-by-default/README.md` (see also A2 in the anti-patterns file).
- Domain events inside the monolith are explicit calls registered with `on_commit`, never signals (D5 in the anti-patterns file).
- Don't rename existing code to pattern names (`OrderAggregate`, `OrderRepository`). Use the domain term.
- CRUD with no rule spanning rows needs none of this.

## See also

- `backend-design/skills/anti-patterns/README.md` for the lock gate, guarded updates and A4 (anemic and leaky models).
- `backend-design/skills/data-modeling-discipline/README.md` for enforcing the invariant in the schema.
- `backend-design/skills/idempotency-and-side-effects/README.md` for the outbox that carries cross-aggregate changes.
