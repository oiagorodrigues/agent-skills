---
name: typescript-practices
description: TypeScript and JavaScript check commands and gotchas on top of engineering-practices, for Node, browser, Vue and Nuxt code. Covers tsc, typescript-eslint, Vitest, Stryker mutation testing without adding a dev dependency, complexity, dead code and import boundaries, plus Zod, Drizzle, Prisma and Kysely. Use whenever you write, change, test or review .ts, .tsx, .mts, .cts, .js, .jsx, .mjs, .cjs or .vue files or a package.json, together with engineering-practices.
---

# TypeScript practices

`engineering-practices` holds the rules that hold in any language; this skill adds the TypeScript and JavaScript commands and the gotchas a strong model still gets wrong. The repo's own config and CI win. For Vue and Nuxt also load `vue-best-practices` (plus `vue-pinia-best-practices`, `vue-router-best-practices` and `vue-testing-best-practices` for stores, routing and component tests); for Vitest's API, `vitest`; for pnpm workspaces and catalogs, `pnpm`; for a security pass, `security-review`.

## Checks

Run the repo's `package.json` scripts the way CI runs them. Use these where the repo has none.

| Check | Command |
|---|---|
| Format and lint | `prettier --check .`, `eslint .` with typescript-eslint `strictTypeChecked` and `parserOptions.projectService: true` |
| Types | `tsc --noEmit`; Vue: `vue-tsc --noEmit`; Nuxt: `nuxi typecheck` |
| Tests | `vitest run <file>`; end to end: `playwright test`; property-based tests with fast-check where the repo has it |
| Mutation | Stryker, see "Mutation testing" below |
| Complexity | ESLint `complexity` (default 20) and `sonarjs/cognitive-complexity` from `eslint-plugin-sonarjs` (default 15) |
| Dead code | `knip`, with `--production` to check only shipped code. `knip --fix` deletes files only with `--allow-remove-files` |
| Import boundaries | dependency-cruiser or `eslint-plugin-boundaries`, where the repo has rules |

A tool the repo doesn't install runs one-off with `pnpm dlx`; ask before installing anything globally.

## Mutation testing

Stryker runs from `pnpm dlx`, so nothing is added to `package.json` or the lockfile. Keep its config outside the repo, in the scratchpad, with absolute paths for every file it writes:

```json
{
  "testRunner": "vitest",
  "reporters": ["clear-text", "html"],
  "htmlReporter": { "fileName": "<scratch>/stryker-out/mutation.html" },
  "tempDirName": "<scratch>/stryker-tmp",
  "incrementalFile": "<scratch>/stryker-out/incremental.json"
}
```

Run it from the repo root, with the repo's own Vitest and TypeScript versions from `package.json`, so the runner uses the same ones as the tests:

```bash
pnpm --config.dlx-cache-max-age=0 --config.node-linker=hoisted dlx \
  --package @stryker-mutator/core@10.1.1 --package @stryker-mutator/vitest-runner@10.1.1 \
  --package vitest@<repo vitest version> --package typescript@<repo typescript version> \
  stryker run <scratch>/stryker.config.json --mutate "src/a.ts,src/b.vue" \
  --testFiles "src/a.unit.spec.ts,src/b.spec.ts" --concurrency 2 --incremental
```

Keep both Stryker packages pinned to the same version (10.1.1 is the one this command was run with), and keep `--config.node-linker=hoisted` and `--config.dlx-cache-max-age=0`. With pnpm's default layout Stryker finds no runner and stops with `Cannot find TestRunner plugin "vitest". In fact, no TestRunner plugins were loaded.`, and a cached non-hoisted install ignores the linker flag. Stryker doesn't support Vitest browser mode.

In a TypeScript repo, keep `--package typescript@<version>`: Stryker's tsconfig preprocessor imports it and stops with `Cannot find package 'typescript' imported from .../ts-config-preprocessor.js` without it. Always pass `--testFiles` with the specs of the mutated files. Without it the Vitest runner uses `vitest related`, which in a large app whose test setup imports most of the code picks hundreds of test files for a one-line util, and the initial run stops with `Initial test run timed out!` after 5 minutes. `vitest.dir` in the config doesn't narrow it.

Done when every surviving mutant in the changed files is killed by a new assertion or noted as equivalent, and `git status` shows nothing from Stryker.

## TypeScript gotchas

From pstack typescript-best-practices (MIT, https://github.com/cursor/plugins/tree/main/pstack), plus the runtime traps:

- Make a switch over a union exhaustive by calling `assertNever(x)` (a helper taking `never` that throws) in the default arm, so a new variant fails to compile; typescript-eslint's `switch-exhaustiveness-check` reports the same gap.
- Use `satisfies` instead of `as`: it reports a mismatch and keeps the value's inferred type, while `as` hides the mismatch.
- A type guard (`isX`, `hasX`) checks everything its return type claims. A guard that lies is worse than `as`, because its name says the value is safe.
- Before hand-writing a guard, infer the type from the repo's runtime schema (`z.infer`), and derive related types with `Pick`, `Omit`, `ReturnType` or `Awaited` instead of declaring a new interface.
- Brand primitives that are easy to mix up (`string & { readonly __brand: "OrderId" }`) and create the brand only through a verifying guard, never with `as`.
- Suppress with `// @ts-expect-error <reason>`, which fails once the error is gone, never `@ts-ignore`.
- Every promise is awaited, returned, or marked fire-and-forget with `void`; typescript-eslint's `no-floating-promises` catches the rest.
- Throw only `Error` objects and reject promises only with them, never strings or plain values (typescript-eslint `only-throw-error` and `prefer-promise-reject-errors`).
- In Node, pass `signal: AbortSignal.timeout(ms)` to every outbound `fetch`; its built-in limits are minutes long.
- Durations use `performance.now()`, not `Date.now()`.
- Numbers past `Number.MAX_SAFE_INTEGER` lose precision in `JSON.parse`, so 64-bit ids travel as strings.
- Read `process.env` once, in a config module that validates it at startup.
- pnpm's dependency age gate is `minimumReleaseAge`, and its bypass is a `minimumReleaseAgeExclude` entry.

## Zod

- Parse, don't validate: the schema's output is the only value code after the boundary uses, and `z.infer<typeof Schema>` is the type's only source. With `.transform()` or `.default()`, the input type differs; use `z.input<typeof Schema>` for it.
- Call `safeParse` at every untrusted input (HTTP bodies and query strings, env vars at startup, LLM output, `localStorage`, `postMessage` data, `JSON.parse` results) and handle `success: false` with a typed error. Never write `JSON.parse(x) as T`.
- `z.object` strips unknown keys. Use `z.strictObject` where an extra key means a client bug, and keep `z.looseObject` (Zod 4; `.passthrough()` in Zod 3) away from objects spread into a write.
- `z.coerce.boolean()` runs `Boolean(value)`, so the string `"false"` becomes `true`. Parse boolean strings with `z.enum(["true", "false"]).transform((v) => v === "true")`, or `z.stringbool()` in Zod 4.

## Drizzle

- Use `typeof table.$inferSelect` and `$inferInsert` for row types instead of hand-written interfaces.
- Load relations with relational queries (`db.query.orders.findMany({ with: { lines: true } })`) or a join; a `db.select()` per row in a loop is N+1.
- Inside `db.transaction(async (tx) => ...)`, every query uses `tx`; a call on `db` inside the callback runs outside the transaction.
- `drizzle-kit push` syncs the schema directly and is for local databases only. Production runs reviewed SQL from `drizzle-kit generate`.
- `drizzle-kit generate` asks whether a changed column was renamed or created; the wrong answer drops the column's data. Read the generated SQL before committing it.
- Postgres `numeric` columns come back as strings by default; keep money as that string or a decimal, never `Number()`.

## Prisma

- Load relations with `include` or a nested `select`. A `findMany` or `findFirst` per row in a loop is N+1; only `findUnique` calls in the same tick get batched.
- Prisma returns every scalar field by default, so select (or `omit`) what the caller needs and keep secrets out of responses.
- In an interactive transaction (`prisma.$transaction(async (tx) => ...)`) every query uses `tx`. It times out after 5 seconds by default, so no network calls inside it.
- `prisma db push` is for prototypes. Production runs `prisma migrate deploy` with checked-in migrations. For a rename, create the migration with `prisma migrate dev --create-only` and edit the generated drop and add into a rename before applying.
- `Decimal` fields come back as `Prisma.Decimal`; do math on it, never on `Number(value)`.
- `$queryRaw` with a tagged template sends parameters. `$queryRawUnsafe` with an interpolated string is SQL injection.
- Type a query result with `Prisma.OrderGetPayload<{ include: { lines: true } }>` instead of a hand-written interface.

## Kysely

- Generate the `Database` interface from the schema (kysely-codegen, or the repo's generator) instead of writing it by hand, so the types match the tables.
- Kysely has no relation loading. Avoid N+1 with a join or the `jsonArrayFrom` and `jsonObjectFrom` helpers from `kysely/helpers/postgres`.
- Inside `db.transaction().execute(async (trx) => ...)`, every query uses `trx`.
- The `sql` template tag sends parameters; `sql.raw` and `sql.lit` paste text into the query, so they never take user input.
- `executeTakeFirst()` returns `T | undefined`; handle the `undefined` or use `executeTakeFirstOrThrow()`.
