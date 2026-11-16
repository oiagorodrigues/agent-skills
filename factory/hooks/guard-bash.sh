#!/usr/bin/env bash
# PreToolUse hook (matcher Bash) for every factory stage. Blocks commands no stage may run,
# whatever the ticket or a page says. The factory script pushes, opens the PR and talks to Jira;
# stages never do. Exit 2 blocks the call and shows stderr to the model.
set -uo pipefail

cmd="$(jq -r '.tool_input.command // empty' 2>/dev/null)"
[ -n "$cmd" ] || exit 0

deny() { printf 'BLOCKED by factory: %s\n' "$1" >&2; exit 2; }
# Matches a git subcommand anywhere in a chain, with or without the rtk prefix or git -C <dir>.
git_sub() { printf '%s' "$cmd" | grep -qE "(^|[;&|(][[:space:]]*)(rtk[[:space:]]+)?git[[:space:]]+([^;&|]*[[:space:]])?($1)([[:space:]]|\$)"; }
has() { printf '%s' "$cmd" | grep -qE "$1"; }

git_sub 'push' && deny "git push. The factory pushes after verify passes."
git_sub 'merge|rebase' && deny "git merge/rebase. Stages commit on their branch only."
git_sub 'reset' && has 'reset[[:space:]]+([^;&|]*[[:space:]])?--hard' && deny "git reset --hard. It drops uncommitted work."
git_sub 'clean' && deny "git clean. It deletes untracked files."
git_sub 'checkout|switch' && has '(checkout|switch)[[:space:]]+(main|master)([[:space:]]|$)' && deny "switching to the trunk."
has '(^|[;&|(][[:space:]]*)(rtk[[:space:]]+)?gh[[:space:]]+(pr[[:space:]]+(create|merge|close|edit|comment|review|ready)|release|repo[[:space:]]+(delete|edit)|api[[:space:]].*(-X|--method)[[:space:]]*(POST|PUT|PATCH|DELETE))' \
  && deny "GitHub write. The factory opens and updates the PR."

case "$cmd" in
  *--insecure*|*"curl -k"*|*NODE_TLS_REJECT_UNAUTHORIZED=0*|*GIT_SSL_NO_VERIFY*|*http.sslVerify=false*|*--trusted-host*|*verify=False*|*--no-check-certificate*)
    deny "disabling TLS verification." ;;
esac
has '(curl|wget)[^|]*\|[[:space:]]*(sudo[[:space:]]+)?(bash|sh|zsh|python3?|node|ruby|perl)' && deny "piping a download into an interpreter."
has '(cat|head|tail|grep|strings|base64)[^|;]*(\.env|id_rsa|id_ed25519|\.aws/credentials|\.ssh/|\.netrc|credentials\.json)' \
  && has '\|[[:space:]]*(curl|wget|nc|ncat|socat|ssh|scp|mail)' && deny "sending local credentials to the network."
has '(npm|pnpm|yarn)[[:space:]]+publish|twine[[:space:]]+upload|poetry[[:space:]]+publish|docker[[:space:]]+push' && deny "publishing an artifact."
exit 0
