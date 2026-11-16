"""Language and binary detection for the file inventory.

Every text file the mapper walks gets a language from this table, even when no import parser exists for it.
"""
from __future__ import annotations

from pathlib import Path

LANG_BY_EXT = {
    ".py": "python", ".pyi": "python",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript", ".mts": "typescript", ".cts": "typescript",
    ".vue": "vue", ".svelte": "svelte", ".astro": "astro",
    ".go": "go", ".rb": "ruby", ".rake": "ruby", ".erb": "erb",
    ".java": "java", ".kt": "kotlin", ".kts": "kotlin", ".scala": "scala", ".groovy": "groovy",
    ".rs": "rust", ".php": "php", ".cs": "csharp", ".fs": "fsharp", ".swift": "swift",
    ".m": "objective-c", ".mm": "objective-c", ".c": "c", ".h": "c", ".cc": "cpp", ".cpp": "cpp",
    ".hpp": "cpp", ".cxx": "cpp", ".dart": "dart", ".ex": "elixir", ".exs": "elixir", ".erl": "erlang",
    ".clj": "clojure", ".hs": "haskell", ".lua": "lua", ".pl": "perl", ".r": "r", ".jl": "julia",
    ".css": "css", ".scss": "scss", ".sass": "sass", ".less": "less", ".styl": "stylus",
    ".html": "html", ".htm": "html", ".hbs": "handlebars", ".mustache": "mustache", ".jinja": "jinja",
    ".j2": "jinja", ".njk": "nunjucks", ".pug": "pug", ".ejs": "ejs", ".twig": "twig",
    ".sql": "sql", ".prisma": "prisma", ".graphql": "graphql", ".gql": "graphql", ".proto": "protobuf",
    ".sh": "shell", ".bash": "shell", ".zsh": "shell", ".fish": "shell", ".ps1": "powershell",
    ".tf": "terraform", ".tfvars": "terraform", ".hcl": "hcl",
    ".json": "json", ".json5": "json", ".jsonc": "json", ".yml": "yaml", ".yaml": "yaml",
    ".toml": "toml", ".ini": "ini", ".cfg": "ini", ".conf": "config", ".env": "dotenv",
    ".xml": "xml", ".xsd": "xml", ".plist": "xml", ".csv": "csv", ".tsv": "csv",
    ".md": "markdown", ".mdx": "markdown", ".rst": "rst", ".txt": "text", ".adoc": "asciidoc",
    ".svg": "svg", ".ipynb": "notebook",
}

LANG_BY_NAME = {
    "Dockerfile": "dockerfile", "Containerfile": "dockerfile", "Makefile": "make", "GNUmakefile": "make",
    "Gemfile": "ruby", "Rakefile": "ruby", "Podfile": "ruby", "Brewfile": "ruby", "Vagrantfile": "ruby",
    "Jenkinsfile": "groovy", "Procfile": "procfile", "Tiltfile": "starlark", "BUILD": "starlark",
    "WORKSPACE": "starlark", "CODEOWNERS": "codeowners",
}

LOCKFILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb", "poetry.lock", "uv.lock",
    "Pipfile.lock", "Cargo.lock", "Gemfile.lock", "go.sum", "composer.lock", "mix.lock",
    "Podfile.lock", "pubspec.lock", "flake.lock",
}

# Known binary formats are skipped by extension so the mapper never opens them.
BINARY_EXT = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".icns", ".webp", ".avif", ".tif", ".tiff", ".psd",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".zip", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar", ".tar", ".jar", ".war", ".ear", ".whl", ".egg",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".key", ".numbers", ".pages",
    ".mp3", ".mp4", ".m4a", ".mov", ".avi", ".mkv", ".webm", ".wav", ".ogg", ".flac",
    ".exe", ".dll", ".so", ".dylib", ".a", ".o", ".obj", ".class", ".pyc", ".pyo", ".wasm", ".bin",
    ".dat", ".db", ".sqlite", ".sqlite3", ".parquet", ".avro", ".orc", ".pkl", ".pickle", ".npy", ".npz",
    ".h5", ".hdf5", ".onnx", ".pt", ".pth", ".ckpt", ".safetensors", ".lockb", ".DS_Store",
}

# A NUL byte in the first 8 KB is the same test git uses to call a file binary.
BINARY_SNIFF_BYTES = 8192


def language_for(path: Path) -> str:
    name = path.name
    if name in LOCKFILES:
        return "lockfile"
    if name in LANG_BY_NAME:
        return LANG_BY_NAME[name]
    if name.startswith(".env"):
        return "dotenv"
    if name.startswith("Dockerfile"):
        return "dockerfile"
    ext = path.suffix.lower()
    if ext in LANG_BY_EXT:
        return LANG_BY_EXT[ext]
    if not ext and name.startswith("."):
        return "dotfile"
    return ext.lstrip(".") or "other"


def is_binary(path: Path) -> bool:
    if path.suffix.lower() in BINARY_EXT or path.name in BINARY_EXT:
        return True
    try:
        with open(path, "rb") as fh:
            return b"\0" in fh.read(BINARY_SNIFF_BYTES)
    except OSError:
        return True
