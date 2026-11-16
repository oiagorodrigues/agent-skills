# /10x-team commit — Smart Commit Message Generator

Analyze all staged and unstaged changes, then create a well-structured commit.

## Commit rules

Every commit this skill makes follows these rules: this command, the commit at each phase gate and the one in `init-project`. The format comes from the `git-commit` skill (Conventional Commits), and the rest from `~/.agents/AGENTS.md` and the repo's own config.

- Read the repo's commitlint or contributing rules first, and the workspace skill for the repo when one exists, which may set the subject limit and the allowed types. Gate commits use `chore(10x): <phase> phase complete`, not a custom `state` type.
- No AI signature of any kind: no `Co-Authored-By`, no "Generated with", no mention of Claude or AI.
- Never pass `--no-verify`, unless the workspace skill for the repo names an exception. If a hook fails, fix the cause and commit again.
- If the current branch is the repo's default branch, create a branch first.
- Commit only. Don't push, amend or rebase unless the user asks.
- Write the body with the `plain-writing` skill.

## Steps

1. **Gather context** — Run these commands to understand the full picture:
   - `git status` to see all changed, staged, and untracked files
   - `git diff` to see unstaged changes
   - `git diff --cached` to see staged changes
   - `git log --oneline -5` to see recent commit style

2. **Analyze the changes** — For each changed file, understand:
   - What was added, removed, or modified
   - The intent behind the change (feature, fix, refactor, docs, test, chore)
   - Whether multiple concerns are mixed (suggest splitting if so)

3. **Stage files** — If nothing is staged, stage the relevant files by name. Never use `git add -A` or `git add .`. Skip files that look like secrets (`.env`, credentials, tokens).

4. **Write the commit message** using this format:

   ```
   <type>(<scope>): <short summary>

   <body — what changed and why, not how>
   ```

   **Types**: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `style`, `perf`, `ci`, `build`

   **Rules**:
   - Summary line: imperative mood, lowercase, no period, under 50 chars
   - Body: wrap at 72 chars, explain WHY not WHAT
   - If changes span multiple concerns, suggest separate commits
   - Match the project's existing commit style from `git log`

5. **Show the proposed commit message** to the user and ask for confirmation before committing.

6. **Commit** using a HEREDOC to preserve formatting:
   ```bash
   git commit -m "$(cat <<'EOF'
   <the message>
   EOF
   )"
   ```

## Examples

```
feat(auth): add OAuth2 login flow

Users can now sign in with Google and GitHub. Session tokens
are stored in HTTP-only cookies per security requirements.
```

```
fix(api): prevent duplicate webhook deliveries

Race condition in the queue consumer caused the same event to
fire twice when processing lagged. Added idempotency key check.
```

```
refactor(db): extract query builder from repository layer

Reduces duplication across 6 repository files. No behavior change.
```

## Anti-Patterns

- Never write vague messages like "update files" or "fix stuff"
- Never commit secrets or `.env` files — warn the user if detected
- Never combine unrelated changes in one commit without flagging it
- Never amend previous commits unless explicitly asked
- Never skip pre-commit hooks
