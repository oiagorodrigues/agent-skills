#!/bin/sh
# Codex reads ~/.agents/skills directly, so it gets no links.
# A skill stays out of an agent folder when its .link-skip file lists that folder, one path
# relative to $HOME per line (e.g. ".claude-work/skills"); blank lines and # comments
# are ignored. Use it when that agent already has a project skill with the same name.
src="$HOME/.agents/skills"

skipped() { # $1 skill folder, $2 agent folder
  [ -f "$1/.link-skip" ] || return 1
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in '' | '#'*) continue ;; esac
    [ "$HOME/${line%/}" = "$2" ] && return 0
  done <"$1/.link-skip"
  return 1
}

# "$HOME"/.claude-*/skills covers every extra Claude Code profile (CLAUDE_CONFIG_DIR); an unmatched glob
# stays literal and fails the -d test below.
for dir in \
  "$HOME/.claude/skills" "$HOME"/.claude-*/skills \
  "$HOME/.gemini/skills" "$HOME/.cursor/skills" "$HOME/.config/opencode/skills" \
  "$HOME/.copilot/skills" "$HOME/.config/goose/skills" "$HOME/.continue/skills" "$HOME/.kiro/skills"; do
  [ -d "$dir" ] || continue
  find "$dir" -maxdepth 1 -type l ! -exec test -e {} \; -print -delete
  for skill in "$src"/*/; do
    name=$(basename "$skill")
    [ -f "$skill/SKILL.md" ] || continue
    if skipped "$skill" "$dir"; then
      # Remove only a link into ~/.agents/skills; a real folder or any other link stays.
      if [ -L "$dir/$name" ]; then
        case "$(readlink "$dir/$name")" in
        "$src"/*) rm "$dir/$name" && echo "unlinked $dir/$name (.link-skip)" ;;
        esac
      fi
      continue
    fi
    [ -e "$dir/$name" ] || [ -L "$dir/$name" ] || { ln -s "$src/$name" "$dir/$name" && echo "linked $dir/$name"; }
  done
done
