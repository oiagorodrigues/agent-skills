# Design principles

Read this when you design a new module, class, service or abstraction, or review one, and a principle decides its shape. Each entry gives the rule, the signs in code that it's broken, when applying it hurts, a bad and a good example, the question to ask in review and the source (the books are in `books.md`). Where `SKILL.md` or `design-rules.md` already holds the rule, the entry says so and adds only what's missing. The last section says how the principles conflict and which one wins.

A principle is a judgment call. In review, report a broken one with the hunk quoted and its concrete cost in this code (the second reason to change, the caller that breaks, the copy that already drifted), never as a rule violation on its own. The repo's documented conventions win over this file unless following them causes a bug.

## Contents

1. Single responsibility (SRP)
2. Open-closed (OCP)
3. Liskov substitution (LSP)
4. Interface segregation (ISP)
5. Dependency inversion (DIP)
6. Keep it simple (KISS)
7. Don't repeat yourself (DRY)
8. You aren't gonna need it (YAGNI)
9. Separation of concerns
10. High cohesion, low coupling
11. Composition over inheritance
12. Law of Demeter
13. Tell, don't ask
14. Command-query separation
15. Fail fast
16. Least astonishment
17. Make illegal states unrepresentable
18. Acyclic and stable dependencies
19. Robustness principle, with care
20. How the principles conflict

## 1. Single responsibility (SRP)

A module, class or function has one reason to change. Martin's later wording makes it testable: it answers to one actor, so a change asked for by finance and a change asked for by operations never land in the same code. In practice, split by the knowledge each part hides (`design-rules.md` §1).

You see it broken when a name needs "and", "Manager" or "Utils" to describe it, when `git log` on one file shows commits for unrelated tickets (Divergent Change), when one function computes, formats and saves, or when a test for one behavior needs setup for another.

It hurts when you split by step order instead of by knowledge, which spreads one decision across several modules, and when you split a small function into several classes for a second reason to change that hasn't appeared yet. Ousterhout calls the over-split result classitis: many shallow classes, each easy to read, the whole hard to follow. Split when the second reason shows up in a real change.

Bad: the invoice changes when finance changes the tax rule, when design changes the PDF and when the storage changes.

```python
class Invoice:
    def total(self) -> Decimal: ...
    def to_pdf(self) -> bytes: ...
    def save(self, session: Session) -> None: ...
```

Good: each piece of knowledge has one home, and the invoice keeps its own rule.

```python
class Invoice:
    def total(self) -> Decimal: ...

def render_invoice_pdf(invoice: Invoice) -> bytes: ...

def save_invoice(session: Session, invoice: Invoice) -> None: ...
```

Review question: who would ask for a change to this module, and would their changes collide here?

Source: Martin, Agile Software Development, Principles, Patterns, and Practices, and Clean Architecture ("one, and only one, actor"); Ousterhout, A Philosophy of Software Design, for classitis.

## 2. Open-closed (OCP)

Add a new variant by adding code, without editing the code that chooses among the existing variants. It matters where variants keep arriving: payment methods, carriers, export formats, integrations.

You see it broken when the same `if kind == ...` or `match` cascade appears in several places (Repeated Switches), or when every new variant edits a shared function and its tests.

It hurts when it builds an extension point for variants nobody asked for (Speculative Generality). With one or two variants a plain `if` reads better; open the code when the third variant arrives or when variants come from outside the team (plugins).

Bad: every carrier operation repeats the cascade.

```python
def shipping_cost(order: Order) -> Decimal:
    if order.carrier == "ups":
        return ups_rate(order)
    if order.carrier == "fedex":
        return fedex_rate(order)
    raise UnknownCarrier(order.carrier)
# the same cascade again in label(), track() and cancel()
```

Good: one registry, and a new carrier is a new entry.

```python
class Carrier(Protocol):
    def rate(self, order: Order) -> Decimal: ...
    def label(self, order: Order) -> bytes: ...

CARRIERS: dict[str, Carrier] = {"ups": Ups(), "fedex": Fedex()}

def shipping_cost(order: Order) -> Decimal:
    return CARRIERS[order.carrier].rate(order)
```

Review question: when the next variant comes, how many files change, and is a next variant actually planned?

Source: Meyer, Object-Oriented Software Construction (the original); Martin, Agile Software Development (the polymorphism version).

## 3. Liskov substitution (LSP)

A subtype works anywhere its base type is expected: it accepts at least what the base accepts, promises at least what the base promises, and raises nothing the base doesn't.

You see it broken when a subclass overrides a method to raise `NotImplementedError` or to do nothing, when callers check `isinstance` for one subtype, when a subclass rejects inputs the base accepted, or when it ignores most of what it inherits (Refused Bequest).

It rarely hurts by itself; the cost comes from bending a hierarchy to satisfy it. When a type can't keep the base's contract, it isn't a subtype: give it its own type or use composition.

Bad: every caller of `Storage` can now crash.

```python
class Storage:
    def write(self, key: str, data: bytes) -> None: ...

class ReadOnlyArchive(Storage):
    def write(self, key: str, data: bytes) -> None:
        raise NotImplementedError
```

Good: split the contract so each type promises only what it does.

```python
class Reader(Protocol):
    def read(self, key: str) -> bytes: ...

class Writer(Protocol):
    def write(self, key: str, data: bytes) -> None: ...

class FileStorage: ...       # satisfies Reader and Writer
class ReadOnlyArchive: ...   # satisfies Reader only
```

Review question: can every caller of the base type take this subtype without a type check or a new `try`?

Source: Liskov, "Data Abstraction and Hierarchy" (OOPSLA keynote, 1987); Liskov and Wing, "A Behavioral Notion of Subtyping" (1994).

## 4. Interface segregation (ISP)

A caller depends only on what it uses. `SKILL.md` holds the rule ("Give each caller a narrow interface with only what it uses"); this entry adds the signs and the limit. With structural typing (Python `Protocol`, TypeScript interfaces, Go interfaces) a narrow interface costs a few lines, so declare it next to the code that consumes it. Go's Code Review Comments give the same advice: the interface belongs in the package that uses it.

You see it broken when a test fake stubs ten methods to exercise one, when a parameter is typed as a whole service but the function calls one method, or when a change to an unrelated method forces callers to change.

It hurts as a reflex: one interface per method, or a narrow interface where every caller uses the whole thing.

Bad:

```ts
function sendReceipt(orders: OrderService, id: string): void {
  const order = orders.get(id); // OrderService has 25 methods
  mailer.send(order.email, receipt(order));
}
```

Good:

```ts
interface OrderLookup {
  get(id: string): Order;
}

function sendReceipt(orders: OrderLookup, id: string): void { ... }
```

Review question: what does this caller actually call, and could its test fake be three lines?

Source: Martin, Agile Software Development.

## 5. Dependency inversion (DIP)

Policy (business rules) doesn't import mechanism (a database driver, an HTTP client, a vendor SDK, the clock). Both depend on an interface the policy side owns, and the concrete pieces are wired at the edge (`main`, the app factory, the framework's dependency injection). Dependency injection in `patterns.md` is the mechanism.

You see it broken when a domain function imports `requests`, `boto3`, the ORM session or `fetch`, when tests patch module globals to stop a network call, or when the rule can't run from a CLI or a worker without the web framework.

It hurts when it adds an interface with one implementation and no test fake, made "for later": one adapter is a hypothetical seam (`improve-codebase-architecture`). In a framework app the ORM already is the persistence layer, and wrapping it in ports adds a hop for nothing (`~/.agents/skills/backend-design/skills/domain-modeling/README.md`, "When not to use DDD patterns"). Invert where something really varies or must be faked: a third-party API, the clock, randomness, a message bus.

Bad: the rule knows the vendor.

```python
def charge(order: Order) -> None:
    stripe.PaymentIntent.create(amount=order.total_cents, currency="usd")
```

Good: the rule owns the interface, and the Stripe adapter lives at the edge.

```python
class PaymentGateway(Protocol):
    def charge(self, amount: Money, idempotency_key: str) -> ChargeResult: ...

def charge(order: Order, gateway: PaymentGateway) -> ChargeResult:
    return gateway.charge(order.total, idempotency_key=f"order-{order.id}")
```

Review question: can this rule be tested without the network, and does the interface belong to the side that uses it?

Source: Martin, Agile Software Development, and Clean Architecture (the dependency rule).

## 6. Keep it simple (KISS)

Pick the design with the fewest concepts and moving parts that meets today's requirements and that the next reader understands without a walkthrough. Fewer concepts, not fewer lines: a dense one-liner is often the complicated version.

You see it broken when a pattern or a framework serves a problem with one case, when a generic engine (rules engine, plugin loader, config DSL) holds three rules, when reflection, metaprogramming or dynamic dispatch replaces a function call, or when a clever expression needs a comment to be read.

It hurts when "simple" drops a real requirement (a transaction, a timeout, idempotency on a payment). That is missing work, and it costs more once it ships. A familiar design can still be tangled: Hickey separates simple (few interleaved parts) from easy (close at hand).

Bad:

```ts
const handlers = Object.fromEntries(
  Object.entries(rules).map(([tier, r]) => [tier, compose(...r.steps.map(resolveStep))]),
);
export const applyDiscount = (o: Order) => handlers[o.tier]?.(o) ?? o;
```

Good:

```ts
export function applyDiscount(order: Order): Order {
  if (order.tier === "gold") return withDiscount(order, 0.1);
  return order;
}
```

Review question: what is the plainest version that passes the same tests, and what does this version buy over it?

Source: the phrase is attributed to Kelly Johnson at Lockheed's Skunk Works; Rich Hickey's talk "Simple Made Easy"; `~/.agents/skills/backend-design/skills/boring-by-default/README.md` applies it to infrastructure.

## 7. Don't repeat yourself (DRY)

Every piece of knowledge (a business rule, a format, a constant that must match elsewhere) has one authoritative home. `SKILL.md` holds the rule and the rule of three; this entry is for telling duplicated knowledge from code that only looks alike.

You see it broken when one rule lives in two places that must change together (tax rounding in the API and in the export), when a value "that must match" sits in two files, or when a bug fixed in one copy turns up later in the other.

It hurts when it merges code that only looks alike: two functions that change for different reasons end up coupled through one helper with flags. Across bounded contexts or services, a shared model package couples their deploys (A2 in `~/.agents/skills/backend-design/skills/anti-patterns/README.md`). Until the third copy shows what's really shared, keep the copies.

Bad: one rule in two places, and the copies already disagree.

```python
# api/serializers.py
total = (subtotal * Decimal("1.0825")).quantize(Decimal("0.01"))
# reports/export.py
total = round(subtotal * 1.0825, 2)  # float, and rounds differently
```

Good:

```python
# billing/tax.py
def with_sales_tax(subtotal: Decimal) -> Decimal:
    return (subtotal * SALES_TAX).quantize(CENT, rounding=ROUND_HALF_UP)
```

Bad (over-applied): two validators merged because they looked alike.

```python
def validate(data: dict, *, is_signup: bool, is_admin_edit: bool) -> None: ...
```

Good: `validate_signup` and `validate_admin_edit` stay apart, because they change for different reasons.

Review question: if this rule changes, how many places must change and would anyone know? And for an extraction: do these copies change for the same reason?

Source: Hunt and Thomas, The Pragmatic Programmer (DRY is about knowledge); Fowler, Refactoring (the rule of three, credited to Don Roberts); Sandi Metz, "The Wrong Abstraction" ("duplication is far cheaper than the wrong abstraction").

## 8. You aren't gonna need it (YAGNI)

Build what the current task needs, without parameters, hooks, config, layers or generality for a future need nobody has asked for. `SKILL.md` "How to work" holds the rule; this entry adds the limit.

You see it broken when an option has the same value at every call site, an abstract base has one subclass, a config key is never set, or a comment says "in case we need".

It hurts when the "future" is a decision that is cheap now and expensive after release: a public API shape, a column type, an id format, idempotency on a payment endpoint. Decide those now. YAGNI covers features and flexibility; it never covers the quality of what you build (tests, error handling, timeouts).

Bad: only CSV is used, and no caller passes the other options.

```python
def export_orders(orders, fmt="csv", compress=False, encryption=None, plugin=None): ...
```

Good:

```python
def export_orders_csv(orders: list[Order]) -> bytes: ...
```

Review question: which ticket or caller needs this option today, and what would adding it later cost?

Source: Extreme Programming (Beck, Jeffries); Fowler's "Yagni" article (the cost of building, delay and carry, and the exception for work that makes later change easier).

## 9. Separation of concerns

Each part of the code deals with one concern (transport, business rules, persistence, presentation, a cross-cutting policy such as auth or retries) and knows little about the others. The layer rules in `SKILL.md` "Design and architecture" are the concrete form.

You see it broken when business rules sit in a view, serializer, controller or UI component, when domain code builds HTTP status codes or reads the request, or when retries and logging are hand-written in every function.

It hurts when concerns that always change together are spread over many files: adding one field touches eight. For a UI component, keeping markup, style and behavior together (locality of behavior) is often easier to change. Separate what changes independently.

Bad: the rule, the persistence and the HTTP answer in one handler.

```python
@app.post("/orders/{order_id}/cancel")
def cancel(order_id: int) -> JSONResponse:
    order = db.get(Order, order_id)
    if order.status == "shipped":
        return JSONResponse({"error": "shipped"}, status_code=409)
    order.status = "cancelled"
    db.commit()
    return JSONResponse({}, status_code=200)
```

Good: the handler translates, and the service owns the rule.

```python
@app.post("/orders/{order_id}/cancel", status_code=204)
def cancel(order_id: int) -> None:
    try:
        orders.cancel(order_id)
    except CannotCancelShipped:
        raise HTTPException(409, "order already shipped")
```

Review question: could this rule run from a CLI or a queue consumer without the web framework?

Source: Dijkstra, "On the role of scientific thought" (EWD 447); Carson Gross, "Locality of Behaviour", for the counterweight.

## 10. High cohesion, low coupling

Code that changes together lives together (cohesion), and modules know as little as possible about each other and talk through small interfaces (coupling). Most other entries here are ways to get these two.

You see it broken when one change edits many files (Shotgun Surgery), when a method uses another object's data more than its own (Feature Envy), when a module reads another module's tables or internals (A1 in the anti-patterns file), or when `git log` shows two files that always change together with no import between them, a hidden coupling (`improve-codebase-architecture`).

It hurts when it chases zero coupling: an event bus or an interface between two modules that are really one hides the dependency instead of removing it. Some coupling is the point; make it explicit and one-directional.

To judge one coupling, weigh three things. Strength, from strongest: reading the other side's internals or tables, sharing a business rule or a transaction, using its domain model, using a contract built for integration. Distance: same function, module, app, service, team. Volatility: how often the upstream changes. Strong coupling is fine at short distance, where it is cohesion, and against a module that rarely changes, such as auth or email. Across a service or team boundary, keep it to a contract. A business rule copied into two modules couples them even with no import between them.

Bad: shipping reaches into billing's storage.

```python
from billing.models import InvoiceLine

lines = InvoiceLine.objects.filter(invoice__order_id=order.id, taxable=True)
weight = sum(line.qty * line.product.weight_kg for line in lines)
```

Good: the owner exposes what others need.

```python
from orders.api import order_weight_kg

weight = order_weight_kg(order.id)
```

Review question: when this changes, what else has to change, and is that list inside one module?

Source: Yourdon and Constantine, Structured Design; Hunt and Thomas, The Pragmatic Programmer (orthogonality); Vlad Khononov, Balancing Coupling in Software Design, via `coupling-analysis` in tech-leads-club/agent-skills (MIT, https://github.com/tech-leads-club/agent-skills).

## 11. Composition over inheritance

Reuse behavior by holding and delegating to objects, not by subclassing. Keep inheritance for a real is-a relation that keeps the base's contract (§3), or for the extension points a framework designed for subclassing.

You see it broken when a hierarchy is more than two levels deep, when subclasses override most of the base, when class names combine features (`CachedRetryingHttpClient`), or when a base class keeps growing protected helpers for its children.

It hurts when it fights the framework. Django class-based views, DRF viewsets and `unittest.TestCase` are built to be subclassed; follow the repo's pattern there.

Bad: every combination of features is a new class.

```python
class HttpClient: ...
class RetryingHttpClient(HttpClient): ...
class CachedHttpClient(HttpClient): ...
class CachedRetryingHttpClient(RetryingHttpClient): ...
```

Good: wrappers compose (the decorator pattern in `patterns.md`).

```python
client = Cached(Retrying(HttpClient(timeout=2.0), attempts=3), ttl_seconds=60)
```

Review question: does the subclass keep every promise of its base, or does it only want some of its code?

Source: Gamma, Helm, Johnson and Vlissides, Design Patterns ("Favor object composition over class inheritance").

## 12. Law of Demeter

A method talks to its own fields, its parameters and the objects it creates, not to the objects those return. Navigation through a chain ties the caller to every link in it.

You see it broken when a caller walks `order.customer.account.billing_address.country` (Message Chains), when a test builds a deep object graph to reach one value, or when changing an inner object's structure breaks distant callers.

It hurts when applied to plain data: DTOs, parsed JSON, config, immutable records, fluent builders and query builders. Wrapping their fields in forwarding methods adds Middle Men. The law is about objects that hide behavior, and counting dots isn't the rule.

Bad:

```ts
if (order.customer.account.billingAddress.country === "US") applyUsTax(order);
```

Good:

```ts
if (order.billingCountry() === "US") applyUsTax(order);
```

Review question: if the inner structure changes, how many callers break?

Source: Lieberherr and Holland, "Assuring Good Style for Object-Oriented Programs" (IEEE Software, 1989).

## 13. Tell, don't ask

Tell an object to act on its own data instead of reading its data, deciding outside and writing the result back. The rule then lives with the data it guards, once.

You see it broken when callers read a field, branch and set a field on the same object, when the same check precedes the same write in several services, or when models are bags of fields set from outside (A4, anemic models, in the anti-patterns file).

It hurts when every behavior moves into the entity, including rendering, persistence and notifications, which breaks §1. Tell the object to change its own state and enforce its own invariants; keep the rest outside. Reading data for display or reports is fine.

Bad: the overdraft rule is repeated by every caller.

```python
if account.balance >= amount:
    account.balance -= amount
```

Good:

```python
account.withdraw(amount)  # raises InsufficientFunds
```

Review question: is the decision about this object's state made by the object, or repeated by its callers?

Source: Hunt and Thomas, "Tell, Don't Ask" (IEEE Software); Fowler's "TellDontAsk" article.

## 14. Command-query separation

A function either returns information or changes state, never both. `design-rules.md` §6 (Query With Side Effects) has the examples and the exception: an operation that must check and write atomically (pop, compare-and-set, consume quota) stays one command whose name says it writes.

Review question: can a caller "just check" this without changing anything?

Source: Meyer, Object-Oriented Software Construction.

## 15. Fail fast

Detect bad input or a broken state as early as possible and stop loudly with a precise error, instead of carrying a bad value onward or substituting a default.

You see it broken when code catches every exception and continues, reads a required field with `.get(key, "")` or `?? 0`, validates after a partial write, or reads config lazily so a typo fails on the first night run instead of at startup.

It hurts in batch or stream work when one bad record stops ten thousand good ones: fail fast per item, collect the failures and report them (a dead-letter queue in `patterns.md`). A failing remote dependency is a different case, handled with timeouts, retries and circuit breakers. Fail fast is also never a reason to crash on a user's typo: fail with a message the user can act on.

Bad: the empty URL fails later, far from the cause.

```python
def load_settings() -> Settings:
    return Settings(api_url=os.environ.get("API_URL", ""))
```

Good: startup fails and names the missing variable.

```python
def load_settings() -> Settings:
    return Settings(api_url=os.environ["API_URL"])
```

Review question: where does this bad value get noticed, and how far is that from where it entered?

Source: Jim Shore, "Fail Fast" (IEEE Software, 2004); Hunt and Thomas, The Pragmatic Programmer ("Crash Early").

## 16. Least astonishment

Code behaves the way its name, signature and the surrounding conventions lead a reader to expect. The same holds for APIs and UIs.

You see it broken when a getter writes (§14), `delete` archives, a function mutates its argument and also returns it, a parameter's unit isn't in its name (`timeout=30`: seconds or milliseconds?), an API returns 200 with an error body, or a function is named differently from its siblings for the same kind of operation.

It hurts when a "less surprising" style is introduced in one place against a convention the repo uses everywhere. Readers expect the repo's convention; raise a change to it as a proposal instead.

Bad: the caller's list is sorted too.

```python
def normalize(items: list[str]) -> list[str]:
    items.sort()
    return items
```

Good:

```python
def normalized(items: list[str]) -> list[str]:
    return sorted(items)
```

Review question: would a caller who reads only the name and the signature be surprised by what this does?

Source: Raymond, The Art of Unix Programming ("Rule of Least Surprise").

## 17. Make illegal states unrepresentable

Shape types so an invalid combination can't be built, and turn untyped input into a typed value once at the boundary (parse, don't validate), so code inside doesn't check again. `SKILL.md`'s one-status-field rule and value objects (`~/.agents/skills/backend-design/skills/domain-modeling/README.md`) are applications of it.

You see it broken when optional fields are only valid together (`shipped_at` set while `status` isn't `shipped`), when two booleans can both be true but mustn't (`is_paid` and `is_refunded`), when the same `if not user.email` check repeats deep inside, or when a plain `str` carries an id, an email or a currency.

It hurts when every rule is pushed into the type system and the types become unreadable; rules that change often or depend on stored data stay in code. In Python the types are checked at runtime only where something validates them, so parse at the boundary (Pydantic, a constructor that raises).

Bad: a paid payment without `paidAt` type-checks.

```ts
type Payment = { status: string; paidAt?: Date; failureReason?: string };
```

Good:

```ts
type Payment =
  | { status: "pending" }
  | { status: "paid"; paidAt: Date }
  | { status: "failed"; failureReason: string };
```

Review question: can this type hold a state the business says can't happen?

Source: Yaron Minsky, "Effective ML" talk (Jane Street); Alexis King, "Parse, don't validate".

## 18. Acyclic and stable dependencies

Module dependencies form no cycles and point toward modules that change less: entry points depend on services, services on the domain, adapters on the domain's interfaces, and the domain on nothing in the app.

You see it broken when an import cycle is dodged with an import inside a function or a `TYPE_CHECKING` guard, when a `common` or `utils` package imports feature modules, or when a module that most PRs touch is imported by everything.

It hurts when a small app gets a package graph and stability metrics. Enforce the direction with the repo's boundary checker once a boundary keeps being crossed (`design-rules.md` §7).

Bad: orders and billing import each other, and the cycle hides inside a function.

```python
# orders/service.py
from billing.service import create_invoice

# billing/service.py
def create_invoice(order_id: int) -> Invoice:
    from orders.service import get_order
    ...
```

Good: billing depends on orders' public API, and orders doesn't know billing exists; a workflow above both, or an "order placed" event, calls billing.

```python
# billing/service.py
from orders.api import get_order
```

Review question: does this new import create a cycle, or make a stable module depend on a volatile one?

Source: Martin, Agile Software Development (the Acyclic Dependencies and Stable Dependencies principles) and Clean Architecture.

## 19. Robustness principle, with care

Be strict in what you send. When reading another system's data, ignore fields you don't know (a tolerant reader), and reject a value that is malformed or breaks a rule instead of guessing what the sender meant. `SKILL.md` asks consumers to tolerate added or removed fields; this entry sets the other edge.

You see it broken one way when a consumer fails on an added field, and the other way when a parser accepts "1,000.00", "1.000,00" and "1000" for one field and guesses, or coerces an invalid value into a valid-looking one.

It hurts when "be liberal in what you accept" is taken whole: every quirk you accept becomes part of the contract (Hyrum's law) and hides the sender's bugs, which is why RFC 9413 advises against it for protocols. Tolerate additions, stay strict on meaning, and pair it with fail fast (§15).

Bad:

```python
amount = Decimal(raw["amount"].replace(",", "").replace("$", "") or "0")
```

Good:

```python
class PaymentIn(BaseModel):
    model_config = ConfigDict(extra="ignore")  # new sender fields don't break us
    amount: Decimal                             # a malformed amount is rejected
```

Review question: does this reader break on an added field, or accept a value it has to guess at?

Source: Postel, RFC 761; Thomson and Schinazi, RFC 9413 "Maintaining Robust Protocols"; Fowler's "TolerantReader" article.

## 20. How the principles conflict

The principles pull against each other, and most bad designs come from applying one without the others. These are the common conflicts and the side that wins.

KISS and YAGNI against OCP, DIP and ISP. Each SOLID seam adds a name and a hop. Add a seam when something varies today: two implementations (a real one and a test fake counts), a third variant, or a dependency you must fake to test. Until then KISS wins.

SRP against KISS. SRP says split by reason to change; KISS says fewer parts. Split when a second reason has shown up in real changes (`git log` shows unrelated tickets editing the module) or when the module hides two decisions. Don't split a small function into classes in advance, and never split by step order.

DRY against low coupling. Shared code couples everything that uses it. Inside one module or bounded context, DRY wins for knowledge. Across bounded contexts or services, decoupling wins: each side keeps its own model, even if the two look alike, and translates at the boundary (`design-rules.md` §4). Share only knowledge that really is the same and stable (a money type, a published contract), and version it.

DRY against readable tests. Readability wins (`SKILL.md` "Testing").

Tell, don't ask against SRP. Telling the object to do everything piles every concern on it. The object enforces its own state and invariants; rendering, persistence and notifications stay outside.

Law of Demeter against plain data. Apply the law to objects with behavior; navigate plain data structures freely.

Separation of concerns against locality of behavior. Separate what changes independently; keep together what always changes together, such as a component's markup and its handlers.

Fail fast against the robustness principle. Be strict on meaning and tolerant of additions. Inside the process, fail fast; at a remote dependency, handle failure with the resilience patterns in `patterns.md`.

Composition against the framework. Follow the framework's extension model where it has one.

Any principle against the repo's conventions. The repo's documented pattern wins unless it causes a bug; propose the change separately instead of mixing styles.

When unsure, settle it in this order: correctness and the system's invariants first, then the repo's own rules, then KISS and YAGNI to decide whether to add structure at all, then cohesion, SRP and information hiding to decide where code goes, then DRY within one context, then the rest.
