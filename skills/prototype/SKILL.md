---
name: prototype
description: "Builds a throwaway logic prototype that answers one design question by running code instead of debating it: a state machine, business rule, data shape or API sketch pushed through the awkward cases. Logic only, no UI variants. Use when the user asks to prototype, spike or sanity-check whether a state model or rule holds, or when a design discussion stalls on \"would this handle X then Y\"."
---

# Prototype

Adapted from Matt Pocock's prototype, logic branch (MIT, https://github.com/mattpocock/skills). The UI-variants branch is left out.

A prototype is throwaway code that answers one question. Its value is the answer and the small pure module behind it, never the code around it.

## Rules

1. **Isolated from real work.** Build it in the scratchpad directory, or on a throwaway branch `prototype/<slug>` (from a git worktree when the user's tree has changes). Never on a branch headed for a PR, and never on `main`.
2. **Ask before any commit.** Committing, pushing or opening a PR waits for the user's yes, even on the throwaway branch.
3. **Trivial to run.** One command (`python3 proto.py`, `node proto.mjs`) or one HTML file opened by double-click. No install steps beyond what the repo has.
4. **No persistence.** State lives in memory. If the question is about persistence, use a scratch SQLite file or local file named `PROTOTYPE-wipe-me`, never a shared or real database.
5. **Skip the polish.** No tests, no error handling beyond what keeps it running, no abstractions for later.
6. **Show the state.** After every action, print or render the full relevant state so the change is visible.

## Steps

1. **Write the question.** One paragraph at the top of the prototype (a docstring or the page intro): the state model or rule, and the question it must answer. **Done when** the user agrees it is the right question, or you stated the assumption at the top if they're away.
2. **Write the logic as a pure module.** Pick the shape that fits the question: a reducer `(state, action) -> state` for discrete events, an explicit state machine when "which actions are legal now" is part of the question, or plain functions over a data type when there is no current state. No I/O, no DOM, no prints inside it; the shell calls into it. This is the part that can move into real code later.
3. **Write a thin driver.** For a developer audience, a script that runs named scenarios and prints the state after each step. For a PM or domain expert, one self-contained HTML file with labels in domain language, the current state as labeled fields, one button per action, and one tab per scenario that resets state and steps through it.
4. **Pick the scenarios.** The happy path, the edge case that is hard to reason about on paper, and an attempt at something that should be illegal. Add the cases the user or the ticket names.
5. **Run it and report.** Show the scenario output (or open the HTML file) and say what it answered: "yes, the model handles X", or "no, after A then B the order ends up both cancelled and shipped". Moments where someone says "wait, that shouldn't be possible" are the findings.
6. **Capture the answer.** Write the verdict and the question it settled where the work is tracked (the ticket, the PR description or the design doc), after the user approves the text. If the user wants the prototype kept, propose committing it to the `prototype/<slug>` branch and wait for the yes. Fold only the validated module into real code, with real tests, through the normal workflow.

**Done when** the question has a yes or no with the scenario that shows it, and the user knows where the prototype lives and how to delete it.

For a UI question ("what should this look like"), use `design-directions` instead.
