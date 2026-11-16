---
name: python-practices
description: Python check commands and gotchas on top of engineering-practices. Covers ruff, mypy or pyright, pytest, mutmut mutation testing without adding a dev dependency, complexity, dead code and import boundaries, plus FastAPI, SQLAlchemy 2.x, Pydantic v2 and Alembic. Use whenever you write, change, test or review Python code (.py files) or a pyproject.toml, together with engineering-practices.
---

# Python practices

`engineering-practices` holds the rules that hold in any language; this skill adds the Python commands and the gotchas a strong model still gets wrong. The repo's own config and CI win. For Django, also load `django-expert`; for asyncio, `async-python-patterns`; for a security pass, `security-review`.

## Checks

Run what the repo configures (`pyproject.toml`, `Makefile`, the CI workflow) the way CI runs it, inside the project's environment (`uv run`, `poetry run`). Use these where the repo has none.

| Check | Command |
|---|---|
| Format and lint | `ruff format --check`, `ruff check` |
| Types | `mypy` or `pyright`, whichever CI runs, in the project's environment so every import resolves. With `warn_unused_ignores` (mypy) or `reportUnnecessaryTypeIgnoreComment` (pyright) on, a `# type: ignore[<code>]` fails once its error is gone |
| Tests | `pytest <path>::<test>`; property-based tests with Hypothesis where the repo has it |
| Mutation | mutmut, see "Mutation testing" below |
| Complexity | `ruff check --select C901` (threshold `max-complexity` under `[tool.ruff.lint.mccabe]`, default 10), or `radon cc -s -n C <files>` |
| Dead code | `vulture <paths> --min-confidence 90` (findings at 60% are guesses); `ruff check --select F401,F841` |
| Import boundaries | `lint-imports` (import-linter), where the repo has contracts |

Tools that only read files (ruff, vulture, radon) run one-off with `uvx <tool>`. Tools that import the project (mypy, pytest, mutmut) need the project's environment.

## Mutation testing

mutmut runs from uv's cache, layered on the project's environment, so nothing is added to the project:

- uv project: `uv run --with mutmut mutmut run "<module>*"`. It leaves `pyproject.toml` and `uv.lock` untouched.
- Poetry or plain-venv project: `uv run --no-project --python "$(poetry env info -p)/bin/python" --with mutmut mutmut run "<module>*"`, or `--python .venv/bin/python` for a plain venv. Plain `uv run --with` in such a repo writes a `uv.lock` into it.
- `uvx mutmut run` fails with `ModuleNotFoundError` as soon as a test imports a project dependency, because it runs in mutmut's own environment.

Then:

1. Limit the run to the changed modules with a quoted glob on the mutant name, which is `<dotted module>.x_<function>__mutmut_<n>`: `"billing.price*"`.
2. If mutmut stops with "Could not figure out where the code to mutate is", add `source_paths = ["<package dir>"]` under `[tool.mutmut]` in `pyproject.toml` for the run, and restore the file before committing.
3. List survivors with `mutmut results` and read one with `mutmut show <mutant name>`.
4. Delete the `mutants/` folder mutmut creates at the repo root; it holds a mutated copy of the project.

Done when every surviving mutant in the changed modules is killed by a new assertion or noted as equivalent, and `mutants/` is gone.

## Python gotchas

- Durations use `time.monotonic()` or `time.perf_counter()`, never `time.time()`. Timestamps are aware, `datetime.now(UTC)` (`timezone.utc` before Python 3.11); `datetime.utcnow()` returns a naive value, which `.timestamp()` reads as local time and which raises `TypeError` when ordered against an aware one.
- Money is a `Decimal` built from a string or an int: `Decimal("0.10")`, never `Decimal(0.1)`, which keeps the float's error. Round with `quantize` and an explicit rounding mode.
- Keep the cause when you translate an error: `raise PaymentFailed(order.id) from err`.
- A `match` over an `Enum` or `Literal` ends in `case _: assert_never(value)` (`typing.assert_never`), so a new member fails the type check.
- Brand ids that are easy to mix up with `NewType` (`OrderId = NewType("OrderId", int)`), and build them in one parsing function that checks the value, since `OrderId(5)` itself checks nothing.
- Patch where the code under test looks the name up: when `app/orders.py` does `from app.email import send`, patch `app.orders.send`. Pass `autospec=True` so a call with the wrong signature fails.
- Expect one error with `pytest.raises(PaymentFailed, match=...)`.
- Keep a reference to every `asyncio.create_task` result (a `TaskGroup` or a set), because the event loop holds tasks weakly and an unreferenced one can disappear mid-run. Never call blocking I/O (`requests`, a sync DB driver) inside `async def`.

## FastAPI

- An `async def` endpoint runs on the event loop, so one blocking call inside it stalls every request. With a sync driver or client, declare the endpoint with plain `def`, which FastAPI runs in a thread pool.
- Give every endpoint a `response_model` or return type. FastAPI filters the response through it, so extra attributes of a returned ORM object (a password hash) stay out of the response.
- Take bodies, query and path parameters as Pydantic models or `Annotated` parameters, so validation runs before your code.
- Put auth on the router (`APIRouter(dependencies=[Depends(require_user)])`) so a new endpoint is protected by default; endpoint-level checks only narrow it.
- Services raise domain errors, and one `@app.exception_handler` per error type maps them to HTTP. `HTTPException` stays in the HTTP layer.
- Commit in the endpoint or service before returning. The code after `yield` in a request-scoped dependency runs after the response is sent, so a commit that fails there never reaches the client; a `yield` dependency only opens, rolls back and closes the session. A `BackgroundTasks` job opens its own session instead of reusing the request's.

## SQLAlchemy 2.x

- Write 2.0 style: `select()` with `session.scalars()` or `session.execute()`, and models with `Mapped[...]` and `mapped_column()`, so results are typed. `session.query()` is the legacy API.
- Relationships lazy-load by default, which is N+1 inside a loop. Set `lazy="raise"` on relationships (or `.options(raiseload("*"))` on the query) so an unplanned load fails in tests, and load what the code needs: `selectinload` for collections, `joinedload` for many-to-one. A `joinedload` of a collection needs `.unique()` on the result.
- With `AsyncSession` a lazy load raises `MissingGreenlet`, so load relationships in the query.
- `expire_on_commit` is on by default, so reading an attribute after `commit()` runs another query (and raises under async). Set `expire_on_commit=False` on sessions whose objects are read after commit, such as the ones behind API responses.
- One session per request or unit of work: `with Session(engine) as session, session.begin():`. Never share a session between threads or tasks, or keep one at module level.
- ORM-enabled `update()` and `delete()` statements skip mapper events (`before_update`, `after_delete`) and relationship cascades; run those side effects explicitly.
- To hunt N+1 across a codebase, follow `/backend-design hunt-n-plus-one`.

## Pydantic v2

- Use the v2 API: `Model.model_validate(data)`, `Model.model_validate_json(raw)` (parses and validates in one step), `model_dump()`, `model_config = ConfigDict(...)`. `.dict()`, `.parse_obj()` and `class Config` are v1.
- Models ignore unknown keys by default. Set `ConfigDict(extra="forbid")` on request models where an extra key means a client bug.
- Lax mode coerces `"123"` to `123` and `"yes"` to `True`. Set `strict=True` on the model or field where that would hide a bug.
- Validate non-model types (a list of models, a union) with `TypeAdapter(list[Order]).validate_python(data)`.
- `model_construct()` skips validation; use it only on data that already passed it.
- With `from_attributes=True`, validating an ORM object reads every field of the model and lazy-loads each relationship in it (N+1, or `MissingGreenlet` under async). Load those relationships in the query first.
- Read settings with `pydantic-settings` `BaseSettings` once at startup, so a missing or malformed variable fails the boot.

## Alembic

- Read every autogenerated migration. Autogenerate can't detect a table or column rename (it writes a drop and an add, which loses the data) and skips server-default changes unless `compare_server_default` is on.
- Keep one head: `alembic heads` prints one revision. Join branches with `alembic merge`.
- Migrations never import application models, which change later and break old migrations. Use `op` and a local `sa.table()` for data steps, and keep backfills out of schema migrations.
- Create Postgres indexes with `op.create_index(..., postgresql_concurrently=True)` inside `with op.get_context().autocommit_block():`.
- Write `downgrade()`, and run `upgrade`, `downgrade -1`, `upgrade` locally.
- Check the SQL a migration runs: `alembic upgrade <from>:<to> --sql | python3 ~/.agents/skills/backend-design/scripts/check_migration.py --stdin`, and follow `/backend-design review-migration` before committing.

## Django

Load `django-expert`, which also shows how to check the SQL of a Django migration with `check_migration.py --stdin`.
