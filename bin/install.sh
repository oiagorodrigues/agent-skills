#!/usr/bin/env bash
# Puts this repo at ~/.agents and sets it up: checks tools, points every installed agent at AGENTS.md,
# installs the third-party skills in third-party.tsv, links the skills and, when asked, adds the retro
# hooks to Claude Code and the RTK hooks.
# Safe to re-run. It never overwrites or deletes a file in ~/.agents (except, under --yes, a third-party
# path from third-party.tsv that has local edits), and every agent config file it changes gets a
# timestamped backup first.
set -u

usage() {
  cat <<'EOF'
Usage: bin/install.sh [options]

Run it from a clone of the repo, anywhere. It first puts the repo at ~/.agents:
  ~/.agents missing                  clones the repo there.
  ~/.agents is a checkout of it      offers to pull (fast-forward only).
  ~/.agents is anything else         lists what differs and asks before merging. A merge adds only
                                     the missing files, keeps every local file as it is and makes
                                     ~/.agents a checkout of the repo, so git status shows the differences.
Then it checks tools, writes the AGENTS.md pointers, installs the third-party files listed in
third-party.tsv at their pinned commits (bin/fetch-third-party.sh, also runnable alone) and links the skills.

  --dry-run          Print what would change and change nothing.
  --yes, -y          Answer yes to the pull and merge questions, and let bin/fetch-third-party.sh
                     replace third-party folders that have local changes.
  --install-tools    Install missing required and recommended tools with Homebrew.
  --all-tools        With --install-tools, also install the optional tools.
  --hooks            Add the retro SessionStart/SessionEnd hooks and the polling guard (PreToolUse) to each Claude Code profile's settings.json.
  --rtk              Run bin/setup-rtk.sh to install the RTK hooks in every agent.
  -h, --help         Show this help.

Without a clone, set AGENTS_REPO_URL and run the script with bash -c; it clones to a temp folder first.
EOF
}

DRY_RUN=0 YES=0 INSTALL_TOOLS=0 ALL_TOOLS=0 HOOKS=0 RTK=0
for arg in "$@"; do
  case "$arg" in
  --dry-run) DRY_RUN=1 ;;
  --yes | -y) YES=1 ;;
  --install-tools) INSTALL_TOOLS=1 ;;
  --all-tools) ALL_TOOLS=1 ;;
  --hooks) HOOKS=1 ;;
  --rtk) RTK=1 ;;
  -h | --help) usage; exit 0 ;;
  *) echo "error: unknown option '$arg'" >&2; usage >&2; exit 2 ;;
  esac
done

AGENTS_DIR="$HOME/.agents"
AGENTS_MD="$AGENTS_DIR/AGENTS.md"
STAMP=$(date +%Y%m%d-%H%M%S)
WARNINGS=0

# Shows paths under $HOME as ~ to keep the output short.
short() { local s="$*" t='~'; printf '%s' "${s//"$HOME"/$t}"; }
say() { printf '%s\n' "$(short "$*")"; }
warn() { printf 'warning: %s\n' "$(short "$*")" >&2; WARNINGS=$((WARNINGS + 1)); }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }
section() { printf '\n== %s\n' "$*"; }

# Runs a command, or skips it under --dry-run. Callers print what the step does.
run() { [ "$DRY_RUN" = 1 ] || "$@"; }

backup() { # $1 file
  [ -e "$1" ] || [ -L "$1" ] || return 0
  say "  backup   $1.bak.$STAMP"
  run cp -P "$1" "$1.bak.$STAMP" || die "can't back up $1; nothing changed in it"
}

# Yes under --yes. Otherwise reads the answer from stdin, and no answer counts as no.
ask() { # $1 question
  if [ "$YES" = 1 ]; then
    say "$1 [y/N] y (--yes)"
    return 0
  fi
  local reply=""
  printf '%s [y/N] ' "$(short "$1")"
  read -r reply || echo
  case "$reply" in [yY] | [yY][eE][sS]) return 0 ;; esac
  return 1
}

# --- Bootstrap --------------------------------------------------------------
# Without a clone around the script (bash -c "$(curl ...)"), clone AGENTS_REPO_URL to a temp folder
# and run the clone's copy, which places it below and deletes the temp folder on exit.
self="${BASH_SOURCE[0]:-}"
if [ -z "$self" ] || [ ! -f "$self" ] || [ ! -f "$(dirname "$self")/../AGENTS.md" ]; then
  url="${AGENTS_REPO_URL:-}"
  [ -n "$url" ] || die "not running from a clone. Clone the repo and run its bin/install.sh, or set AGENTS_REPO_URL to the repo's git URL"
  command -v git >/dev/null 2>&1 || die "git is required (xcode-select --install)"
  tmp=$(mktemp -d "${TMPDIR:-/tmp}/agents-bootstrap.XXXXXX") || die "can't create a temp folder"
  say "Cloning $url"
  git clone --quiet "$url" "$tmp/repo" || { rm -rf "$tmp"; die "can't clone $url"; }
  # Piped into bash, stdin is the script itself, so the questions read the terminal instead.
  if [ ! -t 0 ] && (: </dev/tty) 2>/dev/null; then exec </dev/tty; fi
  AGENTS_BOOTSTRAP_DIR="$tmp" AGENTS_REPO_URL="$url" exec bash "$tmp/repo/bin/install.sh" "$@"
fi

# --- Location ---------------------------------------------------------------
# Skills, hooks and link-skills.sh all use ~/.agents, so the repo must live there.
script_dir=$(cd "$(dirname "$self")" && pwd -P) || die "can't resolve the script folder"
repo_dir=$(cd "$script_dir/.." && pwd -P)
repo_url="${AGENTS_REPO_URL:-$(git -C "$repo_dir" remote get-url origin 2>/dev/null)}"
TAB=$(printf '\t')
WORK_DIR=""
cleanup() {
  [ -z "$WORK_DIR" ] || rm -rf "$WORK_DIR"
  # Only the temp clone this script was started from by the bootstrap above.
  if [ -n "${AGENTS_BOOTSTRAP_DIR:-}" ] && [ "$repo_dir" = "$(cd "$AGENTS_BOOTSTRAP_DIR" 2>/dev/null && pwd -P)/repo" ]; then
    rm -rf "$AGENTS_BOOTSTRAP_DIR"
  fi
}
trap cleanup EXIT

is_checkout() { # $1 folder: true when it is the top of a git work tree
  [ "$(git -C "$1" rev-parse --show-toplevel 2>/dev/null)" = "$(cd "$1" && pwd -P)" ]
}

# Same repo when ~/.agents's history holds the repo's first commit, whatever the remote URLs say.
same_repo() {
  local root
  root=$(git -C "$repo_dir" rev-list --max-parents=0 HEAD 2>/dev/null | tail -1)
  [ -n "$root" ] && git -C "$AGENTS_DIR" merge-base --is-ancestor "$root" HEAD 2>/dev/null
}

offer_pull() {
  local upstream before
  upstream=$(git -C "$AGENTS_DIR" rev-parse --abbrev-ref '@{upstream}' 2>/dev/null) || {
    say "  ~/.agents has no upstream branch to pull from; left as it is"
    return 0
  }
  if [ "$DRY_RUN" = 1 ]; then
    say "  pull     would ask to pull $upstream into ~/.agents (fast-forward only)"
    return 0
  fi
  if ! ask "Pull the latest $upstream into ~/.agents (fast-forward only)?"; then
    say "  skip     pull"
    return 0
  fi
  before=$(git -C "$AGENTS_DIR" rev-parse HEAD)
  git -C "$AGENTS_DIR" pull --ff-only --quiet || {
    warn "git pull --ff-only failed in ~/.agents; its files are unchanged"
    return 0
  }
  if [ "$before" = "$(git -C "$AGENTS_DIR" rev-parse HEAD)" ]; then
    say "  ok       ~/.agents is up to date"
    return 0
  fi
  say "  pulled   $(git -C "$AGENTS_DIR" rev-parse --short "$before")..$(git -C "$AGENTS_DIR" rev-parse --short HEAD)"
  git -C "$AGENTS_DIR" diff --quiet "$before" HEAD -- bin/install.sh ||
    say "  note     bin/install.sh changed; re-run ~/.agents/bin/install.sh to use the new version"
}

clone_home() {
  if [ "$DRY_RUN" = 1 ]; then
    say "  clone    $repo_dir -> ~/.agents"
    say "Dry run: stopping here, because the remaining steps need ~/.agents in place."
    exit 0
  fi
  git clone --quiet "$repo_dir" "$AGENTS_DIR" || die "can't clone $repo_dir to $AGENTS_DIR"
  [ -z "$repo_url" ] || git -C "$AGENTS_DIR" remote set-url origin "$repo_url"
  say "  cloned   $repo_dir -> ~/.agents (origin: ${repo_url:-$repo_dir})"
}

# Writes four lists to $1: only_repo (in the repo's HEAD, missing locally), blocked (missing locally, but a
# local file or link sits where one of its folders goes), only_local (local files the repo lacks, minus what
# its .gitignore ignores) and differ (in both, different content or type).
compare_home() { # $1 work folder
  local w="$1" p mode sha f d
  git -C "$repo_dir" -c core.quotePath=false ls-tree -r --full-tree HEAD |
    awk -F'\t' '{ split($1, m, " "); print $2 "\t" m[1] "\t" m[3] }' >"$w/tree"
  cut -f1 "$w/tree" | LC_ALL=C sort >"$w/repo_paths"
  (cd "$AGENTS_DIR" && find . -name .git -prune -o \( -type f -o -type l \) -print) |
    sed 's|^\./||' | LC_ALL=C sort >"$w/local_paths"
  : >"$w/only_repo"
  : >"$w/blocked"
  LC_ALL=C comm -23 "$w/repo_paths" "$w/local_paths" |
    while IFS= read -r p; do
      f="$w/only_repo"
      d="$p"
      while [ "${d%/*}" != "$d" ]; do
        d="${d%/*}"
        if [ -L "$AGENTS_DIR/$d" ] || { [ -e "$AGENTS_DIR/$d" ] && [ ! -d "$AGENTS_DIR/$d" ]; }; then
          f="$w/blocked"
          break
        fi
      done
      echo "$p" >>"$f"
    done
  LC_ALL=C comm -12 "$w/repo_paths" "$w/local_paths" >"$w/both"
  LC_ALL=C comm -13 "$w/repo_paths" "$w/local_paths" >"$w/local_extra"
  git -C "$repo_dir" -c core.quotePath=false check-ignore --no-index --stdin <"$w/local_extra" |
    LC_ALL=C sort >"$w/ignored"
  LC_ALL=C comm -23 "$w/local_extra" "$w/ignored" >"$w/only_local"

  : >"$w/differ"
  : >"$w/hash_in"
  awk -F'\t' 'NR == FNR { both[$0] = 1; next } ($1 in both)' "$w/both" "$w/tree" |
    while IFS="$TAB" read -r p mode sha; do
      f="$AGENTS_DIR/$p"
      if [ "$mode" = 120000 ]; then
        { [ -L "$f" ] && [ "$(readlink "$f")" = "$(git -C "$repo_dir" cat-file blob "$sha")" ]; } || echo "$p" >>"$w/differ"
      elif [ -L "$f" ] || [ "$mode" = 160000 ]; then
        echo "$p" >>"$w/differ"
      else
        printf '%s\t%s\n' "$p" "$sha" >>"$w/hash_in"
      fi
    done
  cut -f1 "$w/hash_in" | awk -v d="$AGENTS_DIR/" '{ print d $0 }' |
    git -C "$repo_dir" hash-object --no-filters --stdin-paths >"$w/hash_out"
  paste "$w/hash_in" "$w/hash_out" | awk -F'\t' '$2 != $3 { print $1 }' >>"$w/differ"
  LC_ALL=C sort -o "$w/differ" "$w/differ"
}

# Shows the first 40 entries, or all of them under --dry-run.
print_list() { # $1 file, $2 heading, $3 marker
  local n max=40
  n=$(wc -l <"$1" | tr -d ' ')
  [ "$DRY_RUN" = 1 ] && max="$n"
  say "  $2: $n"
  awk -v m="$3" -v max="$max" 'NR <= max { print "    " m " " $0 }' "$1"
  [ "$n" -le "$max" ] || say "    ... and $((n - max)) more (--dry-run lists them all)"
}

merge_home() {
  local w had_git=0 n p
  WORK_DIR=$(mktemp -d "${TMPDIR:-/tmp}/agents-merge.XXXXXX") || die "can't create a temp folder"
  w="$WORK_DIR"
  [ -e "$AGENTS_DIR/.git" ] && had_git=1
  compare_home "$w"

  if [ "$had_git" = 1 ]; then
    say "  ~/.agents is a git checkout of another repo. A merge moves its .git to ~/.agents.git.bak.$STAMP."
  else
    say "  ~/.agents exists and isn't a git checkout."
  fi
  print_list "$w/only_repo" "Only in the repo, a merge adds them" "+"
  [ -s "$w/blocked" ] && print_list "$w/blocked" "Only in the repo, but a local file is in the way, left out" "!"
  print_list "$w/only_local" "Only local, kept, git status shows them as untracked" "?"
  print_list "$w/differ" "In both but different, local copy kept, git status shows them as modified" "~"
  if [ "$DRY_RUN" = 1 ]; then
    say "Dry run: nothing changed. Run without --dry-run to be asked about the merge."
    exit 0
  fi
  if ! ask "Merge?"; then
    say "Nothing changed."
    exit 0
  fi

  git clone --quiet --no-checkout "$repo_dir" "$w/clone" || die "can't clone $repo_dir; nothing changed"
  [ -z "$repo_url" ] || git -C "$w/clone" remote set-url origin "$repo_url"
  if [ "$had_git" = 1 ]; then
    mv "$AGENTS_DIR/.git" "$AGENTS_DIR.git.bak.$STAMP" || die "can't move ~/.agents/.git aside; nothing changed"
    say "  moved    ~/.agents/.git -> ~/.agents.git.bak.$STAMP"
  fi
  mv "$w/clone/.git" "$AGENTS_DIR/.git" || die "can't move the clone's .git into ~/.agents; no file in it changed"
  git -C "$AGENTS_DIR" read-tree HEAD || die "git read-tree failed in ~/.agents"
  # Without -f, checkout-index refuses to write over any path that exists.
  if [ -s "$w/only_repo" ]; then
    git -C "$AGENTS_DIR" -c core.quotePath=false checkout-index --stdin <"$w/only_repo" ||
      warn "some repo files couldn't be added (see above); local files stayed as they were"
  fi
  git -C "$AGENTS_DIR" update-index -q --refresh >/dev/null 2>&1
  n=0
  while IFS= read -r p; do
    { [ -e "$AGENTS_DIR/$p" ] || [ -L "$AGENTS_DIR/$p" ]; } && n=$((n + 1))
  done <"$w/only_repo"
  say "  merged   added $n file(s); ~/.agents now tracks ${repo_url:-$repo_dir}. Run git -C ~/.agents status to see the local differences."
}

[ "$DRY_RUN" = 1 ] && say "Dry run: nothing will change."
section "Location"
if [ -d "$AGENTS_DIR" ] && [ "$(cd "$AGENTS_DIR" && pwd -P)" = "$repo_dir" ]; then
  say "  ok       running from ~/.agents"
  command -v git >/dev/null 2>&1 && is_checkout "$AGENTS_DIR" && offer_pull
else
  command -v git >/dev/null 2>&1 || die "git is required (xcode-select --install or brew install git)"
  is_checkout "$repo_dir" || die "$repo_dir isn't a git clone. Clone the repo and run bin/install.sh from the clone."
  if [ ! -e "$AGENTS_DIR" ] && [ ! -L "$AGENTS_DIR" ]; then
    clone_home
  elif [ ! -d "$AGENTS_DIR" ]; then
    die "$AGENTS_DIR exists but isn't a folder; move it away and re-run"
  elif is_checkout "$AGENTS_DIR" && same_repo; then
    say "  ok       ~/.agents is a checkout of this repo"
    offer_pull
  else
    merge_home
  fi
fi
[ -f "$AGENTS_MD" ] || die "$AGENTS_MD is missing; the checkout looks incomplete"

# --- Tools ------------------------------------------------------------------
# command|brew package (cask: prefix for casks, - for none)|level|used by|hint when brew can't install it
TOOLS='git|git|required|everything|Xcode CLT: xcode-select --install
python3|python|required|bin/retro-hook.py, install.sh, many skill scripts|https://www.python.org/downloads/
rtk|rtk|recommended|AGENTS.md command-output rule, setup-rtk.sh, cutting-agent-costs|https://github.com/rtk-ai/rtk
gh|gh|recommended|create-pr, review-pr, triage, why, jira-workflow, find-skills|https://cli.github.com
jq|jq|recommended|setup-rtk.sh, aws, auth0, security-review, vercel-troubleshooter|https://jqlang.org/download/
uv|uv|recommended|uvx scripts in cartographer, review-skills, security-review (pip-audit), aws, autoresearch|https://docs.astral.sh/uv/
node|node|recommended|npx and pnpm based skills (auth0, harness-architect, find-skills)|https://nodejs.org
gitleaks|gitleaks|recommended|secret scan in security-review, engineering-practices done checks and before pushing this repo|https://github.com/gitleaks/gitleaks
claude|-|optional|bin/retro-hook.py worker (headless retro), review-skills, create-skill evals|https://docs.claude.com/en/docs/claude-code
pnpm|pnpm|optional|pnpm, engineering-practices (Stryker), security-review|https://pnpm.io/installation
dot|graphviz|optional|cartographer diagrams|https://graphviz.org/download/
agent-browser|agent-browser|optional|agent-browser|npm i -g agent-browser@<version> (see the skill)
osv-scanner|osv-scanner|optional|security-review (dependencies)|https://google.github.io/osv-scanner/
zizmor|zizmor|optional|security-review (GitHub Actions)|uvx zizmor
codex|cask:codex|optional|review-pr and cutting-agent-costs cross-vendor checks|https://github.com/openai/codex
aws|awscli|optional|aws, prod-evidence, security-review|https://aws.amazon.com/cli/
sam|aws-sam-cli|optional|aws (serverless topics)|https://docs.aws.amazon.com/serverless-application-model/
cdk|aws-cdk|optional|aws (CDK topics)|npm i -g aws-cdk
docker|cask:docker-desktop|optional|docker, debugging, backend-design, local stacks|https://docs.docker.com/desktop/
yt-dlp|yt-dlp|optional|watch-video|https://github.com/yt-dlp/yt-dlp
ffmpeg|ffmpeg|optional|watch-video, interactive-docs (video)|https://ffmpeg.org/download.html
auth0|-|optional|auth0|brew tap auth0/auth0-cli && brew install auth0'

section "Tools"
missing_install=""
missing_count=0
while IFS='|' read -r cmd pkg level used hint; do
  if command -v "$cmd" >/dev/null 2>&1; then
    printf '  ok       %-14s %s\n' "$cmd" "$level"
    continue
  fi
  missing_count=$((missing_count + 1))
  how="$hint"
  case "$pkg" in
  -) ;;
  cask:*) how="brew install --cask ${pkg#cask:}" ;;
  *) how="brew install $pkg" ;;
  esac
  printf '  MISSING  %-14s %-11s used by %s\n           install: %s\n' "$cmd" "$level" "$used" "$how"
  [ "$level" = required ] && warn "required tool '$cmd' is missing"
  if [ "$pkg" != - ] && { [ "$level" != optional ] || [ "$ALL_TOOLS" = 1 ]; }; then
    missing_install="$missing_install $pkg"
  fi
done <<EOF
$TOOLS
EOF
[ "$missing_count" = 0 ] && say "  All tools found."
say "  MCP servers (Atlassian, Slack, Sentry, Datadog, Sigma, Notion) are set up per agent; see README.md."

if [ "$INSTALL_TOOLS" = 1 ] && [ -n "$missing_install" ]; then
  if ! command -v brew >/dev/null 2>&1; then
    warn "--install-tools needs Homebrew (https://brew.sh); install the tools above by hand"
  else
    for pkg in $missing_install; do
      case "$pkg" in
      cask:*) say "  brew install --cask ${pkg#cask:}"; run brew install --cask "${pkg#cask:}" || warn "brew install --cask ${pkg#cask:} failed" ;;
      *) say "  brew install $pkg"; run brew install "$pkg" || warn "brew install $pkg failed" ;;
      esac
    done
  fi
elif [ "$INSTALL_TOOLS" = 0 ] && [ -n "$missing_install" ]; then
  say "  Run with --install-tools to install the missing required and recommended tools with Homebrew."
fi

# --- AGENTS.md pointers -----------------------------------------------------
# Claude Code and Gemini import with @path; Codex gets a sentence; the rest read a symlink.
POINTER_SENTENCE="Read and follow the shared rules for all agents in $AGENTS_MD before starting any task."

has_pointer() { [ -f "$1" ] && grep -qF '.agents/AGENTS.md' "$1"; }

# Appends a line to a file that may not exist yet.
append_pointer() { # $1 file, $2 line
  if has_pointer "$1"; then
    say "  ok       $1"
    return
  fi
  if [ -e "$1" ]; then
    backup "$1"
    say "  append   $1"
    if [ "$DRY_RUN" = 0 ]; then
      { [ -s "$1" ] && [ "$(tail -c1 "$1")" != "" ] && echo; echo; echo "$2"; } >>"$1" || warn "can't write $1"
    fi
  else
    say "  create   $1"
    [ "$DRY_RUN" = 0 ] && { printf '%s\n' "$2" >"$1" || warn "can't write $1"; }
  fi
}

# Makes $1 a symlink to AGENTS.md. An existing file that doesn't point there gets the sentence appended instead,
# so the user's own content stays.
link_pointer() { # $1 file
  if [ -L "$1" ] && [ "$(readlink "$1")" = "$AGENTS_MD" ]; then
    say "  ok       $1 -> AGENTS.md"
  elif [ -L "$1" ] && [ ! -e "$1" ]; then
    backup "$1"
    say "  relink   $1 (was a broken link)"
    run ln -sf "$AGENTS_MD" "$1" || warn "can't link $1"
  elif [ -e "$1" ]; then
    append_pointer "$1" "$POINTER_SENTENCE"
  else
    say "  link     $1 -> AGENTS.md"
    run mkdir -p "$(dirname "$1")" && run ln -s "$AGENTS_MD" "$1" || warn "can't link $1"
  fi
}

claude_dirs() {
  for d in "$HOME/.claude" "$HOME/.claude-"* ${CLAUDE_CONFIG_DIR:+"$CLAUDE_CONFIG_DIR"}; do
    [ -d "$d" ] && printf '%s\n' "$d"
  done | sort -u
}

section "AGENTS.md pointers"
found_agent=0
for d in $(claude_dirs); do
  found_agent=1
  append_pointer "$d/CLAUDE.md" "@~/.agents/AGENTS.md"
done
if [ -d "$HOME/.codex" ]; then found_agent=1; append_pointer "$HOME/.codex/AGENTS.md" "$POINTER_SENTENCE"; fi
if [ -d "$HOME/.gemini" ]; then found_agent=1; append_pointer "$HOME/.gemini/GEMINI.md" "@$AGENTS_MD"; fi
if [ -d "$HOME/.config/opencode" ]; then found_agent=1; link_pointer "$HOME/.config/opencode/AGENTS.md"; fi
if [ -d "$HOME/.copilot" ]; then found_agent=1; link_pointer "$HOME/.copilot/copilot-instructions.md"; fi
if [ -d "$HOME/.config/goose" ]; then found_agent=1; link_pointer "$HOME/.config/goose/.goosehints"; fi
if [ -d "$HOME/.continue" ]; then found_agent=1; link_pointer "$HOME/.continue/rules/global-agent-rules.md"; fi
if [ -d "$HOME/.kiro" ]; then found_agent=1; link_pointer "$HOME/.kiro/steering/global-agent-rules.md"; fi
if [ -d "$HOME/.cursor" ]; then
  found_agent=1
  say "  manual   Cursor keeps user rules in its settings, not a file. Paste this into Settings > Rules > User Rules:"
  say "           $POINTER_SENTENCE"
fi
[ "$found_agent" = 0 ] && say "  No agent config folders found. Install an agent, start it once, then re-run this script."

# --- Third-party skills -----------------------------------------------------
# Before linking, so the installed skill folders get linked too.
section "Third-party skills"
tp_args=""
[ "$DRY_RUN" = 1 ] && tp_args="$tp_args --dry-run"
[ "$YES" = 1 ] && tp_args="$tp_args --yes"
# shellcheck disable=SC2086 # tp_args holds only fixed flags
bash "$AGENTS_DIR/bin/fetch-third-party.sh" $tp_args || warn "bin/fetch-third-party.sh didn't install everything; see above"

# --- Skills -----------------------------------------------------------------
section "Skills"
# link-skills.sh only links into skill folders that exist, so create one for each installed agent.
for pair in \
  ".gemini:.gemini/skills" ".cursor:.cursor/skills" ".config/opencode:.config/opencode/skills" \
  ".copilot:.copilot/skills" ".config/goose:.config/goose/skills" ".continue:.continue/skills" ".kiro:.kiro/skills"; do
  agent_dir="$HOME/${pair%%:*}" skills_dir="$HOME/${pair#*:}"
  [ -d "$agent_dir" ] && [ ! -d "$skills_dir" ] && { say "  mkdir    $skills_dir"; run mkdir -p "$skills_dir"; }
done
for d in $(claude_dirs); do
  [ -d "$d/skills" ] || { say "  mkdir    $d/skills"; run mkdir -p "$d/skills"; }
done

if [ "$DRY_RUN" = 1 ]; then
  for dir in "$HOME/.claude/skills" "$HOME"/.claude-*/skills "$HOME/.gemini/skills" "$HOME/.cursor/skills" \
    "$HOME/.config/opencode/skills" "$HOME/.copilot/skills" "$HOME/.config/goose/skills" "$HOME/.continue/skills" \
    "$HOME/.kiro/skills"; do
    [ -d "$dir" ] || continue
    n=0
    for skill in "$AGENTS_DIR"/skills/*/; do
      name=$(basename "$skill")
      [ -f "$skill/SKILL.md" ] || continue
      [ -e "$dir/$name" ] || [ -L "$dir/$name" ] || n=$((n + 1))
    done
    say "  link     up to $n skills into $dir (fewer if a .link-skip file excludes it)"
  done
  say "  Codex reads ~/.agents/skills directly and needs no links."
else
  sh "$AGENTS_DIR/bin/link-skills.sh" | sed 's/^/  /' || warn "link-skills.sh failed"
  say "  Skills linked. Codex reads ~/.agents/skills directly."
fi

# --- Retro hooks ------------------------------------------------------------
if [ "$HOOKS" = 1 ]; then
  section "Retro and guard hooks"
  command -v python3 >/dev/null 2>&1 || die "--hooks needs python3"
  dirs=$(claude_dirs)
  [ -n "$dirs" ] || say "  No Claude Code profile folder found (~/.claude). Start Claude Code once, then re-run."
  for d in $dirs; do
    settings="$d/settings.json"
    python3 -I - "$settings" "$AGENTS_DIR/bin/retro-hook.py" "$DRY_RUN" "$STAMP" "$AGENTS_DIR/bin/guard-polling.sh" <<'PY' || warn "couldn't update $settings"
import json, os, shutil, sys, tempfile

path, hook, dry, stamp, guard = sys.argv[1], sys.argv[2], sys.argv[3] == "1", sys.argv[4], sys.argv[5]
shown = path.replace(os.path.expanduser("~"), "~", 1)
try:
    with open(path) as f:
        data = json.load(f) if os.path.getsize(path) else {}
except FileNotFoundError:
    data = {}
except json.JSONDecodeError as e:
    sys.exit(f"  error: {shown} isn't valid JSON ({e}); fix it and re-run")
if not isinstance(data, dict):
    sys.exit(f"  error: {shown} must hold a JSON object")

# (event, matcher fields, command, text that marks it as already installed)
wanted = [
    ("SessionStart", {"matcher": "startup"}, f"python3 -I {hook} pending", "retro-hook.py pending"),
    ("SessionEnd", {}, f"python3 -I {hook} session-end", "retro-hook.py session-end"),
    # Rejects foreground polling loops and long sleeps, pointing to Monitor or run_in_background.
    ("PreToolUse", {"matcher": "Bash"}, guard, "guard-polling.sh"),
]
hooks = data.setdefault("hooks", {})
added = []
for event, extra, command, marker in wanted:
    entries = hooks.setdefault(event, [])
    if any(marker in json.dumps(e) for e in entries):
        continue
    entries.append({**extra, "hooks": [{"type": "command", "command": command, "timeout": 5}]})
    added.append(event)

if not added:
    print(f"  ok       {shown}")
elif dry:
    print(f"  add      {', '.join(added)} hook to {shown}")
else:
    if os.path.exists(path):
        shutil.copy2(path, f"{path}.bak.{stamp}")
        print(f"  backup   {shown}.bak.{stamp}")
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".", prefix=".settings.", suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)
    print(f"  added    {', '.join(added)} hook to {shown}")
PY
  done
fi

# --- RTK hooks --------------------------------------------------------------
if [ "$RTK" = 1 ]; then
  section "RTK hooks"
  if ! command -v rtk >/dev/null 2>&1; then
    warn "--rtk needs rtk (brew install rtk)"
  else
    say "  run      bin/setup-rtk.sh"
    run sh "$AGENTS_DIR/bin/setup-rtk.sh" || warn "setup-rtk.sh failed; read its output above"
  fi
fi

section "Done"
if [ "$WARNINGS" -gt 0 ]; then
  say "Finished with $WARNINGS warning(s)."
  exit 1
fi
say "Finished."
