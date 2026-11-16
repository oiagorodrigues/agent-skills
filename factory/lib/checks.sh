#!/usr/bin/env bash
# Runs a repo's check commands once per commit and caches the result, so verify, review and the
# PR stage read one file instead of re-running the same suite on the same code.
#   checks.sh <worktree> <base> <commands-file> <cache-dir> [--force]
# The commands file has one shell command per line ('#' comments allowed), run in the worktree
# with CHANGED_FILES set to the files changed since <base>, one per line, for targeted tests.
# Prints the result file path; its first line is PASS or FAIL. Exit 0 PASS, 1 FAIL, 2 bad input.
set -uo pipefail
WT="${1:-}"; BASE="${2:-}"; CONF="${3:-}"; CACHE="${4:-}"; FORCE="${5:-}"
[ -n "$CACHE" ] || { echo "usage: checks.sh <worktree> <base> <commands-file> <cache-dir> [--force]" >&2; exit 2; }
[ -f "$CONF" ] || { echo "no commands file at $CONF" >&2; exit 2; }
[ -z "$(git -C "$WT" status --porcelain)" ] || { echo "$WT has uncommitted work; checks run on commits only" >&2; exit 2; }

SHA="$(git -C "$WT" rev-parse HEAD)" || exit 2
mkdir -p "$CACHE"; OUT="$CACHE/$SHA.md"
if [ "$FORCE" != --force ] && [ -f "$OUT" ]; then
  echo "$OUT"; head -1 "$OUT" | grep -q '^PASS'; exit $?
fi

CHANGED_FILES="$(git -C "$WT" diff --name-only "$BASE...HEAD")"; export CHANGED_FILES
status=PASS; body=""
while IFS= read -r cmd; do
  case "$cmd" in ''|'#'*) continue ;; esac
  start=$(date +%s)
  log="$(cd "$WT" && bash -c "$cmd" 2>&1 < /dev/null)"; rc=$?
  [ $rc -eq 0 ] || status=FAIL
  # The tail is enough to see what failed; the stage that fixes it re-runs the one command.
  body+="### \`$cmd\`: exit $rc ($(( $(date +%s) - start ))s)"$'\n''```'$'\n'"$(printf '%s\n' "$log" | tail -20)"$'\n''```'$'\n'
done < "$CONF"

{ echo "$status checks @ ${SHA:0:12} ($(date -u +%Y-%m-%dT%H:%MZ))"; echo; printf '%s' "$body"; } > "$OUT"
echo "$OUT"
[ "$status" = PASS ]
