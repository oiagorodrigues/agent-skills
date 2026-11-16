#!/usr/bin/env python3
"""
Phase 1.7: draft a domain glossary from the code.

Collects domain terms from class, interface, type and enum names, enum values, database tables and models,
route segments and the words that recur across identifiers. Each term gets where it is defined (file:line), how
many files use it and a one-line meaning when a docstring, a comment above the definition or the enum values
give one; otherwise the meaning is "to define". It also flags names that may be the same concept: known synonym
pairs that both appear, near-identical spellings, abbreviations, and models stored in a table with another name.

The script only drafts. The LLM pass in skills/cartographer/prompts/glossary.md fills the "to define" meanings
and settles the synonym flags. Format follows Matt Pocock's domain-modeling GLOSSARY.md (MIT,
https://github.com/mattpocock/skills).

Writes glossary.json and glossary.md next to project-map.json.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from bisect import bisect_right
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from itertools import combinations
from pathlib import Path

CODE_LANGS = {"python", "javascript", "typescript", "vue", "go", "ruby", "java", "kotlin", "rust", "php",
              "csharp", "swift", "scala", "dart", "elixir", "svelte"}
SCHEMA_LANGS = {"sql", "prisma", "graphql", "protobuf"}
MAX_TERMS = 200
# A word must appear in function, class or type names in this many files to count as a frequent identifier.
MIN_IDENTIFIER_FILES = 15
TOP_IDENTIFIER_WORDS = 40
# Spellings this close (SequenceMatcher ratio) are flagged as possible variants of one word: catches
# license/licence and canceled/cancelled while leaving order/border alone.
NEAR_SPELLING_RATIO = 0.85
COMMENT_LOOKBACK_LINES = 6

# Technical suffixes stripped from a definition name to reach its domain word: OrderStore -> Order.
TECH_SUFFIXES = (
    "ViewSet", "Serializer", "Controller", "Component", "Repository", "Service", "Provider", "Factory",
    "Manager", "Handler", "Helper", "Helpers", "Utils", "Util", "Mixin", "Store", "Module", "Props", "Emits",
    "State", "Getters", "Actions", "Mutations", "Schema", "Payload", "Request", "Response", "Params", "Options",
    "Config", "Settings", "Dto", "DTO", "Interface", "Type", "Types", "Model", "Entity", "Record", "View",
    "Page", "Form", "Modal", "Dialog", "Table", "List", "Card", "Test", "Tests", "Spec", "Mock", "Mocks",
    "Fixture", "Fixtures", "Client", "Api", "API", "Error", "Exception", "Admin", "Filter", "Filters", "Query",
    "Mapper", "Adapter", "Wrapper", "Base", "Abstract", "Impl", "Enum", "Choices",
    "Job", "Task", "Worker", "Command", "Input", "Output", "Section", "Container", "Layout",
    "Route", "Routes", "Router", "Composable", "Hook", "ReturnType", "Return", "Data", "Info", "Value", "Values",
)
TECH_PREFIXES = ("Base", "Abstract", "Use", "use", "I", "Mock", "Fake", "Test", "Default", "Generic", "Custom",
                 "Get", "Set", "Fetch", "Create", "Update", "Delete", "Patch", "Post", "Put", "Edit", "New")

# Words too generic to be domain terms: programming vocabulary and common English.
STOPWORDS = set("""
a an and or not the of to in on at by for from with without as is are be been was were has have had do does
did can could should would will shall may might must this that these those it its if else then when while
get set put post patch delete update create remove add new old is has should handle on off init load save
fetch send make build parse format render show hide open close toggle select click change submit reset clear
data value values item items list lists map array object string number boolean bool int float str dict tuple
key keys id ids uuid name names type types kind label text title description desc message msg info meta
props prop state store getter getters action actions mutation mutations commit dispatch emit emits event events
config options option settings setting param params args arg kwargs payload request response res req result
results error errors err exception status code count total index idx num size length min max start end first
last next prev previous current default custom base abstract generic helper helpers util utils service
services manager handler handlers provider factory module component components view views page pages form
forms modal dialog table tables row rows column columns cell field fields input inputs output button link
icon image img file files path url uri route routes router api client server http https fetch query queries
filter filters sort order_by search page_size offset limit cursor true false null none undefined self cls
this super test tests spec mock mocks fixture fixtures expect describe it before after setup teardown wrapper
mount shallow vue react ref refs reactive computed watch watcher mounted created setup template slot slots
style styles class classes css scss html node element el doc document window console log logger logging
debug warn time date datetime timestamp now day days month year years hour minute second seconds ms
async await promise callback cb fn func function method methods return returns yield import export from
module default constant const let var def lambda public private protected static final void main app
version env environment local global loading loaded error_message success fail failed failure ok valid
is_valid enabled disabled visible hidden active inactive selected checked dirty touched has_more more
current_user auth token tokens session cookie header headers body content context ctx
min_value max_value step steps wizard tab tabs menu nav navbar sidebar header footer layout container
wrapper section sections group groups entry entries record records instance instances obj objs val vals
src dist lib assets static public v1 v2 v3 model models interface script lang define only span testing empty full typeof generate flex initial screen
library stash mock test spec wrapper render vitest jest expect tmp temp other others all any some each every one two three foo bar baz test_data mock_data utils_test
""".split())

SYNONYM_GROUPS = [
    {"customer", "client", "buyer", "purchaser", "retailer", "account"},
    {"seller", "vendor", "supplier", "brand", "merchant", "manufacturer"},
    {"product", "item", "sku", "listing", "good"},
    {"order", "purchase", "transaction", "sale"},
    {"company", "organization", "org", "tenant", "business", "account"},
    {"user", "member", "person", "profile"},
    {"invoice", "bill", "statement"},
    {"shipment", "delivery", "fulfillment", "fulfilment", "dispatch"},
    {"license", "licence", "permit"},
    {"location", "store", "facility", "site", "warehouse"},
    {"price", "cost", "rate", "amount"},
    {"payment", "charge", "transaction"},
    {"cancel", "void", "revoke"},
    {"discount", "promotion", "promo", "coupon", "deal"},
]
ABBREVIATIONS = {"org": "organization", "qty": "quantity", "addr": "address", "txn": "transaction",
                 "acct": "account", "cust": "customer", "prod": "product", "inv": "inventory",
                 "amt": "amount", "pmt": "payment", "dept": "department", "mgr": "manager", "co": "company"}

TS_TYPE_RE = re.compile(r"^\s*(?:export\s+)?(?:declare\s+)?(interface|type|enum)\s+([A-Z]\w*)", re.M)
TS_ENUM_BODY_RE = re.compile(r"\benum\s+([A-Z]\w*)\s*\{([^}]*)\}", re.S)
TS_UNION_RE = re.compile(r"\btype\s+([A-Z]\w*)\s*=\s*((?:\s*\|?\s*['\"][^'\"]+['\"]\s*){2,})")
JAVA_ENUM_BODY_RE = re.compile(r"\benum\s+(?:class\s+)?([A-Z]\w*)[^{]*\{([^;}]*)", re.S)
PY_TABLE_RE = re.compile(r"""^\s*(?:db_table|__tablename__)\s*=\s*['"]([\w.]+)['"]""", re.M)
JPA_TABLE_RE = re.compile(r"""@Table\(\s*name\s*=\s*"(\w+)\"""")
SQL_TABLE_RE = re.compile(r"""\bcreate\s+table\s+(?:if\s+not\s+exists\s+)?[`"\[]?(?:\w+[`"\]]?\.[`"\[]?)?(\w+)""",
                          re.I)
RAILS_TABLE_RE = re.compile(r"""\bcreate_table\s+[:'"](\w+)""")
PRISMA_MODEL_RE = re.compile(r"^\s*model\s+(\w+)\s*\{", re.M)
ROUTE_PATH_RE = re.compile(r"""\b(?:path|re_path)\s*[:(]\s*r?['"]\^?(/?[\w\-/:<>{}.*?$]+)['"]""")
IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
CAMEL_SPLIT_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")
COMMENT_PREFIX_RE = re.compile(r"^\s*(?:/\*\*?|\*/?|//+|#+|<!--|\"\"\"|''')\s?")
NOISE_COMMENT_RE = re.compile(r"eslint|@ts-|prettier|noqa|type:\s*ignore|pylint|TODO|FIXME|copyright|license",
                              re.I)
GENERATED_HEADER_RE = re.compile(r"auto[- ]?generated|@generated|do not edit|generated by", re.I)
ENUM_BASES = ("Enum", "TextChoices", "IntegerChoices", "Choices", "StrEnum", "IntEnum", "IntFlag", "Flag")
MODEL_BASES = ("models.Model", "Model", "ApplicationRecord", "ActiveRecord::Base", "db.Model", "DeclarativeBase",
               "SQLModel")


def split_words(name: str) -> list[str]:
    words = []
    for part in re.split(r"[_\-\s./:]+", name):
        words += [w.lower() for w in CAMEL_SPLIT_RE.findall(part)]
    return [w for w in words if w and not w.isdigit()]


def singular(word: str) -> str:
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and word.endswith(("ses", "xes", "ches", "shes")):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def domain_base(name: str) -> str:
    """Strip technical prefixes and suffixes: `BaseOrderLineItemSerializer` -> `OrderLineItem`."""
    base = name
    changed = True
    while changed and base:
        changed = False
        for suf in TECH_SUFFIXES:
            if base.endswith(suf) and len(base) > len(suf):
                base, changed = base[: -len(suf)], True
                break
        for pre in TECH_PREFIXES:
            if base.startswith(pre) and len(base) > len(pre) and base[len(pre)].isupper():
                base, changed = base[len(pre):], True
                break
    return base


def term_key(name: str) -> str:
    words = [singular(w) for w in split_words(name)]
    return " ".join(words)


def is_domain(key: str) -> bool:
    words = key.split()
    return bool(words) and not all(w in STOPWORDS or len(w) < 3 for w in words)


def comment_above(lines: list[str], line_no: int) -> str:
    """First sentence of the comment block right above `line_no` (1-based), skipping decorators."""
    i = line_no - 2
    while i >= 0 and lines[i].strip().startswith("@"):
        i -= 1
    block = []
    while i >= 0 and len(block) < COMMENT_LOOKBACK_LINES:
        raw = lines[i].strip()
        if not raw or not COMMENT_PREFIX_RE.match(lines[i]) or raw.startswith(("#!", "#include")):
            break
        text = COMMENT_PREFIX_RE.sub("", lines[i]).strip().rstrip("*/").strip()
        if text and not text.startswith("@"):
            block.insert(0, text)
        i -= 1
    text = " ".join(block).strip()
    if not text or NOISE_COMMENT_RE.search(text):
        return ""
    return re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0][:160]


class Glossary:
    def __init__(self):
        self.terms: dict[str, dict] = {}

    def add(self, name: str, kind: str, file: str, line: int, meaning: str = "", source: str = "",
            detail: str = ""):
        key = term_key(name)
        if not is_domain(key):
            return
        t = self.terms.setdefault(key, {"key": key, "names": Counter(), "kinds": set(), "definitions": [],
                                        "meaning": "", "meaning_source": "", "values": []})
        t["names"][name] += 1
        t["kinds"].add(kind)
        if len(t["definitions"]) < 12:
            t["definitions"].append({"file": file, "line": line, "kind": kind, "name": name, "detail": detail})
        if meaning and not t["meaning"]:
            t["meaning"], t["meaning_source"] = meaning, source or f"{file}:{line}"

    def display_name(self, t: dict) -> str:
        """Prefer how a class or type spells the term over a route or table spelling."""
        named = Counter({d["name"]: 0 for d in t["definitions"] if d["kind"] not in {"route", "table"}})
        for n in named:
            named[n] = t["names"][n]
        return (named or t["names"]).most_common(1)[0][0]


def collect(root: Path, pmap: dict) -> tuple[Glossary, Counter, dict, list]:
    g = Glossary()
    inventory = pmap.get("inventory") or [{"path": f["path"], "lang": f["lang"]} for f in pmap["files"]]
    code_files = [e["path"] for e in inventory if e["lang"] in CODE_LANGS]
    schema_files = [e for e in inventory if e["lang"] in SCHEMA_LANGS]
    headers = {s["id"]: s.get("header", "") for s in pmap.get("symbols", [])}
    sources: dict[str, list[str]] = {}

    def lines_of(path: str) -> list[str]:
        if path not in sources:
            try:
                sources[path] = (root / path).read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                sources[path] = []
        return sources[path]

    # compact identifier (`order_item`, `OrderItems` -> `orderitem`) -> number of files that use it
    doc_freq: Counter = Counter()
    generated: set[str] = set()
    for path in code_files:
        text = "\n".join(lines_of(path))
        if GENERATED_HEADER_RE.search(text[:2048]):
            generated.add(path)
        for token in {compact(i) for i in IDENT_RE.findall(text)}:
            doc_freq[token] += 1
    # word -> files whose function, class or type names contain it
    word_freq: Counter = Counter()
    word_first_file: dict[str, str] = {}
    names_by_file = defaultdict(set)
    for sym in pmap.get("symbols", []):
        names_by_file[sym["file"]].add(sym["name"])

    table_flags = []
    classes_by_file = defaultdict(list)
    for c in pmap.get("classes", []):
        classes_by_file[c["file"]].append(c)
        is_enum = any(b.split(".")[-1] in ENUM_BASES for b in c.get("bases", []))
        is_model = any(b in MODEL_BASES or b.endswith("models.Model") for b in c.get("bases", []))
        kind = "enum" if is_enum else "model" if is_model else "class"
        lines = lines_of(c["file"])
        meaning, source = headers.get(c["id"], ""), ""
        if not meaning and lines and c["file"] not in generated:
            meaning = comment_above(lines, c["line"])
        values = [f for f in c.get("fields", []) if f.isupper()] if is_enum else []
        if not meaning and values:
            meaning, source = "One of: " + ", ".join(values[:8]) + (" ..." if len(values) > 8 else ""), "enum values"
        name = domain_base(c["name"]) or c["name"]
        g.add(name, kind, c["file"], c["line"], meaning, source, detail=c["name"] if name != c["name"] else "")

    for path in code_files:
        lines = lines_of(path)
        text = "\n".join(lines)
        if not text:
            continue
        line_at = _line_finder(text)
        if path.endswith((".ts", ".tsx", ".vue", ".mts", ".cts")):
            for m in TS_TYPE_RE.finditer(text):
                ln = line_at(m.start(2))
                names_by_file[path].add(m.group(2))
                name = domain_base(m.group(2)) or m.group(2)
                meaning = "" if path in generated else comment_above(lines, ln)
                g.add(name, m.group(1), path, ln, meaning, detail=m.group(2))
            for m in TS_ENUM_BODY_RE.finditer(text):
                vals = [v.split("=")[0].strip() for v in m.group(2).split(",")]
                vals = [v for v in vals if re.fullmatch(r"\w+", v)]
                if vals:
                    _set_values(g, m.group(1), vals)
            for m in TS_UNION_RE.finditer(text):
                vals = re.findall(r"['\"]([^'\"]+)['\"]", m.group(2))
                _set_values(g, m.group(1), vals)
        if path.endswith((".java", ".kt")):
            for m in JAVA_ENUM_BODY_RE.finditer(text):
                vals = re.findall(r"\b([A-Z][A-Z0-9_]+)\b", m.group(2))
                if vals:
                    _set_values(g, m.group(1), vals)
        for regex in (PY_TABLE_RE, JPA_TABLE_RE):
            for m in regex.finditer(text):
                ln = line_at(m.start(1))
                table = m.group(1).split(".")[-1]
                owner = _class_before(classes_by_file[path], ln, after=regex is JPA_TABLE_RE)
                g.add(table, "table", path, ln, detail=f"model {owner}" if owner else "")
                if owner and not set(term_key(domain_base(owner)).split()) & set(term_key(table).split()):
                    table_flags.append({"names": [owner, table], "reason": f"model `{owner}` is stored in table "
                                        f"`{table}`", "where": f"{path}:{ln}"})
        for m in RAILS_TABLE_RE.finditer(text):
            g.add(m.group(1), "table", path, line_at(m.start(1)))
        if path.endswith(("urls.py", ".ts", ".js", ".vue", ".tsx", ".jsx")) or "route" in path.lower():
            for m in ROUTE_PATH_RE.finditer(text):
                _add_route(g, m.group(1), path, line_at(m.start(1)))

    for e in schema_files:
        text = "\n".join(lines_of(e["path"]))
        line_at = _line_finder(text)
        for regex, kind in ((SQL_TABLE_RE, "table"), (PRISMA_MODEL_RE, "model")):
            for m in regex.finditer(text):
                g.add(m.group(1), kind, e["path"], line_at(m.start(1)))

    for ep in pmap.get("endpoints", []):
        _add_route(g, ep["path"], ep["file"], ep["line"])

    for path in sorted(names_by_file):
        for w in {singular(w) for n in names_by_file[path] for w in split_words(n)}:
            word_freq[w] += 1
            word_first_file.setdefault(w, path)
    for t in g.terms.values():
        t["definitions"].sort(key=lambda d: (d["file"] in generated, d["kind"] in {"route", "table"}))
    return g, doc_freq, word_freq, word_first_file, table_flags


def compact(name: str) -> str:
    return singular(re.sub(r"[_\-]", "", name.lower()))


def _line_finder(text: str):
    newlines = [i for i, ch in enumerate(text) if ch == "\n"]
    return lambda pos: bisect_right(newlines, pos - 1) + 1


def _class_before(classes: list[dict], line: int, after: bool = False) -> str:
    if after:
        nxt = [c for c in classes if c["line"] >= line]
        return min(nxt, key=lambda c: c["line"])["name"] if nxt else ""
    prev = [c for c in classes if c["line"] <= line]
    return max(prev, key=lambda c: c["line"])["name"] if prev else ""


def _set_values(g: Glossary, name: str, values: list[str]):
    key = term_key(domain_base(name) or name)
    t = g.terms.get(key)
    if not t:
        return
    t["values"] = values[:20]
    if not t["meaning"]:
        t["meaning"] = "One of: " + ", ".join(values[:8]) + (" ..." if len(values) > 8 else "")
        t["meaning_source"] = "enum values"


def _add_route(g: Glossary, path: str, file: str, line: int):
    for seg in path.strip("^$/").split("/"):
        if not seg or seg.startswith((":", "<", "{", "*", "(")) or not re.fullmatch(r"[A-Za-z][\w\-]*", seg):
            continue
        g.add(seg, "route", file, line, detail=path)


def find_synonyms(terms: list[dict], table_flags: list) -> list[dict]:
    flags = []
    single = {t["key"]: t for t in terms if " " not in t["key"]}
    for group in SYNONYM_GROUPS:
        present = sorted(w for w in group if w in single)
        if len(present) >= 2:
            flags.append({"names": [single[w]["name"] for w in present],
                          "reason": "common synonyms for one concept; check whether they mean the same thing here"})
    for short, full in ABBREVIATIONS.items():
        if short in single and full in single:
            flags.append({"names": [single[short]["name"], single[full]["name"]], "reason": "abbreviation"})
    keys = sorted(single)
    for a, b in combinations(keys, 2):
        if a[:2] != b[:2] or min(len(a), len(b)) < 5:
            continue
        if SequenceMatcher(None, a, b).ratio() >= NEAR_SPELLING_RATIO:
            flags.append({"names": [single[a]["name"], single[b]["name"]], "reason": "near-identical spelling"})
    seen, unique = set(), []
    for f in flags + table_flags:
        names = frozenset(n.lower() for n in f["names"])
        if names not in seen:
            seen.add(names)
            unique.append(f)
    return unique


def build(root: Path, pmap: dict, max_terms: int) -> dict:
    g, doc_freq, word_freq, word_first_file, table_flags = collect(root, pmap)
    terms = []
    for key, t in g.terms.items():
        usage = max((doc_freq.get(compact(n), 0) for n in t["names"]), default=0)
        terms.append({
            "name": g.display_name(t), "key": key, "kinds": sorted(t["kinds"]),
            "usage_files": usage, "meaning": t["meaning"] or "to define",
            "meaning_source": t["meaning_source"], "values": t["values"],
            "definitions": t["definitions"], "names": dict(t["names"]),
        })
    terms.sort(key=lambda t: (-t["usage_files"], t["key"]))
    terms = terms[:max_terms]

    known_words = {w for t in terms for w in t["key"].split()}
    identifier_words = []
    for word, n in word_freq.most_common():
        if len(identifier_words) >= TOP_IDENTIFIER_WORDS or n < MIN_IDENTIFIER_FILES:
            break
        if word in STOPWORDS or word in known_words or len(word) < 4 or not word.isalpha():
            continue
        identifier_words.append({"name": word, "usage_files": n, "first_file": word_first_file[word],
                                 "meaning": "to define"})

    return {"terms": terms, "identifier_words": identifier_words, "synonym_flags": find_synonyms(terms, table_flags),
            "stats": {"terms": len(terms), "to_define": sum(1 for t in terms if t["meaning"] == "to define"),
                      "identifier_words": len(identifier_words)}}


def render_markdown(gl: dict) -> str:
    s = gl["stats"]
    lines = ["# Domain glossary (draft)", "",
             f"{s['terms']} terms drafted from code, {s['to_define']} still marked _to define_. "
             "Usage = files that use one of the term's names as an identifier.", ""]
    if gl["synonym_flags"]:
        lines += ["## Possibly the same concept", ""]
        for f in gl["synonym_flags"]:
            where = f" ({f['where']})" if f.get("where") else ""
            lines.append(f"- {' / '.join(f'**{n}**' for n in f['names'])}: {f['reason']}{where}")
        lines.append("")
    lines += ["## Terms", ""]
    for t in gl["terms"]:
        meaning = t["meaning"] if t["meaning"] != "to define" else "_to define_"
        src = f" (from {t['meaning_source']})" if t["meaning_source"] else ""
        lines.append(f"**{t['name']}** ({', '.join(t['kinds'])}; {t['usage_files']} files):")
        lines.append(f"{meaning}{src}")
        defs = ", ".join(f"`{d['file']}:{d['line']}`" + (f" {d['detail']}" if d["detail"] else "")
                         for d in t["definitions"][:4])
        lines.append(f"_Defined_: {defs}")
        others = [n for n in t["names"] if n != t["name"]]
        if others:
            lines.append(f"_Also written_: {', '.join(others[:6])}")
        lines.append("")
    if gl["identifier_words"]:
        lines += ["## Frequent identifier words", "",
                  "Words that recur in function, class and type names across files but have no term of their own.", ""]
        for w in gl["identifier_words"]:
            lines.append(f"- **{w['name']}** ({w['usage_files']} files, first in `{w['first_file']}`): _to define_")
        lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project_map", help="Path to project-map.json")
    ap.add_argument("--output-dir", "-o", help="Where to write glossary.json/.md (default: next to the map)")
    ap.add_argument("--max-terms", type=int, default=MAX_TERMS, help=f"Terms to keep (default {MAX_TERMS})")
    args = ap.parse_args()

    map_path = Path(args.project_map)
    if not map_path.is_file():
        sys.exit(f"project map not found: {map_path}. Run map_project.py first.")
    pmap = json.loads(map_path.read_text())
    out = Path(args.output_dir) if args.output_dir else map_path.parent
    out.mkdir(parents=True, exist_ok=True)

    gl = build(Path(pmap["root"]), pmap, args.max_terms)
    (out / "glossary.json").write_text(json.dumps(gl, indent=2))
    (out / "glossary.md").write_text(render_markdown(gl))
    s = gl["stats"]
    print(f"Wrote {out / 'glossary.md'}: {s['terms']} terms ({s['to_define']} to define), "
          f"{len(gl['synonym_flags'])} synonym flags, {s['identifier_words']} identifier words", file=sys.stderr)


if __name__ == "__main__":
    main()
