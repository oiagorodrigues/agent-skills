#!/usr/bin/env bash
# Claude Code PreToolUse hook (matcher Bash). Rejects foreground polling: a loop that sleeps, or a
# long leading sleep, sent without run_in_background. Those calls hold the turn, get denied by auto
# mode, and agents kept retrying the same shape. Exit 2 blocks the call and shows stderr to the model.
set -uo pipefail
command -v jq >/dev/null 2>&1 || exit 0   # no jq: never block on our own missing dependency

input="$(cat)"
[ "$(printf '%s' "$input" | jq -r '.tool_input.run_in_background // false' 2>/dev/null)" = "true" ] && exit 0
cmd="$(printf '%s' "$input" | jq -r '.tool_input.command // empty' 2>/dev/null)"
[ -n "$cmd" ] || exit 0

flat="$(printf '%s' "$cmd" | tr '\n' ' ')"
loop_sleeps=0
printf '%s' "$flat" | grep -qE '(^|[;&|({[:space:]])(while|until|for)[[:space:]].*[;[:space:]]do[[:space:]].*(^|[;&|({[:space:]])sleep[[:space:]]' && loop_sleeps=1
# A single sleep under 5 seconds (letting a process settle) is fine; 5 or more is waiting.
long_sleep=0
printf '%s' "$flat" | grep -qE '(^|[;&|({[:space:]])sleep[[:space:]]+([5-9]|[1-9][0-9]+)(\.[0-9]+)?[smh]?([;&|)[:space:]]|$)' && long_sleep=1

if [ "$loop_sleeps" = 1 ] || [ "$long_sleep" = 1 ]; then
  cat >&2 <<'MSG'
BLOCKED: foreground polling (a loop with sleep, or sleep of 5s or more).
To wait for a condition, use the Monitor tool with an until-loop, or send the command with
run_in_background: true and wait for its notification. Don't resend this command in another shape.
MSG
  exit 2
fi
exit 0
