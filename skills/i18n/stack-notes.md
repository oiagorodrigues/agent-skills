# Stack notes — mechanics per stack

Starting points, not a substitute for the library's current docs: confirm APIs against
the library's docs or source before relying on them.

## Contents

- Message syntax per stack
- Any stack: translation packs as JSON
- Vue 3 + Vite (incl. SSR)
- PostgreSQL

## Message syntax per stack

The completeness gate needs one parser per syntax (SKILL.md §3, items 3–4). If packs are
shared across stacks, pick one source syntax and compile it into each.

| Stack / library | Named argument | Plurals | Escaping / gotchas |
|---|---|---|---|
| vue-i18n (v11) | `{name}`; list `{0}` | `a \| b \| c` chosen by count. The default rule is English-like, so register `pluralRules` per locale for Russian, Arabic, Polish and similar | `{ } @ $ \|` are syntax. Write a literal as `{'@'}`. `@:key` links another message. Parse with `@intlify/message-compiler` |
| ICU MessageFormat (`@messageformat/core`, FormatJS) | `{name}` | `{count, plural, one {…} other {…}}` | Apostrophe escaping. Translators often break nested braces, so parse in the gate |

## Any stack: translation packs as JSON

- One file per locale (`locales/<code>.json`), nested by feature namespace. The source
  locale's file is the schema. The gate flattens keys to dotted paths and compares sets.
- **Propagating a new key:** use an **order-preserving** script that inserts the key at
  the same position in every file, so review diffs line up. Write the value as a marked
  draft (`"⟦TODO⟧ English text"`) that the gate's untranslated check rejects. Never
  hand-edit every pack. Run exactly this (same registry and `{locale}` template as the gate):

  ```sh
  node ~/.agents/skills/i18n/scripts/add-key.mjs --registry <registry.json> --packs '<dir>/{locale}.json' \
    --key <dotted.key> --text "<source text>" [--after <sibling.key> | --first] [--dry-run]
  ```

  Without `--after`/`--first` the key goes last in its parent. Nothing is written unless every
  pack can take it (each file is replaced atomically, but a failure partway through the
  renames leaves the earlier packs written: rerun on the rest by hand). Exit 0 written; 2 usage, a bad registry, an unreadable or malformed pack, or `--after`
  absent from the source pack (or in another parent), or a parent whose integer-like keys (`"1"`, `"20"`)
  JavaScript would reorder; 3 the key already exists, or collides with a string, in
  some pack; 4 a pack whose formatting a JSON round trip would change (named): edit that one by
  hand. A `WARN … --after … missing` line means that pack was out of parity, and the key went
  last in its parent there. Then run the gate: check 5 lists every draft still to translate.
- **Translator metadata** goes in a sidecar (`locales/_meta.json`), because JSON has no
  comments. Per key: `description`, `maxLength`, a screenshot link and, if you use the
  staleness policy, `sourceHash`. `i18n-gate.mjs --meta` reads `maxLength` (check 7); it
  does not check `sourceHash` yet, so a staleness policy needs its own step.

## Vue 3 + Vite (incl. SSR)

- **Library:** `vue-i18n` in Composition mode (`legacy: false`), `useI18n()` in components.
  Set the `missing` handler and `missingWarn` / `fallbackWarn` so a missing key is loud in
  dev and reported in prod (SKILL.md §2).
- **SSR: create the i18n instance per request** in the app factory, never as a module
  singleton, or one request's locale leaks into another's render. Set `<html lang dir>` in
  the server entry from the resolved locale. Hydrate the client with the same locale and
  messages so the first client render matches.
- **Build:** `@intlify/unplugin-vue-i18n` (v11) precompiles message files and supports
  lazy-loaded per-locale chunks. Every separate Vite config (an embed or widget build, a
  second entry point) needs the plugin and its own locale loading. Check each one.
- **Lints:**
  - `@intlify/eslint-plugin-vue-i18n`: `no-raw-text`, `no-missing-keys`,
    `no-unused-keys`.
  - `eslint-plugin-vue`: `vue/no-bare-strings-in-template`.
  - Call-site literal fallbacks, via core `no-restricted-syntax`:
    `LogicalExpression[operator=/^(\|\||\?\?)$/][left.callee.name=/^\$?t$/][right.type='Literal']`.
    Extend it to `left.callee.property.name` for `i18n.t(…)` member calls.

  None of these lints see strings built in script code or attributes bound from JS. The
  pseudo-locale sweep does.
- **Dates:** prefer `Intl.DateTimeFormat` / `Intl.RelativeTimeFormat` (or vue-i18n's `d()`)
  for display, and keep dayjs for date arithmetic. dayjs (1.11) is not CLDR-based:
  - its locale codes are lowercase (`zh-cn`, `pt-br`), so map them in the registry;
  - each locale must be imported (`dayjs/locale/<code>`);
  - localized formats and relative time need the `localizedFormat` and `relativeTime`
    plugins;
  - the global `dayjs.locale()` is process-wide on an SSR server, so use the per-instance
    `.locale(code)`.
- **Hydration:** server and browser ICU data and default timezones differ. Pass
  `timeZone` explicitly to every `Intl.DateTimeFormat`, or format on the client only.
  Treat hydration-mismatch warnings as failures in the e2e sweep.

## PostgreSQL

- **Translatable reference data:** either a side table `(entity_id, locale, field, value)`
  or a per-field `jsonb` map `{ "en": "…", "es": "…" }`. The side table is easier to keep
  complete (a parity query is a `GROUP BY … HAVING count(*) < n_locales`); the `jsonb` map
  is simpler to read. Either way, the completeness query runs in the test suite.
- Store codes, not labels, in transactional rows (SKILL.md §5).
- **Collation:**
  - Use an ICU collation per locale for user-visible sorts (`CREATE COLLATION … (provider =
    icu, locale = '…')`), applied as `ORDER BY name COLLATE "…"`.
  - For paginated lists, sort in the database. Sorting a page in the app with
    `Intl.Collator` disagrees with the database's page boundaries.
  - **Collation version drift:** after an ICU or OS upgrade, Postgres warns of a version
    mismatch. Indexes on text columns using that collation must be rebuilt (`REINDEX`),
    then the collation refreshed (`ALTER COLLATION … REFRESH VERSION`). Put this in the
    upgrade runbook.
  - Accent- or case-insensitive matching needs a non-deterministic ICU collation
    (`deterministic = false`), which restricts pattern matching and some index uses.
    Check your server version's docs before choosing it over `unaccent` + `pg_trgm`.
- **Full-text search** is language-specific: `to_tsvector('<config>', …)` per locale, with
  the config chosen from the registry, not hard-coded `'english'`.
- Encoding: UTF-8 everywhere; check `client_encoding` on every importer.
