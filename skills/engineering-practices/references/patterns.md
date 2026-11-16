# Patterns

Read this when you design a new module, service or abstraction, introduce a pattern, or review code that does. Each entry gives the problem the pattern solves, the smell that suggests it, when it is overkill, a short sketch and the question to ask in review. Where another skill or reference owns a pattern in depth, the entry is one line and points there. The books are in `books.md`; the principles behind the patterns are in `design-principles.md`.

A pattern answers a smell. Reach for one when the code shows the smell it fixes, and name that smell in the PR. Without the smell, the pattern is Speculative Generality. Use the domain's words for names (`design-rules.md` §8), not pattern names: `OrderAggregate` or `PricingStrategyFactory` tell the reader nothing the code doesn't. For the review-side smells, see `~/.agents/skills/review-pr/references/code-smells.md` and `~/.agents/skills/backend-design/skills/anti-patterns/README.md`.

## Contents

- Architectural styles
  - Layered
  - Hexagonal (ports and adapters)
  - Clean and onion
  - Vertical slices
  - Modular monolith
  - Microservices
  - Event-driven
  - CQRS
  - Event sourcing
  - Pipes and filters
  - Serverless
  - Microkernel (plugins)
  - MVC, MVP and MVVM
- Design patterns
  - Factory
  - Builder
  - Singleton
  - Adapter
  - Facade
  - Decorator and middleware
  - Proxy
  - Composite
  - Strategy
  - Template method
  - Observer
  - Command
  - State machine
  - Chain of responsibility
  - Rarely worth it
- Application patterns
  - Service layer
  - Repository
  - Unit of work
  - Active record and data mapper
  - Specification
  - Null object
  - Value object
  - Data transfer object
  - Dependency injection
- Integration and resilience patterns
  - Outbox, inbox and idempotency keys
  - Saga
  - Timeout
  - Retry with backoff and jitter
  - Circuit breaker
  - Bulkhead
  - Dead-letter queue
  - Cache-aside
  - Strangler fig and branch by abstraction
  - Anti-corruption layer
  - Covered elsewhere

## Architectural styles

The trade-offs between these styles at system scale are in the `system-design` skill (`topics/service-decomposition`, `topics/messaging-streaming`, `topics/data-storage`). Before adding a service, queue or store, pass `~/.agents/skills/backend-design/skills/boring-by-default/README.md`.

### Layered

- Solves: separates presentation, business rules and data access so each changes on its own. The default shape of most web apps.
- Smell: business rules in controllers, serializers, templates or components; SQL in a view.
- Overkill when: each layer only forwards to the next with the same signature (a service that calls a repository that calls the ORM), which makes shallow modules. When most changes cut through every layer, vertical slices fit better.
- Review: does each import go down exactly one layer, and does each layer hide something?

```text
handlers  ->  services  ->  data access  ->  database
(parse, respond)  (rules, transaction)  (queries)
```

Source: Fowler, Patterns of Enterprise Application Architecture (layering); Richards and Ford, Fundamentals of Software Architecture.

### Hexagonal (ports and adapters)

- Solves: keeps the domain core independent of every driver (HTTP, CLI, queue, tests) and every driven system (database, vendor API, email). The core owns the ports (interfaces); adapters at the edge implement them.
- Smell: the rules can't be tested without a database or an HTTP server; vendor SDK calls sit inside rules; the same use case must run from a request and from a worker.
- Overkill when: the app is CRUD, or the framework's ORM already is the persistence layer. `~/.agents/skills/backend-design/skills/domain-modeling/README.md` says no ports-and-adapters layer inside a Django app; the anti-corruption layer goes only at external boundaries. A port with one adapter and no test fake is a hypothetical seam.
- Review: does anything in the core import an adapter, a framework or an SDK?

```python
class Notifier(Protocol):                 # port, owned by the core
    def send(self, to: Email, text: str) -> None: ...

def place_order(cmd: PlaceOrder, store: OrderStore, notify: Notifier) -> OrderId: ...

class SesNotifier: ...                    # adapter at the edge
class FakeNotifier: ...                   # adapter for tests
```

Source: Alistair Cockburn, "Hexagonal Architecture".

### Clean and onion

- Solves: the hexagonal idea drawn as rings (entities, use cases, interface adapters, frameworks), with every dependency pointing inward (the dependency rule).
- Smell: the same as hexagonal.
- Overkill when: each ring gets its own copy of every model plus a mapper, so a field change edits four classes and three mappings. Keep a mapping only where it translates something.
- Review: does any import point outward, and does each mapping translate or only copy fields?

Source: Jeffrey Palermo, "The Onion Architecture"; Martin, Clean Architecture.

### Vertical slices

- Solves: organizes code by feature or use case (handler, logic and query for "cancel order" in one folder) instead of by technical layer, so a feature change stays in one place.
- Smell: one feature edits `controllers/`, `services/`, `repositories/` and `dtos/` for one field; layers full of pass-through methods.
- Overkill when: slices start copying a business rule another slice owns. Keep shared rules in a domain module both slices call.
- Review: does this change stay inside one slice, and did the slice copy a rule that lives elsewhere?

Source: Jimmy Bogard, "Vertical Slice Architecture".

### Modular monolith

- Solves: one deployable split into modules with enforced boundaries; each module owns its tables and exposes a public API. The default before microservices.
- Smell: any module imports any other module's models; teams collide in the same files; someone proposes microservices to get boundaries.
- Overkill when: the app is small and has one team. Boundaries with no checker decay, so put them in the repo's boundary checker (`design-rules.md` §7).
- Review: does this cross a module boundary only through the module's public API, and does a checker enforce it?

```text
orders/api.py       <- the only orders import other modules may use
billing/ -> orders.api      allowed
billing/ -> orders.models   forbidden by the import-linter contract
```

Source: `system-design` `topics/service-decomposition`; Richards and Ford, Fundamentals of Software Architecture.

### Microservices

- Solves: independent deploy, scaling and ownership for parts run by different teams, each with its own data.
- Smell: teams blocked on one release train; parts with very different scaling or availability needs; a real seam that already owns its data.
- Overkill when: one team owns everything, nothing needs to deploy alone, or the services would share a database (A1) or call each other synchronously in a chain (A2, the distributed monolith) in `~/.agents/skills/backend-design/skills/anti-patterns/README.md`.
- Review: can this service deploy alone and own its data, and what does the caller do when it's down?

Source: Newman, Building Microservices; Richardson, Microservices Patterns; `system-design` `topics/service-decomposition`.

### Event-driven

- Solves: decouples producers from consumers in time and knowledge, and fans one change out to many reactions. Fowler separates event notification (a thin event; the consumer calls back for data), event-carried state transfer (the event carries the data) and event sourcing (below).
- Smell: one write triggers many unrelated side effects inline (email, analytics, search index), so the request slows down or fails with them; modules call each other only to say "this happened".
- Overkill when: the caller needs the result now (make a call), or a reader can no longer find who handles what. Every consumer then needs idempotency, ordering rules, a dead-letter queue and tracing. Inside a monolith, prefer explicit calls registered after commit to framework signals (D5 in the anti-patterns file).
- Review: who consumes this event, and what happens on a duplicate, a reorder or a consumer failure? Is it published through the outbox?

```python
with transaction.atomic():
    order = place_order(cmd)
    outbox.add(OrderPlaced(order_id=order.id, total=order.total))
# a relay publishes it; billing, email and search consume it on their own
```

Source: Fowler, "What do you mean by 'Event-Driven'?"; Hohpe and Woolf, Enterprise Integration Patterns; `system-design` `topics/messaging-streaming`.

### CQRS

- Solves: separate write and read models when they need different shapes or loads. Writes go through commands that enforce invariants; reads come from a model shaped for the screen (a view, a denormalized table, a search index).
- Smell: dashboards join ten tables while writes need strict rules; read load swamps the write database; one ORM model is bent to serve both.
- Overkill when: the app is mostly CRUD. Two models bring replication lag (reads are eventually consistent) and two schemas to keep. The light version, separate query functions and read types over the same database, is usually enough (`SKILL.md`: separate reads from writes).
- Review: does the read side tolerate lag, and does the user still see their own write?

```python
def rename_product(cmd: RenameProduct) -> None: ...             # write side, invariants
def product_list_rows(company_id: int) -> list[ProductRow]: ...   # read side, from a SQL view
```

Source: Greg Young's CQRS documents; Fowler's "CQRS" article, which warns that most systems don't need it.

### Event sourcing

- Solves: stores the sequence of events as the source of truth and derives current state by replaying them, which gives full history, "as of" queries and rebuildable projections.
- Smell: "how did it get to this state" is a core requirement (ledgers, accounting); several projections must come from the same history.
- Overkill when: almost anywhere else. Event schemas must stay readable forever, every query needs a projection, and deleting personal data gets hard. An audit table next to normal state is far cheaper.
- Review: which requirement needs replay rather than an audit table, and how are old event versions read?

```python
events = [Deposited(100), Withdrew(30)]
balance = sum(e.amount if isinstance(e, Deposited) else -e.amount for e in events)
```

Source: Fowler, "Event Sourcing"; `system-design` `topics/messaging-streaming` and `topics/data-storage`.

### Pipes and filters

- Solves: processing as a chain of independent steps, each with one input and one output (ETL, media processing, compilers, Unix pipes).
- Smell: a long function whose stages share local variables; stages that need reordering, reuse or testing alone.
- Overkill when: the steps share a lot of state or need a transaction across them. Each filter must own its own knowledge; when two steps know the same format, that is the split by step order that `design-rules.md` §1 warns about.
- Review: can each step run and be tested alone, and does more than one step know the same format?

```python
def run(rows: Iterable[RawRow]) -> Iterable[Row]:
    return dedupe(enrich(normalize(rows)))  # each one a generator
```

Source: Hohpe and Woolf, Enterprise Integration Patterns ("Pipes and Filters"); Richards and Ford, Fundamentals of Software Architecture (the pipeline style).

### Serverless

- Solves: runs event-triggered code without managing servers; scales to zero and bills per invocation.
- Smell: spiky or rare workloads; glue between managed services (an upload triggers a resize, a queue message triggers a transform); a job that runs a few minutes a day.
- Overkill when: load is steady and high (cost), jobs run long (time limits), the path is latency-critical (cold starts), each invocation opens database connections (connection storms without a proxy), or a workflow spreads over dozens of functions nobody can trace.
- Review: what happens on a cold start, a timeout, a retried event and at peak database connections? Keep the logic in a plain function the handler calls, so it runs and tests outside the platform. AWS work follows the `aws` skill.

```python
def handler(event: dict, context: object) -> None:   # thin: parse, call
    key = event["Records"][0]["s3"]["object"]["key"]
    make_thumbnail(key)                               # plain, idempotent function
```

Source: AWS Lambda documentation (asynchronous invocations are retried, so handlers must be idempotent).

### Microkernel (plugins)

- Solves: a small core with features added as plugins through a stable contract (pytest, ESLint, IDEs, payment or carrier integrations).
- Smell: the core changes for every new integration; customer-specific branches inside a shared flow (`SKILL.md`: no special-case `if` for one customer).
- Overkill when: there is one plugin and it's written in-house. The contract is hard to change once others depend on it.
- Review: is the plugin contract small and versioned, and does the core name any plugin?

Source: Richards and Ford, Fundamentals of Software Architecture (the microkernel style). The registry sketch is under open-closed in `design-principles.md`.

### MVC, MVP and MVVM

- Solves: separates UI state and rules (model) from rendering (view) and input handling (controller, presenter or view model).
- Smell: business rules in components or templates; a component that fetches, computes and renders; UI logic testable only by rendering.
- Overkill when: the framework already sets the split (React components with hooks and a server-state cache, Vue components with composables). Follow it instead of adding classes.
- Review: can the rule in this component be tested without rendering it?

```ts
export function cartTotals(cart: Cart): Totals { ... }       // pure, unit-tested

function CartSummary({ cart }: { cart: Cart }) {
  const totals = useMemo(() => cartTotals(cart), [cart]);
  return <Total value={totals.total} />;
}
```

Source: Trygve Reenskaug (MVC in Smalltalk-80); Fowler, "GUI Architectures".

## Design patterns

The GoF patterns that show up in real code. In Python and TypeScript, functions, closures, dicts and protocols replace most of the class machinery the book shows; prefer the lighter form.

### Factory

- Solves: puts the choice of a concrete type, or complex setup, in one place, so callers ask for "the carrier for this code". Covers the factory function, factory method and abstract factory (a family of related objects, such as a test and a production set).
- Smell: `if kind == ...: X()` construction repeated; setup copied around a constructor.
- Overkill when: the constructor is enough. A `FooFactory` class that only calls `Foo(...)` is a Middle Man; a function or a dict of constructors is the factory.
- Review: does this factory decide anything, or only call a constructor?

```python
def carrier_for(code: str) -> Carrier:
    return CARRIER_CLASSES[code]()  # KeyError names the unknown code
```

Source: Gamma, Helm, Johnson and Vlissides, Design Patterns.

### Builder

- Solves: builds an object with many optional parts step by step and validates it once at the end.
- Smell: constructors with eight or more parameters, most optional; test setup that repeats the same long object.
- Overkill when: keyword arguments, dataclass defaults or an object literal already do it. Builders pay off mostly for test data and for building queries or requests.
- Review: would keyword arguments or an object literal cover this?

```ts
const order = anOrder().withLines(3).paid().build(); // test data builder
```

Source: Design Patterns; Freeman and Pryce, Growing Object-Oriented Software, Guided by Tests (test data builders).

### Singleton

- Solves: one shared instance (a connection pool, a client, settings).
- Smell that it should go: hidden global state; tests leaking state into each other; a mutable singleton; a per-instance cache shared for the life of the process (`SKILL.md`).
- Instead: create it once at startup and pass it in. A module-level instance of a stateless, thread-safe client is fine.
- Review: can a test replace it, and is its state safe across requests and threads?

```python
# Bad: def price(item): return Settings.instance().markup * item.cost
def price(item: Item, settings: Settings) -> Decimal:
    return settings.markup * item.cost
```

Source: Design Patterns; `SKILL.md` ("prefer explicit over implicit").

### Adapter

- Solves: makes an existing interface (a vendor SDK, a legacy class) fit the one your code expects. When it also translates the meaning of a foreign model at a system boundary, it is the anti-corruption layer.
- Smell: vendor types and calls spread through the code, so swapping the library touches many files.
- Overkill when: it wraps a stable standard library, or a library used in one place, and only forwards arguments (Middle Man).
- Review: does the adapter translate something, or forward arguments unchanged?

```python
class S3Storage:  # adapts boto3 to our Storage protocol
    def read(self, key: str) -> bytes:
        return self._s3.get_object(Bucket=self._bucket, Key=key)["Body"].read()
```

Source: Design Patterns.

### Facade

- Solves: one simple entry point over a subsystem of many parts; a module's public API is a facade.
- Smell: callers drive five internal classes of another module in the same order; another module's internals imported from outside.
- Overkill when: it wraps one class (Middle Man), or keeps growing a method for every internal function until it is a god module (A3 in the anti-patterns file).
- Review: do outside callers use only the facade, and does it hide more than it exposes?

```python
# orders/api.py
def place_order(cmd: PlaceOrder) -> OrderId: ...
def cancel_order(order_id: int, actor: User) -> None: ...
def order_weight_kg(order_id: int) -> Decimal: ...
```

Source: Design Patterns; Ousterhout, A Philosophy of Software Design (deep modules).

### Decorator and middleware

- Solves: adds behavior (caching, retries, timing, logging, auth) around a function or object without changing it, in layers that stack.
- Smell: the same retry, timing or logging boilerplate at the start and end of many functions; subclasses for every feature combination (`design-principles.md` §11).
- Overkill when: the stack is so deep nobody knows what runs, or a decorator changes the signature or swallows errors.
- Review: does the wrapper keep the wrapped function's contract (arguments, return, errors), and is the stack in the right order?

```python
@retry(on=(TimeoutError,), attempts=3, wait=exponential_jitter(initial=0.2))
@timed("carrier.rate")
def fetch_rate(order: Order) -> Decimal: ...
```

Source: Design Patterns.

### Proxy

- Solves: a stand-in that controls access to the real object: lazy loading, a remote call, caching or an access check.
- Smell: an expensive object built eagerly but rarely used; the same access check before every call.
- Overkill when: it hides I/O behind attribute access. ORM lazy relations are proxies, and they are where N+1 queries come from (D1 in the anti-patterns file).
- Review: does this hide a network or database call the caller should know about?

Source: Design Patterns.

### Composite

- Solves: treats a tree of objects and a single object the same way (pricing rules made of rules, permission groups, menus, UI trees).
- Smell: recursive code with `isinstance(x, Group)` branches everywhere.
- Overkill when: the structure is a flat list.
- Review: do callers still branch on leaf versus group?

```ts
interface PriceRule { apply(order: Order): Money }

class AllOf implements PriceRule {
  constructor(private readonly rules: PriceRule[]) {}
  apply(order: Order): Money { ... }
}
```

Source: Design Patterns.

### Strategy

- Solves: swaps an algorithm (pricing, tax, routing, rounding) chosen by config or input, without branching at every use.
- Smell: Repeated Switches on the same kind; a long `if`/`elif` that picks an algorithm.
- Overkill when: there are two cases that won't grow. A strategy with one method is a function: pass the function.
- Review: how many strategies exist today, and would a function or a dict do?

```python
Rounding = Callable[[Decimal], Decimal]

def price(item: Item, rounding: Rounding) -> Decimal:
    return rounding(item.cost * item.markup)
```

Source: Design Patterns.

### Template method

- Solves: a fixed sequence of steps where subclasses fill in some of them.
- Smell: several classes copy the same sequence with different middle steps.
- Overkill when: passing the varying step as a function would do, which avoids inheritance (`design-principles.md` §11). Keep it where the framework defines it (`setUp` and `tearDown`, Django class-based view hooks).
- Review: would passing the varying step as a function remove the hierarchy?

Source: Design Patterns.

### Observer

- Solves: notifies several dependents of a change without the subject knowing them (UI stores, in-process domain events).
- Smell: a function that calls a growing list of unrelated follow-ups.
- Overkill when: control flow disappears from view. Handlers that write inside the same transaction, depend on order, or leak because nothing unsubscribes are the common bugs. On the backend, prefer explicit calls registered after commit to framework signals (D5 in the anti-patterns file).
- Review: can a reader find every subscriber, and what happens when one fails?

```ts
const unsubscribe = cartStore.subscribe(renderBadge);
onUnmounted(unsubscribe);
```

Source: Design Patterns.

### Command

- Solves: turns a request into an object (a name plus data) that can be validated, queued, logged, retried or undone. Use-case inputs (`PlaceOrder`) and job payloads are commands.
- Smell: long parameter lists passed through layers; a need for audit, queuing or undo.
- Overkill when: a command, a handler and a bus replace one direct call in a small app.
- Review: is the command serializable, and safe to run twice? A queue will run it twice.

```python
@dataclass(frozen=True)
class CancelOrder:
    order_id: int
    reason: str

def handle_cancel_order(cmd: CancelOrder) -> None: ...
```

Source: Design Patterns.

### State machine

- Solves: behavior that depends on a status with allowed transitions. `SKILL.md` holds the rule (one status field, one function that moves it and checks the from-state), and A4 in the anti-patterns file the backend side.
- Smell: booleans and nullable timestamps written from several places; `if status == ...` before writes everywhere.
- Overkill when: a class per state serves three states and two transitions. A transition table is enough.
- Review: does every write of this status go through the one transition function?

```python
ALLOWED = {
    Status.PENDING: {Status.PAID, Status.CANCELLED},
    Status.PAID: {Status.SHIPPED, Status.REFUNDED},
}

def move(order: Order, to: Status) -> None:
    if to not in ALLOWED.get(order.status, set()):
        raise InvalidTransition(order.status, to)
    order.status = to
```

Source: Design Patterns (State).

### Chain of responsibility

- Solves: passes a request through handlers that may handle, change or stop it (HTTP middleware, validation chains, approval rules).
- Smell: one function with a long run of guards for unrelated concerns (auth, rate limit, tenant, feature flag).
- Overkill when: the order matters but nobody wrote it down, or nobody can tell which handler ended the request.
- Review: is the order explicit, and can you tell which handler stopped the request?

Source: Design Patterns.

### Rarely worth it

- Iterator: built into the language (generators, `for ... of`); write one only for a custom traversal.
- Visitor: use `match` or a discriminated union with an exhaustiveness check instead of double dispatch.
- Prototype, Flyweight, Bridge, Mediator, Memento, Interpreter: they show up inside libraries and frameworks. Proposing one in application code needs the smell it fixes, named in the PR.

## Application patterns

Patterns for organizing business logic and persistence inside one service. Most come from Fowler's Patterns of Enterprise Application Architecture; Percival and Gregory's Architecture Patterns with Python shows them in Python.

### Service layer

- Solves: one function per use case that owns the transaction, the authorization of the action, the call into domain objects and the side effects after commit. Entry points (API, admin, CLI, worker) call it.
- Smell: rules in views, serializers or components (D3 in the anti-patterns file); the same operation implemented differently in the API, the admin and a management command.
- Overkill when: the service only forwards CRUD to the ORM with no rule (shallow).
- Review: does every entry point go through this function?

```python
def cancel_order(order_id: int, actor: User) -> None:
    with transaction.atomic():
        order = Order.objects.get(pk=order_id)
        ensure_can_cancel(actor, order)
        order.cancel()
        transaction.on_commit(lambda: notify_cancelled.delay(order_id))
```

Source: Fowler, Patterns of Enterprise Application Architecture (Service Layer, by Randy Stafford).

### Repository

- Solves: a collection-like interface to load and save aggregates that hides persistence, so rules can run against an in-memory fake.
- Smell: query code scattered through rules; domain code building SQL; rule tests that need a database.
- Overkill when: the ORM already is the repository. In Django the model manager and QuerySet are it (`~/.agents/skills/backend-design/skills/domain-modeling/README.md`), and a generic `Repository<T>` with `getAll` and `save` over an ORM hides the query tuning. It pays off with a data mapper (SQLAlchemy) or a store you don't control.
- Review: what does this repository hide that the ORM doesn't, and does it return domain data rather than persistence objects (`SKILL.md`)?

```python
class Orders(Protocol):
    def get(self, order_id: OrderId) -> Order: ...
    def add(self, order: Order) -> None: ...
```

Source: Fowler, Patterns of Enterprise Application Architecture; Evans, Domain-Driven Design.

### Unit of work

- Solves: tracks the changes of one business operation and commits them once, atomically.
- Smell: commits scattered through helpers; partial writes when the third step fails.
- Overkill when: you'd build your own. Django's `transaction.atomic` and the SQLAlchemy `Session` already are units of work; use them. The transaction rules are in `SKILL.md` "Transactions, events and distributed systems".
- Review: who commits, and is it exactly one place per use case?

```python
with Session(engine) as session, session.begin():
    order = session.get(Order, order_id)
    order.cancel()
# commits here, or rolls back on an exception
```

Source: Fowler, Patterns of Enterprise Application Architecture.

### Active record and data mapper

- Active record: the object wraps a row and saves itself (Django models, Rails, TypeORM's active record mode). Data mapper: a separate mapper moves data between objects and tables (SQLAlchemy ORM, Hibernate).
- Follow the ORM the repo uses. With active record, keep model methods to the row's own data and never write other rows from `save()` (D4 in the anti-patterns file). With a data mapper, keep session calls out of domain classes.
- Review: does a model method write other rows, call a vendor or read the request?

Source: Fowler, Patterns of Enterprise Application Architecture.

### Specification

- Solves: names a business rule as a predicate that can be combined and reused, for in-memory checks and for queries.
- Smell: the same filter rule written once in Python and again in a queryset or SQL, and drifting.
- Overkill when: a generic `and_`, `or_`, `not_` framework serves three filters. A named queryset method or function is usually the whole specification.
- Review: is the rule defined once, and does the in-memory check come from the same definition?

```python
class ProductQuerySet(models.QuerySet):
    def sellable(self) -> "ProductQuerySet":   # the one definition of "sellable"
        return self.filter(archived=False, stock__gt=0, license__expires_at__gt=timezone.now())
```

Source: Evans and Fowler, "Specifications"; Evans, Domain-Driven Design.

### Null object

- Solves: replaces repeated `None` checks with an object that does the neutral thing (no discount, a no-op logger, an anonymous user).
- Smell: the same `if x is None` before every use of `x`.
- Overkill when: absence is an error or needs different handling. Then a null object hides missing data, a symptom fix (`SKILL.md` "Fix the root cause"). Use it only when "nothing" has a neutral behavior the business agrees on.
- Review: is "nothing" really neutral here, or is it hiding missing data?

```ts
const NO_DISCOUNT: Discount = { apply: (total) => total };
const discount = coupon ? couponDiscount(coupon) : NO_DISCOUNT;
```

Source: Bobby Woolf, "Null Object" (Pattern Languages of Program Design 3); Fowler, Refactoring ("Introduce Special Case").

### Value object

A small immutable type compared by value and validated when built (money with a currency, a date range). When to give a value its own type, and when not, is in `~/.agents/skills/backend-design/skills/domain-modeling/README.md` ("Value objects"); the review smell is Primitive Obsession in `~/.agents/skills/review-pr/references/code-smells.md`. Source: Evans, Domain-Driven Design.

### Data transfer object

- Solves: a plain data shape for crossing a boundary (API, queue, process), kept apart from domain objects so the wire contract and the model change independently.
- Smell: ORM objects serialized straight into responses (leaking fields and tying the API to the schema); domain objects carrying JSON concerns.
- Overkill when: every layer copies the same fields into its own DTO. One per real boundary is enough.
- Review: is this DTO at a real boundary, and is the mapping in one place?

```python
class OrderOut(BaseModel):          # the API contract, versioned with the API
    id: int
    status: Literal["pending", "paid", "shipped"]
    total: Decimal
```

Source: Fowler, Patterns of Enterprise Application Architecture.

### Dependency injection

- Solves: passes dependencies in (constructor or parameter) instead of creating or looking them up inside, so wiring happens in one place and tests pass fakes. It is how dependency inversion (`design-principles.md` §5) is done.
- Smell: `datetime.now()`, `requests.get`, `os.environ` or a global client called deep inside a rule; tests full of `patch()` on module paths.
- Overkill when: a DI container is added to a small app or script, or things that never vary (pure helpers, the standard library) are injected. When the framework has DI (FastAPI `Depends`, NestJS, Spring), use it.
- Review: can the test pass this dependency instead of patching it?

```python
def is_expired(license: License, now: datetime) -> bool:
    return license.expires_at <= now
```

Source: Fowler, "Inversion of Control Containers and the Dependency Injection pattern".

## Integration and resilience patterns

Patterns for calls and messages that cross a process or network boundary. The system-scale trade-offs are in `system-design` (`topics/resilience-failure`, `topics/messaging-streaming`, `topics/caching`, `topics/consistency-coordination`).

### Outbox, inbox and idempotency keys

These are owned elsewhere. The outbox (write the event in the same transaction as the state change, deliver it from a relay) and the inbox (consumers record what they processed and tolerate duplicates and reordering) are rules in `SKILL.md` "Transactions, events and distributed systems". The mechanics, idempotency keys for client-driven mutations and the retry table for outgoing calls are in `~/.agents/skills/backend-design/skills/idempotency-and-side-effects/README.md`.

### Saga

- Solves: a business transaction across services or aggregates that can't share one database transaction. It runs as a sequence of local transactions, each with a compensating action for when a later step fails. Orchestration has a coordinator; choreography chains events.
- Smell: an attempt at a cross-service transaction or two-phase commit; partial failures (a charged order with no stock reserved); ad hoc rollback code in `except` blocks.
- Overkill when: everything fits in one database transaction; in a monolith, keep it there. With many steps or long waits, a durable workflow engine beats a hand-rolled saga.
- Review: does each step have a compensation, are steps and compensations idempotent, and where is the saga's state stored?

```text
reserve_stock -> charge_payment -> create_shipment
  charge fails:    release_stock
  shipment fails:  refund_payment, release_stock
```

Source: Garcia-Molina and Salem, "Sagas" (1987); Richardson, Microservices Patterns; `system-design` `topics/consistency-coordination`.

### Timeout

- Solves: bounds how long a caller waits on a remote call, so a slow dependency can't hold workers forever.
- Smell: an HTTP client, database driver or queue call with no timeout (Python's `requests` has none by default); a timeout longer than the caller's own.
- Review: does every remote call have an explicit timeout shorter than its caller's deadline?

Source: Nygard, Release It!; `system-design` `topics/resilience-failure`.

### Retry with backoff and jitter

- Solves: rides out transient failures (5xx, connection resets, throttling, a database deadlock or serialization failure).
- Smell: a bare retry loop with a fixed sleep; retries on 4xx; retries in several layers that multiply (three layers of three attempts is 27 calls).
- Overkill when: the operation isn't idempotent and carries no idempotency key (duplicates); it retries inside a failed database transaction (C6 in the anti-patterns file); it hammers a dependency in an outage (cap it with a retry budget and a circuit breaker). Prefer the repo's retry library to a hand-written loop.
- Review: is the call idempotent, does only one layer retry, and is there a cap?

```python
for attempt in range(MAX_ATTEMPTS):
    try:
        return client.post(url, json=body, headers={"Idempotency-Key": key}, timeout=2.0)
    except TransientError:
        if attempt == MAX_ATTEMPTS - 1:
            raise
        time.sleep(random.uniform(0, BASE_SECONDS * 2**attempt))  # full jitter
```

Source: Marc Brooker, "Exponential Backoff And Jitter" (AWS Architecture Blog); Nygard, Release It!; "Outgoing Calls" in the idempotency file above.

### Circuit breaker

- Solves: stops calling a dependency that keeps failing, fails fast for a cool-down, then lets a few probe calls through (half-open) before closing again.
- Smell: one vendor's outage makes every request wait for its timeout and uses up the worker pool; retry storms.
- Overkill when: the call is in-process, the job is a low-volume batch where retry with backoff is enough, or the caller has nothing useful to do with a fast failure.
- Review: what does the caller do while the breaker is open, and is the breaker shared per dependency, not per request?

```text
closed --(failure rate over threshold)--> open --(cool-down)--> half-open --(probe ok)--> closed
```

Source: Nygard, Release It!; Fowler, "CircuitBreaker".

### Bulkhead

- Solves: isolates resources (connection pools, worker queues, thread pools) per dependency or workload, so one slow part can't starve the rest.
- Smell: one slow report endpoint or vendor ties up every worker; a bulk import on the shared queue delays password resets.
- Overkill when: the service has one dependency and one workload; every pool is one more thing to size and watch.
- Review: if this dependency hangs, what else stops working?

```text
queue "critical" -> 4 workers   (password reset, checkout emails)
queue "bulk"     -> 2 workers   (imports, exports)
```

Source: Nygard, Release It!.

### Dead-letter queue

- Solves: parks messages that still fail after the retry cap, so they neither block the queue nor vanish, with an alert and a way to replay them.
- Smell: a poison message retried forever; failed jobs that exist only in logs.
- Overkill when: never as such, but a dead-letter queue nobody watches is where data goes to be lost.
- Review: who is alerted when a message lands there, and how is it replayed?

Source: Hohpe and Woolf, Enterprise Integration Patterns ("Dead Letter Channel").

### Cache-aside

- Solves: the app reads the cache, and on a miss loads from the store and fills the cache. It stays correct, only slower, when the cache is down.
- Smell: a measured hot read of data that rarely changes.
- Overkill when: nobody profiled first (the `perf-review` skill never answers "make it faster" with a cache before it runs), the data must be fresh, or the read is already cheap.
- Review: what invalidates the entry on write, does the TTL have jitter, what stops a stampede, and is the tenant in the key?

Source: `system-design` `topics/caching`, which owns the strategies, eviction and stampede control.

### Strangler fig and branch by abstraction

- Solves: replaces a legacy system or module gradually. Strangler fig routes one capability at a time to the new code behind a facade or proxy until the old path has no traffic, then deletes it. Branch by abstraction does the same inside one codebase: put an interface in front of the old implementation, build the new one behind it, switch callers, delete the old one (`SKILL.md`: migrate behind the existing interface).
- Smell: a big-bang rewrite proposal; legacy code too risky to change in place.
- Overkill when: the module is small enough for one PR guarded by characterization tests.
- Review: how is traffic split and measured, what is the rollback, and when does the old path get deleted?

```text
client -> router:  /invoices/*  -> new service
                   everything else -> legacy app
```

Source: Fowler, "StranglerFigApplication" and "BranchByAbstraction"; the `code-modernization` skill for whole-stack migrations; `system-design` `topics/service-decomposition`.

### Anti-corruption layer

Translate a vendor's or legacy system's model into your own types in one adapter at the boundary. The rule and its example are in `design-rules.md` §4, and the Django version in `~/.agents/skills/backend-design/skills/domain-modeling/README.md`.

### Covered elsewhere

- API gateway and backend for frontend: `system-design` `topics/service-decomposition`.
- Rate limiting, load shedding, graceful degradation and failover: `system-design` `topics/resilience-failure`.
- Sharding, replication and read replicas: `system-design` `topics/data-storage`.
- Leader election, quorum and consistent hashing: `system-design` `topics/consistency-coordination`.
- Locks, guarded updates and lock order: "Adding a lock" in `~/.agents/skills/backend-design/skills/anti-patterns/README.md`.
