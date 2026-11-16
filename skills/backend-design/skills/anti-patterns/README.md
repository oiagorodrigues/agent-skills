---
name: anti-patterns
description: Catalog of backend anti-patterns in Django, DRF and Postgres code (locks, transactions, side effects, serializers that write other models, signals, querysets, migrations, service boundaries), each with why it hurts, grep-able signs in a diff, the preferred alternative and when the pattern is fine. Holds the gate for adding a lock. Use before writing or reviewing a backend fix for a race, deadlock, duplicate or Sentry error, and when a diff adds a lock, a save() override, a signal, a serializer write or a transaction.
---

# Backend anti-patterns

Each entry gives the smell, why it hurts, how to spot it in a diff, what to write instead, and when the pattern is fine. Entries that other files already cover in depth point there instead of repeating them. Paths are relative to `~/.agents/skills/`. When the workspace skill for the repo has a "Values for backend-design" section, read it too: it names the repo's own rules that win over this file, its lock-order inventory and worked examples for these entries.

"The code next to it does the same" is never a reason on its own. An older codebase has many of these patterns already, and copying them is how the lock fixes in the "Adding a lock" section go wrong. Name the alternative you weighed and why it lost.

## Contents

- Scan a diff
- Adding a lock (the gate)
  - The whiteboard defense
  - Alternatives, in the order to try them
  - Lock order in the repo
  - If the lock stays
- Concurrency and transactions
  - C1 Read, change in Python, save
  - C2 Check, then insert
  - C3 Catching a database error inside `atomic`
  - C4 Transaction wider than the writes
  - C5 Side effects before commit
  - C6 Retrying inside the failed transaction
  - C7 Correctness that depends on an accident
  - C8 Locking rows one at a time in a loop
  - C9 Session-level advisory locks
  - C10 Testing a lock in `TestCase`
- Django ORM and DRF
  - D1 N+1, unbounded querysets, write loops
  - D2 Serializers that write models they don't own
  - D3 Business logic in views and serializers
  - D4 `save()` overrides that write other rows
  - D5 Signals as hidden coupling
  - D6 Bulk calls that skip `save()` by surprise
  - D7 Querysets evaluated more than once, or cached when you need fresh rows
  - D8 `F()` left on an instance
  - D9 Queryset methods that ignore their queryset
- Postgres and SQL
  - P1 Migrations that lock hot tables
  - P2 Missing indexes, OFFSET pagination, non-sargable filters, wide selects
- Architecture
  - A1 Shared database across services
  - A2 Distributed monolith
  - A3 God modules
  - A4 Anemic and leaky domain models
- Sources

## Scan a diff

Run this on the branch and read the entry for each hit. It prints each changed file's `+++` line followed by its added lines that match. A hit is a lead, so confirm it in the code before calling it a finding.

```bash
git diff origin/main...HEAD -U0 -- '*.py' ':!*tests*' | grep -E '^\+' | grep -E \
  '^\+\+\+ |select_for_update|FOR (NO KEY )?UPDATE|FOR (KEY )?SHARE|LOCK TABLE|pg_(try_)?advisory|\.lock\(|setnx|nx=True|cache\w*\.add\(|transaction\.atomic|ATOMIC_REQUESTS|\.delay\(|apply_async|send_mail|requests\.(get|post|put|patch)|@receiver|post_save|pre_save|\.connect\(|def save\(|def (create|update|validate)\(|\.save\(|objects\.create|get_or_create|update_or_create|except (Exception|IntegrityError|DatabaseError)|bulk_(create|update)|\.update\(|F\(|for .* in .*(objects|_set|\.all\(\))'
```

Lock hits go to "Adding a lock". `def create(`, `def update(` and `def validate(` hits inside a serializer go to D2. `.save()` or `objects.create` inside `def save(` goes to D4.

## Adding a lock (the gate)

A lock here means `select_for_update`, raw `FOR UPDATE`/`FOR SHARE`, `LOCK TABLE`, `pg_advisory_*`, or a cache or Redis lock (`.lock(`, `setnx`, `set(..., nx=True)`, `cache.add` with a lock-named key). Widening an existing lock (more rows, earlier in the transaction, held longer, `FOR UPDATE` where `NO KEY` was enough) counts too.

Every new lock adds a lock order that all other code touching those rows must follow, or Postgres kills one side with `deadlock detected`. In one codebase, four PRs each fixed one Sentry error with a lock, and review found a new deadlock or a longer wait in each: an order merge against a draft submit, a cart update against checkout, a child-product edit against fulfillment, and a product update against order edits.

When you are fixing a bug and the fix you reach for is a lock, stop before writing it. Write the whiteboard defense below and show it to the user. The lock goes in only after a person accepts the defense, and the PR stays a draft until a human reviewer approves the lock. An agent review never clears it. The review side of the same check is `review-pr/references/mechanism-defense.md`.

When the repo has its own concurrency rule (an agent rules file such as `.cursor/rules/` or `CLAUDE.md`, or a CI label that flags PRs adding a lock), it wins where it differs from this file. The workspace skill for the repo, when one exists, names it. This section adds the lock-order inventory and the proof it doesn't spell out.

### The whiteboard defense

Write all four in the PR description, short enough to draw on a whiteboard.

1. The race. The two operations, the interleaving that breaks (who reads, who writes, in what order), and the evidence it happens: the Sentry issue and event count, log lines, or a reproduction. "Two requests could collide" with no evidence is a hypothesis, so prove it first.
2. The alternatives. Each option from the list below that could apply, and the specific reason it fails on this code. "Lock is simpler" is not a reason.
3. The lock order. Every other code path that locks or writes the same rows and tables, the order each takes its locks in, and why the new lock can't close a cycle with any of them. Include implicit locks: every `UPDATE` takes `FOR NO KEY UPDATE` on its rows, a `save()` is an `UPDATE`, and Django's Postgres foreign keys are `DEFERRABLE INITIALLY DEFERRED`, so an insert that references a row takes `FOR KEY SHARE` on it at `COMMIT`. A plain `FOR UPDATE` conflicts with that `KEY SHARE`.
4. The proof. A test that runs the two operations on two real connections, fails or deadlocks on the base branch and passes on the branch, plus one test per other locker from step 3 showing they still don't deadlock. If a test can't run, say why and what stands in for it.

Template for the PR description:

```markdown
### Why a lock
Race: <A> and <B> both <read/write X>; when <interleaving>, <bad outcome>. Evidence: <Sentry issue, N events in 90 days / repro>.
Rejected: unique constraint (<why>), guarded update (<why>), F() (<why>), idempotency key (<why>), on_commit (<why>), separate the state (<why>).
Lock order: this takes <rows> in <order>. Other lockers of these rows: <path:line takes ... in ... order>, ... No cycle because <reason>.
Proof: <test name> deadlocks/fails on main, passes here. <other test names> cover <other lockers>.
```

### Alternatives, in the order to try them

1. Separate the state. Ask whether the two actors need the same mutable row at all. If each one publishes its own fact (its own row, column or key), merge at read time and there is nothing to lock. Serialize only when one shared value is a real invariant. (From Lauren Tan's pstack `principle-separate-before-serializing-shared-state`, MIT.)
2. Unique constraint, when the race creates a duplicate. Add the constraint (with `CREATE UNIQUE INDEX CONCURRENTLY` on a big table), insert inside its own `transaction.atomic()`, catch `IntegrityError` outside that block, and return the existing row or a 400. See C2 and C3.
3. Guarded update (compare-and-set), when the race changes state. Put the expected state in the filter and check the row count: `Order.objects.filter(id=pk, state=SUBMITTED).update(state=ACCEPTED)`. Under READ COMMITTED an `UPDATE` that waited on a locked row re-evaluates its `WHERE` against the committed version, so the check and the write are one step. Fewer rows than expected means another request won, which becomes a 400. Worked example: an order-merge fix that first added a lock moved, after review, to a guarded update of the merged-into column on rows it already held, with no new lock and no lock-order change.
4. `F()` expression, for counters and totals: `.update(quantity=F("quantity") - n)`, with a `filter(quantity__gte=n)` guard when the value must not go negative.
5. Optimistic version column, for a long edit (a form a user holds open). Add `version`, update with `filter(pk=pk, version=v).update(..., version=F("version") + 1)`, and return 409 when it matches 0 rows.
6. Idempotency key, for a retried or double-submitted request. The second request with the same key returns the first result. A `cache.add` on the key is the smallest version. The full contract is in `backend-design/skills/idempotency-and-side-effects/README.md`.
7. `transaction.on_commit`, so emails, webhooks and tasks run once, after the winning transaction commits (C5).
8. `SKIP LOCKED`, for a worker claiming jobs from a table, so workers never wait on each other (`postgres-best-practices/references/lock-skip-locked.md`).
9. Retry the whole transaction on `40P01` (deadlock) or `40001` (serialization failure), with capped exponential backoff and jitter, when the deadlock is rare and the operation is idempotent. It hides a cycle instead of removing it, so log every retry (C6).

### Lock order in the repo

Before claiming "no cycle", list every explicit lock on current `main`: `git grep -nE 'select_for_update|pg_advisory|FOR (NO KEY )?UPDATE' -- '*.py' ':!*tests*'`. For each hit, note which rows it locks and in what order. The workspace skill for the repo, when one exists, may hold an inventory of the known lockers; check each line there on current `main`, because lines move.

The usual lockers in an order system, as a starting list:

- Fulfillment locks the order's products, ordered by `id`, then inventory rows by `id`.
- State transitions lock the order row first.
- Order numbers come from an advisory lock per seller and buyer, so every order creation for that seller waits on it.
- Checkout splits and deletes cart rows while a cart update locks the cart.
- A child row's save writes its parent and a parent's save writes each child, so the two deadlock with no explicit lock (D4).

The rule that resolves most of these: lock parents before children, lock several rows in one statement ordered by `id`, and lock in the same order as the busiest existing locker (often fulfillment).

### If the lock stays

- Lock the fewest rows, in one query, ordered by primary key: `Model.objects.filter(pk__in=ids).order_by("pk").select_for_update(...)`. Never lock "every item of the product" when the caller writes one.
- Use `select_for_update(no_key=True, of=("self",))` unless you change a key column or delete the row. `no_key` lets inserts that reference the row (FK checks) proceed; `of=("self",)` stops `select_related` rows from being locked too, and a `select_related` on a nullable FK makes `FOR UPDATE` fail outright.
- Take the lock after validation and as late as possible, and before the first write to those rows, since the first lock on a row should be the strongest one the transaction needs.
- Hold it only for the writes. No HTTP call, email, vendor API, Celery `.delay()` or loop over every row a company owns while it's held.
- Bound the wait: `nowait=True` for "someone else is doing this, return 409", or `SET LOCAL lock_timeout` for a short wait. An unbounded wait turns a slow request into a pile-up.
- Fence a lock that has a TTL. A cache or Redis lock (`cache.add`, `.lock(timeout=...)`) can expire while its holder still writes, after a slow query, a GC pause or a vendor call, and a second holder then writes too. Hand each holder a token that increases with every grant (`INCR` on a counter key) and make the write reject a stale one: `filter(pk=pk, fence__lte=token).update(..., fence=token)` matching 0 rows means a newer holder took over. Row locks and `pg_advisory_xact_lock` end with their transaction, so they need no token.
- One lock helper per row family, shared by every caller, so the order lives in one place. A copy of the order in a second function with a comment tying them together breaks the first time someone edits one side.

## Concurrency and transactions

### C1 Read, change in Python, save

The code loads a row, computes a new value in Python and calls `save()`.

- Why: two requests read the same value and the second save overwrites the first. `save()` without `update_fields` also writes every column, so it overwrites fields another request changed.
- Spot: `obj.field = obj.field + x` or `-=` followed by `obj.save()`; `save()` with no `update_fields` in a service that changes one field.
- Instead: `F()` update or guarded update (alternatives 3 and 4). When you must save an instance, pass `update_fields`.
- OK when: the row is only ever written by one actor (a per-user draft) or the transaction already holds the row lock for another reason.

### C2 Check, then insert

`if not X.objects.filter(...).exists(): X.objects.create(...)`, or `get_or_create` on fields without a unique constraint.

- Why: both requests see "missing" and both insert. Django documents that `get_or_create` and `update_or_create` race unless the database enforces uniqueness.
- Spot: `.exists()` or `.first() is None` followed by `create`; `get_or_create(` on a model whose `Meta.constraints` has no matching `UniqueConstraint`.
- Instead: a unique constraint (partial, with `condition=`, when only some rows must be unique), then `get_or_create` or insert-and-catch as in C3. In raw SQL, `INSERT ... ON CONFLICT DO NOTHING` (`postgres-best-practices/references/data-upsert.md`).
- OK when: a duplicate is harmless and cleaned up later, and you say so.

### C3 Catching a database error inside `atomic`

`try: obj.save() except IntegrityError: ...` inside an outer `atomic` block, then more queries.

- Why: after a database error Postgres aborts the transaction, so the next query fails with `current transaction is aborted`, or Django thinks the block is fine and commits half the work. Django's docs: "Avoid catching exceptions inside atomic!"
- Spot: `except (IntegrityError|DatabaseError|OperationalError)` with no `with transaction.atomic():` directly inside the `try`.
- Instead: wrap only the risky statement in its own `transaction.atomic()` (a savepoint) and catch outside it.
- OK when: the `except` re-raises.

### C4 Transaction wider than the writes

`@transaction.atomic` on a whole view or service call that also validates, renders, calls vendors or loops over many rows.

- Why: every row lock is held until commit, so a wide transaction turns a fast write into a long lock and makes deadlock cycles more likely. An idle open transaction also blocks vacuum. Check `ATOMIC_REQUESTS` in the settings: when it is off, a new decorator is a deliberate widening.
- Spot: `@transaction.atomic` added to a function that contains `requests.`, a client call, `send_mail`, `render`, or a loop over a queryset; an `atomic` added to a function whose callers didn't run in one before.
- Instead: validate and fetch outside, open the transaction around the writes only, and move remote calls after commit (C5). When a function needs a caller's transaction, assert `connection.in_atomic_block` instead of opening a new one.
- OK when: everything inside is local writes that must succeed or fail together.

### C5 Side effects before commit

An email, webhook, cache write, Celery `.delay()` or vendor call inside a transaction.

- Why: if the transaction rolls back, the email is already sent. A Celery worker can start before the commit and not find the row (Celery's Django guide names this race). A slow vendor call holds every lock the transaction took (one review found a vendor HTTP call per product inside a `FOR UPDATE`).
- Spot: `.delay(`, `.apply_async(`, `send_mail`, `requests.`, `cache.set` lexically inside `with transaction.atomic()` or a function decorated with it.
- Instead: `transaction.on_commit(lambda: task.delay(pk))`, or `task.delay_on_commit(pk)` on Celery 5.4+ `DjangoTask`. Pass ids, not instances, so the task reads committed data. For effects that must not be lost if the process dies after commit, use the outbox in `backend-design/skills/idempotency-and-side-effects/README.md`.
- OK when: the effect is local and transactional (another row in the same database).

### C6 Retrying inside the failed transaction

A `try/except OperationalError: retry` around one statement inside `atomic`, or a retry decorator on a function that runs inside a caller's transaction.

- Why: a deadlock or serialization failure aborts the whole transaction, so retrying one statement can't work, and retrying a non-idempotent operation duplicates its effects.
- Spot: `retry`, `tenacity`, `backoff` or a `for attempt in range` around ORM calls; `except OperationalError` near `deadlock`.
- Instead: retry the whole transaction from outside the outermost `atomic`, only on SQLSTATE `40P01` and `40001`, with a cap and backoff with jitter, and only when the operation is idempotent. Log or count each retry so the hidden cycle stays visible.
- OK when: it is that outer retry.

To make an operation safe to retry, derive each step from the state that exists (read it, compare with the goal, apply the difference), so a second run finds nothing left to do (Lauren Tan's pstack `principle-make-operations-idempotent`, MIT).

### C7 Correctness that depends on an accident

The code is safe only because of a side effect nobody wrote on purpose: a cache reset by an unrelated `.update()`, a fresh read that happens to come later, an exception that happens to fire on the second request.

- Why: a refactor removes the accident and the double-write ships with green tests. One review found that a second combine failed only because `self.orders.update()` cleared the queryset cache and a later loop re-read the state.
- Spot: hard to grep. Ask, for each race fix, "which line makes the loser fail?" If the answer is not a line written for that purpose, it's this smell.
- Instead: make the check explicit where the rows are already held: a guarded update with a row-count check, raising a `ValidationError` from the service.
- OK when: never on purpose. Document it as a known gap if you can't fix it now.

### C8 Locking rows one at a time in a loop

`for item in items: Item.objects.select_for_update().get(pk=item.pk)` or a lock per product inside one transaction.

- Why: rows are locked in loop order, which differs between callers, so two transactions sharing two rows deadlock. One review found returns, restock and facility transfer still locking items one product at a time.
- Spot: `select_for_update` inside a `for` body; a lock helper called once per element of a list.
- Instead: collect every id first and lock them in one query ordered by `pk`.
- OK when: each iteration commits its own transaction.

### C9 Session-level advisory locks

`pg_advisory_lock` (session level) instead of `pg_advisory_xact_lock`.

- Why: a session lock survives rollback and stays held on a pooled connection until someone unlocks it, so one exception path blocks every later caller.
- Spot: `pg_advisory_lock(` or `pg_try_advisory_lock(` without `_xact_`.
- Instead: `pg_advisory_xact_lock`, released at commit or rollback. It is still a lock and goes through the gate above. More in `postgres-best-practices/references/lock-advisory-locks.md`.
- OK when: a long-running single-instance job holds it for its whole run and releases it in `finally`.

### C10 Testing a lock in `TestCase`

A test of a lock, race or `on_commit` that runs in Django's `TestCase` or a default `pytest.mark.django_db`.

- Why: those wrap each test in one transaction, so `select_for_update` passes without `atomic`, two "connections" are the same one, and `on_commit` callbacks never run unless captured. A test that asserts the SQL text of the lock proves nothing about the order.
- Spot: a race test without `TransactionTestCase` or `django_db(transaction=True)`; assertions on `str(queryset.query)` containing `FOR UPDATE`.
- Instead: two threads on two connections, `transaction=True`, and poll `pg_locks` for the waiting backend's `pg_backend_pid()` to prove who waited. For `on_commit`, use `django_capture_on_commit_callbacks(execute=True)` or `TestCase.captureOnCommitCallbacks`.
- OK when: the test checks only single-request behavior.

## Django ORM and DRF

### D1 N+1, unbounded querysets, write loops

Already covered. Use `backend-design/commands/hunt-n-plus-one.md` to find N+1, `django-expert/references/access-and-performance-review.md` ("Performance review") for unbounded querysets, missing indexes and write loops, and `postgres-best-practices/references/data-n-plus-one.md` for the SQL side. `count()` against `exists()` is low priority there and stays so: Django's docs say `exists()` is faster than evaluating the queryset "but not by a large degree", and it costs an extra query when the queryset is evaluated later anyway.

### D2 Serializers that write models they don't own

A serializer's `create`, `update`, `validate` or a field's `to_internal_value` saves, creates or deletes rows of another model (a product serializer that creates custom-menu rows, an order serializer that moves inventory).

- Why: writes hide in a layer reviewers read as parsing. Lock order then depends on field order in the payload, and the same write skips the service's checks when another endpoint calls the service directly. In one case, inserts from `ProductSerializer.update` ran before the service's lock and kept a deadlock with fulfill open.
- Spot: in a `serializers.py` diff, `.save(`, `.objects.create(`, `.delete(`, `.update(`, `bulk_create` or a service call inside `def create`, `def update`, `def validate` or `def validate_<field>` for a model other than `Meta.model`.
- Instead: the serializer validates and returns data; the view calls one service that does every write in a stated order. When the repo has its own rule or CI check for serializer writes, it wins over this entry.
- OK when: a nested writable serializer writes its own child rows (`Meta.model`'s owned children) through the parent's `create`.

### D3 Business logic in views and serializers

Prices, state changes, permission rules or multi-model workflows written in a view or serializer.

- Why: the logic gets copied per endpoint (v2, internal, unified) and the copies drift. One review found the same unlocked validation in the combine and split actions.
- Spot: `if obj.state ==`, arithmetic on money fields, or `.objects.` writes inside a view method or serializer.
- Instead: a function in the app's `services/`, called from each endpoint. Views keep request parsing, permission classes and response shape.
- OK when: the logic is presentation only (formatting, which fields to show).

### D4 `save()` overrides that write other rows

`def save(self, ...)` that saves a parent, children, or another model, or calls a vendor.

- Why: every caller of `save()` takes those extra locks without seeing them, so lock order becomes invisible. Example: a product variant's save writes its parent and a parent's save writes each variant, so the two deadlock on the products table. Bulk calls also skip the override (D6), so the rule holds only some of the time.
- Spot: `def save(` in a `models.py` diff whose body contains another `.save(`, `.objects.`, `.update(`, `.delete(`, or a task call.
- Instead: keep `save()` to the row's own fields (defaults, derived columns). Put cross-row effects in the service that knows the order, or in `on_commit` when they are side effects.
- OK when: the extra write is to a strictly owned child with one parent and one lock order, and every writer goes through `save()`.

### D5 Signals as hidden coupling

A `post_save`, `pre_save`, `m2m_changed` or custom signal receiver that writes data or calls out, for code inside the same project.

- Why: Django's docs: "Signals give the appearance of loose coupling, but they can quickly lead to code that is hard to understand, adjust and debug," and they recommend calling the handler directly. Receivers run inside the sender's transaction and take locks the sender's author never sees (for example, an order-number advisory lock taken from a receiver). Bulk calls don't send them. List the repo's receivers with `git grep -nE '@receiver|post_save\.connect' -- '*.py' ':!*tests*'` to see which writes carry hidden effects.
- Spot: `@receiver(`, `post_save.connect`, `pre_save`, `Signal()` in a diff.
- Instead: call the function explicitly from the service that does the write. When it is a side effect, register it with `on_commit` there.
- OK when: the receiver is for a third-party app's model you can't edit, or it's pure instrumentation that can't fail or lock.

### D6 Bulk calls that skip `save()` by surprise

`queryset.update()`, `bulk_create`, `bulk_update` or `queryset.delete()` replacing a `save()` loop.

- Why: they skip `save()`, `pre_save`/`post_save` and `auto_now`, so behavior that lived there silently stops. Covered in `django-expert/references/access-and-performance-review.md` ("Write loops") and `django-expert/references/models-and-orm.md`.
- Spot and fix there.

### D7 Querysets evaluated more than once, or cached when you need fresh rows

A queryset iterated twice, `len(qs)` then a loop, `if qs:` then `qs.first()`, or code that trusts a queryset's cached rows after another write.

- Why: each evaluation of an uncached queryset is a query; a cached one returns rows from before your last write. `queryset.update()` clears that queryset's cache, but `Model.objects.filter(...).update()` doesn't clear another variable's cache.
- Spot: the same queryset variable used in two `for` loops or in `len()` and a loop; a re-read missing after a guarded update.
- Instead: evaluate once into a list when you need the rows several times; re-read explicitly after a write you depend on; use `.iterator(chunk_size=...)` for one pass over many rows.
- OK when: the two reads are meant to see different data.

### D8 `F()` left on an instance

`obj.qty = F("qty") - 1; obj.save()` and then the instance is used again.

- Why: Django applies the `F()` again on every later `save()`, and `obj.qty` is an expression, not a number, until `refresh_from_db()`.
- Spot: `= F(` assigned to an instance attribute.
- Instead: `Model.objects.filter(pk=obj.pk).update(qty=F("qty") - 1)`, or `refresh_from_db(fields=[...])` right after the save.
- OK when: the instance is discarded after the save.

### D9 Queryset methods that ignore their queryset

A custom `QuerySet` or manager method that takes instances or ids and queries `Model.objects` instead of `self`.

- Why: `Product.objects.non_archived().lock_with_parents(...)` reads as filtered but isn't, so callers get rows (and locks) they didn't ask for.
- Spot: `def <name>(self, ...)` in a `QuerySet` subclass whose body uses `Model.objects` or `self.model.objects`.
- Instead: build on `self` (`self.filter(...)`, `Q(pk__in=self.values("pk"))`), or make it a plain function.
- OK when: it's a manager-level constructor that never claims to filter.

## Postgres and SQL

### P1 Migrations that lock hot tables

Covered by `backend-design/skills/migration-safety/README.md`, `postgres-best-practices/references/schema-online-ddl.md` and `backend-design/scripts/check_migration.py`, which parses Django migrations. One gap to add to that review: an `ALTER TABLE` waiting for its `ACCESS EXCLUSIVE` lock blocks every query queued behind it, even reads, so a migration on a busy table should set `SET LOCAL lock_timeout` (a few seconds) and be retried, instead of waiting behind a long transaction. Postgres recommends setting `lock_timeout` per session, not in `postgresql.conf`.

### P2 Missing indexes, OFFSET pagination, non-sargable filters, wide selects

Covered. Indexes: `django-expert/references/access-and-performance-review.md` ("Missing indexes"); Django indexes every `ForeignKey` by default, so the common gap is a composite index starting with the company column, and FK columns in raw SQL or SQLAlchemy tables, which get no automatic index. Pagination: `postgres-best-practices/references/data-keyset-pagination.md`. Implicit casts and functions on indexed columns: `postgres-best-practices/references/query-sargable-expressions.md`. Wide selects: `backend-design/skills/query-discipline/README.md` ("ORM Hygiene"), low priority unless the rows carry large text or JSON.

## Architecture

### A1 Shared database across services

Two services (or a service and an ETL) read and write the same tables.

- Why: schema changes need both teams, and one side's long transaction or lock blocks the other (microservices.io lists development-time and runtime coupling). SQLAlchemy code that shares Django's connection and transaction takes part in Django's lock order too.
- Spot: a new reader or writer of another app's or service's table; raw SQL against a table the module doesn't own.
- Instead: call the owning module's service or API; give a separate service a read replica, a view, or events.
- OK when: a reporting job reads a replica.

### A2 Distributed monolith

Services that must deploy together, call each other synchronously in a chain on every request, or share models through a common package.

- Why: you pay for network calls and partial failures and still can't deploy or scale them apart.
- Spot: a new synchronous HTTP call between internal services on a request path; a shared models package; a change that needs PRs in several repos released in order.
- Instead: keep the code in the monolith as a module with a service interface, or make the boundary asynchronous (events, outbox). The `system-design` skill covers the trade-off.
- OK when: the call is read-only, cached, and has a timeout and a fallback.

### A3 God modules

One module or class that every flow edits, often thousands of lines long: an order service, an orders `utils.py`, a products `models.py`. List the largest with `git ls-files '*.py' | xargs wc -l | sort -n | tail`.

- Why: every change touches the same file, so unrelated flows share helpers and locks and reviewers can't see the whole lock order.
- Spot: a diff that adds a new responsibility to one of these instead of a new module.
- Instead: put a new flow in its own service module and call the shared pieces. Don't refactor a god module inside a bug fix; propose it separately.
- OK when: the change is a fix to an existing function there.

### A4 Anemic and leaky domain models

Anemic: models are bags of fields and every rule lives in services that set those fields from outside; Fowler says they "incur all of the costs of a domain model, without yielding any of the benefits." Leaky: models reach out instead (D4, D5), saving other models, calling vendors or reading the request.

- Why: anemic models let any caller set an invalid state; leaky models hide writes and locks.
- Spot: anemic, `obj.state = "..."` assigned from several services; leaky, D4 and D5 signs.
- Instead: give a state field one function that checks the from-state and moves it (a state-machine library such as viewflow or django-fsm), keep model methods to the row's own data, and keep cross-model workflows in services.
- OK when: a plain data record with no rules.

## Sources

- Django: `select_for_update` options and the nullable-join and `TestCase` notes, `exists()`, `update()` and `get_or_create` race notes (https://docs.djangoproject.com/en/5.2/ref/models/querysets/); transactions, `on_commit` and "Avoid catching exceptions inside atomic!" (https://docs.djangoproject.com/en/5.2/topics/db/transactions/); signals warning (https://docs.djangoproject.com/en/5.2/topics/signals/); `F()` race conditions and persistence (https://docs.djangoproject.com/en/5.2/ref/models/expressions/).
- PostgreSQL: row lock modes, deadlock advice and advisory lock semantics (https://www.postgresql.org/docs/current/explicit-locking.html); READ COMMITTED re-check and serialization retries (https://www.postgresql.org/docs/current/transaction-iso.html); `ALTER TABLE` lock levels (https://www.postgresql.org/docs/current/sql-altertable.html); `lock_timeout` (https://www.postgresql.org/docs/current/runtime-config-client.html).
- Celery `delay_on_commit` (https://docs.celeryq.dev/en/stable/django/first-steps-with-django.html); Stripe idempotency keys and backoff (https://stripe.com/blog/idempotency); Brandur Leach, idempotency keys in Postgres (https://brandur.org/idempotency-keys); microservices.io shared database (https://microservices.io/patterns/data/shared-database.html); Martin Fowler, Anemic Domain Model (https://martinfowler.com/bliki/AnemicDomainModel.html).
- Lauren Tan's pstack principles `principle-separate-before-serializing-shared-state` and `principle-make-operations-idempotent` (MIT).
