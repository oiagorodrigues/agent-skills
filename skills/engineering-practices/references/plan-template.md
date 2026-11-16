# <TICKET> plan

Write this before larger work (`SKILL.md`, "How to work"), in an interactive session or as a pipeline's plan stage. A short read-only check passes it only when every criterion has a check, the files cover every criterion and no step leaves the scope (`reducing-ai-slop.md`).

**Repo:** <repo> · **Base:** <branch> · **Test command:** `<exact command for the changed files>`

## Scope
IN: <what this ticket changes>
OUT: <adjacent work this ticket must not touch>

## Files to change
```
<path/one>
<path/two>
```
`~/.agents/skills/review-pr/scripts/review-bundle.sh` lists any other changed file as out of plan.

## Steps
1. <change, file, the AC it serves>

## Acceptance criteria
One pass/fail line each, with how to check it on the running result (see `reducing-ai-slop.md`).
- **AC1** <input> → <observable output> · check: <command, page and action, or query>
- **AC2** <failure input> → <error and status> · check: <...>

## Tests that will fail without the change
- AC1: <test file::name, written before the implementation, by another step when there is one>

## Definition of done
- [ ] Every AC has a test that fails without the change
- [ ] Lint and type check pass on the changed files
- [ ] No file changed outside "Files to change", or the reason is in the PR notes
- [ ] No new dependency unless the plan names it
