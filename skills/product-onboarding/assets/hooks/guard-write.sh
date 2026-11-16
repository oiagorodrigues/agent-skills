#!/usr/bin/env bash
# PreToolUse: Edit|Write|MultiEdit|NotebookEdit
# Onboarding is discovery, not repair: while .claude/ONBOARDING_ACTIVE exists, the only
# writable path is docs/onboarding/**. Inert without the marker, so normal work is free.
set -uo pipefail

proj="${CLAUDE_PROJECT_DIR:-$PWD}"
[ -f "$proj/.claude/ONBOARDING_ACTIVE" ] || exit 0

target="$(cat | jq -r '.tool_input.file_path // .tool_input.notebook_path // empty' 2>/dev/null)"
[ -n "$target" ] || exit 0
case "$target" in "$proj"/*) rel="${target#"$proj"/}" ;; *) rel="$target" ;; esac

case "$rel" in
  docs/onboarding/*) exit 0 ;;
  /tmp/*|/private/tmp/*|/var/folders/*) exit 0 ;;   # scratchpad
esac

{
  echo "ONBOARDING FENCE: '$rel' is outside docs/onboarding/."
  echo "This skill reconstructs requirements; it does not change the product. Record the"
  echo "finding as drift or a risk in docs/onboarding/REQUIREMENTS.md instead."
  echo "If the user has approved real changes, end onboarding first:"
  echo "  rm $proj/.claude/ONBOARDING_ACTIVE"
} >&2
exit 2
