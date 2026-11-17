#!/usr/bin/env bash
# Installs each line of third-party.tsv from its upstream git repo at the pinned commit.
# Nothing from the download is run. Safe to re-run: a path that still matches its recorded install is skipped.
set -u

usage() {
  cat <<'EOF'
Usage: bin/fetch-third-party.sh [--dry-run] [--yes]

Installs the third-party files listed in third-party.tsv at their pinned commits, and records each
install in .third-party-state/. A path that already matches its recorded install is left alone.
A path whose files differ from both the recorded install and the pinned commit (local edits) is
listed and skipped.

  --dry-run   Print what would change and change nothing.
  --yes, -y   Overwrite paths with local edits.
  -h, --help  Show this help.
EOF
}

DRY_RUN=0 YES=0
for arg in "$@"; do
  case "$arg" in
  --dry-run) DRY_RUN=1 ;;
  --yes | -y) YES=1 ;;
  -h | --help) usage; exit 0 ;;
  *) echo "error: unknown option '$arg'" >&2; usage >&2; exit 2 ;;
  esac
done

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P) || exit 1
manifest="$repo_dir/third-party.tsv"
state_dir="$repo_dir/.third-party-state"
WARNINGS=0

say() { printf '  %s\n' "$*"; }
warn() { printf '  warning: %s\n' "$*" >&2; WARNINGS=$((WARNINGS + 1)); }

[ -f "$manifest" ] || { echo "error: $manifest is missing" >&2; exit 1; }
command -v git >/dev/null 2>&1 || { echo "error: git is required" >&2; exit 1; }
work=$(mktemp -d "${TMPDIR:-/tmp}/third-party.XXXXXX") || exit 1
trap 'rm -rf "$work"' EXIT

# One "blob-hash<TAB>relative path" line per file, sorted; empty when $1 is missing.
listing() { # $1 file or folder
  if [ -f "$1" ]; then
    printf '%s\t.\n' "$(git hash-object --no-filters "$1")"
  elif [ -d "$1" ]; then
    # Absolute paths, because git hash-object reads --stdin-paths from the top of any repo around the cwd.
    find "$1" -type f ! -name .DS_Store | LC_ALL=C sort >"$work/paths"
    git hash-object --no-filters --stdin-paths <"$work/paths" |
      paste - "$work/paths" | awk -F'\t' -v n="${#1}" '{ print $1 "\t" substr($2, n + 2) }'
  fi
}

# Prints "~ path" (content differs), "+ path" (only in $1) and "- path" (only in $2) for two listings.
compare() { # $1 listing file, $2 listing file
  awk -F'\t' 'NR == FNR { a[$2] = $1; next }
    { if (!($2 in a)) print "- " $2; else if (a[$2] != $1) print "~ " $2; delete a[$2] }
    END { for (p in a) print "+ " p }' "$1" "$2" | LC_ALL=C sort -k2
}

# Clones the repo once per url and commit (trees only, blobs on demand) and prints the clone's folder.
fetch() { # $1 url, $2 commit
  local dir
  dir="$work/$(printf '%s' "$1" | git hash-object --stdin | cut -c1-12)"
  if [ ! -d "$dir" ]; then
    git clone -q --filter=blob:none --no-checkout "$1" "$dir" || return 1
  fi
  if ! git -C "$dir" cat-file -e "$2^{commit}" 2>/dev/null; then
    git -C "$dir" fetch -q --filter=blob:none origin "$2" || return 1
  fi
  [ "$(git -C "$dir" rev-parse --verify -q "$2^{commit}")" = "$2" ] || return 1
  printf '%s' "$dir"
}

record() { # uses the loop's header, state and local_path
  mkdir -p "$state_dir" && { echo "$header"; cat "$work/upstream"; } >"$state" ||
    warn "can't record $local_path in $state_dir"
}

n=0
while IFS="$(printf '\t')" read -r local_path url commit upstream_path license <&3; do
  case "$local_path" in '' | '#'*) continue ;; esac
  n=$((n + 1))
  if [ -z "$license" ] || ! printf '%s' "$commit" | grep -Eq '^[0-9a-f]{40}$'; then
    warn "third-party.tsv line for '$local_path' needs 5 tab-separated fields and a full commit SHA; skipped"
    continue
  fi
  case "/$local_path/$upstream_path/" in
  *'/../'* | *'//'*) warn "'$local_path' or '$upstream_path' leaves its folder; skipped"; continue ;;
  esac

  dest="$repo_dir/$local_path"
  short="${commit:0:7}"
  state="$state_dir/$(printf '%s' "$local_path" | tr '/' '%').tsv"
  header="# $url $commit $upstream_path"
  listing "$dest" >"$work/current"
  : >"$work/recorded"
  if [ -f "$state" ]; then tail -n +2 "$state" >"$work/recorded"; fi

  if [ -s "$work/current" ] && [ -f "$state" ] && [ "$(head -1 "$state")" = "$header" ] &&
    cmp -s "$work/current" "$work/recorded"; then
    say "ok       $local_path ($short)"
    continue
  fi
  if [ ! -s "$work/current" ] && [ "$DRY_RUN" = 1 ]; then
    say "install  $local_path from $url at $short"
    continue
  fi

  dir=$(fetch "$url" "$commit") || { warn "can't fetch $commit from $url; $local_path unchanged"; continue; }
  # One batched fetch of the blobs; a path checkout alone fetches them one request at a time.
  if ! git -C "$dir" cat-file -e "$commit:$upstream_path" 2>/dev/null ||
    ! git -C "$dir" ls-tree -r "$commit" -- "$upstream_path" | awk '$2 == "blob" { print $3 }' |
    git -C "$dir" -c fetch.negotiationAlgorithm=noop fetch -q --no-tags --no-write-fetch-head \
      --filter=blob:none origin --stdin ||
    ! git -C "$dir" checkout -q "$commit" -- "$upstream_path"; then
    warn "$upstream_path isn't in $url at $short; $local_path unchanged"
    continue
  fi
  listing "$dir/$upstream_path" >"$work/upstream"

  if cmp -s "$work/current" "$work/upstream"; then
    if [ "$DRY_RUN" = 1 ]; then
      say "ok       $local_path already matches $short"
    else
      say "ok       $local_path already matches $short; recorded"
      record
    fi
    continue
  elif [ -s "$work/current" ] && ! cmp -s "$work/current" "$work/recorded"; then
    say "changed  $local_path differs from $short (~ changed, + only local, - only upstream):"
    compare "$work/current" "$work/upstream" | sed 's/^/           /'
    if [ "$YES" = 0 ]; then
      warn "$local_path has local changes; left as it is. Re-run with --yes to replace it with $short"
      continue
    fi
    say "replace  $local_path with $short (--yes)"
  else
    say "install  $local_path from $url at $short"
  fi
  [ "$DRY_RUN" = 1 ] && continue

  rm -rf "$dest" && mkdir -p "$(dirname "$dest")" && cp -R "$dir/$upstream_path" "$dest" ||
    { warn "can't copy $upstream_path to $local_path"; continue; }
  record
done 3<"$manifest"

[ "$n" -gt 0 ] || say "third-party.tsv lists nothing to install."
[ "$WARNINGS" = 0 ] || exit 1
