---
name: perf-review
description: Report-only performance review of a project, module, endpoint or function. Profiles first, finds the 5 slowest spots with measured times, matches each to one fix pattern (redesign instead of caching, flat arrays instead of hash tables, struct-of-arrays, parallel awaits, batched queries, data-oriented rewrite) and writes a report with current time, file and lines, and expected speedup. Changes nothing. Use when the user runs /perf-review, asks to make something faster, asks why something is slow, or asks for a performance review or optimization plan. Skip it for ordinary feature work.
argument-hint: "[path | endpoint | function | command to profile]"
metadata:
  source: "https://x.com/Voxyz_ai (perf-review prompt, Nov 2026), building on Jarred Sumner's data-oriented design prompts"
---

# Perf review

"Make it faster" tends to end with another cache. This skill measures first, picks the one fix pattern that fits each hot spot, and hands back a report. It does not change code.

The target is the argument (a path, endpoint, function, test or command). With no argument, review the project's main entry points and ask which workload matters if there's more than one obvious candidate.

## 1. Profile first

Measure a realistic workload before reading code for problems. Use the profiler that fits the stack, and the benchmark tool for the repeated runs in "Vet each number":

| Stack | Profile | Benchmark |
|---|---|---|
| Python | `py-spy record`/`py-spy top`, `pyinstrument`, or `cProfile` + `pstats`. For Django, also count queries with `CaptureQueriesContext` on realistic data | `pytest-benchmark`, `python -m timeit` |
| Node, TS | `node --cpu-prof`, `--inspect` with the DevTools profiler, or `clinic flame` | Vitest `bench` |
| Browser, Vue | DevTools Performance panel, Lighthouse for page load; Vue DevTools timeline with `app.config.performance = true` for component render and patch time; React Profiler | |
| SQL | `EXPLAIN (ANALYZE, BUFFERS)` on the queries the profile points at | |
| Rust | `cargo flamegraph --bin <name>` (or `--test`, `--bench`); it builds release, so set `debug = true` under `[profile.release]` for symbols | criterion with `cargo bench` |
| Java | `asprof -d 30 -f flame.html <pid>` (async-profiler), or JFR: `jcmd <pid> JFR.start duration=60s filename=rec.jfr`, then `jfr summary rec.jfr` | JMH |
| Go, other | `go test -cpuprofile cpu.out` with `go tool pprof`, `perf`, or the stack's equivalent | `go test -bench . -benchmem` |
| Any CLI command | | `hyperfine --warmup 3 '<old>' '<new>'` |

For production or staging behavior (endpoint latency, call volume, real traces), get the data with the `prod-evidence` skill and rank by total cost, which is call volume times latency. A slow endpoint nobody calls matters less than a medium one called a million times a day.

If profiling isn't possible (no runnable workload, missing data, no access), say so, say what was measured instead, and mark every time in the report as an estimate.

Pick the 5 slowest spots and record how much time each one takes (absolute and share of the total).

### Vet each number before you use it

From Lauren Tan's pstack benchmark-checklist and principle-explain-the-number (MIT, https://github.com/cursor/plugins/tree/main/pstack). Answer each with evidence from a run; reading the code is a guess.

- Before running, write the sentence you expect to report ("export takes 4.1 s at p50 on the 60k-row dataset") and read the measurement script for what it times and ignores. Check the machine's load (`uptime`, core count); if it is busy and you can't stop the load, interleave the runs and say so.
- Name the limiter: the core, lock, disk, network or load generator that bounds the number, taken from a profile or system counters. Profile in a run you don't report, because profilers slow the work down. If the load generator saturates first, you measured the load generator.
- Run the workload the way production runs it: release build, production flags, pool and batch settings, warm or cold caches as production sees them, realistic data. A limiter that is a setting (a debug build, a commit per row, a missing index) means that side is untuned: fix the setting and measure again.
- Do the arithmetic. A spot that takes 10% of the run can make the run at most about 11% faster, and a number past disk, network or core limits measured something else (a cache, a no-op, a bug).
- Count errors and check outputs are correct. Rejections are fast and timeouts are slow, so both skew the time.
- Run at least 5 times, alternating sides when comparing, and report the median and range. A gap smaller than the run-to-run spread is no measurable difference.
- Confirm the work happened inside the timed region: rows written, requests reached the server, lazy generators iterated and promises awaited.

## 2. Match each spot to one case

Check each spot against these cases in order and apply only the first one that matches:

1. **It uses a cache.** Caching usually covers for a slow design, so don't add more caches. See whether the code can be redesigned to be fast on its own. List the existing caches on this path and flag which ones are hiding a slow design.
2. **A hot loop keeps hitting hash tables.** Can the hash tables become a flat array? Can the pointers become indexes into that array? Can the most-used data be packed into the upper bits of the index?
3. **Many objects, but each pass reads only one or two fields.** Should this be a structure of arrays instead of an array of structures (AoS to SoA)?
4. **Independent awaits or I/O calls run one after another.** Run them in parallel.
5. **Queries or remote calls inside a loop (N+1).** Batch them into one query or call, or prefetch. Confirm the N+1 exists today with a real test (for Django, `CaptureQueriesContext` or `assertNumQueries` on realistic data), not from reading the code, and measure rows read and bytes returned as well as the query count: fewer queries that pull more rows can be slower.
6. **Nothing matches.** How would this be rewritten to follow data-oriented design: lay data out by how it's accessed, process it in batches, and avoid per-item indirection?

## 3. Report, don't change

Write the report and stop. Don't edit code, add caches or open a PR until the user picks what to do.

For each spot, give:

- Current time (and how it was measured), with the run count, the range and the limiter.
- The case it matched, with one sentence on why.
- The file and lines to change (`path/to/file.py:120-148`).
- The proposed change in a sentence or two.
- Expected speedup, with the reasoning behind the number. Label it an estimate.

Then add the list of existing caches from case 1 with the ones flagged as hiding a slow design, and end with a recommended order: biggest win for the least risk first.
