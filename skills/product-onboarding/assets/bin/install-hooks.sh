#!/usr/bin/env bash
# Arms the onboarding fence + the REQUIREMENTS.md validator for this repo.
#   install-hooks.sh          arm
#   install-hooks.sh --end    disarm (leaves the hooks registered, they go inert)
set -euo pipefail

proj="${CLAUDE_PROJECT_DIR:-$PWD}"
skill="$HOME/.agents/skills/product-onboarding"
marker="$proj/.claude/ONBOARDING_ACTIVE"

if [ "${1:-}" = "--end" ]; then
  rm -f "$marker"; echo "onboarding fence off — writes outside docs/onboarding/ allowed again"; exit 0
fi

command -v jq >/dev/null || { echo "jq required" >&2; exit 1; }
mkdir -p "$proj/.claude" "$proj/docs/onboarding"

settings="$proj/.claude/settings.local.json"   # local: never committed into someone else's repo
[ -f "$settings" ] || echo '{}' > "$settings"

tmp="$(mktemp)"
jq -s '
  .[0] as $cur | .[1].hooks as $add |
  ($cur.hooks // {}) as $h |
  $cur + {hooks: ($h + (reduce ($add | to_entries[]) as $e ({};
      .[$e.key] = ((($h[$e.key] // []) + $e.value)
                   | unique_by((.matcher // "") + (.hooks[0].command // ""))))))}
' "$settings" "$skill/assets/templates/settings.hooks.json" > "$tmp"
mv "$tmp" "$settings"

[ -f "$proj/docs/onboarding/REQUIREMENTS.md" ] || cp "$skill/assets/templates/REQUIREMENTS.md" "$proj/docs/onboarding/REQUIREMENTS.md"
touch "$marker"

echo "armed:"
echo "  fence      writes limited to docs/onboarding/**  (marker: .claude/ONBOARDING_ACTIVE)"
echo "  validator  docs/onboarding/REQUIREMENTS.md checked on every write"
echo "  settings   $settings"
echo "end with: $0 --end"
