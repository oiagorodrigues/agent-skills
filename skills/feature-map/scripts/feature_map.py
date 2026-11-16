#!/usr/bin/env python3
"""Check, stamp and render a feature map (map.yaml) whose facts point at code.

Usage (needs PyYAML; git on the PATH; run from anywhere inside the repo):
    uv run --no-project --with pyyaml python feature_map.py check  [--map PATH]
    uv run --no-project --with pyyaml python feature_map.py stamp  ID [ID ...] [--map PATH]
    uv run --no-project --with pyyaml python feature_map.py render [--map PATH]

check   compares each fact's lines in the working tree with the same lines at the commit
        in its `verified` field. Prints one line per fact that needs attention and a count
        line. Exits 1 when any fact is changed, missing, ambiguous or unverified.
stamp   sets `verified` to HEAD for the given fact ids, after you have read their code.
        Refuses a fact whose lines have uncommitted edits. Rewrites map.yaml, so comments
        in it are lost.
render  writes README.md next to map.yaml. With a `diagram` block it also writes
        feature-map.json and, when the system-design renderer is installed, feature-map.svg.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML is missing. Run: uv run --no-project --with pyyaml python feature_map.py ...", file=sys.stderr)
    sys.exit(2)

DEFAULT_MAP = "docs/feature-map/map.yaml"
KINDS = ("entry", "step", "data", "call", "control", "command")
KIND_TITLES = {
    "entry": "Entry points",
    "step": "Flow",
    "data": "Data",
    "call": "Calls to other systems",
    "control": "Controls",
    "command": "Run and inspect",
}
RENDERER = Path.home() / ".agents/skills/system-design/topics/architecture-diagram/scripts/render_diagram.py"


def fail(msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(2)


def git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)


def repo_root(start: Path) -> Path:
    out = git(start, "rev-parse", "--show-toplevel")
    if out.returncode != 0:
        fail(f"{start} is not inside a git work tree: {out.stderr.strip()}")
    return Path(out.stdout.strip())


def find_map(arg: str | None) -> Path:
    if arg:
        path = Path(arg).resolve()
    else:
        path = repo_root(Path.cwd()) / DEFAULT_MAP
    if not path.is_file():
        fail(f"No map at {path}. Pass --map PATH or create {DEFAULT_MAP} first.")
    return path


def load(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        fail(f"{path} is not valid YAML: {exc}")
    errors = []
    if not isinstance(data.get("features"), list) or not data["features"]:
        errors.append("`features` must be a non-empty list")
    feature_ids, fact_ids = set(), set()
    for feature in data.get("features") or []:
        fid = feature.get("id")
        if not fid or fid in feature_ids:
            errors.append(f"feature {fid!r}: missing or duplicate id")
        feature_ids.add(fid)
        for k in ("name", "summary"):
            if not feature.get(k):
                errors.append(f"feature {fid}: missing `{k}`")
        for fact in feature.get("facts") or []:
            xid = fact.get("id")
            if not xid or xid in fact_ids:
                errors.append(f"feature {fid}: fact {xid!r} has a missing or duplicate id")
            fact_ids.add(xid)
            if fact.get("kind") not in KINDS:
                errors.append(f"fact {xid}: kind must be one of {', '.join(KINDS)}")
            if not fact.get("claim"):
                errors.append(f"fact {xid}: missing `claim`")
            if bool(fact.get("source")) == bool(fact.get("url")):
                errors.append(f"fact {xid}: needs exactly one of `source` or `url`")
            src = fact.get("source")
            if src and not (src.get("path") and src.get("anchor")):
                errors.append(f"fact {xid}: `source` needs `path` and `anchor`")
            if src and not (isinstance(src.get("lines", 1), int) and src.get("lines", 1) >= 1):
                errors.append(f"fact {xid}: `source.lines` must be a whole number of 1 or more")
            if fact.get("kind") == "command" and not fact.get("command"):
                errors.append(f"fact {xid}: kind `command` needs a `command` field")
    if errors:
        fail(f"{path} has {len(errors)} problem(s):\n  " + "\n  ".join(errors))
    return data


def facts(data: dict):
    for feature in data["features"]:
        for fact in feature.get("facts") or []:
            yield feature, fact


def span(text: str, anchor: str, lines: int) -> tuple[str, int | None, int]:
    """Return (status, first line number, match count) for the anchor in text."""
    rows = text.splitlines()
    hits = [i for i, row in enumerate(rows) if anchor in row]
    if not hits:
        return "missing", None, 0
    if len(hits) > 1:
        return "ambiguous", None, len(hits)
    return "\n".join(rows[hits[0]: hits[0] + lines]), hits[0] + 1, 1


def current_span(root: Path, src: dict):
    file = root / src["path"]
    if not file.is_file():
        return "missing", None
    text, first, count = span(file.read_text(encoding="utf-8", errors="replace"), src["anchor"], src.get("lines", 1))
    if first is None:
        return text, count
    return "ok", (text, first)


def span_at(root: Path, sha: str, src: dict, with_line: bool = False):
    out = git(root, "show", f"{sha}:{src['path']}")
    if out.returncode != 0:
        return None
    text, first, _ = span(out.stdout, src["anchor"], src.get("lines", 1))
    if first is None:
        return None
    return (text, first) if with_line else text


def fact_status(root: Path, fact: dict) -> tuple[str, str]:
    src = fact["source"]
    status, found = current_span(root, src)
    if status == "missing":
        return "missing", f"anchor {src['anchor']!r} not found in {src['path']}"
    if status == "ambiguous":
        return "ambiguous", f"anchor {src['anchor']!r} matches {found} lines in {src['path']}"
    if not fact.get("verified"):
        return "unverified", "no `verified` commit"
    old = span_at(root, fact["verified"], src)
    if old is None:
        return "changed", f"{src['path']} or its anchor is not at {fact['verified'][:10]}"
    if old != found[0]:
        return "changed", f"lines differ from {fact['verified'][:10]}"
    return "ok", ""


def cmd_check(args) -> int:
    path = find_map(args.map)
    data, root = load(path), repo_root(path.parent)
    counts: dict[str, int] = {}
    for feature, fact in facts(data):
        if fact.get("url"):
            counts["url"] = counts.get("url", 0) + 1
            continue
        status, why = fact_status(root, fact)
        counts[status] = counts.get(status, 0) + 1
        if status != "ok":
            print(f"{status:<10} {feature['id']}/{fact['id']}: {why}")
    print(", ".join(f"{n} {s}" for s, n in sorted(counts.items())))
    return 1 if set(counts) - {"ok", "url"} else 0


def cmd_stamp(args) -> int:
    path = find_map(args.map)
    data, root = load(path), repo_root(path.parent)
    head = git(root, "rev-parse", "HEAD").stdout.strip()
    by_id = {fact["id"]: fact for _, fact in facts(data)}
    unknown = [i for i in args.ids if i not in by_id]
    if unknown:
        fail(f"Unknown fact id(s): {', '.join(unknown)}. Valid ids: {', '.join(sorted(by_id))}")
    problems = []
    for xid in args.ids:
        fact = by_id[xid]
        if not fact.get("source"):
            problems.append(f"{xid}: a `url` fact has nothing to stamp")
            continue
        status, found = current_span(root, fact["source"])
        if status != "ok":
            problems.append(f"{xid}: anchor is {status}; fix `source` first")
        elif span_at(root, head, fact["source"]) != found[0]:
            problems.append(f"{xid}: its lines have uncommitted edits; commit them, then stamp")
        else:
            fact["verified"] = head
    if problems:
        fail("Nothing stamped:\n  " + "\n  ".join(problems))
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=1000), encoding="utf-8")
    print(f"stamped {len(args.ids)} fact(s) at {head[:10]}")
    return 0


def link(data: dict, root: Path, out_dir: Path, fact: dict) -> str:
    if fact.get("url"):
        return f"[source]({fact['url']})"
    src = fact["source"]
    status, found = current_span(root, src)
    if status != "ok":
        return f"`{src['path']}` (anchor {status})"
    first = found[1]
    repo = (data.get("repo") or "").rstrip("/")
    pinned = span_at(root, fact["verified"], src, with_line=True) if repo and fact.get("verified") else None
    if pinned:
        first = pinned[1]  # the permalink shows the verified commit, so use its line numbers
    last = first + src.get("lines", 1) - 1
    label = f"{src['path']}:{first}" + (f"-{last}" if last > first else "")
    if pinned:
        return f"[{label}]({repo}/blob/{fact['verified']}/{src['path']}#L{first}-L{last})"
    rel = os.path.relpath(root / src["path"], out_dir).replace(os.sep, "/")
    return f"[{label}]({rel}#L{first})"


def cmd_render(args) -> int:
    path = find_map(args.map)
    data, root = load(path), repo_root(path.parent)
    out_dir = path.parent
    title = data.get("title") or "Feature map"
    lines = [f"# {title}", "", "Generated from map.yaml by feature_map.py render. Edit map.yaml, then render again.", ""]
    if data.get("intro"):
        lines += [data["intro"].strip(), ""]
    svg_note = None
    if data.get("diagram"):
        spec = {"title": title, **data["diagram"]}
        (out_dir / "feature-map.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")
        if RENDERER.is_file():
            res = subprocess.run([sys.executable, str(RENDERER), str(out_dir / "feature-map.json"),
                                  "-o", str(out_dir / "feature-map.svg")], capture_output=True, text=True)
            if res.returncode != 0:
                fail(f"render_diagram.py failed:\n{res.stderr or res.stdout}")
            svg_note = (res.stderr or res.stdout).strip() or None
        else:
            svg_note = f"feature-map.svg not refreshed: {RENDERER} not found. feature-map.json holds the spec."
        lines += [f"![{title}](feature-map.svg)", ""]
    lines += ["## Features", ""]
    lines += [f"- [{f['name']}](#{f['id']}): {f['summary']}" for f in data["features"]]
    lines.append("")
    for feature in data["features"]:
        lines += [f'<a id="{feature["id"]}"></a>', f"## {feature['name']}", "", feature["summary"], ""]
        for url in feature.get("docs") or []:
            lines.append(f"- Doc: {url}")
        if feature.get("docs"):
            lines.append("")
        for kind in KINDS:
            group = [f for f in feature.get("facts") or [] if f["kind"] == kind]
            if not group:
                continue
            lines += [f"### {KIND_TITLES[kind]}", ""]
            for fact in group:
                cmd = f"`{fact['command']}`: " if fact.get("command") else ""
                lines.append(f"- {cmd}{fact['claim']} ({link(data, root, out_dir, fact)})")
            lines.append("")
    (out_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out_dir / 'README.md'}")
    if svg_note:
        print(svg_note, file=sys.stderr)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("check", "stamp", "render"):
        p = sub.add_parser(name)
        p.add_argument("--map", help=f"path to map.yaml (default: <repo root>/{DEFAULT_MAP})")
        if name == "stamp":
            p.add_argument("ids", nargs="+", help="fact ids to mark verified at HEAD")
    args = ap.parse_args()
    return {"check": cmd_check, "stamp": cmd_stamp, "render": cmd_render}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
