---
name: improve-codebase-architecture
description: "Finds shallow modules in a codebase with the deletion test and proposes deepening refactors (more behavior behind a smaller interface, at a cleaner seam) for testability and easier navigation, weighted toward the git hot spots. Report first; a refactor starts only after the user picks a candidate and approves the design. Use when the user asks to improve a codebase's architecture, find refactoring or deepening opportunities, reduce coupling, make a module easier to test or to navigate, or asks where the design hurts. For migrating a legacy system to a new stack use code-modernization; for a whole-repo map and audit use cartographer."
---

# Improve codebase architecture

Adapted from Matt Pocock's improve-codebase-architecture and codebase-design (MIT, https://github.com/mattpocock/skills).

This skill improves the shape of code that stays on its stack: it finds modules whose interface is nearly as complex as their implementation and proposes merging or reshaping them so callers learn less and changes land in one place. `code-modernization` is a different job (moving a legacy system to a new language, framework or architecture); `cartographer` maps and audits a whole repo, and its hot spots feed this skill.

## Vocabulary

Use these terms exactly in every proposal.

- **Module**: anything with an interface and an implementation (a function, class, package or a slice across layers).
- **Interface**: everything a caller must know to use it correctly: signature, invariants, ordering, error modes, required config, performance.
- **Depth**: behavior a caller or test gets per unit of interface learned. **Deep** means a lot behind a small interface; **shallow** means the interface is nearly as complex as the implementation.
- **Seam**: where an interface lives, a place you can change behavior without editing there. **Adapter**: what fills a seam.
- **Leverage** (for callers) and **locality** (for maintainers: change, bugs and knowledge in one place) are what depth buys.

Principles:

- **The deletion test.** Imagine deleting the module. If complexity vanishes, it was a pass-through. If it reappears across N callers, it earns its keep. A shallow candidate is one whose deletion would concentrate complexity, not spread it.
- **The interface is the test surface.** If tests must reach past the interface, the module is the wrong shape.
- **One adapter is a hypothetical seam; two is a real one.** Don't add a port unless something varies across it (production plus a test fake counts).

## 1. Scope

1. If the user named a module, subsystem or pain point, start there.
2. Otherwise use git hot spots, because deepening pays off where code keeps changing. Look for cartographer output first: `<repo>/.cartographer/hotspots.md` or `~/.cartographer/<hash>/hotspots.md` (find the folder with `grep -l "<repo absolute path>" ~/.cartographer/*/_project.txt`). If neither exists, run `/cartographer map <repo> --readonly`, which writes `hotspots.md` (commits times indentation complexity per file, plus files that change together) to `~/.cartographer/<hash>/` without touching the repo. If cartographer can't run, use `git log --since="12 months ago" --name-only --format= | sort | uniq -c | sort -rn | head -40`.
3. Read the domain glossary (`GLOSSARY.md`, or cartographer's `glossary.md`) and any ADRs in the area. Don't re-litigate an ADR unless the friction is real enough to reopen it, and say so.

Files that change together in hot spots' temporal coupling, with no import between them, are strong candidates: a hidden dependency the interface doesn't show. **Done when** you have the 3 to 8 areas to explore and why each.

## 2. Explore

Send one `Explore` subagent per area (in parallel when there are several) with the vocabulary above and these questions. Each returns `file:line` evidence, not opinions.

- Where does understanding one concept require bouncing between many small modules?
- Where is a module shallow (interface about as complex as its body, a pass-through, a wrapper that renames)?
- Where were pure functions extracted only for testability while the bugs live in how they're called?
- Where do modules leak across their seams (callers knowing internal ordering, shared mutable state)?
- What is untested, or testable only by mocking internals?

Apply the deletion test to every suspect. **Done when** each candidate has its files, its deletion-test result and the evidence.

## 3. Report candidates

Report in chat, most valuable first. For each candidate:

- **Files** involved.
- **Problem**: the friction, in terms of depth, locality and leverage, with the hot-spot numbers when they exist.
- **Proposal**: what would merge, move or hide, in plain words. No interface design yet.
- **Dependencies**, which decide how the deepened module is tested: in-process (merge and test through the new interface), local stand-in (test with it, such as a test database), owned remote service (a port with a production adapter and an in-memory one), or third party (an injected port with a fake).
- **Tests**: which tests on the shallow modules become waste and get replaced by tests at the new interface.
- **Strength**: strong, worth exploring, or speculative.

End with the one you'd do first and why, then ask which to explore. If the user wants a visual version, build it as an Artifact (load `artifact-design`).

## 4. Design the chosen one

Once the user picks a candidate, walk the design with them one question at a time (`brainstorming` rules): constraints, what sits behind the seam, the interface shape, which tests survive. For a hard interface, design it twice: two or three subagents each propose a radically different interface; compare them on depth, locality and seam placement.

When the conversation names a new domain concept or sharpens a term, propose the `GLOSSARY.md` line. When the user rejects a candidate for a lasting reason, offer to record it as an ADR so future reviews don't suggest it again.

Changing code starts only after the user approves the design. Then follow `engineering-practices`: work on a branch, pin current behavior with tests at the new interface first, refactor, prove behavior didn't change, and ask before committing or opening a PR.
