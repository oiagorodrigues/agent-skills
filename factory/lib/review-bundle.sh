#!/usr/bin/env bash
# Builds the review input for a ticket's branch with git, so the verify and PR stages read one
# file instead of rediscovering the diff and its callers one tool call at a time. Read-only.
#   review-bundle.sh <worktree> <base> <out-file> [planned-files]
# planned-files lists the paths the plan said to change (one per line, globs allowed); files
# changed outside it are listed as out of plan.
set -uo pipefail
WT="${1:-}"; BASE="${2:-}"; OUT="${3:-}"; PLANNED="${4:-}"
[ -n "$OUT" ] || { echo "usage: review-bundle.sh <worktree> <base> <out-file> [planned-files]" >&2; exit 2; }
g() { git -C "$WT" "$@"; }
MB="$(g merge-base "$BASE" HEAD)" || { echo "no merge base between $BASE and HEAD in $WT" >&2; exit 2; }
# Diff more than this many lines goes to a side file, so the bundle stays readable in one Read.
MAX_INLINE=1500
NOISE=(':(exclude)*lock.yaml' ':(exclude)*lock.json' ':(exclude)*.lock' ':(exclude)**/generated/**'
       ':(exclude)**/dist/**' ':(exclude)**/__snapshots__/**' ':(exclude)*.snap' ':(exclude)*.min.*')
changed="$(g diff --name-only "$MB" HEAD -- . "${NOISE[@]}")"
mkdir -p "$(dirname "$OUT")"

{
  echo "# Review bundle"
  echo "base $BASE @ $(g rev-parse --short "$BASE") · merge-base $(g rev-parse --short "$MB") · head $(g rev-parse --short HEAD)"
  echo
  echo "## Commits"
  g log --format='- %h %s' "$MB..HEAD" | head -40
  echo
  if [ -n "$PLANNED" ] && [ -f "$PLANNED" ]; then
    echo "## Out of plan"
    outside=""
    while IFS= read -r f; do
      [ -n "$f" ] || continue; ok=0
      while IFS= read -r pat; do
        [ -n "$pat" ] || continue
        # shellcheck disable=SC2254
        case "$f" in $pat|$pat/*) ok=1; break ;; esac
      done < "$PLANNED"
      [ "$ok" = 1 ] || outside+="- $f"$'\n'
    done <<< "$changed"
    printf '%s\n' "${outside:-none}"
  fi
  echo "## Stat"
  echo '```'; g diff --stat=120 "$MB" HEAD -- . "${NOISE[@]}" | tail -60; echo '```'
  echo
  echo "## Callers outside the diff"
  syms="$(g diff -U0 "$MB" HEAD -- '*.ts' '*.tsx' '*.js' '*.jsx' '*.mjs' '*.vue' '*.py' "${NOISE[@]}" \
    | grep -E '^[+-][^+-]' \
    | grep -oE '(export (default )?(async )?(function|const|let|class|interface|type|enum) +[A-Za-z_][A-Za-z0-9_]*|^[+-][[:space:]]*(async )?def +[A-Za-z_][A-Za-z0-9_]*|^[+-]class +[A-Za-z_][A-Za-z0-9_]*)' \
    | awk '{print $NF}' | sort -u | head -40)"
  if [ -z "$syms" ]; then
    echo "no exported symbol changed"
  else
    skip=(); while IFS= read -r f; do [ -n "$f" ] && skip+=(":(exclude)$f"); done <<< "$changed"
    for s in $syms; do
      files="$(g grep -l -w -I "$s" HEAD -- . "${NOISE[@]}" ':(exclude)*.md' ':(exclude)docs/**' "${skip[@]}" 2>/dev/null | sed 's#^HEAD:##')"
      echo "- \`$s\`: $(printf '%s' "$files" | grep -c . ) file(s)"
      [ -n "$files" ] && printf '%s\n' "$files" | head -8 | sed 's/^/    /'
    done
  fi
  echo
  echo "## Tests touched"
  tests="$(printf '%s\n' "$changed" | grep -E '(\.test\.|\.spec\.|/__tests__/|/tests?/|(^|/)test_[^/]*\.py$|_test\.)' || true)"
  printf '%s\n' "${tests:-none: a behavior change with no test change is a finding}" | sed '/^none/!s/^/- /'
  echo
  echo "## Diff"
  lines="$(g diff -U3 "$MB" HEAD -- . "${NOISE[@]}" | wc -l | tr -d ' ')"
  if [ "$lines" -le "$MAX_INLINE" ]; then
    echo '```diff'; g diff -U3 --diff-algorithm=histogram "$MB" HEAD -- . "${NOISE[@]}"; echo '```'
  else
    g diff -U3 --diff-algorithm=histogram "$MB" HEAD -- . "${NOISE[@]}" > "${OUT%.md}.diff"
    echo "$lines lines, too big to inline: ${OUT%.md}.diff. Lines per file:"
    g diff --numstat "$MB" HEAD -- . "${NOISE[@]}" | awk '{printf "- %s (+%s -%s)\n", $3, $1, $2}'
  fi
} > "$OUT"
echo "$OUT"
