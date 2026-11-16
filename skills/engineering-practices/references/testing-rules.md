# Testing rules, explained

Read this when a testing rule in `SKILL.md` points here and you need the reasoning or an example. Each rule has the why, a bad and a good example, and its source (the books are in `books.md`).

## Contents

1. Property-based tests for invariants
2. Sprout and wrap in code you can't test

## 1. Property-based tests for invariants

When code must hold an invariant over a large input space (money math, parsers and serializers, merges, state machines), a few hand-picked examples test the cases the author already thought of. A property-based test states the invariant and lets the tool generate inputs and shrink any failure to the smallest counterexample. Use the library the repo already has (the language skills name them); without one, use the language's built-in fuzzing where it has it, or a generated table of cases, since adding a test library is a new dependency.

Bad: two cases the author picked; splitting 100 cents three ways loses a cent and no test notices.

```python
def test_split():
    assert split(100, 2) == [50, 50]
    assert split(10, 5) == [2, 2, 2, 2, 2]
```

Good: the invariant, checked over generated inputs.

```python
from hypothesis import given, strategies as st

@given(total=st.integers(min_value=0, max_value=10**9), parts=st.integers(min_value=1, max_value=50))
def test_split_keeps_every_cent(total: int, parts: int) -> None:
    shares = split(total, parts)
    assert sum(shares) == total
    assert max(shares) - min(shares) <= 1
```

Source: QuickCheck (Claessen and Hughes), the origin of property-based testing; Designing Data-Intensive Applications, 2nd edition.

## 2. Sprout and wrap in code you can't test

When new behavior must go into a function too tangled to put under test, growing its body adds untested code to untested code. Write the new behavior as a new function or class with its own tests and call it from one line in the old code (sprout). When the new behavior runs before or after the old one, rename the old function and wrap it with a new function of the original name (wrap). The old body stays as it was until someone puts it under test.

Bad: new logic inside a 400-line function nobody can test.

```python
def process_order(order: Order) -> None:
    ...
    if order.customer.tier == "gold" and order.total > 500:
        order.total -= order.total * Decimal("0.05")
    ...
```

Good, sprout: the new rule is a tested function, and the old body gains one call.

```python
def loyalty_discount(tier: Tier, total: Decimal) -> Decimal:
    if tier is Tier.GOLD and total > 500:
        return total * Decimal("0.05")
    return Decimal(0)

def process_order(order: Order) -> None:
    ...
    order.total -= loyalty_discount(order.customer.tier, order.total)
    ...
```

Good, wrap: the new step runs around the untouched old function.

```python
def post_payment(payment: Payment) -> None:
    audit_log.record("payment.posted", payment.id)
    _post_payment_unaudited(payment)        # the old function, renamed, body unchanged
```

Source: Working Effectively with Legacy Code, "Sprout Method", "Sprout Class" and "Wrap Method".
