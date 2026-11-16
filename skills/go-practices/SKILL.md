---
name: go-practices
description: Go check commands and gotchas on top of engineering-practices. Covers golangci-lint, go vet, the race detector, table tests, error wrapping, context, gocognit and gocyclo, mutation testing without adding a dependency, plus sqlc, pgx and GORM. Use whenever you write, change, test or review Go code or a go.mod, together with engineering-practices.
---

# Go practices

`engineering-practices` holds the rules that hold in any language; this skill adds the Go commands and the gotchas a strong model still gets wrong. The repo's own config (`.golangci.yml`, `Makefile`, the CI workflow) wins. For a security pass, load `security-review`.

## Checks

Run what the repo configures the way CI runs it. Use these where the repo has none.

| Check | Command |
|---|---|
| Format and lint | `gofmt -l .` (prints nothing when clean), `go vet ./...`, `golangci-lint run ./...` |
| Types | The compiler: `go build ./...` |
| Tests | `go test -race ./...`; one test: `go test -race -run 'TestName/subtest' ./pkg/...`; add `-count=1` to skip the test cache. Fuzz tests, one package at a time: `go test -run='^$' -fuzz='^FuzzName$' -fuzztime=30s ./pkg/one` |
| Mutation | Gremlins, see "Mutation testing" below |
| Complexity | `golangci-lint run --enable-only gocognit,gocyclo ./...` (each with `min-complexity` default 30; use the repo's value when set) |
| Dead code | golangci-lint's `unused`; whole-program, for a module with a `main` package: `go run golang.org/x/tools/cmd/deadcode@latest -test ./...` (`-test` counts code used only by tests as live) |
| Import boundaries | `internal/` packages, which the compiler enforces, and golangci-lint's `depguard` where the repo configures it |

Run the race detector in CI and locally on any change that touches goroutines, channels or shared state. On Linux it needs cgo (`CGO_ENABLED=1` and a C compiler), so it fails in slim CI images without one.

## Mutation testing

`go run <module>@<version>` runs a tool without touching `go.mod` or `go.sum`, so Gremlins needs no project change:

```bash
go run github.com/go-gremlins/gremlins/cmd/gremlins@v0.5.0 unleash ./path/to/changed/pkg
```

Done when every lived mutant in the changed package is killed by a new assertion or noted as equivalent, and every not-covered mutant in the changed lines is covered by a test or noted.

## Go gotchas

- Wrap with `%w` to keep the chain: `fmt.Errorf("load order %d: %w", id, err)`. `%v` flattens it, so `errors.Is` and `errors.As` stop matching. Compare with `errors.Is` and `errors.As`, never `==` on a wrapped error or a match on `err.Error()` text.
- A wrapped error becomes part of your API, because callers start matching it. At a package boundary where callers shouldn't depend on the inner error, wrap with `%v` on purpose.
- Handle an error once: return it with context or log it, not both.
- Return a literal `nil` for "no error". Returning a typed nil pointer (`var e *MyErr; return e`) gives a non-nil `error`.
- `ctx context.Context` is the first parameter of anything that does I/O, and every call passes it on (`QueryContext`, `http.NewRequestWithContext`). Never store a context in a struct or start a fresh `context.Background()` inside a request path. Call `defer cancel()` right after `context.WithTimeout`. Work that must outlive the request uses `context.WithoutCancel(ctx)`, which also drops the deadline, so give it its own `context.WithTimeout`.
- `http.Client{}` and `http.DefaultClient` have no timeout. Set `Timeout`, or a deadline on the request's context.
- Every goroutine has an owner that waits for it and a way to stop. Use `errgroup.WithContext`, with `SetLimit` for fan-out over a list.
- A map isn't safe for concurrent use once any goroutine writes to it (a read during a write crashes too); guard it or confine it to one goroutine.
- Table tests: a slice of named cases run with `t.Run(tc.name, ...)`, `t.Helper()` in assertion helpers, `t.Cleanup` for teardown.
- Compare `time.Time` with `Equal`, not `==`. `time.Since(start)` uses the monotonic clock reading; a time that went through serialization has lost it.
- Money is `int64` minor units or the repo's decimal type, never `float64`.
- `defer rows.Close()` right after the query's error check, and check `rows.Err()` after the loop.

## sqlc

- The query file is the source and the generated Go is the typed result. Edit the SQL, run `sqlc generate` and commit both; `sqlc diff` in CI fails when they drift, and `sqlc vet` runs the repo's query rules.
- A `:one` or `:many` query called per item in a loop is N+1. Write one query over the whole list: in Postgres, `WHERE id = ANY(@ids::bigint[])`; in MySQL and SQLite, `sqlc.slice`.
- Read the nullability of every generated field. A column from an outer join must come out as a nullable type (`pgtype.Text`, `sql.NullString`); fix the query or add a type override rather than converting the zero value.
- Run queries inside a transaction with `queries.WithTx(tx)`.

## pgx

- Share a `pgxpool.Pool`. A single `pgx.Conn` isn't safe for concurrent use.
- Map rows with `pgx.CollectRows(rows, pgx.RowToStructByName[Order])` for typed results. `QueryRow(...).Scan` returns `pgx.ErrNoRows` when nothing matches; check it with `errors.Is`.
- Use `pgx.BeginFunc` (commits on nil, rolls back on error), or `defer tx.Rollback(ctx)` right after `Begin`, which is a no-op after commit.
- Send many statements in one round trip with `pgx.Batch`, and bulk-insert with `CopyFrom`.
- Behind PgBouncer in transaction mode without `max_prepared_statements`, pgx's prepared-statement cache breaks; set `default_query_exec_mode` to `exec` or `simple_protocol` in the connection config.

## GORM

- Load associations with `Preload("Lines")`, or `Joins` for a belongs-to; `First` or `Find` per item in a loop is N+1.
- `Updates(struct)` skips zero values (`false`, `0`, `""`). Update with a `map[string]any` or `Select("Active")` when a zero value must be written.
- `Save` writes every field, zero values included; use `Updates` with the fields that changed.
- `AutoMigrate` is a schema auto-sync; production ships versioned migrations with the repo's migration tool.
- `First`, `Take` and `Last` return `gorm.ErrRecordNotFound`; `Find` returns an empty slice and no error.
- A `*gorm.DB` with conditions applied carries them into the next call. Start each query from the base handle or `db.Session(&gorm.Session{})`.
- Start a transaction as `db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {...})` so `tx` carries the request context, and run every query inside it on `tx`.
- `Delete` on a model with a `gorm.DeletedAt` field soft-deletes, and every query filters those rows out until `Unscoped()`.
