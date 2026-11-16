# Design rules, explained

Read this when a design rule in `SKILL.md` points here and you need the reasoning or an example to apply it. Each rule has the why, a bad and a good example, and its source (the books are in `books.md`). The examples are short Python, TypeScript or config; the rules hold in any language.

## Contents

1. Split modules by the knowledge they hide
2. Pull complexity down
3. Define errors out of existence
4. Translate foreign models at the boundary (anti-corruption layer)
5. Flag Argument
6. Query With Side Effects
7. Keep architecture rules in a checker (fitness functions)
8. Use the domain's words

## 1. Split modules by the knowledge they hide

A module earns its place by hiding a design decision (a file format, a protocol, an ordering rule) so that changing the decision touches one module. Splitting code by the order steps run (read, then parse, then write) spreads one decision across every step, so a change to it edits all of them. Ousterhout calls this information leakage, and the split by step order temporal decomposition. When two modules both know the same format or rule, merge them or move that knowledge behind one interface.

Bad: three functions split by step order, and two of them know the column layout.

```python
def read_rows(path: Path) -> list[list[str]]: ...

def parse_order(row: list[str]) -> Order:
    return Order(id=row[0], total=Decimal(row[3]) / 100)   # knows column 3 is cents

def write_order(writer: CsvWriter, order: Order) -> None:
    writer.writerow([order.id, "", "", int(order.total * 100)])  # knows it again
```

Good: one module owns the format, and callers only see `Order`.

```python
class OrderFile:
    def load(self, path: Path) -> list[Order]: ...
    def save(self, path: Path, orders: list[Order]) -> None: ...
```

Source: A Philosophy of Software Design, "Information Hiding (and Leakage)".

## 2. Pull complexity down

When every caller of a module makes the same choice (the same normalization, the same retry policy, the same default), make it inside the module once. A parameter or exception that every caller handles the same way moves the module's complexity into each caller. This only applies to a choice every caller already makes identically: it is not a license to invent defaults or fallbacks nobody asked for, and a choice callers make differently stays a parameter.

Bad: every caller normalizes the code and repeats the same retry settings.

```python
rate = rates.fetch(code.strip().upper(), retries=3, timeout=2.0)
```

Good: the module does what every caller did.

```python
def fetch(code: str) -> Decimal:
    return _client.get_rate(code.strip().upper(), retries=3, timeout=2.0)

rate = rates.fetch(code)
```

Source: A Philosophy of Software Design, "Pull Complexity Downwards".

## 3. Define errors out of existence

When the caller's goal is already met (delete something already gone, cancel something already cancelled, add a member who is already in), returning quietly is the correct answer, and raising forces every caller to write the same handler that ignores it. Keep raising when the state means a real conflict or a bug: this rule never covers swallowing an unexpected error, and "fail loudly" still holds everywhere else.

Bad: every caller wraps `cancel` in a try that ignores `AlreadyCancelled`.

```python
def cancel(order: Order) -> None:
    if order.status is Status.CANCELLED:
        raise AlreadyCancelled(order.id)
    ...
```

Good: the goal is met, so return; a shipped order is a real conflict and still raises.

```python
def cancel(order: Order) -> None:
    if order.status is Status.CANCELLED:
        return
    if order.status is Status.SHIPPED:
        raise CannotCancelShipped(order.id)
    ...
```

Source: A Philosophy of Software Design, "Define Errors Out of Existence".

## 4. Translate foreign models at the boundary (anti-corruption layer)

A vendor's or legacy system's model (field names, status codes, error codes) changes on the vendor's schedule and carries meanings that don't match yours. Translate it into your own types in one adapter at the boundary, so domain code never branches on the vendor's vocabulary and a vendor change edits one file.

Bad: domain code reads the carrier's codes directly.

```python
if shipment["sts"] in ("C3", "C4") and shipment["dlv_dt"]:
    order.mark_delivered(shipment["dlv_dt"])
```

Good: one adapter maps the validated wire type to a domain type.

```python
_DELIVERED_CODES = {"C3", "C4"}  # the carrier's codes for "delivered" and "left at door"

def to_delivery(raw: CarrierShipment) -> Delivery:
    return Delivery(delivered=raw.sts in _DELIVERED_CODES, delivered_at=raw.dlv_dt)

delivery = to_delivery(shipment)
if delivery.delivered:
    order.mark_delivered(delivery.delivered_at)
```

Source: Domain-Driven Design (Evans), the anti-corruption layer pattern.

## 5. Flag Argument

A boolean parameter that picks between two behaviors hides which behavior a call site gets (`send(user, msg, true)`), and the function body holds two functions. Split it into two functions named for each behavior. A boolean that is data passed through (a stored setting the function records) is fine.

Bad:

```ts
sendNotification(user, msg, true);

function sendNotification(user: User, msg: string, urgent: boolean): void {
  if (urgent) {
    sms.send(user.phone, msg);
    return;
  }
  email.send(user.email, msg);
}
```

Good:

```ts
sendUrgentNotification(user, msg);   // texts
sendNotification(user, msg);         // emails
```

Source: Refactoring (Fowler), "Remove Flag Argument"; Fowler's FlagArgument article.

## 6. Query With Side Effects

A function named as a question (`is_`, `has_`, `get_`, `check_`) is expected to only read. When it also writes, a caller that "just checks" changes state, and calling it twice changes it twice. Keep the query and the command apart, and name the command for its write. When the check and the write must be atomic (a race between them), keep them in one command whose name says it writes, and make the write conditional.

Bad: checking the quota spends it.

```python
def has_quota(account: Account) -> bool:
    if account.calls_left > 0:
        account.calls_left -= 1
        account.save()
        return True
    return False
```

Good: a pure query, and a command named for its write that decides atomically.

```python
def has_quota(account: Account) -> bool:
    return account.calls_left > 0

def try_consume_quota(account_id: int) -> bool:
    # UPDATE accounts SET calls_left = calls_left - 1
    # WHERE id = :id AND calls_left > 0
    return accounts.decrement_if_positive(account_id) == 1
```

Source: Refactoring (Fowler), "Separate Query from Modifier"; command-query separation from Meyer's Object-Oriented Software Construction.

## 7. Keep architecture rules in a checker (fitness functions)

A layering rule ("the domain never imports the web layer") written only in a doc or a review comment gets broken the first time nobody is looking. An automated check that fails the build when the rule breaks keeps it true. When the repo already has a boundary checker, add the rule there. When a boundary keeps being crossed in review and the repo has none, propose one to the user instead of adding a tool (a new tool is a new dependency). The language skills name the checker for each language.

Bad: the same review comment on three PRs.

```text
"services/ must not import from api/, please move this helper."
```

Good: the rule lives in the checker the repo already runs (import-linter shown).

```ini
[importlinter:contract:layers]
name = API depends on services, services on domain, never the reverse
type = layers
layers =
    app.api
    app.services
    app.domain
```

Source: Building Evolutionary Architectures (Ford, Parsons, Kua), fitness functions.

## 8. Use the domain's words

Code, API fields and tests use the word the business uses for a concept, the one in the repo's glossary or the one product and support say. When code and business use different words for one thing, every reader translates, and the next author adds a third word. Flag the mismatch instead of picking a new synonym.

Bad: product says "brand", the API says "seller", and new code adds a third word.

```python
def get_supplier_orders(supplier_id: int) -> list[Order]: ...
```

Good: the glossary word, with the mismatch raised in the PR.

```python
def list_brand_orders(brand_id: int) -> list[Order]: ...
```

Source: Domain-Driven Design (Evans), ubiquitous language.
