#!/usr/bin/env python3
"""Download the icons a diagram uses from their official sources into a cache outside the repo.

    fetch_icons.py aws-lambda postgresql database     # fetch what is missing, print each icon's cache file
    fetch_icons.py aws:Arch_Amazon-Aurora_64           # any icon of a family, by its file name
    fetch_icons.py --list aws                          # print the icon names inside an archive family
    fetch_icons.py --keys                              # print the catalog keys by family
    fetch_icons.py --offline aws-lambda                # report what the cache holds, never download

The cache is $SYSTEM_DESIGN_ICON_CACHE, else ${XDG_CACHE_HOME:-~/.cache}/agents/system-design-icons,
with one folder per family and version. ../icons/SOURCES.md lists each family's source and terms.
Python 3.9+ standard library only. Downloads are untrusted data: nothing in them is executed, archives
are only read with zipfile, and SVGs are parsed with every DOCTYPE and entity declaration refused.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
CATALOG = HERE.parent / "icons" / "catalog.json"
CACHE_ENV = "SYSTEM_DESIGN_ICON_CACHE"
USER_AGENT = "system-design-icons/1 (python urllib)"
TIMEOUT_S = 60
# The largest archive (AWS) is about 14 MB; the cap stops a wrong URL from filling the disk.
MAX_DOWNLOAD_BYTES = 200 * 1024 * 1024
# Official service icons are under 50 KB; anything far larger inside an archive is not an icon.
MAX_SVG_BYTES = 2 * 1024 * 1024
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ ()&+-]*$")


@dataclass(frozen=True)
class Family:
    """Where one icon set comes from. `paint` is how the renderer draws it: `stroke` and `fill` are
    one-color glyphs drawn white on a tile in the kind color, `color` is a full-color icon drawn as is."""
    version: str
    paint: str
    url: str
    sha256: str | None = None

    @property
    def is_archive(self) -> bool:
        return self.url.endswith(".zip")


FAMILIES = {
    "lucide": Family("1.66.0", "stroke",
                     "https://cdn.jsdelivr.net/npm/lucide-static@{version}/icons/{name}.svg"),
    "tabler": Family("3.50.0", "stroke",
                     "https://cdn.jsdelivr.net/npm/@tabler/icons@{version}/icons/outline/{name}.svg"),
    "simple-icons": Family("16.36.0", "fill",
                           "https://cdn.jsdelivr.net/npm/simple-icons@{version}/icons/{name}.svg"),
    # gilbarbara/logos publishes no tags or npm package, so the version is a commit.
    "logos": Family("b9edc65f8946027cb5e2fe6c772e914cf3649fba", "color",
                    "https://cdn.jsdelivr.net/gh/gilbarbara/logos@{version}/logos/{name}.svg"),
    "aws": Family("07312026", "color",
                  "https://d1.awsstatic.com/onedam/marketing-channels/website/public/shared/"
                  "architecture-icon-release/Icon-package_07312026.5846e92413caa21490223536cc97f1269e44fa92.zip",
                  sha256="d2d166c453526471749d520e0db022c459abef759d2946cf2dd1d1c992dc6526"),
    "azure": Family("V25", "color", "https://arch-center.azureedge.net/icons/Azure_Public_Service_Icons_V25.zip",
                    sha256="f293d99252b3638557dd08ccbff9f2529083473d39b373fb2af29a7200351339"),
    # Google serves these from URLs with no version, so the version is the start of the pinned hash.
    "gcp": Family("6531a10f58bc", "color", "https://services.google.com/fh/files/misc/core-products-icons.zip",
                  sha256="6531a10f58bc599c24d9a455d81dd757c1a03c3c43da9cddf639b859c1c1eece"),
    "gcp-category": Family("e5bc3abd3527", "color", "https://services.google.com/fh/files/misc/category-icons.zip",
                           sha256="e5bc3abd3527dc2500e9bff7f15870783e2c764129c49b7cd4c1b4e105345002"),
}

XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
ALLOWED_TAGS = {
    "g", "path", "rect", "circle", "ellipse", "line", "polyline", "polygon", "defs", "linearGradient",
    "radialGradient", "stop", "clipPath", "mask", "use", "symbol",
}
ALLOWED_ATTRS = {
    "d", "x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry", "fx", "fy", "width", "height",
    "points", "transform", "offset", "id", "fill", "fill-rule", "fill-opacity", "stroke", "stroke-width",
    "stroke-linecap", "stroke-linejoin", "stroke-miterlimit", "stroke-dasharray", "stroke-dashoffset",
    "stroke-opacity", "opacity", "stop-color", "stop-opacity", "gradientUnits", "gradientTransform",
    "spreadMethod", "clip-path", "clip-rule", "clipPathUnits", "mask", "maskUnits", "viewBox", "style",
    "href", "display", "visibility",
}
# Presentation attributes of a full-color icon's root <svg> that its shapes inherit.
ROOT_PAINT_ATTRS = {"fill", "fill-rule", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin",
                    "clip-rule", "opacity", "style"}


class IconError(Exception):
    """An icon can't be fetched or converted."""


# An archive that failed once in this run fails the same way for its other icons, so it isn't retried.
_archive_errors: dict[str, IconError] = {}


def cache_root() -> Path:
    env = os.environ.get(CACHE_ENV)
    if env:
        return Path(env).expanduser()
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base).expanduser() / "agents" / "system-design-icons"


def load_catalog() -> dict[str, str]:
    try:
        return json.loads(CATALOG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IconError(f"can't read the icon catalog {CATALOG}: {exc}") from exc


def resolve(key: str, catalog: dict[str, str]) -> tuple[str, str]:
    """Map a catalog key or a `family:name` reference to (family, name). Raises KeyError for neither."""
    ref = catalog.get(key, key)
    family, sep, name = ref.partition(":")
    if not sep or family not in FAMILIES or not NAME_RE.match(name):
        raise KeyError(key)
    return family, name


def icon_file(family: str, name: str) -> Path:
    fam = FAMILIES[family]
    return cache_root() / family / fam.version / "icons" / f"{name}.json"


def load_cached(family: str, name: str) -> dict | None:
    path = icon_file(family, name)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        raise IconError(f"cached icon {path} is unreadable ({exc}); delete it to fetch it again") from exc


# ---------- download ----------

def download(url: str, dest: Path) -> None:
    """Fetch `url` into `dest` through a temp file, so a failed download never leaves a partial file."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    fd, tmp = tempfile.mkstemp(dir=dest.parent, prefix=".part-")
    try:
        with os.fdopen(fd, "wb") as out, urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            total = 0
            while chunk := resp.read(1 << 16):
                total += len(chunk)
                if total > MAX_DOWNLOAD_BYTES:
                    raise IconError(f"{url} is larger than {MAX_DOWNLOAD_BYTES // (1024 * 1024)} MB")
                out.write(chunk)
        os.replace(tmp, dest)
    except urllib.error.HTTPError as exc:
        raise IconError(f"{url}: HTTP {exc.code} {exc.reason}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        raise IconError(f"{url}: download failed ({reason}); check the network or run with --offline") from exc
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def archive_path(family: str) -> Path:
    fam = FAMILIES[family]
    filename = fam.url.rsplit("/", 1)[-1]
    return cache_root() / family / fam.version / "downloads" / Path(filename).stem / filename


def ensure_archive(family: str, offline: bool) -> Path:
    path = archive_path(family)
    if family in _archive_errors:
        raise _archive_errors[family]
    if not path.exists():
        try:
            download_archive(family, path, offline)
        except IconError as exc:
            _archive_errors[family] = exc
            raise
    return path


def download_archive(family: str, path: Path, offline: bool) -> None:
    fam = FAMILIES[family]
    if offline:
        raise IconError(f"{family} archive is not in the cache ({path}) and fetching is off")
    print(f"downloading the {family} {fam.version} archive from {fam.url}", file=sys.stderr)
    download(fam.url, path)
    actual = sha256_of(path)
    if fam.sha256 and actual != fam.sha256:
        path.unlink()
        raise IconError(f"{family} archive sha256 is {actual}, expected {fam.sha256}; the vendor changed "
                        "the file, so check it and update the version and sha256 in fetch_icons.py")


def archive_index(path: Path) -> dict[str, str]:
    """Basename without .svg -> member name, for every SVG in the archive (macOS metadata skipped)."""
    try:
        with zipfile.ZipFile(path) as zf:
            members = [i for i in zf.infolist() if not i.is_dir()]
    except zipfile.BadZipFile as exc:
        raise IconError(f"{path} is not a valid zip ({exc}); delete it to download it again") from exc
    index: dict[str, str] = {}
    for info in members:
        base = info.filename.rsplit("/", 1)[-1]
        if "__MACOSX/" in info.filename or base.startswith("._") or not base.lower().endswith(".svg"):
            continue
        index.setdefault(base[:-4], info.filename)
    return index


def read_from_archive(family: str, name: str, offline: bool) -> tuple[bytes, str]:
    path = ensure_archive(family, offline)
    index = archive_index(path)
    member = index.get(name)
    if member is None:
        close = difflib.get_close_matches(name, list(index), n=5, cutoff=0.5)
        hint = f"; close matches: {', '.join(close)}" if close else f"; run fetch_icons.py --list {family}"
        raise IconError(f"{family} has no icon named {name!r}{hint}")
    with zipfile.ZipFile(path) as zf:
        info = zf.getinfo(member)
        if info.file_size > MAX_SVG_BYTES:
            raise IconError(f"{family} {member} is {info.file_size} bytes, too large for an icon")
        data = zf.read(member)
    extracted = path.parent.parent.parent / "extracted" / f"{name}.svg"
    extracted.parent.mkdir(parents=True, exist_ok=True)
    extracted.write_bytes(data)
    return data, f"{FAMILIES[family].url}#{member}"


def read_single(family: str, name: str, offline: bool) -> tuple[bytes, str]:
    fam = FAMILIES[family]
    url = fam.url.format(version=fam.version, name=name)
    path = cache_root() / family / fam.version / "downloads" / name / f"{name}.svg"
    if not path.exists():
        if offline:
            raise IconError(f"{family}:{name} is not in the cache and fetching is off")
        download(url, path)
    if path.stat().st_size > MAX_SVG_BYTES:
        raise IconError(f"{path} is too large for an icon")
    return path.read_bytes(), url


# ---------- convert ----------

def parse_svg(data: bytes, where: str) -> ET.Element:
    if re.search(rb"<!(DOCTYPE|ENTITY)", data, re.IGNORECASE):
        raise IconError(f"{where}: refusing an SVG with a DOCTYPE or entity declaration")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise IconError(f"{where}: not valid XML ({exc})") from exc
    if local(root.tag) != "svg":
        raise IconError(f"{where}: root element is <{local(root.tag)}>, not <svg>")
    return root


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def view_box(root: ET.Element, where: str) -> list[float]:
    raw = root.get("viewBox")
    try:
        if raw:
            box = [float(v) for v in raw.replace(",", " ").split()]
        else:
            box = [0.0, 0.0, float(root.get("width", "").rstrip("px")), float(root.get("height", "").rstrip("px"))]
    except ValueError as exc:
        raise IconError(f"{where}: can't read the viewBox or size") from exc
    if len(box) != 4 or box[2] <= 0 or box[3] <= 0:
        raise IconError(f"{where}: bad viewBox {raw!r}")
    return box


def safe_value(attr: str, value: str) -> bool:
    """Only same-document references survive: url(#id) and href="#id"."""
    if attr == "href" and not value.startswith("#"):
        return False
    lowered = value.lower()
    if "javascript:" in lowered or "expression(" in lowered or "@import" in lowered:
        return False
    return all(m.startswith("#") for m in re.findall(r"url\(\s*['\"]?([^)'\"]*)", value))


def serialize(el: ET.Element, prefix: str, ids: set[str]) -> str:
    tag = local(el.tag)
    if tag not in ALLOWED_TAGS:
        return ""
    attrs = []
    for key, value in el.attrib.items():
        name = "href" if key == XLINK_HREF else local(key)
        if name in ALLOWED_ATTRS and safe_value(name, value):
            attrs.append((name, rewrite_refs(name, value, prefix, ids)))
    children = "".join(serialize(child, prefix, ids) for child in el)
    attr_text = "".join(f' {k}="{escape_attr(v)}"' for k, v in attrs)
    return f"<{tag}{attr_text}>{children}</{tag}>" if children else f"<{tag}{attr_text}/>"


def class_rules(css: str, where: str) -> dict[str, dict[str, str]]:
    rules: dict[str, dict[str, str]] = {}
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        decls = {prop.strip(): value.strip()
                 for prop, sep, value in (decl.partition(":") for decl in body.split(";")) if sep}
        for selector in selectors.split(","):
            selector = selector.strip()
            if not re.fullmatch(r"\.[A-Za-z0-9_-]+", selector):
                raise IconError(f"{where}: <style> selector {selector!r} is not a plain class")
            rules.setdefault(selector[1:], {}).update(decls)
    return rules


def inline_class_styles(root: ET.Element, where: str) -> None:
    """Move `.class { prop: value }` rules from <style> sheets onto the elements as attributes, because a
    sheet inside one icon would restyle every other icon in the diagram. Other selectors are refused."""
    rules: dict[str, dict[str, str]] = {}
    for el in root.iter():
        if local(el.tag) == "style":
            for cls, decls in class_rules(el.text or "", where).items():
                rules.setdefault(cls, {}).update(decls)
    for el in root.iter():
        for cls in (el.get("class") or "").split():
            for prop, value in rules.get(cls, {}).items():
                el.set(prop, value)


def rewrite_refs(name: str, value: str, prefix: str, ids: set[str]) -> str:
    """Prefix ids and the references to them, so two icons in one diagram never share an id."""
    def new_id(old: str) -> str:
        return prefix + re.sub(r"[^A-Za-z0-9_.-]", "_", old)

    if name == "id":
        return new_id(value)
    if name == "href" and value[1:] in ids:
        return "#" + new_id(value[1:])
    return re.sub(r"url\(\s*(['\"]?)#([^)'\"]+)\1\s*\)",
                  lambda m: f"url(#{new_id(m.group(2))})" if m.group(2) in ids else m.group(0), value)


def escape_attr(value: str) -> str:
    return value.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


def convert(data: bytes, family: str, name: str, source_url: str) -> dict:
    """Turn a downloaded SVG into what render_diagram.py draws: the viewBox and the inner shapes, with
    scripts, style sheets, external references and unknown elements removed and ids made unique."""
    where = f"{family}:{name}"
    root = parse_svg(data, where)
    fam = FAMILIES[family]
    inline_class_styles(root, where)
    ids = {el.attrib["id"] for el in root.iter() if el.get("id")}
    prefix = re.sub(r"[^A-Za-z0-9_-]", "-", f"{family}-{name}") + "-"
    mono = fam.paint != "color"
    body = "".join(serialize(child, prefix, ids) for child in root)
    if not mono:
        paint = "".join(f' {k}="{escape_attr(v)}"' for k, v in root.attrib.items()
                        if local(k) in ROOT_PAINT_ATTRS and safe_value(local(k), v))
        body = f"<g{paint}>{body}</g>" if paint else body
    if not body:
        raise IconError(f"{where}: the SVG has no drawable shapes")
    return {
        "family": family,
        "name": name,
        "version": fam.version,
        "paint": fam.paint,
        "viewBox": view_box(root, where),
        "body": body,
        "source_url": source_url,
        "archive_sha256": fam.sha256 if fam.is_archive else None,
    }


# ---------- public entry points ----------

def fetch(family: str, name: str, offline: bool = False) -> dict:
    cached = load_cached(family, name)
    if cached is not None:
        return cached
    reader = read_from_archive if FAMILIES[family].is_archive else read_single
    data, source_url = reader(family, name, offline)
    icon = convert(data, family, name, source_url)
    path = icon_file(family, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.part")
    tmp.write_text(json.dumps(icon, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return icon


def ensure(keys: Iterable[str], offline: bool = False) -> tuple[dict[str, dict], list[str]]:
    """Return {key: icon} for every key that is cached or could be fetched, and one warning per key
    that couldn't. Keys must already be valid (see `resolve`)."""
    catalog = load_catalog()
    icons: dict[str, dict] = {}
    warnings: list[str] = []
    for key in dict.fromkeys(keys):
        family, name = resolve(key, catalog)
        try:
            icons[key] = fetch(family, name, offline)
        except IconError as exc:
            warnings.append(f"icon {key!r} left out: {exc}")
    return icons, warnings


def is_known(key: str, catalog: dict[str, str]) -> bool:
    try:
        resolve(key, catalog)
    except KeyError:
        return False
    return True


def print_keys(catalog: dict[str, str]) -> None:
    by_family: dict[str, list[str]] = {}
    for key in sorted(catalog):
        by_family.setdefault(resolve(key, catalog)[0], []).append(key)
    for family, keys in by_family.items():
        print(f"{family}: {' '.join(keys)}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("keys", nargs="*", help="catalog keys or family:name references")
    ap.add_argument("--list", metavar="FAMILY", help="print the icon names in an archive family and exit")
    ap.add_argument("--keys", action="store_true", dest="list_keys", help="print the catalog keys and exit")
    ap.add_argument("--offline", action="store_true", help="use only the cache; never download")
    args = ap.parse_args(argv)

    try:
        catalog = load_catalog()
        if args.list_keys:
            print_keys(catalog)
            return 0
        if args.list:
            if args.list not in FAMILIES or not FAMILIES[args.list].is_archive:
                archives = [f for f, fam in FAMILIES.items() if fam.is_archive]
                ap.error(f"--list takes an archive family: {', '.join(archives)}")
            print("\n".join(sorted(archive_index(ensure_archive(args.list, args.offline)))))
            return 0
    except IconError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if not args.keys:
        ap.error("name at least one icon key")
    unknown = [key for key in args.keys if not is_known(key, catalog)]
    if unknown:
        print(f"error: unknown icon keys {unknown}; use a catalog key (--keys) or family:name with a family "
              f"in {sorted(FAMILIES)}", file=sys.stderr)
        return 1
    icons, warnings = ensure(args.keys, args.offline)
    for key in args.keys:
        if key in icons:
            print(f"{key}\t{icon_file(*resolve(key, catalog))}")
    for w in warnings:
        print(f"error: {w}", file=sys.stderr)
    return 1 if warnings else 0


if __name__ == "__main__":
    sys.exit(main())
