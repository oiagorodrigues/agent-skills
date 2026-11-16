---
name: correct
description: "Turns a repeated agent mistake into a rule that enforces itself. Climbs a ladder (architecture, then a type, then a lint or CI check whose error names the fix, then a test, and prose rules last), proves each new check fails on a real past mistake, and implements the highest rung that works. Use when the user runs /correct, corrects the same kind of mistake a second time, says \"you keep doing X\" or \"make this impossible\", or when retro or debugging finds a mistake class that a check could catch."
---

# Correct

Adapted from Lauren Tan's correct in pstack (MIT, https://github.com/cursor/plugins/tree/main/pstack). Turn every mistake into a rule, and every rule into something that fails when it is broken.

Assume every contributor is an agent that sees only the files it opened, copies the nearest example and takes the shortest path that compiles. Change the repo so a change that looks right from one file is right for the whole repo.

## 1. Find the mistake class

Start from the correction in front of you. Then look for the same class in recent commits, reverts, PR review comments (`gh pr list --state merged --limit 30`, `gh api repos/<org>/<repo>/pulls/<n>/comments`), the saved retros in `~/.agents/retros/`, and comments that explain workarounds. A class counts once it has happened twice. **Done when** you can name the class in one sentence and cite two occurrences.

## 2. Pick the highest rung that works

1. **Architecture.** Make the wrong thing impossible to write: one owner per piece of state, one supported way per task, internals hidden so the wrong import fails, one source of truth instead of hand-synced lists, old ways and dead code deleted so nobody copies them.
2. **Types.** Make the bad state unrepresentable (a narrower type, an enum, a parsed value object at the boundary).
3. **Lint or CI check.** If bad code still compiles, add a rule in the repo's existing linter (ruff, eslint, a custom check script) or a pre-commit or CI step, whose error message names the file, function or type to use instead. If the pattern is already common, fail only on new occurrences (a baseline, or a diff-only check).
4. **Test.** Test the behavior through the public interface. Fix or delete a test that still passes when the behavior breaks, or fails when only internals change.
5. **Prose rule, last.** A line in the repo's CLAUDE.md or AGENTS.md, `~/.agents/AGENTS.md` or a skill, only for judgment calls no check can catch. Nothing fails when an agent skips it.

For each class, write why each higher rung doesn't work before settling on a lower one. **Done when** each class has one rung and that reason.

## 3. Prove it, then implement

- Show the check fails on a real past mistake (check out the old commit or paste the old snippet into a scratch file) and passes on the fixed code. A check that has never failed proves nothing.
- Run the same command locally and in CI. Wire it into the repo's existing lint or CI config rather than a new runner.
- Exceptions go on the offending line with a reason and an owner.
- Follow `engineering-practices` and the repo's own rules. Work on a branch, never on `main`.

Implement it, then stop. Commits, pushes and PRs wait for the user's yes, and a PR goes through `create-pr` and the local review in AGENTS.md. Changes to `~/.agents/AGENTS.md` or a skill go through `create-skill`.

## 4. Keep the rule table

When the repo's agent instruction file (CLAUDE.md or AGENTS.md) has room for it, propose a short table pairing each rule with what enforces it (`Never call X directly | lint: no-direct-x`). When the user corrects you again for a rule already in the table and nothing enforces it, that is a repeat: fix it on a higher rung in the same change. Drop a row once its mistake can't happen.

## Reply

For each class: the evidence (two occurrences), the rung picked and why higher rungs didn't work, the proof that the check fails on the old mistake, and what is waiting for the user's yes.
