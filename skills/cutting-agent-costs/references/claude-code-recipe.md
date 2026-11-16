# Claude Code headless recipe

Measured with Haiku, prompt "reply with: ok", in an empty directory, Claude Code 2.1.322. Numbers move by a few thousand tokens between runs; the trend is what matters.

## Startup context by flag set

| Flags | Context tokens |
|---|---|
| default | ~35,000 |
| `--disable-slash-commands` (no skills) | ~18,000 to 23,500 |
| + `--strict-mcp-config --mcp-config '{"mcpServers":{}}'` | ~18,000 |
| + `--tools "Bash,Read,Edit,Write,Grep,Glob"` | ~13,300 |
| + `--setting-sources project` | ~8,600 |
| + `--system-prompt-file` with a 1-line prompt | ~10,200 (vs 13,300 without it) |
| `--safe-mode --tools ...` | ~7,600 |
| Stage recipe below (both accounts) | ~11,500; second run reads ~11,470 from cache and costs about $0.0001 |
| Recipe, read-only stage (`--tools "Read,Grep,Glob,Skill"`) | ~9,500 |
| Recipe, text stage (`--tools "Read,Skill"` + 3-line `--system-prompt-file`) | ~4,900 |

Trimming tools and the system prompt doesn't change reasoning (effort and model do) or the task context the stage receives. What a text stage loses is Claude Code's own guidance on tools, environment details (cwd, git status) and safety wording, so use it only for stages that read files and write text, and compare output quality on a few real tasks before making it the default.

The skill listing alone was about 11k tokens with ~80 skills.

## Stage recipe

```bash
claude -p "$(cat stage-input.md)" \
  --model "$MODEL" --effort "$EFFORT" \
  --output-format json --no-session-persistence \
  --max-budget-usd "$BUDGET" --max-turns "$TURNS" \
  --permission-mode dontAsk \
  --setting-sources project \
  --settings factory-settings.json \
  --plugin-dir "stages/$STAGE/plugin" \
  --strict-mcp-config --mcp-config "stages/$STAGE/mcp.json" \
  --tools "$STAGE_TOOLS" \
  --allowedTools $STAGE_ALLOWED \
  --append-system-prompt-file "stages/$STAGE/prompt.md" \
  < /dev/null
```

`factory-settings.json` holds `skillOverrides` set to `"off"` for every personal skill (generate it from the skills folder) plus only the hooks the run needs, for example:

```json
{"hooks":{"PreToolUse":[{"matcher":"Bash","hooks":[{"type":"command","command":"rtk hook claude"}]}]}}
```

## Gotchas found in testing

- `skillOverrides` hides personal skills but not Claude Code's built-in skills or plugin skills; the plugin skill shows up as `<plugin>:<skill>` and the model can invoke it.
- The rtk hook rewrites `git ...` to `rtk git ...` before the permission check, so allow rules must match the rewritten command (`Bash(rtk git log:*)`), or the call is denied.
- Pipe `< /dev/null` into headless runs; otherwise the CLI waits 3 seconds for stdin.
- Setting `CLAUDE_CONFIG_DIR=$HOME/.claude` explicitly made runs return zero usage (no auth). Leave the variable unset for the default account; set it only for another account (for example `~/.claude-work`).
- `--bare` skips hooks even when they come from `--settings`, and does not read OAuth logins.
- `--output-format stream-json` needs `--verbose` in `-p` runs.
- `--setting-sources project` skips user settings, so a model allowlist (`availableModels`, `enforceAvailableModels`) in `~/.claude*/settings.json` does not apply to those runs. Put it in the `--settings` file too. A `--model` outside the list does not fail: Claude Code swaps in the default model with a warning, so a pipeline that must fail closed checks the model itself. Managed settings, when deployed, always apply. https://code.claude.com/docs/en/model-config
- Check the stream-json `system/init` message (`tools`, `skills`, `plugins`, `mcp_servers`) to confirm what a stage actually loaded.
