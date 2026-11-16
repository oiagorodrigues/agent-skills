#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""Check agent skills against the create-skill authoring rules and the supply-chain
gaps Trail of Bits found in skill registries. Reads files only; no network, no writes.

Usage:
    uv run --no-project --with pyyaml python -I check_skill.py [--json OUT] [--list] [TARGET ...]
    uv run --no-project --with pyyaml python -I check_skill.py --sensitive [--json OUT] FILE_OR_FOLDER ...

TARGET is a skill name (resolved to ~/.agents/skills/NAME, then to a real folder of that name
in ~/.claude/skills or ~/.claude-*/skills), a skill folder, a SKILL.md, or a folder of
skills. With no TARGET it checks every skill in ~/.agents/skills plus the real skill folders in
~/.claude/skills and ~/.claude-*/skills; links back to ~/.agents/skills, synced/ and
hidden folders are skipped. --list prints the resolved skill folders, one per line, and stops.
--sensitive runs only the sensitive-value check, over any files or folders (AGENTS.md, bin/).
Prints a table to stdout. --json OUT also writes the full result as JSON ("-" for stdout,
which then replaces the table). Exits 0 whatever it finds, 2 on bad usage, an unknown target
or missing PyYAML.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print(
        "PyYAML is not installed. Run: uv run --no-project --with pyyaml python -I check_skill.py PATH",
        file=sys.stderr,
    )
    sys.exit(2)

HOME = Path.home()
SKILLS_ROOT = HOME / ".agents" / "skills"
# Agent folders that may hold plugin, synced or built-in skills a skill can name.
# ~/.claude-<profile> folders are extra Claude Code profiles (CLAUDE_CONFIG_DIR); their names vary per machine.
OTHER_SKILL_DIRS = [HOME / ".claude" / "skills", *sorted(HOME.glob(".claude-*/skills"))]

# Limits from Anthropic's skill authoring best practices, as written in create-skill.
NAME_MAX = 64
DESCRIPTION_MAX = 1024
BODY_MAX_LINES = 500
REFERENCE_TOC_LINES = 100
# How far into a reference file a table of contents may start.
TOC_SEARCH_LINES = 40
# Rough token estimate: about 4 characters per token for English prose.
CHARS_PER_TOKEN = 4
# Trail of Bits found padding of hundreds of blank lines used to push payloads past
# what a reviewer scrolls to; 200 is well above any formatting need.
BLANK_RUN_MAX = 200
# Bytes read when sniffing for binary content (a NUL byte means binary).
SNIFF_BYTES = 8192
# Past this offset the "when to use" clause may fall in the part a truncated listing hides.
TRIGGER_LATE_CHARS = 500

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

# Fields Claude Code or claude.ai read; anything else is ignored by every agent.
KNOWN_FIELDS = {
    "name", "description", "disable-model-invocation", "user-invocable", "argument-hint",
    "allowed-tools", "context", "agent", "model", "paths", "license", "compatibility",
    "metadata", "hidden",
}

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp", ".svg", ".pdf",
             ".woff", ".woff2", ".ttf", ".otf"}
BINARY_EXT = {".pyc", ".pyo", ".so", ".dylib", ".dll", ".exe", ".bin", ".class", ".jar",
              ".o", ".a", ".wasm", ".node"}
ARCHIVE_EXT = {".zip", ".docx", ".xlsx", ".pptx", ".tar", ".gz", ".tgz", ".bz2", ".xz",
               ".7z", ".rar", ".whl", ".egg"}
PACKAGE_CONFIGS = {".npmrc", ".yarnrc", ".yarnrc.yml", "pip.conf", "pip.ini", ".pypirc",
                   "bunfig.toml"}
SKIP_DIRS = {".git", "node_modules"}

BAD_OPENERS = re.compile(
    r"^\s*(I\s|I'm\b|I can\b|I will\b|You can\b|You should\b|Use this (skill )?to\b|"
    r"This skill (helps|lets|allows) you\b)",
    re.I,
)
TRIGGER_RE = re.compile(
    r"\b(use|used|load|run|invoke|apply|usar?)\w*(\s+[\w-]+){0,3}?\s+"
    r"(when|whenever|for|before|after|every|only|on|if|quando|sempre)\b|"
    r"\btrigger|\bwhen (the )?(user|asked)\b",
    re.I,
)
MONTHS = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
DATE_RE = re.compile(
    rf"\b(before|after|until|since|as of|prior to|starting)\s+(?:{MONTHS}\s+)?(?:\d{{1,2}},?\s+)?(?:19|20)\d{{2}}\b",
    re.I,
)
CURL_PIPE_RE = re.compile(r"\b(curl|wget)\b[^\n|]*\|\s*(sudo\s+)?(ba|z|da|k)?sh\b", re.I)
NPX_RE = re.compile(r"\bnpx\s+((?:-{1,2}[\w-]+(?:=\S+)?\s+)*)([@\w][\w./@-]*)")
PIP_RE = re.compile(r"\bpip3?\s+install\s+([^\n`|;&]+)")
MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
BACKTICK_RE = re.compile(r"`([^`\s]+)`")
SKILL_REF_RE = re.compile(r"`([a-z0-9][a-z0-9-]*)`\s+skill(?:'s)?\b|\bskill\s+`([a-z0-9][a-z0-9-]*)`")
LOCAL_PREFIXES = ("references/", "scripts/", "assets/", "~/.agents/")
PLACEHOLDER_CHARS = set("<>*{}$|")

# Sensitive values: a skill reads them at run time instead of holding them (create-skill rule).
# A line holding this marker is skipped, for a value that is public on purpose.
SENSITIVE_SKIP_MARKER = "sensitive-ok"
# (category, severity, value pattern, group holding the value, context the line must hold or None).
# High: secrets and AWS accounts. Medium: values that point at a person, a workspace or a host.
SENSITIVE_PATTERNS = [
    ("private-key", "high", re.compile(r"-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----"), 0, None),
    ("token", "high", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), 0, None),
    ("token", "high", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,})"), 0, None),
    ("token", "high", re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}"), 0, None),
    ("token", "high", re.compile(r"hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]+"), 0, None),
    ("token", "high", re.compile(r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{32,}"), 0, None),
    ("token", "high", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"), 0, None),
    ("token", "high", re.compile(r"\b[rs]k_live_[0-9A-Za-z]{16,}"), 0, None),
    ("token", "high", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), 0, None),
    ("token", "high", re.compile(
        r"(?i)\b(?:api[_-]?key|secret|token|password|passwd)\w*['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9/+_.-]{20,})"), 1, None),
    ("aws-arn", "high", re.compile(r"\barn:aws[\w-]*:[\w-]*:[\w-]*:(\d{12}):"), 1, None),
    # A bare 12-digit number is only an account ID when the line talks about AWS.
    ("aws-account", "high", re.compile(r"(?<![\d.:/-])(\d{12})(?![\d.])"), 1,
     re.compile(r"(?i)aws|account|iam|sso|role|profile|amazonaws|ecr")),
    ("email", "medium", re.compile(r"\b([A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,})\b"), 1, None),
    # Slack channel (C), user (U, W) and group (G) IDs; at least one digit keeps out uppercase words.
    ("slack-id", "medium", re.compile(r"\b([CUGW](?=[A-Z]*\d)[A-Z0-9]{8,11})\b"), 1,
     re.compile(r"(?i)slack|channel|<#|<@|member id|user id")),
    # Every hostname; is_placeholder keeps the internal ones (see INTERNAL_HOST_RE).
    ("internal-host", "medium", re.compile(r"(?i)\b((?:[a-z0-9-]+\.)+[a-z]{2,})\b"), 1, None),
]
# Documentation placeholders (AWS docs use 123456789012 and keys ending in EXAMPLE).
PLACEHOLDER_VALUES = re.compile(
    r"(?i)example|placeholder|^(\d)\1+$|^(\d)\2{3}(\d)\3{3}(\d)\4{3}$|123456789012|012345678901|x{4,}|0{6,}"
    r"|your[_-]|redacted|dummy|fake|sample|changeme|insecure")
PLACEHOLDER_DOMAINS = re.compile(r"(?i)(^|\.)(example\.(com|org|net)|acme\.com|[\w-]+\.(example|test|invalid|localhost))$")
# Placeholder people and role inboxes a vendor publishes (support@vendor.com).
PLACEHOLDER_LOCALPARTS = {"user", "you", "your", "name", "me", "someone", "foo", "email", "first.last",
                          "firstname.lastname", "jane", "john", "jdoe", "git", "noreply", "no-reply",
                          "support", "help", "info", "security", "sales", "contact", "hello", "privacy", "abuse"}
# A host is internal when a label after the first names a private zone, or it is an AWS resource
# endpoint with a generated ID (prod-db.c9akciq32.us-east-1.rds.amazonaws.com; sensitive-ok);
# my-db.rds... is a docs placeholder.
INTERNAL_HOST_RE = re.compile(r"(?i)\.(internal|corp|intranet|intra|lan)(\.|$)|\.svc\.cluster\.local$")
AWS_ENDPOINT_RE = re.compile(r"(?i)\.(rds|elb|cache|es|redshift)\.amazonaws\.com$")
PLACEHOLDER_HOST_START = re.compile(r"(?i)^(my|your|new|endpoint|example|sample|test)")
# Mail providers anyone uses; any other domain in the user's git emails is taken as a company domain,
# and hostnames under it as internal.
PUBLIC_MAIL_DOMAINS = {"gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com", "icloud.com",
                       "me.com", "yahoo.com", "proton.me", "protonmail.com", "users.noreply.github.com"}


def finding(sev: str, check: str, file: str, line: int | None, msg: str, evidence: str = "") -> dict[str, Any]:
    f = {"severity": sev, "check": check, "location": f"{file}:{line}" if line else file, "message": msg}
    if evidence:
        f["evidence"] = evidence.strip()[:160]
    return f


def mask(value: str) -> str:
    """Never print a whole sensitive value: the first 4 characters and the length are enough to find it."""
    return f"{value[:4]}... ({len(value)} chars)"


def company_domains() -> set[str]:
    """Domains of the user's work emails, read from ~/.gitconfig and the files it includes."""
    domains: set[str] = set()
    pending, seen = [HOME / ".gitconfig"], set()
    while pending:
        cfg = pending.pop()
        if cfg in seen:
            continue
        seen.add(cfg)
        try:
            text = cfg.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for m in re.finditer(r"(?m)^\s*email\s*=\s*\S+@([\w.-]+)", text):
            if m.group(1).lower() not in PUBLIC_MAIL_DOMAINS:
                domains.add(m.group(1).lower())
        for m in re.finditer(r"(?m)^\s*path\s*=\s*(\S+)", text):
            pending.append(Path(m.group(1)).expanduser())
    return domains


def is_placeholder(category: str, value: str) -> bool:
    if PLACEHOLDER_VALUES.search(value):
        return True
    if category == "email":
        local, _, domain = value.rpartition("@")
        # pkg@1.2.3.js is a pinned package, not a mailbox.
        return (local.lower() in PLACEHOLDER_LOCALPARTS or not domain[0].isalpha()
                or bool(PLACEHOLDER_DOMAINS.search(domain)))
    if category == "internal-host":
        if INTERNAL_HOST_RE.search(value):
            return False
        labels = value.split(".")
        has_id = any(re.fullmatch(r"(?=.*\d)(?=.*[a-z])[a-z0-9]{6,}", lab, re.I) for lab in labels[1:])
        return not (AWS_ENDPOINT_RE.search(value) and has_id and not PLACEHOLDER_HOST_START.match(value))
    if category == "token" and not value.startswith(("-----", "AKIA", "ASIA", "gh", "github_pat", "xox", "hooks",
                                                     "sk-", "AIza", "rk_", "sk_", "eyJ")):
        # The generic key = value pattern: a real secret mixes digits and letters.
        return sum(c.isdigit() for c in value) < 3 or sum(c.isalpha() for c in value) < 3
    return False


def check_sensitive(rel: str, text: str, domains: set[str]) -> list[dict]:
    """Values a skill must read at run time (env, a command, the private skill) instead of holding."""
    out: list[dict] = []
    # The company's own hosts (staging.acme.io) and its tenants on SaaS hosts (acme.atlassian.net).
    company_labels = {d.split(".")[-2] for d in domains if d.count(".") >= 1}
    host_re = re.compile(r"(?i)\b((?:[a-z0-9-]+\.)+[a-z]{2,})\b") if domains else None
    for i, line in enumerate(text.split("\n"), 1):
        if SENSITIVE_SKIP_MARKER in line:
            continue
        seen: set[str] = set()
        for category, sev, pattern, group, context in SENSITIVE_PATTERNS:
            if context is not None and not context.search(line):
                continue
            for m in pattern.finditer(line):
                value = m.group(group)
                if value in seen or is_placeholder(category, value):
                    continue
                seen.add(value)
                out.append(finding(sev, "sensitive", rel, i,
                                   f"{category}: read it at run time or move it to a private skill", mask(value)))
        if host_re:
            for m in host_re.finditer(line):
                value = m.group(1)
                labels = value.lower().split(".")
                if not (any(value.lower().endswith(d) for d in domains) or company_labels & set(labels[:-1])):
                    continue
                if any(value in s for s in seen):
                    continue  # already reported, for example as part of an email
                seen.add(value)
                out.append(finding("medium", "sensitive", rel, i,
                                   "company-host: a hostname of the company in your work email (git config)", mask(value)))
    return out


def tokens(text: str) -> int:
    return round(len(text) / CHARS_PER_TOKEN)


def split_frontmatter(text: str) -> tuple[str | None, int]:
    """Return (frontmatter text, line index where the body starts)."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None, 0
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[1:i]), i + 1
    return None, 0


def field_line(fm_text: str, key: str) -> int:
    for i, line in enumerate(fm_text.split("\n"), 2):
        if line.startswith(f"{key}:"):
            return i
    return 1


def known_skill_names(skill_dir: Path) -> set[str]:
    names: set[str] = set()
    for root in [SKILLS_ROOT, skill_dir.parent, *OTHER_SKILL_DIRS]:
        if not root.is_dir():
            continue
        try:
            for child in root.iterdir():
                names.add(child.name)
                if child.is_dir() and not (child / "SKILL.md").exists():
                    names.update(c.name for c in child.iterdir())
        except OSError:
            continue
    return names


def check_frontmatter(skill_dir: Path, text: str) -> tuple[list[dict], dict[str, Any], int]:
    out: list[dict] = []
    fm_text, body_start = split_frontmatter(text)
    if fm_text is None:
        out.append(finding("high", "frontmatter", "SKILL.md", 1,
                           "No YAML frontmatter: the file must start with '---', the fields, then '---'"))
        return out, {}, 0
    try:
        fm = yaml.safe_load(fm_text)
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        line = mark.line + 2 if mark else 1
        out.append(finding("high", "frontmatter", "SKILL.md", line,
                           f"Frontmatter is not valid YAML ({getattr(e, 'problem', e)}); quote a description that holds ': '"))
        return out, {}, body_start
    if not isinstance(fm, dict):
        out.append(finding("high", "frontmatter", "SKILL.md", 1, "Frontmatter is not a key: value mapping"))
        return out, {}, body_start

    name = fm.get("name")
    nl = field_line(fm_text, "name")
    if not name:
        out.append(finding("high", "name", "SKILL.md", nl, "Missing 'name'"))
    else:
        name = str(name)
        if name != skill_dir.name:
            out.append(finding("high", "name", "SKILL.md", nl, f"name '{name}' differs from folder '{skill_dir.name}'"))
        if len(name) > NAME_MAX:
            out.append(finding("medium", "name", "SKILL.md", nl, f"name is {len(name)} chars, max {NAME_MAX}"))
        if not re.fullmatch(r"[a-z0-9-]+", name):
            out.append(finding("medium", "name", "SKILL.md", nl, "name may only hold lowercase letters, digits and hyphens"))
        if re.search(r"anthropic|claude", name, re.I):
            out.append(finding("medium", "name", "SKILL.md", nl, "name may not contain 'anthropic' or 'claude'"))

    desc = fm.get("description")
    dl = field_line(fm_text, "description")
    if desc is None or (isinstance(desc, str) and not desc.strip()):
        out.append(finding("high", "description", "SKILL.md", dl, "Missing or empty 'description'; the skill can't trigger"))
    elif not isinstance(desc, str):
        out.append(finding("high", "description", "SKILL.md", dl, f"description is a YAML {type(desc).__name__}, not text"))
    else:
        if len(desc) > DESCRIPTION_MAX:
            out.append(finding("medium", "description", "SKILL.md", dl, f"description is {len(desc)} chars, max {DESCRIPTION_MAX}"))
        if "<" in desc or ">" in desc:
            out.append(finding("medium", "description", "SKILL.md", dl, "description holds '<' or '>' (XML tags are not allowed)"))
        if BAD_OPENERS.search(desc):
            out.append(finding("medium", "description", "SKILL.md", dl,
                               "description is not third person; start with what the skill does ('Reviews...')", desc[:60]))
        m = TRIGGER_RE.search(desc)
        if not m:
            out.append(finding("medium", "trigger", "SKILL.md", dl, "description says what but not when to use it"))
        elif m.start() > TRIGGER_LATE_CHARS:
            out.append(finding("low", "trigger", "SKILL.md", dl,
                               f"when-to-use clause starts at char {m.start()}; truncated listings may hide it"))

    for key in fm:
        if key not in KNOWN_FIELDS and key != "hooks":  # scan_skill.py reports hooks
            out.append(finding("low", "frontmatter", "SKILL.md", field_line(fm_text, str(key)),
                               f"Unknown field '{key}' is ignored by every agent"))
    return out, fm, body_start


def is_binary(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            return b"\x00" in fh.read(SNIFF_BYTES)
    except OSError:
        return False


def iter_files(skill_dir: Path):
    stack = [skill_dir]
    while stack:
        d = stack.pop()
        try:
            entries = sorted(d.iterdir())
        except OSError:
            continue
        for p in entries:
            if p.is_symlink():
                continue  # scan_skill.py reports symlinks
            if p.is_dir():
                if p.name not in SKIP_DIRS:
                    stack.append(p)
            elif p.is_file():
                yield p


def check_supply_chain(rel: str, path: Path, text: str | None) -> list[dict]:
    out: list[dict] = []
    name, ext = path.name, path.suffix.lower()
    if ext in BINARY_EXT or "__pycache__" in path.parts:
        out.append(finding("high", "binary", rel, None, "Compiled or binary file; its code can't be reviewed. Remove it"))
    elif ext in ARCHIVE_EXT or name.endswith(".tar.gz"):
        out.append(finding("medium", "archive", rel, None, "Archive or Office file; its contents skip review. Unpack and read it"))
    elif text is None and ext not in IMAGE_EXT:
        out.append(finding("high", "binary", rel, None, "Binary content in a file without a known media type"))
    if name in PACKAGE_CONFIGS:
        out.append(finding("high", "package-config", rel, None,
                           "Package-manager config can redirect installs to another registry"))
    if text is None:
        return out

    blank_run, run_start = 0, 0
    reported: set[str] = set()  # report each unpinned package once per file
    for i, line in enumerate(text.split("\n"), 1):
        if not line.strip():
            if blank_run == 0:
                run_start = i
            blank_run += 1
            if blank_run == BLANK_RUN_MAX + 1:
                out.append(finding("high", "padding", rel, run_start,
                                   f"More than {BLANK_RUN_MAX} blank lines in a row can hide content past the fold"))
            continue
        blank_run = 0
        if CURL_PIPE_RE.search(line):
            out.append(finding("high", "curl-pipe-shell", rel, i, "Downloads and runs a script unread", line))
        for m in NPX_RE.finditer(line):
            pkg = m.group(2)
            if "@" not in pkg[1:] and not set(pkg) & PLACEHOLDER_CHARS and f"npx:{pkg}" not in reported:
                reported.add(f"npx:{pkg}")
                out.append(finding("medium", "unpinned", rel, i, f"npx {pkg} runs whatever version is latest; pin it ({pkg}@x.y.z)", line))
        for m in PIP_RE.finditer(line):
            args = [a for a in m.group(1).split() if not a.startswith("-")]
            loose = [a for a in args if not re.search(r"==|\.whl$|^[./~]|\.txt$|^<", a) and f"pip:{a}" not in reported]
            if loose:
                reported.update(f"pip:{a}" for a in loose)
                out.append(finding("medium", "unpinned", rel, i, f"Unpinned pip install: {' '.join(loose)}", line))
    return out


def resolve_ref(ref: str, base: Path, skill_dir: Path) -> Path | None:
    """Resolve against the file's folder, then each parent up to the skill root, since
    bundled sub-skills link relative to their own root."""
    ref = ref.split("#", 1)[0].rstrip(".,;:)")
    if not ref:
        return base
    if ref.startswith("~/"):
        p = HOME / ref[2:]
        return p if p.exists() else None
    d = base
    while True:
        if (d / ref).exists():
            return d / ref
        if d == skill_dir or skill_dir not in d.parents:
            return None
        d = d.parent


def iter_refs(text: str, top_entries: set[str]):
    """Yield (line number, ref, is markdown link) for local path references outside code fences."""
    in_fence = False
    for i, line in enumerate(text.split("\n"), 1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        if in_fence:
            continue
        candidates = [(m.group(1), True) for m in MD_LINK_RE.finditer(line)]
        candidates += [(m.group(1), False) for m in BACKTICK_RE.finditer(line)]
        for ref, is_link in candidates:
            if re.match(r"^[a-z]+:", ref) or ref.startswith("#") or set(ref) & PLACEHOLDER_CHARS or "..." in ref:
                continue
            if ref.startswith("~/") and not ref.startswith("~/.agents/"):
                continue
            bare = ref[2:] if ref.startswith("./") else ref
            looks_local = bare.startswith(LOCAL_PREFIXES) or bare.split("/", 1)[0] in top_entries
            # A bare folder name in backticks (`scripts/`) names the concept, not a path to open.
            if is_link or (looks_local and not bare.endswith("/") and ("/" in bare or "." in bare)):
                yield i, line, ref


def check_references(skill_dir: Path, md_files: dict[Path, str], skill_names: set[str]) -> list[dict]:
    out: list[dict] = []
    skill_md = skill_dir / "SKILL.md"
    top_entries = {p.name for p in skill_dir.iterdir()}
    resolved_links: dict[Path, set[Path]] = {}
    for path, text in md_files.items():
        rel = str(path.relative_to(skill_dir))
        seen: set[str] = set()
        links: set[Path] = set()
        for i, line, ref in iter_refs(text, top_entries):
            target = resolve_ref(ref, path.parent, skill_dir)
            if target is None:
                if ref not in seen:
                    seen.add(ref)
                    out.append(finding("medium", "broken-ref", rel, i, f"Points to '{ref}', which doesn't exist"))
            elif target.suffix == ".md":
                links.add(target.resolve())
        resolved_links[path.resolve()] = links

        in_fence = False
        for i, line in enumerate(text.split("\n"), 1):
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
            if in_fence:
                continue
            m = DATE_RE.search(line)
            if m:
                out.append(finding("low", "dated", rel, i,
                                   "Time-bound wording goes stale; move it under 'Old patterns' or drop it", m.group(0)))
            for m in SKILL_REF_RE.finditer(line):
                sname = m.group(1) or m.group(2)
                if sname not in skill_names and f"skill:{sname}" not in seen:
                    seen.add(f"skill:{sname}")
                    out.append(finding("low", "broken-ref", rel, i, f"Names the `{sname}` skill, but no skill folder has that name"))

    # One level deep: a file SKILL.md links to should not send the model on to a third file.
    root = skill_dir.resolve()
    level1 = {p for p in resolved_links.get(skill_md.resolve(), set()) if p != skill_md.resolve()}
    for ref_file in sorted(level1):
        deeper = sorted(
            t for t in resolved_links.get(ref_file, set())
            if t.is_relative_to(root) and t not in level1 and t not in (skill_md.resolve(), ref_file)
        )
        if deeper:
            out.append(finding("low", "nested-ref", str(ref_file.relative_to(root)), None,
                               f"Linked from SKILL.md and links on to {len(deeper)} more file(s), e.g. "
                               f"'{deeper[0].relative_to(root)}'; link those from SKILL.md instead"))

    # Table of contents for long reference files (files SKILL.md links to, or under references/).
    for path, text in md_files.items():
        rp = path.resolve()
        if rp == skill_md.resolve() or not (rp in level1 or "references" in path.relative_to(skill_dir).parts):
            continue
        lines = text.split("\n")
        if len(lines) > REFERENCE_TOC_LINES:
            head = "\n".join(lines[:TOC_SEARCH_LINES])
            has_toc = re.search(r"(?im)^#+\s*(table of )?contents\b|^#+\s*toc\b", head) or head.count("](#") >= 3
            if not has_toc:
                out.append(finding("low", "toc", str(path.relative_to(skill_dir)), 1,
                                   f"{len(lines)} lines and no table of contents in the first {TOC_SEARCH_LINES} lines"))
    return out


def private_skill_names() -> set[str]:
    """Skills ~/.agents/.gitignore keeps out of the repo; they are where private values belong."""
    try:
        text = (SKILLS_ROOT.parent / ".gitignore").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return set()
    return set(re.findall(r"(?m)^/?skills/([\w.-]+)/?\s*$", text))


def check_skill(skill_dir: Path, domains: set[str], private: set[str]) -> dict[str, Any]:
    result: dict[str, Any] = {"skill": skill_dir.name, "path": str(skill_dir), "findings": []}
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        result["findings"].append(finding("high", "missing", str(skill_dir), None, "No SKILL.md in this folder"))
        return result
    try:
        text = skill_md.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        result["findings"].append(finding("high", "encoding", "SKILL.md", None, "SKILL.md is not UTF-8 text"))
        return result
    except OSError as e:
        result["findings"].append(finding("high", "missing", "SKILL.md", None, f"Can't read SKILL.md: {e.strerror}"))
        return result

    fm_findings, fm, body_start = check_frontmatter(skill_dir, text)
    result["findings"] += fm_findings
    body_lines = text.split("\n")[body_start:]
    body = "\n".join(body_lines)
    desc = fm.get("description") if isinstance(fm.get("description"), str) else ""
    result["body_lines"] = len(body_lines)
    if len(body_lines) > BODY_MAX_LINES:
        result["findings"].append(finding("high", "size", "SKILL.md", None,
                                          f"Body is {len(body_lines)} lines, max {BODY_MAX_LINES}; move detail to reference files"))

    md_files: dict[Path, str] = {}
    other_chars = 0
    for path in iter_files(skill_dir):
        rel = str(path.relative_to(skill_dir))
        content: str | None = None
        if not is_binary(path):
            try:
                content = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                content = None
        result["findings"] += check_supply_chain(rel, path, content)
        if content is not None and skill_dir.name not in private:
            result["findings"] += check_sensitive(rel, content, domains)
        if content is not None:
            if path.suffix == ".md":
                md_files[path] = content
            if path != skill_md and path.suffix.lower() not in IMAGE_EXT:
                other_chars += len(content)
    result["findings"] += check_references(skill_dir, md_files, known_skill_names(skill_dir))
    result["tokens"] = {"description": tokens(desc), "body": tokens(body), "other_files": round(other_chars / CHARS_PER_TOKEN)}
    result["findings"].sort(key=lambda f: SEVERITY_ORDER.get(f["severity"], 9))
    return result


def agent_skill_dirs() -> list[Path]:
    """Real skill folders in the agent skill folders; links into ~/.agents/skills are duplicates."""
    found = []
    shared = SKILLS_ROOT.resolve()
    for root in OTHER_SKILL_DIRS:
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            if child.name.startswith(".") or not (child / "SKILL.md").is_file():
                continue
            if child.is_symlink() and child.resolve().is_relative_to(shared):
                continue
            found.append(child)
    return found


def default_targets() -> list[Path]:
    shared = sorted(c for c in SKILLS_ROOT.iterdir() if (c / "SKILL.md").is_file()) if SKILLS_ROOT.is_dir() else []
    return shared + agent_skill_dirs()


def looks_like_path(raw: str) -> bool:
    return "/" in raw or raw.startswith(("~", ".")) or raw.endswith(".md")


def resolve_name(name: str) -> Path | None:
    for root in [SKILLS_ROOT, *OTHER_SKILL_DIRS]:
        if (root / name / "SKILL.md").is_file():
            return root / name
    return None


def unknown_name_error(name: str) -> str:
    names = sorted({p.name for p in default_targets()})
    close = difflib.get_close_matches(name, names, n=5, cutoff=0.5)
    close += [n for n in names if name in n and n not in close][:5 - len(close)]
    hint = f" Close matches: {', '.join(close)}." if close else ""
    roots = ", ".join(str(r) for r in [SKILLS_ROOT, *OTHER_SKILL_DIRS])
    return f"{name}: no skill with that name in {roots}.{hint}"


def discover(targets: list[str]) -> tuple[list[Path], list[str]]:
    if not targets:
        return default_targets(), []
    skills, errors = [], []
    for raw in targets:
        if not looks_like_path(raw):
            named = resolve_name(raw)
            if named:
                skills.append(named)
                continue
            if not Path(raw).exists():
                errors.append(unknown_name_error(raw))
                continue
        p = Path(raw).expanduser()
        if not p.exists():
            errors.append(f"{raw}: no such file or folder")
        elif p.is_file():
            if p.name == "SKILL.md":
                skills.append(p.parent)
            else:
                errors.append(f"{raw}: is a file but not a SKILL.md; pass the skill folder")
        elif (p / "SKILL.md").exists():
            skills.append(p)
        else:
            found = sorted(c for c in p.iterdir() if c.is_dir() and (c / "SKILL.md").exists())
            if found:
                skills += found
            else:
                errors.append(f"{raw}: holds no SKILL.md and no skill folders")
    return skills, errors


def print_table(results: list[dict], errors: list[str]) -> None:
    print(f"{'skill':32} {'lines':>5} {'desc_tok':>8} {'body_tok':>8} {'files_tok':>9}  crit high med low")
    for r in results:
        c = {s: 0 for s in SEVERITY_ORDER}
        for f in r["findings"]:
            c[f["severity"]] = c.get(f["severity"], 0) + 1
        t = r.get("tokens", {})
        print(f"{r['skill'][:32]:32} {r.get('body_lines', 0):>5} {t.get('description', 0):>8} {t.get('body', 0):>8} "
              f"{t.get('other_files', 0):>9}  {c['critical']:>4} {c['high']:>4} {c['medium']:>3} {c['low']:>3}")
    for r in results:
        if r["findings"]:
            print(f"\n## {r['skill']}")
            for f in r["findings"]:
                ev = f"  [{f['evidence']}]" if f.get("evidence") else ""
                print(f"  {f['severity']:6} {f['check']:15} {f['location']}  {f['message']}{ev}")
    for e in errors:
        print(f"\nerror: {e}")


def sensitive_only(targets: list[str], json_out: str | None) -> int:
    """Sensitive-value check over any files or folders, for instruction files and scripts outside skills."""
    if not targets:
        print("error: --sensitive needs at least one file or folder", file=sys.stderr)
        return 2
    domains = company_domains()
    results, errors = [], []
    for raw in targets:
        p = Path(raw).expanduser()
        if not p.exists():
            errors.append(f"{raw}: no such file or folder")
            continue
        files = [p] if p.is_file() else list(iter_files(p))
        findings: list[dict] = []
        for f in files:
            if is_binary(f):
                continue
            try:
                text = f.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            findings += check_sensitive(str(f.relative_to(p)) if p.is_dir() else f.name, text, domains)
        results.append({"skill": str(p), "path": str(p), "findings": findings})
    if errors:
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        return 2
    total = sum(len(r["findings"]) for r in results)
    if json_out:
        data = json.dumps({"targets": results, "findings": total}, indent=2)
        if json_out == "-":
            print(data)
            return 0
        try:
            Path(json_out).write_text(data, encoding="utf-8")
        except OSError as e:
            print(f"Can't write {json_out}: {e.strerror}", file=sys.stderr)
            return 2
    for r in results:
        if r["findings"]:
            print(f"## {r['path']}")
            for f in r["findings"]:
                print(f"  {f['severity']:6} {f['location']}  {f['message']}  [{f['evidence']}]")
    print(f"\n{len(results)} targets, {total} sensitive findings")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Check agent skills against the create-skill rules.")
    ap.add_argument("targets", nargs="*", metavar="TARGET",
                    help="skill name, skill folder, SKILL.md, or folder of skills (default: every skill)")
    ap.add_argument("--json", metavar="OUT", help="also write JSON to OUT ('-' for stdout instead of the table)")
    ap.add_argument("--list", action="store_true", help="print the resolved skill folders and stop")
    ap.add_argument("--sensitive", action="store_true",
                    help="only look for sensitive values; TARGET may then be any file or folder")
    args = ap.parse_args()
    if args.sensitive:
        return sensitive_only(args.targets, args.json)

    skills, errors = discover(args.targets)
    if errors:
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        return 2
    if not skills:
        print(f"error: no skills found in {SKILLS_ROOT}", file=sys.stderr)
        return 2
    if args.list:
        print("\n".join(str(s) for s in skills))
        return 0
    domains, private = company_domains(), private_skill_names()
    results = [check_skill(s, domains, private) for s in skills]
    summary: dict[str, int] = {s: 0 for s in SEVERITY_ORDER}
    for r in results:
        for f in r["findings"]:
            summary[f["severity"]] = summary.get(f["severity"], 0) + 1
    data = {"skills_checked": len(results), "findings_by_severity": summary, "errors": errors, "skills": results}

    if args.json == "-":
        print(json.dumps(data, indent=2))
        return 0
    if args.json:
        try:
            Path(args.json).write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError as e:
            print(f"Can't write {args.json}: {e.strerror}", file=sys.stderr)
            return 2
    print_table(results, errors)
    print(f"\n{len(results)} skills, findings: " + ", ".join(f"{k} {v}" for k, v in summary.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
