# <TICKET> plan

**Repo:** <repo> · **Base:** <branch> · **Test command:** `<exact command for the changed files>`

## Scope
IN: <what this ticket changes>
OUT: <adjacent work this ticket must not touch>

## Files to change
```
<path/one>
<path/two>
```
The factory lists any other changed file as out of plan in the review bundle.

## Steps
1. <change, file, the AC it serves>

## Acceptance criteria
One pass/fail line each, with how to check it on the running result (see `engineering-practices`, `references/reducing-ai-slop.md`).
- **AC1** <input> → <observable output> · check: <command, page and action, or query>
- **AC2** <failure input> → <error and status> · check: <...>

## Tests that will fail without the change
- AC1: <test file::name, written by qa before implement>

## Definition of done
- [ ] Every AC has a test that fails without the change
- [ ] Lint and type check pass on the changed files (`checks.sh` result is PASS)
- [ ] No file changed outside "Files to change", or the reason is in the PR notes
- [ ] No new dependency unless the plan names it
