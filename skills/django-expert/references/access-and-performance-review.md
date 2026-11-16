# Access and performance review

How to review Django and DRF code for cross-company data access and for query performance, and report only findings you traced in the code. Method adapted from getsentry's `django-access-review` and `django-perf-review` skills (Apache-2.0, https://github.com/getsentry/skills), rewritten for a marketplace where every record belongs to a company and orders have a buyer side and a seller side.

## Contents

- How to review
- Access review
  - 1. Learn the authorization model
  - 2. Map the endpoints
  - 3. Trace each endpoint
  - DRF gaps that pass a quick read
  - Marketplace checks
  - Fixes and tests
- Performance review
  - N+1 queries
  - Unbounded querysets
  - Missing indexes
  - Write loops
  - What to leave out
- Finding format

## How to review

- Read how this codebase does authorization and data access before judging any line. Every project has its own base views, permission classes and managers.
- Report a finding only after tracing it from the request to the query. A pattern match is a lead to investigate.
- Zero findings is a valid result. Say what you checked.
- Match severity to impact. A finding you would describe as "minor" is not high or critical.
- Unconfirmed leads go under "Needs manual check" with what would confirm them, never as findings.

## Access review

The question for every endpoint, task and export: can a user of company A read, change or delete company B's data by sending B's ID?

### 1. Learn the authorization model

Answer these before reading the diff, with `file:line` for each:

- Where checks live: `DEFAULT_PERMISSION_CLASSES` in settings, project base views and mixins, custom permission classes, decorators, middleware.
- How the requesting company is resolved: from the user's membership, a session value, a URL kwarg or a header. If the URL or a header names the company, find where membership in that company is checked.
- How querysets get scoped: `get_queryset()` overrides, custom managers or queryset methods (`for_company(...)`), filter backends.
- The ownership model per resource: which field points at the owning company, and for orders, which fields point at buyer and seller.

```bash
grep -rn "DEFAULT_PERMISSION_CLASSES\|permission_classes\|has_object_permission" --include="*.py" | head -30
grep -rn "def get_queryset\|class .*Manager\|class .*QuerySet" --include="*.py" | head -30
grep -rn "class Base.*View\|class .*Mixin" --include="*.py" | head -30
```

Done when you can say in two sentences how a request gets its company and where its querysets get filtered by it.

### 2. Map the endpoints

For each resource the change touches, list every way in: list, retrieve, create, update, partial update, delete, each `@action`, nested routes, bulk endpoints, exports and reports, Celery tasks and webhooks that take an ID, admin actions. Note where each ID enters: URL path, query param, request body, task argument.

### 3. Trace each endpoint

1. Find where the ID enters.
2. Find the query or call that fetches with it.
3. List every check between the two: queryset scoped to the company, explicit ownership check, object permission, base class, manager, middleware.
4. Before calling a check missing, read the parent classes, the manager, the middleware and the URL-level decorators.

Also ask:

- List endpoints: does the queryset filter by company, or return every row?
- Create: does the server set the company and owner, or can the request body set them?
- Related resources: if A can read an order, can A read its line items, documents and payments through their own routes, and does a nested route check the child belongs to the parent?
- Company switching: if a user belongs to several companies, is the switch checked against membership?

Done when every endpoint in the map has its check named with `file:line`, or is a finding.

### DRF gaps that pass a quick read

- `has_object_permission()` runs only inside `self.get_object()`. A view that calls `Model.objects.get(pk=pk)` directly, or a list endpoint, never runs it. List and bulk endpoints depend on `get_queryset()` scoping alone.
- `IsAuthenticated` checks login only, and `DjangoModelPermissions` checks model-level perms only. Neither checks which company owns the object. Read each custom permission class; don't trust its name.
- `permission_classes` on an `@action` replaces the viewset's list, so an action can drop the company check the viewset had.
- `get_queryset()` returning `.all()` exposes every company's rows to retrieve, update and delete, since `get_object()` looks up inside it.
- Writable related fields: `PrimaryKeyRelatedField(queryset=Model.objects.all())` lets a client attach another company's object (a product, location or license) to its own record. Scope that field's queryset to the requesting company.
- `fields = "__all__"` or a writable `company`, `buyer`, `seller` or `owner` field lets the client set ownership. Set it in `perform_create()` and mark it read-only.
- Forward relations (`order.seller`) load through `Model._base_manager`, not the default manager, so a custom manager that filters by company doesn't apply there.
- A second unscoped manager (`all_objects`, `unscoped`) is an escape hatch. Check every use in the diff.

### Marketplace checks

- Buyer and seller each see an order. Check which side may call each write action (accept, ship, cancel, edit lines, refund), and that the queryset for each side filters by that side's field.
- Bulk endpoints that take a list of IDs filter with `id__in` and the company scope together. When the scoped count differs from the IDs sent, fail the request instead of acting on the subset.
- Exports, reports and search endpoints apply the same company scope as the list endpoint they mirror.
- Celery tasks and webhooks that receive an ID re-scope it or trust only IDs the server produced.
- Cache keys for company data include the company ID.

### Fixes and tests

A fix enforces the check in code. A comment or docstring saying "caller must check access" is not a fix.

```python
# Bad: the docstring asks callers to check access
def get_order(order_id):
    """Caller must verify the order belongs to the user's company."""
    return Order.objects.get(pk=order_id)

# Good: the lookup itself is scoped
def get_order(order_id, company):
    return get_object_or_404(Order.objects.for_company(company), pk=order_id)
```

`for_company` stands for whatever scoping helper the codebase already has. Returning 404 for another company's object, the way a scoped `get_object_or_404` does, doesn't reveal that the ID exists.

Every access fix ships with a test that creates two companies and has company A request company B's object on each route touched (retrieve, update, delete, the bulk endpoint, the action), expecting 404 or 403 and no change in the database.

## Performance review

Look at these in priority order. Critical and high findings matter; low ones go in only as notes next to real findings.

| Priority | Problem | Impact |
|----------|---------|--------|
| 1 | N+1 queries | Critical: queries grow with rows |
| 2 | Unbounded querysets | Critical: memory exhaustion, OOM kills |
| 3 | Missing indexes | High: full scans on large tables |
| 4 | Write loops | High: N writes, lock contention |
| 5 | Small inefficiencies (`count()` vs `exists()`, `len(qs)`) | Low: rarely worth reporting |

Before reporting any of them:

1. Trace the queryset from where it's built to where it's consumed (view, serializer, template, task).
2. Grep for an existing fix: `select_related`, `prefetch_related`, pagination, `iterator()`, an index in `Meta.indexes` or a migration.
3. Check the data volume. Use real row counts from the `prod-evidence` sources when you can, and label the volume "unverified" when you can't.
4. Confirm the path is hot: a user-facing request or a job that runs over many rows.

### N+1 queries

The detection and fix steps are in `~/.agents/skills/backend-design/commands/hunt-n-plus-one.md`, the Django patterns in `references/performance-optimization.md` ("Avoid N+1 Queries"), and the SQL side in `~/.agents/skills/postgres-best-practices/references/data-n-plus-one.md`. For reviews, prove one with a query count at two list sizes (`assertNumQueries`, `django_assert_num_queries` or `CaptureQueriesContext`). A single object that takes two queries instead of one is low at most; N+1 needs a loop.

### Unbounded querysets

- A list endpoint with no pagination class, no `paginate_by` and no slice, on a table that has 10k+ rows or grows per company.
- `list(qs)`, `len(qs)` or a plain `for` over a whole large table in a request. Background jobs stream with `.iterator(chunk_size=...)` or batch by primary key.
- Exports and reports that build the full result in memory.

Report it when the table is large or grows without bound and the code runs on a request path.

### Missing indexes

- A field used in `filter()` or `order_by()` on a hot path of a table with 10k+ rows, with no `db_index=True`, `Meta.indexes` entry or index migration. Foreign keys already get an index.
- Company-scoped tables are queried as `filter(company=..., status=...).order_by("-created")`. The single-column index on the company foreign key doesn't cover the extra filter or the sort, so check for a composite index that starts with the company column.
- Confirm with the plan before reporting: `~/.agents/skills/backend-design/commands/explain-this-query.md`. For composite and partial index design, read `query-composite-indexes.md` and `query-partial-indexes.md` in `~/.agents/skills/postgres-best-practices/references/`.

### Write loops

- `create()`, `save()` or `delete()` inside a loop over 100+ items, or an unbounded number, on a request path.
- Fix with `bulk_create`, `queryset.update()`, `bulk_update(objs, fields, batch_size=...)` or `queryset.delete()`. These skip `save()`, model signals and `auto_now`, so check whether the loop relied on any of them before suggesting the bulk call.

### What to leave out

- Tests, migrations, management commands, one-time scripts, admin-only views and code behind a disabled flag.
- Tables under 1,000 rows that won't grow.
- Micro-optimizations without a measurement (`exists()` vs `count()`, `only()`/`defer()`).
- Assigning a queryset to a variable before evaluating it. Querysets are lazy, so it changes nothing.
- One `list()` call on a filtered queryset. That's one query.
- Style changes presented as performance.

## Finding format

````markdown
#### [ACCESS-001 | PERF-001] Title (critical / high / medium)
- Location: `path/to/file.py:123`
- Question: Can company A read company B's orders by ID? / Does this list load every row?
- Trace: request → view → queryset → check (or none) → consumer, each step with `file:line`
- Evidence: the code that shows the gap
- Impact: who can do what, or the query count / rows loaded, with the source of the number
- Fix: code that enforces the check or removes the extra queries, plus the test that proves it
````

End with "Needs manual check" (leads you couldn't confirm and what would confirm them) and "Not reviewed" (endpoints or flows you skipped).
