#!/bin/sh
# Installs or repairs the RTK hooks in every agent that supports them. Safe to re-run after `brew upgrade rtk`.
# Goose, Continue and Kiro have no RTK hook; they follow the RTK rule in ~/.agents/AGENTS.md.
set -e
# "$HOME"/.claude-*/ matches every extra Claude Code profile folder (CLAUDE_CONFIG_DIR).
for dir in "$HOME/.claude" "$HOME"/.claude-*/; do
  dir=${dir%/}
  [ -d "$dir" ] && CLAUDE_CONFIG_DIR="$dir" rtk init -g --auto-patch </dev/null
done
rtk init -g --agent cursor --auto-patch </dev/null
rtk init -g --codex </dev/null
rtk init -g --gemini --hook-only --auto-patch </dev/null
rtk init -g --opencode --auto-patch </dev/null

# `rtk init --copilot` writes into ~/.copilot/copilot-instructions.md, a symlink to ~/.agents/AGENTS.md,
# so only the hook file is written here.
mkdir -p "$HOME/.copilot/hooks"
cat > "$HOME/.copilot/hooks/rtk-rewrite.json" <<'EOF'
{
  "version": 1,
  "hooks": {
    "PreToolUse": [
      { "type": "command", "command": "rtk hook copilot", "cwd": ".", "timeout": 5 }
    ]
  }
}
EOF

# An old Cursor entry pointing at ./hooks/rtk-rewrite.sh survives the migration, which deletes that script.
jq '(.hooks.preToolUse[] | select(.command | test("rtk"))).command = "rtk hook cursor"' \
  "$HOME/.cursor/hooks.json" > "$HOME/.cursor/hooks.json.tmp" && mv "$HOME/.cursor/hooks.json.tmp" "$HOME/.cursor/hooks.json"
