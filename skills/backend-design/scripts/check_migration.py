#!/usr/bin/env python3
"""
Pre-write check for database migration files.

Scans migration files for the dangerous patterns from the migration-safety
skill and warns. Does NOT block. The point is to flag, not gate.

Triggers on file paths that look like migrations:
- contains "/migrations/" or "\\migrations\\"
- contains "/migrate/" or "\\migrate\\"
- contains "/alembic/" or "\\alembic\\"
- filename matches a typical migration prefix (V123__, 20240101_, 0001_, etc.)

A Django migration (a .py file under migrations/ that defines
`class Migration(migrations.Migration)`) is parsed with `ast`, without importing
Django, and its operations (AddField, RemoveField, AlterField, AddIndex,
RunPython, ...) are checked; the SQL rules run on the strings passed to RunSQL.
Every other migration file is matched against the SQL rules as raw text.

Usage:
  check_migration.py <files>    check files on disk
  check_migration.py --stdin    check raw SQL piped in, such as `manage.py sqlmigrate` output
  check_migration.py            read Claude Code PreToolUse hook JSON from stdin

Emits warnings to stderr, exits 0 (allow).
"""

import ast
import json
import os
import re
import subprocess
import sys


MIGRATION_PATH_PATTERNS = [
    re.compile(r"[\\/](migrations?|migrate|alembic|db[\\/]migrate|knex[\\/]migrations)[\\/]", re.IGNORECASE),
]

MIGRATION_FILENAME_PATTERNS = [
    re.compile(r"^V\d+__", re.IGNORECASE),
    re.compile(r"^\d{4,}[_-]"),
    re.compile(r"^\d{8,14}[_-]"),
]


DANGER_RULES = [
    {
        "name": "ALTER ... NOT NULL without DEFAULT",
        "pattern": re.compile(
            r"ALTER\s+TABLE\s+\S+\s+(?:ALTER\s+COLUMN\s+\S+\s+SET\s+NOT\s+NULL|ADD\s+COLUMN\s+\S+\s+(?:(?!\bDEFAULT\b)[^;])*?\bNOT\s+NULL(?![^;]*\bDEFAULT\b))",
            re.IGNORECASE | re.DOTALL,
        ),
        "why": "On large tables this takes an exclusive lock and rewrites every row. Split into 3 migrations: add nullable, backfill in a separate script, then SET NOT NULL.",
    },
    {
        "name": "DROP COLUMN",
        "pattern": re.compile(r"ALTER\s+TABLE\s+\S+\s+DROP\s+COLUMN\b", re.IGNORECASE),
        "why": "Drops break any service version still reading the column. Deprecate reads, deprecate writes, then drop in a separate deploy.",
    },
    {
        "name": "DROP TABLE",
        "pattern": re.compile(r"\bDROP\s+TABLE\b", re.IGNORECASE),
        "why": "Irreversible without backups. Confirm the table is no longer referenced anywhere and document the rollback plan in the PR description.",
    },
    {
        "name": "RENAME in one shot",
        "pattern": re.compile(r"ALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?:ONLY\s+)?\S+\s+RENAME\s+", re.IGNORECASE),
        "why": "Breaks all app instances during a rolling deploy. Use add-new + dual-write + switch + drop-old across multiple migrations.",
    },
    {
        "name": "CREATE INDEX without CONCURRENTLY",
        "pattern": re.compile(r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?!CONCURRENTLY\b)", re.IGNORECASE),
        "why": "Locks writes on the table while building. Use `CREATE INDEX CONCURRENTLY` for any non-empty table.",
    },
    {
        "name": "ADD CONSTRAINT CHECK without NOT VALID",
        "pattern": re.compile(r"ADD\s+CONSTRAINT\s+\S+\s+CHECK\s*\((?:(?!NOT\s+VALID).)*\)\s*;?$", re.IGNORECASE | re.MULTILINE),
        "why": "Scans every row under a lock. Use `ADD CONSTRAINT ... CHECK (...) NOT VALID`, then `VALIDATE CONSTRAINT` in a later step.",
    },
    {
        "name": "FOREIGN KEY without NOT VALID",
        "pattern": re.compile(r"ADD\s+(?:CONSTRAINT\s+\S+\s+FOREIGN\s+KEY|COLUMN\s+[^;]*?\bREFERENCES\b)(?![^;]*\bNOT\s+VALID\b)", re.IGNORECASE),
        "why": "Validates every row while blocking writes to both tables. Add it `NOT VALID`, then `VALIDATE CONSTRAINT` in a later step.",
    },
    {
        "name": "UNIQUE without USING INDEX",
        "pattern": re.compile(r"ADD\s+(?:CONSTRAINT\s+\S+\s+UNIQUE(?![^;]*\bUSING\s+INDEX\b)|COLUMN\s+[^;]*?\bUNIQUE\b)", re.IGNORECASE),
        "why": "Builds the unique index while blocking writes. Build it with `CREATE UNIQUE INDEX CONCURRENTLY`, then `ADD CONSTRAINT ... UNIQUE USING INDEX`.",
    },
    {
        "name": "ALTER COLUMN ... TYPE",
        "pattern": re.compile(r"ALTER\s+COLUMN\s+\S+\s+(?:SET\s+DATA\s+)?TYPE\b", re.IGNORECASE),
        "why": "Rewrites the table under an ACCESS EXCLUSIVE lock unless the change is binary-compatible (varchar to text, a longer varchar, more numeric digits with the same scale). Otherwise add a new column, backfill, switch, drop the old one.",
    },
    {
        "name": "CONCURRENTLY inside a transaction",
        "pattern": re.compile(r"^\s*BEGIN\s*;.*\bCONCURRENTLY\b", re.IGNORECASE | re.MULTILINE | re.DOTALL),
        "why": "Postgres refuses CONCURRENTLY inside a transaction block. Run it in a non-transactional migration (`atomic = False` in Django).",
    },
    {
        "name": "Embedded data backfill (UPDATE/INSERT in migration)",
        "pattern": re.compile(r"^\s*(UPDATE|INSERT)\s+", re.IGNORECASE | re.MULTILINE),
        "why": "Long-running data changes inside a migration hold locks for the duration. Move to a separate, batched, restartable script.",
    },
]


def is_migration_path(path: str) -> bool:
    if not path:
        return False
    for pat in MIGRATION_PATH_PATTERNS:
        if pat.search(path):
            return True
    basename = os.path.basename(path)
    for pat in MIGRATION_FILENAME_PATTERNS:
        if pat.match(basename):
            return True
    return False


def extract_content(tool_name: str, tool_input: dict) -> str:
    if tool_name == "Write":
        return tool_input.get("content", "") or ""
    if tool_name == "Edit":
        return (tool_input.get("new_string", "") or "") + "\n" + (tool_input.get("old_string", "") or "")
    return ""


def sql_findings(content: str) -> list:
    return [rule for rule in DANGER_RULES if rule["pattern"].search(content)]


def report_sql(path: str, findings: list) -> None:
    print("", file=sys.stderr)
    print("[backend-design] migration-safety review for {}".format(path), file=sys.stderr)
    for f in findings:
        print("  - {}".format(f["name"]), file=sys.stderr)
        print("    {}".format(f["why"]), file=sys.stderr)
    print("  See: skills/migration-safety/README.md. Run `/backend-design review-migration` for a full review.", file=sys.stderr)
    print("", file=sys.stderr)


DJANGO_MIGRATION_CLASS = re.compile(r"^class\s+Migration\s*\(\s*(?:migrations\.)?Migration\s*\)", re.MULTILINE)
DJANGO_MIGRATION_DIR = re.compile(r"[\\/]migrations[\\/]")
BASE_REFS = ("origin/HEAD", "origin/main", "origin/master", "main", "master")
_shipped_cache = {}


def shipped_on_base(path: str) -> bool:
    """True when the file already exists on the repo's default branch, so it has run in production and can't change."""
    path = os.path.abspath(path)
    if path in _shipped_cache:
        return _shipped_cache[path]
    shipped = False
    try:
        top = subprocess.run(["git", "-C", os.path.dirname(path), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=10)
        if top.returncode == 0:
            rel = os.path.relpath(os.path.realpath(path), os.path.realpath(top.stdout.strip()))
            for ref in BASE_REFS:
                found = subprocess.run(["git", "-C", top.stdout.strip(), "cat-file", "-e", "{}:{}".format(ref, rel)],
                                       capture_output=True, timeout=10)
                if found.returncode == 0:
                    shipped = True
                    break
    except (OSError, subprocess.SubprocessError):
        shipped = False
    _shipped_cache[path] = shipped
    return shipped

INDEX_SAFE = (
    "Add the field without the index (db_index=False), then add it with AddIndexConcurrently in its own migration "
    "with atomic = False, after a RunSQL `DROP INDEX CONCURRENTLY IF EXISTS` so a retry works."
)
UNIQUE_SAFE = (
    "Build the index with RunSQL `CREATE UNIQUE INDEX CONCURRENTLY`, attach it with "
    "`ADD CONSTRAINT ... UNIQUE USING INDEX` under `SET lock_timeout`, all in SeparateDatabaseAndState with "
    "atomic = False."
)
DROP_SAFE = (
    "Expand/contract: ship a state-only RemoveField/DeleteModel in SeparateDatabaseAndState first, then drop the "
    "column or table with RunSQL and `SET LOCAL lock_timeout` in a later release. "
    "Fine as is if an earlier release already stopped reading and writing it."
)
BACKFILL_SAFE = (
    "Batch it: atomic = False, one short transaction per batch of primary keys with `SET LOCAL lock_timeout`, "
    "rerunnable until no rows match, "
    "or move it to a separate rerunnable job."
)
NOT_VALID_SAFE = (
    "Use AddConstraintNotValid (django.contrib.postgres.operations), then ValidateConstraint in a later migration; "
    "VALIDATE only takes a SHARE UPDATE EXCLUSIVE lock (postgres-best-practices schema-online-ddl.md)."
)
REWRITE_SAFE = "Add a new column of the new type, backfill it in batches, switch reads, and drop the old column in a later release."

# Field classes stored as varchar, matched by suffix so subclasses (ProcessedImageField, ...) count too.
VARCHAR_FIELDS = ("CharField", "SlugField", "EmailField", "URLField", "FilePathField", "FileField", "ImageField")
FK_FIELDS = {"ForeignKey", "OneToOneField"}
# AlterField attributes that change the column, its constraints or its indexes; the rest (choices, help_text,
# validators, blank, on_delete, ...) only change Python state, and sqlmigrate shows no SQL for them.
DB_FIELD_ATTRS = (
    "null", "unique", "db_index", "primary_key", "max_length", "max_digits", "decimal_places", "db_column",
    "db_default", "db_constraint", "db_collation", "db_comment", "to", "db_tablespace",
)
QUERYSET_SOURCES = {"objects", "_default_manager", "_base_manager"}
DML = re.compile(r"\b(?:UPDATE\s+\S+\s+SET|INSERT\s+INTO|DELETE\s+FROM|MERGE\s+INTO)\b", re.IGNORECASE)
DDL = re.compile(r"\b(?:CREATE|ALTER|DROP|COMMENT\s+ON|TRUNCATE)\b", re.IGNORECASE)


class Unknown:
    """A value that can't be known without running the migration (a call, an import, a variable)."""


UNKNOWN = Unknown()


def call_name(node) -> str:
    if isinstance(node, ast.Call):
        node = node.func
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


def op_arg(call, index, name):
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    if index is not None and index < len(call.args) and not any(isinstance(a, ast.Starred) for a in call.args[: index + 1]):
        return call.args[index]
    return None


def literal(node, consts):
    if node is None:
        return None
    if isinstance(node, ast.Name) and node.id in consts:
        return consts[node.id]
    if isinstance(node, ast.JoinedStr):
        return joined_str(node, consts)
    try:
        return ast.literal_eval(node)
    except Exception:
        return UNKNOWN


def joined_str(node, consts) -> str:
    parts = []
    for value in node.values:
        if isinstance(value, ast.Constant):
            parts.append(str(value.value))
        elif isinstance(value, ast.FormattedValue) and isinstance(value.value, ast.Name) and value.value.id in consts:
            parts.append(str(consts[value.value.id]))
        else:
            parts.append("{}")
    return "".join(parts)


def module_constants(tree) -> dict:
    consts = {}
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            value = literal(stmt.value, consts)
            if value is not UNKNOWN:
                consts[stmt.targets[0].id] = value
    return consts


def sql_text(node, consts) -> str:
    if node is None:
        return ""
    if isinstance(node, (ast.List, ast.Tuple)):
        return "\n".join(sql_text(elt, consts) for elt in node.elts)
    value = literal(node, consts)
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return "\n".join(v if isinstance(v, str) else str(v[0]) for v in value if v)
    return ""


def field_spec(node, consts):
    """(field class name, {keyword: value}) for a field constructor call, or None."""
    if not isinstance(node, ast.Call):
        return None
    return call_name(node), {kw.arg: literal(kw.value, consts) for kw in node.keywords if kw.arg}


def is_null(spec) -> bool:
    return spec[1].get("null") is True


def is_unique(spec) -> bool:
    cls, kw = spec
    if "unique" in kw:
        return kw["unique"] is True
    return cls == "OneToOneField" or kw.get("primary_key") is True


def is_indexed(spec) -> bool:
    cls, kw = spec
    if "db_index" in kw:
        return kw["db_index"] is True
    return cls in ("ForeignKey", "SlugField")


def has_fk_constraint(spec) -> bool:
    return spec[0] in FK_FIELDS and spec[1].get("db_constraint") is not False


def has_default(spec) -> bool:
    """True when Django fills existing rows while adding the column: default=, auto_now(_add), or '' for a blank text field."""
    cls, kw = spec
    if "default" in kw or kw.get("auto_now") is True or kw.get("auto_now_add") is True:
        return True
    return kw.get("blank") is True and (is_varchar(cls) or cls == "TextField")


def is_varchar(cls) -> bool:
    # CICharField and CIEmailField are citext columns, not varchar.
    return cls.endswith(VARCHAR_FIELDS) and not cls.startswith("CI")


def is_decimal(cls) -> bool:
    return cls.endswith("DecimalField") or cls.endswith("MoneyField")


def migration_class(tree):
    for stmt in tree.body:
        if isinstance(stmt, ast.ClassDef) and stmt.name == "Migration":
            return stmt
    return None


def class_attr(cls, name):
    for stmt in cls.body:
        if isinstance(stmt, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in stmt.targets):
            return stmt.value
    return None


def operation_calls(node):
    if isinstance(node, (ast.List, ast.Tuple)):
        return [elt for elt in node.elts if isinstance(elt, ast.Call)]
    return []


_parsed = {}


def parse_migration(path):
    """(operations, constants) of a migration file on disk, or None when it isn't a parseable Django migration."""
    if path not in _parsed:
        _parsed[path] = None
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                tree = ast.parse(fh.read())
        except (OSError, SyntaxError, ValueError):
            return None
        cls = migration_class(tree)
        if cls is not None:
            _parsed[path] = (operation_calls(class_attr(cls, "operations")), module_constants(tree))
    return _parsed[path]


def apply_state(op, state, consts) -> None:
    """Replay one operation on {model: {field: spec}}, the way Django's migration state would."""
    name = call_name(op)
    if name == "SeparateDatabaseAndState":
        for inner in operation_calls(op_arg(op, 1, "state_operations")):
            apply_state(inner, state, consts)
        return
    if name == "RunSQL":
        for inner in operation_calls(op_arg(op, None, "state_operations")):
            apply_state(inner, state, consts)
        return
    if name == "CreateModel":
        model = literal(op_arg(op, 0, "name"), consts)
        fields = op_arg(op, 1, "fields")
        if isinstance(model, str) and isinstance(fields, (ast.List, ast.Tuple)):
            state[model.lower()] = {}
            for item in fields.elts:
                if isinstance(item, ast.Tuple) and len(item.elts) == 2:
                    field_name = literal(item.elts[0], consts)
                    spec = field_spec(item.elts[1], consts)
                    if isinstance(field_name, str) and spec:
                        state[model.lower()][field_name] = spec
        return
    if name in ("DeleteModel", "RenameModel"):
        old = literal(op_arg(op, 0, "old_name" if name == "RenameModel" else "name"), consts)
        new = literal(op_arg(op, 1, "new_name"), consts) if name == "RenameModel" else None
        if isinstance(old, str):
            fields = state.pop(old.lower(), None)
            if isinstance(new, str) and fields is not None:
                state[new.lower()] = fields
        return
    model = literal(op_arg(op, 0, "model_name"), consts)
    if not isinstance(model, str):
        return
    fields = state.setdefault(model.lower(), {})
    if name in ("AddField", "AlterField"):
        field_name = literal(op_arg(op, 1, "name"), consts)
        spec = field_spec(op_arg(op, 2, "field"), consts)
        if isinstance(field_name, str) and spec:
            fields[field_name] = spec
    elif name == "RemoveField":
        fields.pop(literal(op_arg(op, 1, "name"), consts), None)
    elif name == "RenameField":
        old, new = literal(op_arg(op, 1, "old_name"), consts), literal(op_arg(op, 2, "new_name"), consts)
        if isinstance(old, str) and isinstance(new, str) and old in fields:
            fields[new] = fields.pop(old)


def prior_state(path):
    """Model fields as left by the migrations before `path` in the same folder, in file name order, or None."""
    directory, base = os.path.split(os.path.abspath(path))
    try:
        names = sorted(n for n in os.listdir(directory) if n.endswith(".py") and n != "__init__.py" and n < base)
    except OSError:
        return None
    state = {}
    for name in names:
        parsed = parse_migration(os.path.join(directory, name))
        if parsed:
            for op in parsed[0]:
                apply_state(op, state, parsed[1])
    return state


class DjangoCheck:
    def __init__(self, path, tree):
        self.path = path
        self.consts = module_constants(tree)
        self.functions = {s.name: s for s in tree.body if isinstance(s, ast.FunctionDef)}
        self.cls = migration_class(tree)
        self.atomic = literal(class_attr(self.cls, "atomic"), self.consts) is not False
        self.operations = operation_calls(class_attr(self.cls, "operations"))
        self.created = set()
        self.deleted = set()
        self.findings = []
        self.schema_line = None
        self.data_line = None
        self.state = None
        self.state_loaded = False
        self.top_index = 0
        self.sql_in_file = ""
        for op in self.walk_database_ops(self.operations):
            if call_name(op) == "CreateModel":
                model = literal(op_arg(op, 0, "name"), self.consts)
                if isinstance(model, str):
                    self.created.add(model.lower())
            elif call_name(op) == "DeleteModel":
                model = literal(op_arg(op, 0, "name"), self.consts)
                if isinstance(model, str):
                    self.deleted.add(model.lower())
            elif call_name(op) == "RunSQL":
                self.sql_in_file += sql_text(op_arg(op, 0, "sql"), self.consts) + "\n"

    def walk_database_ops(self, ops):
        for op in ops:
            if call_name(op) == "SeparateDatabaseAndState":
                for inner in self.walk_database_ops(operation_calls(op_arg(op, 0, "database_operations"))):
                    yield inner
            else:
                yield op

    def prior_field(self, model, field):
        if not self.state_loaded:
            self.state_loaded = True
            self.state = prior_state(self.path) if self.path else None
            if self.state is not None:
                for op in self.operations[: self.top_index]:
                    apply_state(op, self.state, self.consts)
        if self.state is None:
            return None
        return self.state.get(model.lower(), {}).get(field)

    def warn(self, node, label, why, safe):
        self.findings.append((node.lineno, label, why, safe))

    def schema(self, node):
        if self.schema_line is None:
            self.schema_line = node.lineno

    def data(self, node):
        if self.data_line is None:
            self.data_line = node.lineno

    def run(self):
        for self.top_index, top in enumerate(self.operations):
            for op in self.walk_database_ops([top]):
                name = call_name(op)
                handler = getattr(self, "check_" + name, None)
                if handler:
                    handler(op, name)
                elif name not in ("AlterModelOptions", "AlterModelManagers"):
                    self.schema(op)
            # Earlier operations in this file are prior state for the later ones.
            if self.state is not None:
                apply_state(top, self.state, self.consts)
        if self.schema_line is not None and self.data_line is not None:
            why = "A failed run repeats or half-applies both (schema op at line {}, data op at line {}).".format(self.schema_line, self.data_line)
            if self.atomic:
                why = ("In one transaction the schema change keeps its ACCESS EXCLUSIVE lock until the data step ends, and Postgres "
                       "can fail with \"cannot ALTER TABLE because it has pending trigger events\". " + why)
            self.findings.append((self.cls.lineno, "Migration mixes schema and data operations", why,
                                  "Put the schema change and the data change in separate migrations."))
        return sorted(self.findings, key=lambda f: f[0])

    def model_of(self, op):
        model = literal(op_arg(op, 0, "model_name"), self.consts)
        return model if isinstance(model, str) else "?"

    def is_new_model(self, model):
        return model.lower() in self.created

    def check_CreateModel(self, op, name):
        """Not a schema change for the mixing check: seeding a table created in the same migration is the usual pattern."""

    def check_AddField(self, op, name):
        model = self.model_of(op)
        field = literal(op_arg(op, 1, "name"), self.consts)
        spec = field_spec(op_arg(op, 2, "field"), self.consts)
        if self.is_new_model(model) or (spec is not None and spec[0] == "ManyToManyField"):
            return
        self.schema(op)
        if spec is None:
            return
        label = "AddField {}.{}".format(model, field)
        cls, kw = spec
        if not is_null(spec) and "db_default" not in kw:
            if not has_default(spec):
                self.warn(op, label, "NOT NULL with no default, so the ALTER fails on a table that already has rows.",
                          "Add it with db_default=<value> (Django 5.0+), or null=True, backfill in a separate migration, then make it NOT NULL.")
            elif not shipped_on_base(self.path):
                self.warn(op, label, "NOT NULL with default= but no db_default. Django uses default= only to fill the existing rows and then drops "
                          "the database default, so pods still on the old code fail with a NOT NULL violation when they insert a row during the deploy.",
                          "Set db_default to the same value as default (for example default=False, db_default=False; Django 5.0+). The default "
                          "then stays in Postgres, old code can still insert, and adding the column is instant for a constant on Postgres 11+.")
        if has_fk_constraint(spec):
            why = ("Django adds the FOREIGN KEY constraint validated, which scans the whole table under the ALTER's lock and "
                   "blocks writes to the referenced table meanwhile")
            if is_indexed(spec) or is_unique(spec):
                why += ", and builds its index without CONCURRENTLY, which also blocks writes for a full scan"
            self.warn(op, label, why + ".",
                      "Add the field with db_constraint=False and db_index=False, add the index with AddIndexConcurrently (atomic = False), "
                      "and add the constraint with RunSQL `... NOT VALID` plus `VALIDATE CONSTRAINT` in a later migration, keeping Django's state in SeparateDatabaseAndState.")
        elif is_unique(spec):
            self.warn(op, label, "unique=True builds a unique index without CONCURRENTLY, which blocks writes while it scans the table.", UNIQUE_SAFE)
        elif is_indexed(spec):
            self.warn(op, label, "db_index builds an index without CONCURRENTLY, which blocks writes while it scans the table.", INDEX_SAFE)

    def check_RemoveField(self, op, name):
        model = self.model_of(op)
        if self.is_new_model(model) or model.lower() in self.deleted:
            return
        self.schema(op)
        self.warn(op, "RemoveField {}.{}".format(model, literal(op_arg(op, 1, "name"), self.consts)),
                  "Drops the column in the same deploy that removes the field. App instances still on the old code select every "
                  "column of the model, so their queries fail until they're replaced.", DROP_SAFE)

    def check_DeleteModel(self, op, name):
        self.schema(op)
        self.warn(op, "DeleteModel {}".format(literal(op_arg(op, 0, "name"), self.consts)),
                  "Drops the table while app instances on the old code may still query it, and the data is gone for good.", DROP_SAFE)

    def check_RenameField(self, op, name):
        self.schema(op)
        old, new = literal(op_arg(op, 1, "old_name"), self.consts), literal(op_arg(op, 2, "new_name"), self.consts)
        self.warn(op, "RenameField {}.{} -> {}".format(self.model_of(op), old, new),
                  "Renames the column while app instances on the old code still query the old name, so they fail until the deploy ends.",
                  "Keep the column: set db_column='{}' on the renamed field so no SQL runs, or add a new column, dual-write, backfill, "
                  "switch reads and drop the old one in later releases.".format(old))

    def check_RenameModel(self, op, name):
        self.schema(op)
        old, new = literal(op_arg(op, 0, "old_name"), self.consts), literal(op_arg(op, 1, "new_name"), self.consts)
        self.warn(op, "RenameModel {} -> {}".format(old, new),
                  "Renames the table (and its M2M tables) unless Meta.db_table pins it, so app instances on the old code fail until the deploy ends.",
                  "Set Meta.db_table to the current table name before renaming the model, so no SQL runs.")

    def check_AlterModelTable(self, op, name):
        self.schema(op)
        self.warn(op, "AlterModelTable {}".format(literal(op_arg(op, 0, "name"), self.consts)),
                  "Renames the table while app instances on the old code still query the old name.",
                  "Keep the old db_table, or move to a new table across releases (create, dual-write, backfill, switch, drop).")

    def check_AlterField(self, op, name):
        model = self.model_of(op)
        field = literal(op_arg(op, 1, "name"), self.consts)
        new = field_spec(op_arg(op, 2, "field"), self.consts)
        label = "AlterField {}.{}".format(model, field)
        if self.is_new_model(model):
            return
        if new is None:
            self.schema(op)
            return
        old = self.prior_field(model, field)
        if old is None:
            self.schema(op)
            self.warn(op, label, "Couldn't find the field's previous definition in the earlier migrations of this folder, so type, "
                      "NOT NULL, unique and max_length changes weren't checked.",
                      "Check the exact SQL: `python manage.py sqlmigrate <app> <migration> | python3 check_migration.py --stdin`.")
            return
        changed = [a for a in DB_FIELD_ATTRS if old[1].get(a, UNKNOWN) != new[1].get(a, UNKNOWN)]
        if old[0] != new[0] or changed:
            self.schema(op)
        (old_cls, old_kw), (new_cls, new_kw) = old, new
        if old_cls != new_cls:
            binary_compatible = (is_varchar(old_cls) and (is_varchar(new_cls) or new_cls == "TextField")) or {old_cls, new_cls} == FK_FIELDS
            if not binary_compatible:
                self.warn(op, label, "Changes the type from {} to {}, which rewrites the table and its indexes under an ACCESS EXCLUSIVE "
                          "lock (no reads or writes).".format(old_cls, new_cls), REWRITE_SAFE)
        if is_null(old) and not is_null(new):
            self.warn(op, label, "Sets NOT NULL: Postgres scans the whole table under an ACCESS EXCLUSIVE lock, and the ALTER fails if any row is still NULL.",
                      "Backfill first, add CHECK (col IS NOT NULL) with AddConstraintNotValid, ValidateConstraint in a later migration, "
                      "then SET NOT NULL skips the scan (Postgres 12+).")
        if not is_unique(old) and is_unique(new):
            self.warn(op, label, "Adds unique=True, which builds a unique index without CONCURRENTLY and blocks writes while it scans the table.", UNIQUE_SAFE)
        elif not is_indexed(old) and is_indexed(new) and not is_unique(new):
            self.warn(op, label, "Adds db_index, which builds an index without CONCURRENTLY and blocks writes while it scans the table.", INDEX_SAFE)
        old_len, new_len = old_kw.get("max_length"), new_kw.get("max_length")
        if isinstance(old_len, int) and isinstance(new_len, int) and new_len < old_len:
            self.warn(op, label, "Shrinks max_length from {} to {}: the table is rewritten under an ACCESS EXCLUSIVE lock and the ALTER "
                      "fails on any longer value.".format(old_len, new_len),
                      "Check the longest stored value first, or add CHECK (length(col) <= {}) NOT VALID and validate it before shrinking.".format(new_len))
        if is_decimal(old_cls) and is_decimal(new_cls):
            old_places, new_places = old_kw.get("decimal_places"), new_kw.get("decimal_places")
            old_digits, new_digits = old_kw.get("max_digits"), new_kw.get("max_digits")
            if (isinstance(old_places, int) and isinstance(new_places, int) and old_places != new_places) or (
                isinstance(old_digits, int) and isinstance(new_digits, int) and new_digits < old_digits
            ):
                self.warn(op, label, "Changes the numeric precision ({},{} to {},{}), which rewrites the table under an ACCESS EXCLUSIVE lock."
                          .format(old_digits, old_places, new_digits, new_places), REWRITE_SAFE)
        if old_cls in FK_FIELDS and old_kw.get("db_constraint") is False and has_fk_constraint(new):
            self.warn(op, label, "Turns db_constraint on, which validates the FOREIGN KEY on every row while blocking writes to both tables.",
                      "Add the constraint with RunSQL `... NOT VALID` and `VALIDATE CONSTRAINT` in a later migration, keeping Django's state in SeparateDatabaseAndState.")

    def check_AddIndex(self, op, name):
        model = self.model_of(op)
        if self.is_new_model(model):
            return
        self.schema(op)
        self.warn(op, "AddIndex {}".format(model), "Runs CREATE INDEX without CONCURRENTLY, which blocks writes to the table while it scans every row.",
                  "Use AddIndexConcurrently in its own migration with atomic = False, after a RunSQL `DROP INDEX CONCURRENTLY IF EXISTS` "
                  "so a retry works.")

    def check_AddIndexConcurrently(self, op, name):
        self.schema(op)
        label = "{} {}".format(name, self.model_of(op))
        if self.atomic:
            self.warn(op, label, "Django refuses to run it inside a transaction, so the migration fails.", "Set atomic = False on the Migration.")
        if name == "AddIndexConcurrently" and not re.search(r"DROP\s+INDEX\s+CONCURRENTLY\s+IF\s+EXISTS", self.sql_in_file, re.IGNORECASE):
            self.warn(op, label, "A failed concurrent build leaves an INVALID index under this name, so every retry fails with \"already exists\".",
                      "Put a RunSQL `DROP INDEX CONCURRENTLY IF EXISTS \"<name>\"` before it.")

    check_RemoveIndexConcurrently = check_AddIndexConcurrently

    def check_RemoveIndex(self, op, name):
        self.schema(op)
        self.warn(op, "RemoveIndex {}".format(self.model_of(op)),
                  "DROP INDEX takes an ACCESS EXCLUSIVE lock. It's quick, but it waits behind long transactions and every query on the table queues behind it.",
                  "Use RemoveIndexConcurrently (django.contrib.postgres.operations) with atomic = False.")

    def check_AddConstraint(self, op, name):
        model = self.model_of(op)
        if self.is_new_model(model):
            return
        self.schema(op)
        kind = call_name(op_arg(op, 1, "constraint"))
        label = "AddConstraint {} {}".format(model, kind)
        if kind == "UniqueConstraint":
            self.warn(op, label, "Builds a unique index without CONCURRENTLY, which blocks writes while it scans the table.", UNIQUE_SAFE)
        elif kind == "CheckConstraint":
            self.warn(op, label, "Checks every row under an ACCESS EXCLUSIVE lock (no reads or writes) before it commits.", NOT_VALID_SAFE)
        elif kind == "ExclusionConstraint":
            self.warn(op, label, "Builds its index without CONCURRENTLY, which blocks writes while it scans the table.",
                      "Build the index concurrently first, or add the constraint in a quiet window with `SET lock_timeout`.")

    def check_AddConstraintNotValid(self, op, name):
        self.schema(op)

    def check_AlterUniqueTogether(self, op, name):
        model = literal(op_arg(op, 0, "name"), self.consts)
        value = literal(op_arg(op, 1, "unique_together"), self.consts)
        if isinstance(model, str) and self.is_new_model(model):
            return
        self.schema(op)
        if not isinstance(model, str) or not value:
            return
        self.warn(op, "AlterUniqueTogether {}".format(model),
                  "Each new tuple becomes a UNIQUE constraint built without CONCURRENTLY, which blocks writes while it scans the table.", UNIQUE_SAFE)

    def check_RunPython(self, op, name):
        self.data(op)
        if op_arg(op, 1, "reverse_code") is None:
            self.warn(op, "RunPython", "Has no reverse_code, so `migrate` can't roll back past it (IrreversibleError).",
                      "Pass reverse_code; use migrations.RunPython.noop when undoing isn't needed.")
        code = op_arg(op, 0, "code")
        func = self.functions.get(code.id) if isinstance(code, ast.Name) else None
        if func is not None:
            self.check_backfill(func)

    def check_RunSQL(self, op, name):
        sql = sql_text(op_arg(op, 0, "sql"), self.consts)
        if DML.search(sql):
            self.data(op)
        elif DDL.search(sql):
            self.schema(op)
        if op_arg(op, 1, "reverse_sql") is None:
            self.warn(op, "RunSQL", "Has no reverse_sql, so `migrate` can't roll back past it (IrreversibleError).",
                      "Pass reverse_sql; use migrations.RunSQL.noop when undoing isn't needed.")
        if self.atomic and re.search(r"\bCONCURRENTLY\b", sql, re.IGNORECASE):
            self.warn(op, "RunSQL", "Uses CONCURRENTLY in an atomic migration, and Postgres refuses it inside a transaction.", "Set atomic = False on the Migration.")
        for rule in sql_findings(sql):
            if rule["name"] != "CONCURRENTLY inside a transaction":
                self.warn(op, "RunSQL: " + rule["name"], rule["why"], None)

    def check_backfill(self, func):
        assigned = {}
        for node in ast.walk(func):
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                assigned[node.targets[0].id] = node.value
        label = "RunPython {}()".format(func.name)
        for node in ast.walk(func):
            if isinstance(node, ast.For):
                source = assigned.get(node.iter.id, node.iter) if isinstance(node.iter, ast.Name) else node.iter
                if unbatched_queryset(source):
                    saves = any(isinstance(n, ast.Call) and call_name(n) == "save" for n in ast.walk(node))
                    why = "Loops over a queryset without .iterator() or batches, so it loads every row into memory"
                    if saves:
                        why += " and sends one UPDATE per row"
                    why += ", all inside one transaction{}.".format(" that holds the row locks until the end" if self.atomic else "")
                    self.warn(node, label, why, BACKFILL_SAFE)
            elif isinstance(node, ast.Call) and call_name(node) in ("update", "delete") and isinstance(node.func, ast.Attribute):
                target = node.func.value
                if (isinstance(target, ast.Attribute) and target.attr in QUERYSET_SOURCES) or (
                    isinstance(target, ast.Call) and call_name(target) == "all"
                ):
                    self.warn(node, label, "Runs .{}() over the whole table in one statement, which locks every row until the transaction commits."
                              .format(call_name(node)), BACKFILL_SAFE)


def unbatched_queryset(node) -> bool:
    """True for a Model.objects... expression that is neither sliced nor read with .iterator()."""
    from_manager = False
    while True:
        if isinstance(node, ast.Subscript):
            return False
        if isinstance(node, ast.Call):
            if call_name(node) == "iterator":
                return False
            node = node.func
        elif isinstance(node, ast.Attribute):
            if node.attr in QUERYSET_SOURCES:
                from_manager = True
            node = node.value
        else:
            return from_manager


def check_django(path, content):
    """Findings as (line, label, why, safe pattern), or None when the source isn't a parseable Django migration."""
    try:
        tree = ast.parse(content)
    except (SyntaxError, ValueError):
        return None
    cls = migration_class(tree)
    if cls is None:
        return None
    if literal(class_attr(cls, "initial"), module_constants(tree)) is True:
        # Initial migrations create the app's tables in the same run, so every table they touch is still empty.
        return []
    return DjangoCheck(path, tree).run()


def report_django(path, findings) -> None:
    print("", file=sys.stderr)
    print("[backend-design] migration-safety review for {} (Django operations)".format(path), file=sys.stderr)
    for line, label, why, safe in findings:
        print("  - {}:{} {}".format(path, line, label), file=sys.stderr)
        print("    Why: {}".format(why), file=sys.stderr)
        if safe:
            print("    Safe: {}".format(safe), file=sys.stderr)
    print("  See: skills/migration-safety/README.md. For the exact SQL, pipe `python manage.py sqlmigrate <app> <migration>` "
          "into `check_migration.py --stdin`.", file=sys.stderr)
    print("", file=sys.stderr)


def django_source(tool_name, tool_input, path):
    """The whole migration file as it will be after this Write or Edit, or None when it can't be rebuilt."""
    if not path.endswith(".py") or not DJANGO_MIGRATION_DIR.search(path):
        return None
    if tool_name == "Write":
        return tool_input.get("content", "") or ""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            current = fh.read()
    except OSError:
        return None
    old, new = tool_input.get("old_string", "") or "", tool_input.get("new_string", "") or ""
    if not old or old not in current:
        return None
    return current.replace(old, new) if tool_input.get("replace_all") else current.replace(old, new, 1)


def main(payload=None) -> int:
    if payload is None:
        try:
            payload = json.load(sys.stdin)
        except Exception:
            return 0

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}
    path = tool_input.get("file_path", "") or ""

    if tool_name not in ("Write", "Edit"):
        return 0
    if not is_migration_path(path):
        return 0

    source = django_source(tool_name, tool_input, path)
    if source is not None and DJANGO_MIGRATION_CLASS.search(source):
        findings = check_django(path, source)
        if findings is not None:
            if findings:
                report_django(path, findings)
            return 0

    content = extract_content(tool_name, tool_input)
    if not content.strip():
        return 0

    findings = sql_findings(content)
    if findings:
        report_sql(path, findings)
    return 0


def cli(paths) -> int:
    """Check files on disk by sending each one through main() as a Write of its full content.

    Paths are made absolute because the path rules match on "/dir/" segments, the
    same shape Claude Code passes to the hook. Returns 1 if any file can't be read.
    """
    status = 0
    for path in paths:
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                content = fh.read()
        except OSError as exc:
            print("[backend-design] cannot read {}: {}".format(path, exc.strerror or exc), file=sys.stderr)
            status = 1
            continue
        main({"tool_name": "Write", "tool_input": {"file_path": os.path.abspath(path), "content": content}})
    return status


def check_stdin() -> int:
    findings = sql_findings(sys.stdin.read())
    if findings:
        report_sql("<stdin>", findings)
    return 0


if __name__ == "__main__":
    # --stdin checks raw SQL; file arguments check those files; with neither, read PreToolUse hook JSON from stdin.
    if sys.argv[1:] == ["--stdin"]:
        sys.exit(check_stdin())
    if len(sys.argv) > 1:
        sys.exit(cli(sys.argv[1:]))
    sys.exit(main())
