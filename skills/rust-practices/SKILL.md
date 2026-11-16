---
name: rust-practices
description: Rust check commands and gotchas on top of engineering-practices. Covers rustfmt, clippy, cargo test, Miri, cargo-mutants mutation testing without adding a dependency, complexity and dead code, plus error handling, serde at the boundary and async locks. Use whenever you write, change, test or review Rust code or a Cargo.toml, together with engineering-practices.
---

# Rust practices

`engineering-practices` holds the rules that hold in any language; this skill adds the Rust commands and the gotchas a strong model still gets wrong. The repo's own config (`clippy.toml`, `rustfmt.toml`, the CI workflow) wins. For a security pass, load `security-review`.

## Checks

Run what the repo configures the way CI runs it. Use these where the repo has none.

| Check | Command |
|---|---|
| Format and lint | `cargo fmt --check`, `cargo clippy --all-targets -- -D warnings` |
| Types | `cargo check` (clippy above includes it) |
| Tests | `cargo test <name>`; code with `unsafe`: `cargo +nightly miri test`; property-based tests with proptest where the repo has it |
| Mutation | `cargo mutants -f <file>` (repeatable), or `git diff <base>... > <scratch>/x.diff` then `cargo mutants --in-diff <scratch>/x.diff` |
| Complexity | Clippy `too_many_lines`, a pedantic lint that the default run skips: add `-W clippy::too_many_lines`. Clippy's `cognitive_complexity` sits in `restriction` because its own docs say it doesn't measure that, so judge nesting by reading |
| Dead code | rustc's `dead_code` warnings from `cargo check`; unused crates: `cargo machete`, which has false positives for crates used only by `build.rs` output or renamed imports |
| Module boundaries | Crate and module visibility; rustc's allow-by-default `unreachable_pub` lint (`-W unreachable_pub`) flags `pub` items no other crate can reach |

cargo-mutants and cargo-machete install as global tools with `cargo install --locked <tool>`, and Miri with `rustup +nightly component add miri`; neither adds anything to the project, but ask before installing. Point cargo-mutants' output outside the repo with `--output <scratch>`, or delete `mutants.out/` when done.

## Rust gotchas

- No `unwrap()` or `expect()` on values that depend on input; return a `Result`. Clippy's opt-in `unwrap_used` and `expect_used` lints enforce it, with `allow-unwrap-in-tests` and `allow-expect-in-tests` in `clippy.toml` for test code.
- Deserialize into a typed struct at the boundary (`serde_json::from_str::<T>`) and keep `serde_json::Value` out of the domain. Add `#[serde(deny_unknown_fields)]` where an extra key means a client bug; serde doesn't support it on a struct that uses `#[serde(flatten)]`.
- Match your own enums without a `_` arm, so a new variant fails to compile (clippy's opt-in `wildcard_enum_match_arm`).
- Every `unsafe` block gets a `// SAFETY:` comment (clippy's opt-in `undocumented_unsafe_blocks`) and a Miri run; Miri can't execute most FFI calls, so FFI code needs tests against the real library instead.
- Library crates return typed error enums; applications may use the repo's catch-all error type with context on each `?`. `From` impls (or `#[from]`) that map several error sources into one variant leave callers unable to tell those failures apart.
- Mark public enums and structs that will grow `#[non_exhaustive]`, because adding a variant or field to an exhaustive public type breaks every downstream match or literal.
- Never hold a `std::sync::Mutex` guard across `.await` (clippy `await_holding_lock`), and move blocking work out of async code with `spawn_blocking`.
- Durations use `std::time::Instant`, not `SystemTime`.
