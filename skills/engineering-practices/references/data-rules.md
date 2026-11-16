# Data, contract and distributed-systems rules, explained

Read this when a rule in the "Transactions, events and distributed systems" or "Data, schema and contract changes" sections of `SKILL.md` points here and you need the reasoning or an example. Each rule has the why, a bad and a good example, and its source (the books are in `books.md`).

## Contents

1. Hyrum's law: observable behavior is contract
2. Name the system of record for every copy
3. Change an invariant's rows together, and nothing else
4. Monotonic clocks for durations, versions for ordering

## 1. Hyrum's law: observable behavior is contract

With enough callers, every observable behavior of an interface has someone relying on it, whatever the docs promise: result order, default page size, null versus a missing key, error text a client parses, how long a call takes, whether it is synchronous. Before changing such a behavior on a live interface, search the consumers as you would for a breaking change, and treat a change someone relies on as breaking (expand, migrate, contract). This is about changing a live interface; what a test should assert is a separate question, covered in the Testing section.

Bad: "clean up" a response by dropping null fields, since no doc said they were there.

```jsonc
// before: the key is always present, null when there is no discount
{"id": 7, "discount": null}
// after: the key is gone
{"id": 7}
// A client that does `"discount" in order` to decide whether to show the row breaks.
```

Good: keep the shape callers see, and ship a change to it as a breaking change (a new field or version, consumers moved, then the old shape removed).

```jsonc
{"id": 7, "discount": null}
```

Bad: an unpromised order that callers paginate by.

```sql
-- No ORDER BY was promised, but rows came back in id order, and a consumer
-- resumes from "the last id it saw". A new index changes the order and the
-- consumer starts skipping rows.
SELECT * FROM orders WHERE company_id = $1 LIMIT 100;
```

Good: make the behavior callers depend on explicit, and keep it.

```sql
SELECT * FROM orders WHERE company_id = $1 AND id > $2 ORDER BY id LIMIT 100;
```

Source: Software Engineering at Google, Hyrum's law.

## 2. Name the system of record for every copy

Every copy of data (a cache, a denormalized column, a search index, a counter, an export, a table in another service) is derived from one system of record. Say which one, and how the copy is rebuilt from it: a backfill job, a replay of events, a cache that refills on miss. A copy nobody can rebuild becomes a second source of truth that drifts and can't be fixed. Also say whether it is a derived copy (must follow the source) or a snapshot (frozen on purpose, like the price on an invoice), because the fix for a mismatch is the opposite in each case.

Bad: a copy with no owner and no way back.

```sql
ALTER TABLE orders ADD COLUMN customer_name text;
```

Good: the copy says where it comes from and how to rebuild it.

```sql
ALTER TABLE orders ADD COLUMN customer_name text;
COMMENT ON COLUMN orders.customer_name IS
  'Derived from customers.name. Kept in sync by the customer-renamed consumer; rebuild with the rebuild-order-customer-names job.';
```

Source: Designing Data-Intensive Applications, "Systems of Record and Derived Data".

## 3. Change an invariant's rows together, and nothing else

Name the invariant a write protects (an order's total equals the sum of its lines; a ledger balances) and the smallest set of rows it spans. Those rows change in one transaction, through their owning parent row, so no reader sees half of it. Rows outside that set (stock, statistics, notifications) update after commit, from an event or a job, instead of widening the transaction to include them. Use this to choose transaction and lock boundaries only; it doesn't call for repository or port layers in an ORM-centric codebase. Adding a lock still follows the lock rule in `SKILL.md`.

Bad: the invariant spans two transactions, and unrelated rows ride along in the second.

```python
with transaction():
    add_line(order_id, item, qty)
with transaction():
    recompute_total(order_id)                 # a reader between the two sees a wrong total
    bump_customer_stats(customer_id)
    reserve_stock(item, qty)
```

Good: the lines and the total change together, guarded by the order row's version; the rest follows the commit.

```python
with transaction():
    order = load_order(order_id)
    order.add_line(item, qty)                 # updates lines and total together
    save_order(order)                         # UPDATE orders ... WHERE id = :id AND version = :version
    outbox_add("order.line_added", order.id, item, qty)
# stock and customer stats update from the event, outside this transaction
```

Source: Domain-Driven Design (Evans) and Implementing Domain-Driven Design (Vernon), aggregates as consistency boundaries.

## 4. Monotonic clocks for durations, versions for ordering

The wall clock can jump (NTP steps it, an operator changes it, a VM resumes), so an elapsed time measured with it can come out negative or hours long. Measure durations and timeouts with the monotonic clock (the language skills name the call). Clocks on different machines also disagree, so "latest timestamp wins" can keep the older write. Order events and pick winners with something one authority hands out: a sequence, a version column, a broker offset.

Bad: a duration from the wall clock, and a winner picked by two hosts' clocks.

```python
start = time.time()
call()
elapsed = time.time() - start
```

```sql
UPDATE prices SET amount = $2, updated_at = $3 WHERE sku = $1 AND updated_at < $3;
```

Good: the monotonic clock, and a version the database hands out.

```python
start = time.monotonic()
call()
elapsed = time.monotonic() - start
```

```sql
UPDATE prices SET amount = $2, version = version + 1 WHERE sku = $1 AND version = $3;
```

Source: Designing Data-Intensive Applications, "Unreliable Clocks".
