# Checks before calling work done

Run every line before you call a task done, whether you are an interactive agent, a reviewer or the verify stage of a pipeline, and report each as PASS or FAIL with its proof. Whoever writes the code doesn't grade it against this list: in a pipeline the verifier runs it, and the implementer never receives it (`reducing-ai-slop.md`). In an interactive session, run it yourself as a last pass before the final reply.

Each line is a mistake a person caught after an agent called the work done, added after the user's yes (the `correct` and `retro` skills). Checks for one repo go in that repo's checks file, in the workspace skill when one exists (`references/checks/<repo>.md`), and run after these.

- Every acceptance criterion has a PASS with saved proof (a screenshot on disk, a command and its output, a query and its result), listed in the report · open each listed file or output
- Tests written before the change to prove it (by another step, or before the implementation) are unchanged since they were written and now pass · `git diff <sha where they were written>..HEAD -- <those test files>` is empty and the test command passes
- No comment or docstring restates the code ("Comments and docstrings" in `SKILL.md`) · read the added comment lines in the diff
- No file changed outside the plan's "Files to change", or the reason is in the PR notes · `~/.agents/skills/review-pr/scripts/review-bundle.sh` lists them under "Out of plan"
- No secret in the lines the branch adds · gitleaks over `<base>..HEAD` (`~/.agents/skills/security-review/references/sinks-and-secrets.md`), or `~/.agents/skills/security-review/scripts/secret-scan.sh` when gitleaks isn't available
