#!/usr/bin/env bash
# Scans lines added between <base> and HEAD for high-signal secret patterns before a push,
# when gitleaks isn't available (references/sinks-and-secrets.md). Prints file:line and the pattern name, never the matched value, so logs stay clean.
#   secret-scan.sh <worktree> <base>     exit 0 clean, 1 possible secret, 2 bad input
set -uo pipefail
WT="${1:-}"; BASE="${2:-}"
[ -n "$WT" ] && [ -n "$BASE" ] || { echo "usage: secret-scan.sh <worktree> <base>" >&2; exit 2; }
git -C "$WT" rev-parse --verify -q "$BASE" >/dev/null || { echo "unknown base $BASE in $WT" >&2; exit 2; }

# name|regex. Kept to formats with few false positives; a hit stops the push for a person to look.
PATTERNS='private key|-----BEGIN [A-Z ]*PRIVATE KEY-----
aws access key|AKIA[0-9A-Z]{16}
github token|gh[pousr]_[A-Za-z0-9]{20,}
slack token|xox[abprs]-[A-Za-z0-9-]{10,}
api key (sk-)|sk-[A-Za-z0-9_-]{20,}
assigned secret|(api[_-]?key|secret|passwd|password|token)["'"'"' ]*[:=]["'"'"' ]*[A-Za-z0-9/+_-]{16,}'

found=0
diff="$(git -C "$WT" diff -U0 "$BASE...HEAD" -- . ':(exclude)*.lock' ':(exclude)*lock.json' ':(exclude)*lock.yaml' ':(exclude)*.snap')"
while IFS='|' read -r name re; do
  printf '%s\n' "$diff" | awk -v re="$re" -v name="$name" '
    /^\+\+\+ b\// { file = substr($0, 7); next }
    /^@@/ { split($3, a, ","); line = substr(a[1], 2) + 0; next }
    /^\+/ { if (tolower($0) ~ tolower(re)) { printf "%s:%d possible %s\n", file, line, name; hit = 1 } line++ }
    END { exit hit ? 1 : 0 }' || found=1
done <<< "$PATTERNS"
exit "$found"
