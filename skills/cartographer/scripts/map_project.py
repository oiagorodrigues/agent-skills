#!/usr/bin/env python3
"""
Phase 1: Build a dependency graph + call graph + class model for a codebase.

Walks the project, lists every text file in an inventory (language, size, lines), parses the languages
it has parsers for (Python AST; JS/TS, Vue <script> blocks, Go, Ruby, Java, Kotlin, Rust, PHP, CSS/SCSS/Less
and HTML by regex), and extracts:
  - file -> file edges (via imports)
  - function/class definitions with one-line headers
  - **call edges** (function -> function), Python AST-precise, JS/TS regex
  - **class hierarchy** (class -> base classes, fields, methods)
  - API endpoint declarations (FastAPI, Flask, Express, Next.js, etc.)
  - external integration markers (Supabase, Telegram, OpenAI, scientific Python, ...)

Outputs project-map.json, plus project-map.svg and class_diagram.svg (Graphviz; .dot sources alongside).

Designed to be dependency-light. Optional deps: pathspec.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
from bisect import bisect_right
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

try:
    import pathspec  # type: ignore
    HAS_PATHSPEC = True
except ImportError:
    HAS_PATHSPEC = False

# progress heartbeat (no-op if file unwritable)
sys.path.insert(0, str(Path(__file__).parent))
from _diagrams import dot_quote, render_dot
from _languages import is_binary, language_for

try:
    import _progress
except Exception:
    class _progress:  # type: ignore
        @staticmethod
        def start(*a, **k): pass
        @staticmethod
        def update(*a, **k): pass
        @staticmethod
        def done(*a, **k): pass


# ---------- file walking ----------

DEFAULT_IGNORES = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", ".cartographer",
    "dist", "build", ".next", ".turbo", "coverage", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "target", ".idea", ".vscode",
    "vendor", "bower_components", ".gradle", ".terraform", ".nuxt", ".svelte-kit", ".tox", ".output",
}

# Extensions with an import parser. Their files join the dependency graph and the segments; every other
# text file only goes to the inventory.
SUPPORTED_EXT = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".go",
    ".vue", ".rb", ".rake", ".java", ".kt", ".kts", ".rs", ".php",
    ".css", ".scss", ".sass", ".less", ".html", ".htm",
}
GIT_LS_TIMEOUT_SECONDS = 120


def load_gitignore(root: Path):
    if not HAS_PATHSPEC:
        return None
    gi = root / ".gitignore"
    if not gi.exists():
        return None
    with open(gi) as f:
        return pathspec.PathSpec.from_lines("gitwildmatch", f)


def iter_source_files(root: Path):
    spec = load_gitignore(root)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in DEFAULT_IGNORES]
        for fn in filenames:
            ext = Path(fn).suffix.lower()
            if ext not in SUPPORTED_EXT:
                continue
            full = Path(dirpath) / fn
            rel = full.relative_to(root)
            if spec and spec.match_file(str(rel)):
                continue
            yield full, rel


def _git_listed_files(root: Path) -> list[str] | None:
    """Tracked plus untracked-but-not-ignored files, so every nested .gitignore applies. None outside git."""
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            capture_output=True, timeout=GIT_LS_TIMEOUT_SECONDS)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    return sorted({p for p in out.stdout.decode("utf-8", "replace").split("\0") if p})


def iter_project_files(root: Path):
    """Every file in the project, minus .gitignore matches and DEFAULT_IGNORES directories."""
    listed = _git_listed_files(root)
    if listed is None:
        spec = load_gitignore(root)
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in DEFAULT_IGNORES]
            for fn in filenames:
                full = Path(dirpath) / fn
                rel = full.relative_to(root)
                if spec and spec.match_file(str(rel)):
                    continue
                yield full, rel
        return
    for rel_str in listed:
        rel = Path(rel_str)
        if any(part in DEFAULT_IGNORES for part in rel.parts[:-1]):
            continue
        full = root / rel
        # Deleted-but-tracked files and submodule entries are not regular files.
        if not full.is_file():
            continue
        yield full, rel


# ---------- integration detectors ----------

INTEGRATIONS = {
    "supabase":     [r"\bsupabase\b", r"@supabase/", r"createClient\("],
    "telegram":     [r"python-telegram-bot", r"telegraf", r"node-telegram-bot-api",
                     r"\btelegram\b", r"\bbot\.send_message\b", r"\bTelegramBot\b"],
    "vercel":       [r"@vercel/", r"vercel\.json", r"\bvercel\b"],
    "railway":      [r"railway\.json", r"\brailway\b"],
    "openai":       [r"\bopenai\b", r"OpenAI\(", r"openai\.ChatCompletion"],
    "anthropic":    [r"\banthropic\b", r"Anthropic\(", r"claude-3", r"claude-sonnet",
                     r"claude-opus"],
    "google_api":   [r"google-cloud", r"googleapis", r"google\.cloud"],
    "aws":          [r"\bboto3\b", r"@aws-sdk/", r"\baws-sdk\b"],
    "stripe":       [r"\bstripe\b", r"Stripe\("],
    "redis":        [r"\bredis\b", r"ioredis"],
    "postgres":     [r"\bpsycopg\b", r"\basyncpg\b", r"pg-promise", r"\bpg\b"],
    "mongo":        [r"\bpymongo\b", r"mongoose", r"\bMongoClient\b"],
    "queue":        [r"\bcelery\b", r"\brq\b", r"\bbullmq\b", r"\brabbitmq\b",
                     r"\bkafka\b"],
    "websocket":    [r"\bwebsocket\b", r"\bwebsockets\b", r"socket\.io"],
    "sqlalchemy":   [r"\bsqlalchemy\b"],
    "prisma":       [r"@prisma/client", r"\bprisma\b"],
    # scientific / data-science Python
    "pandas":       [r"\bimport pandas\b", r"\bfrom pandas\b", r"\bpd\."],
    "numpy":        [r"\bimport numpy\b", r"\bfrom numpy\b", r"\bnp\.\w"],
    "scipy":        [r"\bimport scipy\b", r"\bfrom scipy\b"],
    "sklearn":      [r"\bsklearn\b", r"scikit-learn"],
    "yfinance":     [r"\byfinance\b"],
    "pyarrow":      [r"\bpyarrow\b", r"\.parquet\b"],
    "matplotlib":   [r"\bmatplotlib\b", r"\bplt\."],
    "seaborn":      [r"\bseaborn\b", r"\bsns\."],
    "torch":        [r"\bimport torch\b", r"\bfrom torch\b"],
    "tensorflow":   [r"\bimport tensorflow\b", r"\bfrom tensorflow\b"],
    "huggingface":  [r"\bhuggingface\b", r"\btransformers\b", r"\bdatasets\b"],
    # fastapi / flask explicit (lets the matcher boost backend-api specialists)
    "fastapi":      [r"\bfrom fastapi\b", r"\bimport fastapi\b", r"\bFastAPI\("],
    "flask":        [r"\bfrom flask\b", r"\bimport flask\b", r"\bFlask\("],
    "express":      [r"\bexpress\b", r"\brequire\(['\"]express['\"]\)"],
    "react":        [r"\bfrom ['\"]react['\"]", r"\breact-dom\b"],
    "nextjs":       [r"\bnext/router\b", r"\bnext/navigation\b", r"\bnext/server\b",
                     r"\bnext\.config\b"],
    # mobile
    "react_native": [r"\bfrom ['\"]react-native['\"]", r"\b@react-native\b"],
    "expo":         [r"\bfrom ['\"]expo[-/]", r"\bexpo-modules\b", r"\bexpo-router\b"],
    "flutter":      [r"\bimport 'package:flutter/", r"\bflutter:\s*sdk:"],
    "ionic":        [r"\b@ionic/", r"\bionic-native\b"],
    "capacitor":    [r"\b@capacitor/"],
    # cli frameworks
    "click":        [r"\bimport click\b", r"\bfrom click\b", r"@click\.command"],
    "typer":        [r"\bimport typer\b", r"\bfrom typer\b", r"\btyper\.Typer\("],
    "argparse":     [r"\bimport argparse\b", r"\bargparse\.ArgumentParser\b"],
    "cobra":        [r"github\.com/spf13/cobra"],
    "commander":    [r"\bfrom ['\"]commander['\"]", r"\brequire\(['\"]commander['\"]\)"],
    "yargs":        [r"\bfrom ['\"]yargs['\"]", r"\brequire\(['\"]yargs['\"]\)"],
    "clap":         [r"\buse clap::"],
    "oclif":        [r"\b@oclif/"],
    # test frameworks
    "pytest":       [r"\bimport pytest\b", r"\bfrom pytest\b", r"@pytest\."],
    "unittest":     [r"\bimport unittest\b", r"\bunittest\.TestCase\b"],
    "jest":         [r"\b@jest/", r"\bjest\.(?:fn|mock|spyOn)\("],
    "vitest":       [r"\bfrom ['\"]vitest['\"]", r"\bvi\.(?:fn|mock|spyOn)\("],
    "mocha":        [r"\bfrom ['\"]mocha['\"]", r"\brequire\(['\"]mocha['\"]\)"],
    "playwright":   [r"\b@playwright/", r"\bplaywright/test\b"],
    "cypress":      [r"\bcypress\b", r"\bcy\.\w"],
    "testing_library": [r"\b@testing-library/"],
    "hypothesis":   [r"\bfrom hypothesis\b", r"@given\("],
    # filesystem stays but is demoted (segmenter ignores it as primary marker)
    "filesystem":   [r"\bos\.path\b", r"\bpathlib\b", r"fs\.readFile", r"fs/promises"],
}

INTEGRATION_PATTERNS = {
    label: [re.compile(p, re.IGNORECASE) for p in patterns]
    for label, patterns in INTEGRATIONS.items()
}

# Vitest copies Jest's describe('...')/test('...') API, so these calls name the
# project's runner (see project_test_runner), not a fixed one.
JEST_STYLE_API_PATTERNS = [re.compile(r"\bdescribe\(\s*['\"]"), re.compile(r"\btest\(\s*['\"]")]
_TEST_RUNNER_BY_ROOT: dict[str, str] = {}


def project_test_runner(root: str) -> str:
    """'vitest' when the root package.json depends on vitest and not on jest, else 'jest'."""
    if root not in _TEST_RUNNER_BY_ROOT:
        try:
            pkg = json.loads((Path(root) / "package.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pkg = {}
        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        _TEST_RUNNER_BY_ROOT[root] = "vitest" if "vitest" in deps and "jest" not in deps else "jest"
    return _TEST_RUNNER_BY_ROOT[root]

# Integrations the segmenter should NOT use as a primary segment-naming key
# (too broad — they appear in nearly every file)
LOW_SIGNAL_INTEGRATIONS = {"filesystem"}


# ---------- endpoint detectors ----------

ENDPOINT_PATTERNS = [
    (re.compile(r"@(?:\w+)\.(get|post|put|patch|delete|head|options)\(\s*['\"]([^'\"]+)['\"]"), "rest"),
    (re.compile(r"@\w+\.route\(\s*['\"]([^'\"]+)['\"](?:.*?methods\s*=\s*\[([^\]]+)\])?", re.S), "flask_route"),
    (re.compile(r"(?<!@)\b(?:app|router)\.(get|post|put|patch|delete|use)\(\s*['\"]([^'\"]+)['\"]"), "express"),
    (re.compile(r"export\s+(?:async\s+)?function\s+(GET|POST|PUT|PATCH|DELETE)\b"), "nextjs"),
]


# ---------- data classes ----------

@dataclass
class Symbol:
    id: str             # "file::QualName" e.g. "src/foo.py::MyClass.bar"
    name: str
    qualname: str       # "MyClass.bar" for methods, "bar" for functions
    kind: str           # "function" | "class" | "method"
    file: str
    line: int
    header: str = ""
    class_of: str = ""  # if method: parent class name


@dataclass
class ClassInfo:
    id: str
    name: str
    file: str
    line: int
    bases: list[str] = field(default_factory=list)     # base class names
    methods: list[str] = field(default_factory=list)
    fields: list[str] = field(default_factory=list)


@dataclass
class CallEdge:
    caller_id: str      # symbol id of caller (e.g. "src/foo.py::bar")
    callee_name: str    # raw callee name as appeared in source
    callee_id: str = "" # filled by resolver — symbol id, or "" if external/unresolved
    file: str = ""
    line: int = 0


@dataclass
class Endpoint:
    method: str
    path: str
    file: str
    line: int
    framework: str
    handler_id: str = ""  # symbol id of the handler function (filled if resolvable)


@dataclass
class FileNode:
    path: str
    lang: str
    loc: int
    imports: list[str] = field(default_factory=list)
    integrations: list[str] = field(default_factory=list)
    symbol_count: int = 0
    script_lang: str = ""  # .vue only: "typescript" when a <script> block has lang="ts"


@dataclass
class InventoryEntry:
    path: str
    lang: str
    dir: str
    bytes: int
    loc: int
    parsed: bool  # True when the file also has a FileNode (imports, symbols)


@dataclass
class ProjectMap:
    root: str
    files: list[FileNode] = field(default_factory=list)
    edges: list[tuple[str, str]] = field(default_factory=list)
    symbols: list[Symbol] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)
    calls: list[CallEdge] = field(default_factory=list)
    endpoints: list[Endpoint] = field(default_factory=list)
    integration_index: dict[str, list[str]] = field(default_factory=dict)
    parse_errors: list[str] = field(default_factory=list)
    ts_path_aliases: dict[str, str] = field(default_factory=dict)
    inventory: list[InventoryEntry] = field(default_factory=list)
    skipped_binary: int = 0


# ---------- python parsing (precise, AST) ----------

def parse_python(rel_path: str, src: str, pmap: ProjectMap) -> FileNode:
    node = FileNode(path=rel_path, lang="python", loc=src.count("\n") + 1)
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        pmap.parse_errors.append(f"{rel_path}: {e}")
        return node

    # imports
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for alias in n.names:
                node.imports.append(alias.name)
        elif isinstance(n, ast.ImportFrom):
            # Relative imports keep their leading dots (`..pkg.mod`) so they resolve from this file's package.
            dots = "." * n.level
            if n.module:
                node.imports.append(dots + n.module)
            elif dots:
                node.imports.extend(dots + alias.name for alias in n.names)

    # classes + their methods, top-level functions, calls
    for n in tree.body:
        if isinstance(n, ast.ClassDef):
            _emit_class(n, rel_path, src, pmap, node)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _emit_function(n, rel_path, src, pmap, node, qualname=n.name, class_of="")
            _emit_calls_in(n, f"{rel_path}::{n.name}", rel_path, pmap)

    return node


def _emit_class(node: ast.ClassDef, rel_path: str, src: str,
                pmap: ProjectMap, fnode: FileNode):
    bases = [_unparse(b) for b in node.bases]
    cls_id = f"{rel_path}::{node.name}"
    info = ClassInfo(id=cls_id, name=node.name, file=rel_path, line=node.lineno, bases=bases)

    pmap.symbols.append(Symbol(
        id=cls_id, name=node.name, qualname=node.name, kind="class",
        file=rel_path, line=node.lineno, header=_docstring_first_line(node) or "",
    ))
    fnode.symbol_count += 1

    for n in node.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            qual = f"{node.name}.{n.name}"
            sym_id = f"{rel_path}::{qual}"
            info.methods.append(n.name)
            pmap.symbols.append(Symbol(
                id=sym_id, name=n.name, qualname=qual, kind="method",
                file=rel_path, line=n.lineno,
                header=_docstring_first_line(n) or "",
                class_of=node.name,
            ))
            fnode.symbol_count += 1
            _emit_calls_in(n, sym_id, rel_path, pmap)
            # collect fields from self.X = ... in __init__
            if n.name == "__init__":
                for stmt in ast.walk(n):
                    if isinstance(stmt, ast.Assign):
                        for tgt in stmt.targets:
                            if (isinstance(tgt, ast.Attribute)
                                    and isinstance(tgt.value, ast.Name)
                                    and tgt.value.id == "self"):
                                if tgt.attr not in info.fields:
                                    info.fields.append(tgt.attr)
        elif isinstance(n, ast.Assign):
            # class-level fields: x = ...
            for tgt in n.targets:
                if isinstance(tgt, ast.Name) and tgt.id not in info.fields:
                    info.fields.append(tgt.id)
        elif isinstance(n, ast.AnnAssign):
            # class-level annotated fields: x: int = ...
            if isinstance(n.target, ast.Name) and n.target.id not in info.fields:
                info.fields.append(n.target.id)

    pmap.classes.append(info)


def _emit_function(node, rel_path: str, src: str, pmap: ProjectMap,
                   fnode: FileNode, qualname: str, class_of: str):
    sym_id = f"{rel_path}::{qualname}"
    pmap.symbols.append(Symbol(
        id=sym_id, name=node.name, qualname=qualname, kind="function",
        file=rel_path, line=node.lineno,
        header=_docstring_first_line(node) or "",
        class_of=class_of,
    ))
    fnode.symbol_count += 1


def _emit_calls_in(scope_node, caller_id: str, rel_path: str, pmap: ProjectMap):
    """Walk a function/method body and record every Call node."""
    for n in ast.walk(scope_node):
        if isinstance(n, ast.Call):
            name = _call_name(n.func)
            if not name:
                continue
            pmap.calls.append(CallEdge(
                caller_id=caller_id, callee_name=name,
                file=rel_path, line=getattr(n, "lineno", 0),
            ))


def _call_name(func: ast.AST) -> str:
    """Best-effort stringification of the callee.
    Examples: foo() -> "foo", obj.method() -> "obj.method", a.b.c() -> "a.b.c"
    """
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        base = _call_name(func.value)
        return f"{base}.{func.attr}" if base else func.attr
    return ""


def _unparse(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return f"{_unparse(node.value)}.{node.attr}"
        return ""


def _docstring_first_line(node) -> str | None:
    body = getattr(node, "body", None)
    if not body:
        return None
    first = body[0]
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
        return first.value.value.strip().split("\n", 1)[0][:120]
    return None


# ---------- js/ts parsing (regex, best-effort) ----------

# Import lists wrapped over several lines, re-exports from barrel files, `require` with destructuring and
# lazy `import()` route components are all edges.
JS_IMPORT_RE = re.compile(
    r"""(?:^|\n)\s*
        (?:import\s+(?:[^'";]*?\s+from\s+)?['"]([^'"]+)['"]
         |  export\s+(?:type\s+)?(?:\*(?:\s+as\s+\w+)?|\{[^}]*\})\s*from\s+['"]([^'"]+)['"])
     |  \b(?:require|import)\(\s*['"]([^'"]+)['"]\s*\)
    """,
    re.X,
)
JS_FN_RE = re.compile(
    r"""(?:^|\n)\s*
        (?:export\s+)?
        (?:async\s+)?
        (?:function\s+(\w+)
         |  (?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\()
    """,
    re.X,
)
JS_CLASS_RE = re.compile(
    r"(?:^|\n)\s*(?:export\s+)?class\s+(\w+)(?:\s+extends\s+([\w.]+))?"
)
JS_CALL_RE = re.compile(r"\b([A-Za-z_$][\w$]*)\s*\(")


def parse_js_like(rel_path: str, src: str, pmap: ProjectMap, lang: str) -> FileNode:
    node = FileNode(path=rel_path, lang=lang, loc=src.count("\n") + 1)

    for m in JS_IMPORT_RE.finditer(src):
        node.imports.append(m.group(1) or m.group(2) or m.group(3))

    # functions
    for m in JS_FN_RE.finditer(src):
        name = m.group(1) or m.group(2)
        if not name:
            continue
        line = src[: m.start()].count("\n") + 1
        sym_id = f"{rel_path}::{name}"
        pmap.symbols.append(Symbol(
            id=sym_id, name=name, qualname=name,
            kind="function", file=rel_path, line=line,
        ))
        node.symbol_count += 1

    # classes
    for m in JS_CLASS_RE.finditer(src):
        cname = m.group(1)
        base = m.group(2)
        line = src[: m.start()].count("\n") + 1
        cls_id = f"{rel_path}::{cname}"
        pmap.symbols.append(Symbol(
            id=cls_id, name=cname, qualname=cname,
            kind="class", file=rel_path, line=line,
        ))
        pmap.classes.append(ClassInfo(
            id=cls_id, name=cname, file=rel_path, line=line,
            bases=[base] if base else [],
        ))
        node.symbol_count += 1

    # crude call extraction at file scope (not per-function — we don't have scopes)
    # caller_id is the file itself; the synthesizer will treat this as approximate
    KW = {"if", "for", "while", "switch", "return", "function", "catch",
          "typeof", "new", "throw", "await", "yield", "async", "class"}
    for m in JS_CALL_RE.finditer(src):
        callee = m.group(1)
        if callee in KW:
            continue
        line = src[: m.start()].count("\n") + 1
        pmap.calls.append(CallEdge(
            caller_id=f"{rel_path}::__file__", callee_name=callee,
            file=rel_path, line=line,
        ))

    return node


# ---------- go parsing (regex) ----------

GO_IMPORT_RE = re.compile(r'import\s*\(\s*((?:.|\n)*?)\)')
GO_IMPORT_LINE_RE = re.compile(r'"([^"]+)"')
GO_FN_RE = re.compile(r"^func\s+(?:\([^)]+\)\s+)?(\w+)\s*\(", re.M)


def parse_go(rel_path: str, src: str, pmap: ProjectMap) -> FileNode:
    node = FileNode(path=rel_path, lang="go", loc=src.count("\n") + 1)
    for block in GO_IMPORT_RE.finditer(src):
        for imp in GO_IMPORT_LINE_RE.findall(block.group(1)):
            node.imports.append(imp)
    for m in GO_FN_RE.finditer(src):
        line = src[: m.start()].count("\n") + 1
        name = m.group(1)
        pmap.symbols.append(Symbol(
            id=f"{rel_path}::{name}", name=name, qualname=name,
            kind="function", file=rel_path, line=line,
        ))
        node.symbol_count += 1
    return node


# ---------- vue single-file components ----------

VUE_SCRIPT_RE = re.compile(r"<script\b([^>]*)>(.*?)</script\s*>", re.S | re.I)
VUE_LANG_RE = re.compile(r"""\blang\s*=\s*['"]?(tsx?|jsx?)['"]?""", re.I)


def parse_vue(rel_path: str, src: str, pmap: ProjectMap) -> FileNode:
    """Parse every <script> / <script setup> block like JS or TS. Text outside the blocks is blanked but its
    newlines are kept, so symbol line numbers stay true to the .vue file."""
    parts, last, script_lang = [], 0, "javascript"
    for m in VUE_SCRIPT_RE.finditer(src):
        lang_m = VUE_LANG_RE.search(m.group(1))
        if lang_m and lang_m.group(1).lower().startswith("ts"):
            script_lang = "typescript"
        parts.append("\n" * src.count("\n", last, m.start(2)))
        parts.append(m.group(2))
        last = m.end(2)
    parts.append("\n" * src.count("\n", last))
    node = parse_js_like(rel_path, "".join(parts), pmap, "vue")
    node.loc = src.count("\n") + 1
    node.script_lang = script_lang
    return node


# ---------- other languages (regex, imports + definitions only, no call edges) ----------

def _line_index(src: str) -> list[int]:
    return [i for i, ch in enumerate(src) if ch == "\n"]


def _line_of(newlines: list[int], pos: int) -> int:
    return bisect_right(newlines, pos - 1) + 1


def _add_symbol(pmap: ProjectMap, node: FileNode, rel_path: str, name: str, kind: str, line: int,
                bases: list[str] | None = None, class_of: str = ""):
    qual = f"{class_of}.{name}" if class_of else name
    sym_id = f"{rel_path}::{qual}"
    pmap.symbols.append(Symbol(id=sym_id, name=name, qualname=qual, kind=kind, file=rel_path, line=line,
                               class_of=class_of))
    if kind == "class":
        pmap.classes.append(ClassInfo(id=sym_id, name=name, file=rel_path, line=line, bases=bases or []))
    node.symbol_count += 1


RB_REQUIRE_RE = re.compile(r"""^\s*require(_relative)?\s*\(?\s*['"]([^'"]+)['"]""", re.M)
RB_CLASS_RE = re.compile(r"^\s*(?:class|module)\s+([A-Z][\w:]*)(?:\s*<\s*([A-Z][\w:]*))?", re.M)
RB_DEF_RE = re.compile(r"^\s*def\s+(?:self\.)?([a-z_]\w*[?!=]?)", re.M)

JVM_IMPORT_RE = re.compile(r"^\s*import\s+(?:static\s+)?([\w.]+?)(?:\.\*)?\s*(?:as\s+\w+)?\s*;?\s*$", re.M)
JVM_CLASS_RE = re.compile(
    r"^\s*(?:@\w+(?:\([^)]*\))?\s+)*(?:(?:public|private|protected|internal|abstract|final|static|sealed|"
    r"data|open|inner|value|enum|annotation)\s+)*(?:class|interface|enum|record|object)\s+(\w+)"
    r"([^{\n]*)", re.M)
JVM_EXTENDS_RE = re.compile(r"\bextends\s+([\w.]+)|^\s*(?:\([^)]*\))?\s*:\s*([\w.]+)")
KOTLIN_FUN_RE = re.compile(r"^\s*(?:(?:\w+)\s+)*fun\s+(?:<[^>]*>\s*)?(?:[\w.]+\.)?(\w+)\s*\(", re.M)
JAVA_METHOD_RE = re.compile(
    r"^\s*(?:(?:public|private|protected|static|final|abstract|synchronized|native|default)\s+)+"
    r"[\w<>\[\],.? ]+\s+(\w+)\s*\(", re.M)

RUST_USE_RE = re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?use\s+([^;]+);", re.M)
RUST_MOD_RE = re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?mod\s+(\w+)\s*;", re.M)
RUST_DEF_RE = re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?(?:(fn)|struct|enum|trait)\s+(\w+)", re.M)

PHP_USE_RE = re.compile(r"^\s*use\s+([\w\\]+)", re.M)
PHP_REQUIRE_RE = re.compile(r"""\b(?:require|include)(?:_once)?\s*\(?\s*(?:__DIR__\s*\.\s*)?['"]([^'"]+)['"]""")
PHP_CLASS_RE = re.compile(r"^\s*(?:abstract\s+|final\s+)?(?:class|interface|trait|enum)\s+(\w+)"
                          r"(?:\s+extends\s+([\w\\]+))?", re.M)
PHP_FN_RE = re.compile(r"\bfunction\s+(\w+)\s*\(")

STYLE_IMPORT_RE = re.compile(r"""@(?:import|use|forward)\s+(?:url\(\s*)?['"]([^'"]+)['"]""")
HTML_REF_RE = re.compile(r"""<script\b[^>]*\bsrc\s*=\s*['"]([^'"]+)['"]"""
                         r"""|<link\b[^>]*\bhref\s*=\s*['"]([^'"]+\.(?:css|scss|less))['"]""", re.I)


def _is_external_url(ref: str) -> bool:
    return ref.startswith(("http:", "https:", "//", "data:", "mailto:")) or "{{" in ref or "${" in ref


def parse_ruby(rel_path: str, src: str, pmap: ProjectMap) -> FileNode:
    node = FileNode(path=rel_path, lang="ruby", loc=src.count("\n") + 1)
    nl = _line_index(src)
    for m in RB_REQUIRE_RE.finditer(src):
        target = m.group(2)
        node.imports.append(("./" + target if not target.startswith(".") else target) if m.group(1) else target)
    for m in RB_CLASS_RE.finditer(src):
        _add_symbol(pmap, node, rel_path, m.group(1).split("::")[-1], "class", _line_of(nl, m.start()),
                    bases=[m.group(2)] if m.group(2) else [])
    for m in RB_DEF_RE.finditer(src):
        _add_symbol(pmap, node, rel_path, m.group(1), "function", _line_of(nl, m.start()))
    return node


def parse_jvm(rel_path: str, src: str, pmap: ProjectMap, lang: str) -> FileNode:
    node = FileNode(path=rel_path, lang=lang, loc=src.count("\n") + 1)
    nl = _line_index(src)
    for m in JVM_IMPORT_RE.finditer(src):
        node.imports.append(m.group(1).replace(".", "/"))
    for m in JVM_CLASS_RE.finditer(src):
        ext = JVM_EXTENDS_RE.search(m.group(2))
        base = (ext.group(1) or ext.group(2)) if ext else ""
        _add_symbol(pmap, node, rel_path, m.group(1), "class", _line_of(nl, m.start()),
                    bases=[base] if base else [])
    fn_re = KOTLIN_FUN_RE if lang == "kotlin" else JAVA_METHOD_RE
    for m in fn_re.finditer(src):
        if m.group(1) not in {"if", "for", "while", "switch", "catch", "return", "new"}:
            _add_symbol(pmap, node, rel_path, m.group(1), "function", _line_of(nl, m.start()))
    return node


def _expand_rust_use(spec: str) -> list[str]:
    """`crate::{orders::Order, billing::{self, charge}}` -> one path per imported item."""
    spec = re.sub(r"\s+", "", re.sub(r"\s+as\s+\w+", "", spec))
    start = spec.find("{")
    if start < 0:
        return [spec]
    prefix, body = spec[:start], spec[start + 1:spec.rfind("}")]
    items, depth, cur = [], 0, ""
    for ch in body:
        if ch == "," and depth == 0:
            items.append(cur)
            cur = ""
            continue
        depth += (ch == "{") - (ch == "}")
        cur += ch
    items.append(cur)
    paths = []
    for item in filter(None, items):
        for sub in _expand_rust_use(item):
            paths.append(prefix.rstrip(":") if sub == "self" else prefix + sub)
    return paths


def parse_rust(rel_path: str, src: str, pmap: ProjectMap) -> FileNode:
    node = FileNode(path=rel_path, lang="rust", loc=src.count("\n") + 1)
    nl = _line_index(src)
    for m in RUST_USE_RE.finditer(src):
        for use_path in _expand_rust_use(m.group(1)):
            segs = [s for s in use_path.split("::") if s and s != "*"]
            if segs and segs[0] in {"crate", "super", "self"}:
                segs = segs[1:]
            if len(segs) > 1 and segs[-1][:1].isupper():
                segs = segs[:-1]  # `use crate::orders::Order` points at the orders module
            if segs and "/".join(segs) not in node.imports:
                node.imports.append("/".join(segs))
    for m in RUST_MOD_RE.finditer(src):
        node.imports.append("./" + m.group(1))
    for m in RUST_DEF_RE.finditer(src):
        _add_symbol(pmap, node, rel_path, m.group(2), "function" if m.group(1) else "class",
                    _line_of(nl, m.start()))
    return node


def parse_php(rel_path: str, src: str, pmap: ProjectMap) -> FileNode:
    node = FileNode(path=rel_path, lang="php", loc=src.count("\n") + 1)
    nl = _line_index(src)
    for m in PHP_USE_RE.finditer(src):
        node.imports.append(m.group(1).strip("\\").replace("\\", "/"))
    for m in PHP_REQUIRE_RE.finditer(src):
        target = m.group(1)
        node.imports.append(target if target.startswith((".", "/")) else "./" + target)
    for m in PHP_CLASS_RE.finditer(src):
        base = (m.group(2) or "").split("\\")[-1]
        _add_symbol(pmap, node, rel_path, m.group(1), "class", _line_of(nl, m.start()),
                    bases=[base] if base else [])
    for m in PHP_FN_RE.finditer(src):
        _add_symbol(pmap, node, rel_path, m.group(1), "function", _line_of(nl, m.start()))
    return node


def parse_stylesheet(rel_path: str, src: str, lang: str) -> FileNode:
    node = FileNode(path=rel_path, lang=lang, loc=src.count("\n") + 1)
    for m in STYLE_IMPORT_RE.finditer(src):
        ref = m.group(1)
        if _is_external_url(ref) or ref.startswith("sass:"):
            continue
        ref = ref.lstrip("~")
        # Sass and Less resolve a bare path next to the importing file.
        node.imports.append(ref if ref.startswith((".", "/", "@")) else "./" + ref)
    return node


def parse_html(rel_path: str, src: str) -> FileNode:
    node = FileNode(path=rel_path, lang="html", loc=src.count("\n") + 1)
    for m in HTML_REF_RE.finditer(src):
        ref = (m.group(1) or m.group(2)).split("?")[0]
        if not _is_external_url(ref):
            node.imports.append(ref if ref.startswith((".", "/")) else "./" + ref)
    return node


# ---------- endpoint & integration scan ----------

def scan_endpoints_and_integrations(rel_path: str, src: str, pmap: ProjectMap, node: FileNode):
    for pattern, fw in ENDPOINT_PATTERNS:
        for m in pattern.finditer(src):
            line = src[: m.start()].count("\n") + 1
            if fw == "flask_route":
                path = m.group(1)
                methods = m.group(2) or "GET"
                methods = re.findall(r"['\"](\w+)['\"]", methods) or ["GET"]
                for method in methods:
                    pmap.endpoints.append(Endpoint(method.upper(), path, rel_path, line, fw))
            elif fw == "nextjs":
                path = "/" + str(Path(rel_path).parent).replace(os.sep, "/")
                pmap.endpoints.append(Endpoint(m.group(1).upper(), path, rel_path, line, fw))
            else:
                method, path = m.group(1), m.group(2)
                pmap.endpoints.append(Endpoint(method.upper(), path, rel_path, line, fw))

    found = set()
    for label, patterns in INTEGRATION_PATTERNS.items():
        for pat in patterns:
            if pat.search(src):
                found.add(label)
                break
    if any(pat.search(src) for pat in JEST_STYLE_API_PATTERNS):
        found.add(project_test_runner(pmap.root))
    node.integrations = sorted(found)
    for label in found:
        pmap.integration_index.setdefault(label, []).append(rel_path)


# ---------- TS path-alias resolution ----------

def load_ts_path_aliases(root: Path) -> dict[str, str]:
    """Read tsconfig.json compilerOptions.paths into a flat alias->target map.

    Conservative: handles the common case `"@/*": ["src/*"]`. Returns
    paths relative to the project root.
    """
    aliases = {}
    for tsconfig_name in ("tsconfig.json", "frontend/tsconfig.json", "frontend/tsconfig.app.json"):
        p = root / tsconfig_name
        if not p.exists():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
            # strip // comments and trailing commas (tsconfig is JSON-with-comments)
            text = re.sub(r"//[^\n]*", "", text)
            text = re.sub(r",(\s*[}\]])", r"\1", text)
            cfg = json.loads(text)
        except Exception:
            continue
        co = cfg.get("compilerOptions", {})
        base_url = co.get("baseUrl", ".")
        ts_dir = p.parent.relative_to(root) if p.parent != root else Path(".")
        base = (ts_dir / base_url).as_posix().lstrip("./") or "."
        for alias, targets in (co.get("paths") or {}).items():
            if not targets:
                continue
            target = targets[0]
            alias_clean = alias.rstrip("/*")
            target_clean = (Path(base) / target.rstrip("/*")).as_posix().lstrip("./")
            aliases[alias_clean] = target_clean
    for alias, target in load_vite_aliases(root).items():
        aliases.setdefault(alias, target)
    return aliases


VITE_ALIAS_RE = re.compile(
    r"""['"]?([@~\w][\w@~./-]*)['"]?\s*:\s*
        (?:(?:path\.)?resolve\(\s*__dirname\s*,\s*['"]([^'"]+)['"]\s*\)
         | fileURLToPath\(\s*new\s+URL\(\s*['"]([^'"]+)['"]\s*,\s*import\.meta\.url\s*\)\s*\))""",
    re.X,
)


def load_vite_aliases(root: Path) -> dict[str, str]:
    """Read `resolve.alias` entries written as `path.resolve(__dirname, 'x')` or
    `fileURLToPath(new URL('x', import.meta.url))` from a root vite.config, as root-relative targets."""
    aliases = {}
    for name in ("vite.config.ts", "vite.config.mts", "vite.config.js", "vite.config.mjs"):
        p = root / name
        if not p.exists():
            continue
        for m in VITE_ALIAS_RE.finditer(_vite_alias_block(p.read_text(encoding="utf-8", errors="replace"))):
            target = os.path.normpath(m.group(2) or m.group(3)).lstrip("/")
            aliases.setdefault(m.group(1), target)
    return aliases


def _vite_alias_block(src: str) -> str:
    """The `{...}` object after `alias:`, so other `path.resolve(__dirname, ...)` settings aren't read as aliases."""
    m = re.search(r"\balias\s*:\s*\{", src)
    if not m:
        return ""
    depth = 0
    for i in range(m.end() - 1, len(src)):
        depth += {"{": 1, "}": -1}.get(src[i], 0)
        if depth == 0:
            return src[m.end():i]
    return src[m.end():]


# ---------- import resolution (file -> file edges) ----------

STYLE_LANGS = {"css", "scss", "sass", "less"}
# Package-style imports (`com.acme.orders.Order`, `App\Models\User`, `crate::orders`) name a path from a source
# root the mapper doesn't know, so they fall back to matching the last two path segments.
TAIL_MATCH_LANGS = {"java", "kotlin", "php", "rust"}
JS_LANGS = {"javascript", "typescript", "vue"}
# TypeScript's extension order, then plain JS, then single-file components; each is also tried as `<dir>/index<ext>`.
JS_RESOLVE_EXTS = (".ts", ".tsx", ".d.ts", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".json")


def _apply_alias(imp: str, aliases: dict[str, str]) -> str | None:
    """`imp` with its longest matching alias prefix replaced by the alias target, or None when no alias matches."""
    matches = [a for a in aliases if imp == a or imp.startswith(a + "/")]
    if not matches:
        return None
    alias = max(matches, key=len)
    return aliases[alias] + imp[len(alias):]


def _js_import_candidates(importer: str, imp: str, aliases: dict[str, str]) -> list[str] | None:
    """Root-relative files a relative or aliased JS/TS import can load, in resolution order.
    None for a package import (`vue`, `lodash/merge`), which names no project path."""
    if imp in {".", ".."} or imp.startswith(("./", "../")):
        base = os.path.normpath(Path(importer).parent / imp)
    else:
        aliased = _apply_alias(imp, aliases)
        if aliased is None:
            return None
        base = os.path.normpath(aliased)
    return [base, *(base + ext for ext in JS_RESOLVE_EXTS), *(f"{base}/index{ext}" for ext in JS_RESOLVE_EXTS)]


def _python_relative_candidates(importer: str, imp: str) -> list[str]:
    """Files a dotted relative import (`.mod`, `..pkg.mod`, `..`) can load. The package's `__init__.py` comes last
    because `from . import name` may name something defined there rather than a submodule."""
    level = len(imp) - len(imp.lstrip("."))
    package = Path(os.path.normpath(Path(importer).parent / ("../" * (level - 1))))
    rest = imp[level:].replace(".", "/")
    module = Path(os.path.normpath(package / rest)) if rest else package
    return [f"{module.as_posix()}.py", (module / "__init__.py").as_posix(), (package / "__init__.py").as_posix()]


def _rust_use_candidates(importer: str, imp: str) -> list[str]:
    """Files a `use` path can load, longest module path first, read from the importer's crate `src/` folder.
    `billing/charge` names the function `charge` in `billing.rs`, so shorter prefixes are tried too."""
    parts = Path(importer).parts
    if "src" not in parts:
        return []
    root = Path(*parts[:len(parts) - parts[::-1].index("src")])
    segs = imp.split("/")
    out = []
    for k in range(len(segs), 0, -1):
        base = root.joinpath(*segs[:k])
        out += [f"{base.as_posix()}.rs", (base / "mod.rs").as_posix()]
    return out


def resolve_imports_to_edges(pmap: ProjectMap):
    by_module = {}
    by_tail = {}
    for f in pmap.files:
        p = Path(f.path)
        stem = p.with_suffix("").as_posix()
        by_module[stem] = f.path
        by_module[p.stem] = f.path
        # also index parent dir as resolving to __init__/index files
        if p.stem in {"__init__", "index"} or (p.stem == "mod" and p.suffix == ".rs"):
            by_module[p.parent.as_posix()] = f.path
        # imports that keep the extension, e.g. `import Foo from './Foo.vue'`
        by_module.setdefault(p.as_posix(), f.path)
        by_module.setdefault(p.name, f.path)
        # Sass/Less partials: `@use 'colors'` loads `_colors.scss`
        if p.stem.startswith("_") and f.lang in STYLE_LANGS:
            by_module.setdefault((p.parent / p.stem[1:]).as_posix(), f.path)
            by_module.setdefault(p.stem[1:], f.path)
        tail = "/".join(p.with_suffix("").parts[-2:])
        by_tail.setdefault(tail, f.path)

    aliases = pmap.ts_path_aliases
    paths = {f.path for f in pmap.files}

    for f in pmap.files:
        for imp in f.imports:
            # Relative and aliased imports name one exact file, so they never fall back to the name-only index below,
            # which would link a same-named file in another folder. Package imports (`pinia`) name no project file.
            exact = None
            if f.lang in JS_LANGS:
                exact = _js_import_candidates(f.path, imp, aliases)
                if exact is None and not imp.startswith("/"):
                    continue
            elif f.lang == "python" and imp.startswith("."):
                exact = _python_relative_candidates(f.path, imp)
            elif f.lang == "rust" and not imp.startswith("."):
                hit = next((c for c in _rust_use_candidates(f.path, imp) if c in paths), None)
                exact = [hit] if hit else None
            if exact is not None:
                target = next((c for c in exact if c in paths), None)
                if target and target != f.path:
                    pmap.edges.append((f.path, target))
                continue

            resolved = _apply_alias(imp, aliases) or imp
            candidates = [
                resolved,
                resolved.replace(".", "/"),
                resolved.lstrip("./"),
                resolved.split("/")[-1] if "/" in resolved else resolved,
            ]
            if imp.startswith("."):
                candidates.insert(0, os.path.normpath(Path(f.path).parent / imp))

            for c in candidates:
                c = c.rstrip("/")
                if c in by_module and by_module[c] != f.path:
                    pmap.edges.append((f.path, by_module[c]))
                    break
            else:
                if f.lang in TAIL_MATCH_LANGS:
                    tail = "/".join(resolved.split("/")[-2:])
                    if tail in by_tail and by_tail[tail] != f.path:
                        pmap.edges.append((f.path, by_tail[tail]))

    # A Rust file names a module both in `mod x;` and in `use crate::x::...`, which is one dependency.
    pmap.edges[:] = list(dict.fromkeys(pmap.edges))


# ---------- call resolution (callee_name -> callee symbol id) ----------

def resolve_calls(pmap: ProjectMap):
    """Resolve callee_name to a project-internal symbol id where possible.

    Strategy (in order):
      1. If `caller_file::callee_name` matches a known symbol id, use it.
      2. If callee is "obj.method" and a class with that method exists in the
         caller's reachable file set, prefer that.
      3. Otherwise, if any project symbol has that bare name, link to the
         lexicographically first match (best-effort).
      4. Else leave callee_id="" (external / unresolved).
    """
    by_id = {s.id: s for s in pmap.symbols}
    by_name = {}
    by_qualname = {}
    for s in pmap.symbols:
        by_name.setdefault(s.name, []).append(s.id)
        by_qualname.setdefault(s.qualname, []).append(s.id)

    # files reachable from each file via 1-hop edges
    reachable = {}
    for src, dst in pmap.edges:
        reachable.setdefault(src, set()).add(dst)

    for c in pmap.calls:
        callee = c.callee_name
        caller_file = c.file

        # 1. same-file definition
        sid = f"{caller_file}::{callee}"
        if sid in by_id:
            c.callee_id = sid
            continue

        # 2. obj.method form — try matching by qualname first, then by method name
        if "." in callee:
            tail = callee.split(".")[-1]
            qual = callee
            # match Class.method exactly
            if qual in by_qualname:
                cands = by_qualname[qual]
                # prefer one in caller_file or its reachable set
                pick = _pick_in_reachable(cands, caller_file, reachable, by_id)
                if pick:
                    c.callee_id = pick
                    continue
            # else just try the method name
            if tail in by_name:
                pick = _pick_in_reachable(by_name[tail], caller_file, reachable, by_id)
                if pick:
                    c.callee_id = pick
                    continue

        # 3. bare name lookup
        if callee in by_name:
            pick = _pick_in_reachable(by_name[callee], caller_file, reachable, by_id)
            if pick:
                c.callee_id = pick
                continue

        # 4. unresolved (probably external/stdlib/builtin)
        c.callee_id = ""


def _pick_in_reachable(candidates, caller_file, reachable, by_id):
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    in_file = [c for c in candidates if by_id[c].file == caller_file]
    if in_file:
        return in_file[0]
    in_reach = [c for c in candidates if by_id[c].file in reachable.get(caller_file, set())]
    if in_reach:
        return in_reach[0]
    return sorted(candidates)[0]


# ---------- diagram render ----------

def render_file_graph(pmap: ProjectMap) -> str:
    """Graphviz source for the file-level import graph, importers above what they import."""
    lines = ["digraph project_map {", "  rankdir=TB;",
             '  node [shape=box, style="rounded,filled", fillcolor="#ffffff", color="#d0d7de", '
             'fontname="Helvetica", fontsize=11];',
             '  edge [color="#59636e", arrowsize=0.7];']
    files = sorted({f for edge in pmap.edges for f in edge})
    for path in files:
        lines.append(f"  {dot_quote(path)};")
    for src, dst in pmap.edges:
        lines.append(f"  {dot_quote(src)} -> {dot_quote(dst)};")
    lines.append("}")
    return "\n".join(lines) + "\n"


def _record_text(text: str) -> str:
    return re.sub(r'([{}|<>"\\])', r"\\\1", text)


def render_class_diagram(pmap: ProjectMap, max_classes: int = 80) -> str:
    """Graphviz source for a UML-style class diagram (limited for readability), base classes on top."""
    classes = pmap.classes[:max_classes]
    lines = ["digraph classes {", "  rankdir=BT;",
             '  node [shape=record, style=filled, fillcolor="#ffffff", color="#8c959f", '
             'fontname="Helvetica", fontsize=10];',
             '  edge [arrowhead=empty, color="#59636e"];']
    cls_names = {c.name for c in classes}
    for c in classes:
        fields = "".join(_record_text(f) + "\\l" for f in c.fields[:6])
        methods = "".join(_record_text(m) + "()\\l" for m in c.methods[:8])
        lines.append(f'  {dot_quote(c.name)} [label="{{{_record_text(c.name)}|{fields}|{methods}}}"];')
        for base in c.bases:
            base_simple = base.split(".")[-1]
            if base_simple in cls_names:
                lines.append(f"  {dot_quote(c.name)} -> {dot_quote(base_simple)};")
    lines.append("}")
    return "\n".join(lines) + "\n"


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="Project root directory")
    ap.add_argument("--output", "-o", default=".cartographer", help="Output directory")
    ap.add_argument("--no-render", action="store_true",
                    help="Write the graph diagrams as .dot sources only, skipping the Graphviz render")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    pmap = ProjectMap(root=str(root))
    pmap.ts_path_aliases = load_ts_path_aliases(root)
    if pmap.ts_path_aliases:
        print(f"TS aliases: {pmap.ts_path_aliases}", file=sys.stderr)

    _progress.start("phase-1", out_dir=out)
    print(f"Walking {root}...", file=sys.stderr)
    n = 0
    for full, rel in iter_project_files(root):
        rel_str = rel.as_posix()
        if is_binary(full):
            pmap.skipped_binary += 1
            continue
        try:
            src = full.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            pmap.parse_errors.append(f"{rel_str}: read error {e}")
            continue

        ext = full.suffix.lower()
        lang = language_for(rel)
        pmap.inventory.append(InventoryEntry(
            path=rel_str, lang=lang, dir=rel.parent.as_posix(), bytes=len(src.encode("utf-8", "replace")),
            loc=src.count("\n") + (0 if src.endswith("\n") or not src else 1),
            parsed=ext in SUPPORTED_EXT))
        if ext not in SUPPORTED_EXT:
            continue

        if ext == ".py":
            node = parse_python(rel_str, src, pmap)
        elif ext in {".js", ".jsx", ".mjs", ".cjs"}:
            node = parse_js_like(rel_str, src, pmap, "javascript")
        elif ext in {".ts", ".tsx"}:
            node = parse_js_like(rel_str, src, pmap, "typescript")
        elif ext == ".go":
            node = parse_go(rel_str, src, pmap)
        elif ext == ".vue":
            node = parse_vue(rel_str, src, pmap)
        elif ext in {".rb", ".rake"}:
            node = parse_ruby(rel_str, src, pmap)
        elif ext == ".java":
            node = parse_jvm(rel_str, src, pmap, "java")
        elif ext in {".kt", ".kts"}:
            node = parse_jvm(rel_str, src, pmap, "kotlin")
        elif ext == ".rs":
            node = parse_rust(rel_str, src, pmap)
        elif ext == ".php":
            node = parse_php(rel_str, src, pmap)
        elif ext in {".css", ".scss", ".sass", ".less"}:
            node = parse_stylesheet(rel_str, src, lang)
        elif ext in {".html", ".htm"}:
            node = parse_html(rel_str, src)
        else:
            continue

        scan_endpoints_and_integrations(rel_str, src, pmap, node)
        pmap.files.append(node)
        n += 1
        if n % 50 == 0:
            print(f"  parsed {n} files", file=sys.stderr)
            _progress.update(step="parsing", current=n, total=0,
                             message=f"parsed {n} files")

    _progress.update(step="resolving imports", current=len(pmap.files),
                     total=len(pmap.files))
    print(f"Resolving imports...", file=sys.stderr)
    resolve_imports_to_edges(pmap)
    _progress.update(step="resolving calls",
                     current=0, total=len(pmap.calls),
                     message=f"{len(pmap.calls)} call sites")
    print(f"Resolving calls ({len(pmap.calls)} call sites)...", file=sys.stderr)
    resolve_calls(pmap)

    # link endpoints to handler symbols (best-effort)
    sym_by_file_line = {(s.file, s.line): s for s in pmap.symbols if s.kind in {"function", "method"}}
    for ep in pmap.endpoints:
        # find the next function definition at or after the endpoint's decorator line
        candidates = [s for (f, l), s in sym_by_file_line.items()
                      if f == ep.file and l >= ep.line]
        if candidates:
            best = min(candidates, key=lambda s: s.line - ep.line)
            ep.handler_id = best.id

    inventory_by_lang: dict[str, int] = {}
    for entry in pmap.inventory:
        inventory_by_lang[entry.lang] = inventory_by_lang.get(entry.lang, 0) + 1
    inventory_by_lang = dict(sorted(inventory_by_lang.items(), key=lambda kv: -kv[1]))

    # write outputs
    map_path = out / "project-map.json"
    with open(map_path, "w") as f:
        json.dump({
            "root": pmap.root,
            "files": [asdict(x) for x in pmap.files],
            "edges": [list(e) for e in pmap.edges],
            "symbols": [asdict(s) for s in pmap.symbols],
            "classes": [asdict(c) for c in pmap.classes],
            "calls": [asdict(c) for c in pmap.calls],
            "endpoints": [asdict(e) for e in pmap.endpoints],
            "integration_index": pmap.integration_index,
            "ts_path_aliases": pmap.ts_path_aliases,
            "parse_errors": pmap.parse_errors,
            "inventory": [asdict(x) for x in pmap.inventory],
            "stats": {
                "files": len(pmap.files),
                "inventory_files": len(pmap.inventory),
                "inventory_by_lang": inventory_by_lang,
                "skipped_binary": pmap.skipped_binary,
                "edges": len(pmap.edges),
                "symbols": len(pmap.symbols),
                "classes": len(pmap.classes),
                "calls": len(pmap.calls),
                "calls_resolved": sum(1 for c in pmap.calls if c.callee_id),
                "endpoints": len(pmap.endpoints),
                "integrations": list(pmap.integration_index.keys()),
            },
        }, f, indent=2)

    def write_diagram(source: str, svg_path: Path) -> bool:
        if args.no_render:
            svg_path.with_suffix(".dot").write_text(source, encoding="utf-8")
            return False
        return render_dot(source, svg_path)

    graph_path = out / "project-map.svg"
    graph_ok = write_diagram(render_file_graph(pmap), graph_path)
    cls_path = out / "class_diagram.svg"
    cls_ok = write_diagram(render_class_diagram(pmap), cls_path)

    print(f"\nWrote {map_path}", file=sys.stderr)
    for path, ok in ((graph_path, graph_ok), (cls_path, cls_ok)):
        print(f"Wrote {path if ok else path.with_suffix('.dot')}", file=sys.stderr)
    resolved = sum(1 for c in pmap.calls if c.callee_id)
    print(f"Files: {len(pmap.files)}  Edges: {len(pmap.edges)}  "
          f"Symbols: {len(pmap.symbols)}  Classes: {len(pmap.classes)}  "
          f"Calls: {resolved}/{len(pmap.calls)} resolved  "
          f"Endpoints: {len(pmap.endpoints)}", file=sys.stderr)
    top_langs = ", ".join(f"{lang} {count}" for lang, count in list(inventory_by_lang.items())[:12])
    print(f"Inventory: {len(pmap.inventory)} text files ({top_langs}); "
          f"{pmap.skipped_binary} binary files skipped", file=sys.stderr)
    if pmap.integration_index:
        print(f"Integrations detected: {', '.join(sorted(pmap.integration_index.keys()))}", file=sys.stderr)
    _progress.done()


if __name__ == "__main__":
    main()
