# Vendored modern-web-guidance

`scripts/mwg` runs the CLI in `modern-web-guidance/` so searches never touch the network.

- Package: `modern-web-guidance` 0.0.197 from npm (published 2026-11-02), skill version `2026_10_30-58d055df` (`skills/modern-web-guidance/skill-version.txt`).
- Tarball integrity: `sha512-+svoxOlW0GYmj1GW8QfUrycD2MIB8F/C3WuKHzN7BpYBgFzvGvhY7Zbo7JjfYMRQAHdsIYYOWP1J32aUVuzYOQ==` (shasum `d1a09cd2494b5c3df2b6219f04d8d85d7a35b267`), checked against `npm view modern-web-guidance@0.0.197 dist`.
- License: Apache-2.0, Copyright Google LLC (`modern-web-guidance/LICENSE`). The bundled libraries (tfjs 4.22.0, @huggingface/tokenizers 0.2.0, long, seedrandom) are listed with their licenses in `modern-web-guidance/THIRD_PARTY_NOTICES`.
- Version 1.0.0 exists but was held back by `min-release-age=7` in `~/.npmrc`.

## What was copied

Unchanged files from the tarball: `package.json`, `LICENSE`, `THIRD_PARTY_NOTICES`, and `skills/modern-web-guidance/` (CLI, search bundle, guides, vectors, MiniLM model, watchdog). Left out: both `SKILL.md` files (the text lives in `topics/`, and a nested `SKILL.md` could register as a second skill), `search.mjs.map`, `skills/chrome-extensions/` (already in `topics/chrome-extensions/`), the upstream `README.md`, plugin manifests, `.github/`, `assets/` and `policies/`. No source is patched. The package has no npm dependencies; everything is bundled.

Only the built files the GitHub repos don't hold are committed here: `THIRD_PARTY_NOTICES`, `modern-web.mjs`, `search.mjs`, `guides.json`, `use-cases.vectors.gen.json.gz`, `skill-version.txt` and `watchdog/main.js`. `bin/fetch-third-party.sh` installs the rest (`LICENSE`, both `package.json` files, `guides/` and `tfjs-model-minilm/`) at the commits in `~/.agents/third-party.tsv`, which are tag `v0.0.197` of `GoogleChrome/modern-web-guidance` and `GoogleChrome/modern-web-guidance-src` and hold the same bytes as the tarball.

## Network calls in the package and how they stay off

- Telemetry: `skills/modern-web-guidance/watchdog/main.js:13` (endpoint `https://play.googleapis.com/log`) and `:74` (`fetch`). The CLI starts that process from `modern-web.mjs:312` only when `ClearcutLogger` is enabled (`modern-web.mjs:382-391`, `:413-421`). `scripts/mwg` sets `DISABLE_TELEMETRY=1`, so the process is never started.
- `install`, `update`, `uninstall` run `npx skills ...` (`modern-web.mjs:673`, `:689`, `:704`), which downloads from npm and GitHub. `scripts/mwg` refuses these commands.
- The MiniLM model and tokenizer load from `tfjs-model-minilm/` with `fs.readFileSync` and `tf.io.fromMemory` (`search.mjs:34`, function `zE`). The tfjs HTTP loader in `search.mjs:8` and `:21` is bundled but never reached. Nothing is fetched from Hugging Face.
- The "new SKILL.md available" check (`modern-web.mjs:738`) compares `--skill-version` with the local `skill-version.txt`. No request is made, and `scripts/mwg` callers don't pass the flag.

## Update

1. `npm pack modern-web-guidance@<version>` into an empty scratch folder, check the integrity against `npm view modern-web-guidance@<version> dist`, and extract it.
2. Re-read `modern-web.mjs`, `watchdog/main.js` and the model loader in `search.mjs` for new network calls.
3. Replace the committed built files above, move the commits in `third-party.tsv` to the new version's tags, run `bin/fetch-third-party.sh`, and update this file.
4. Refresh `topics/modern-web-guidance/README.md` from the new `skills/modern-web-guidance/SKILL.md`, keeping the `scripts/mwg` commands.
5. Re-run the offline check: `sandbox-exec -p '(version 1)(allow default)(deny network* (with send-signal SIGKILL))' ~/.agents/skills/modern-web-guidance/scripts/mwg search "light dismiss dialog"` must exit 0 with results.
