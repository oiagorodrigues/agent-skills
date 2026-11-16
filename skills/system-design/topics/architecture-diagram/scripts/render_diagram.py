#!/usr/bin/env python3
"""Render an architecture diagram spec (JSON) to one self-contained SVG, or to an HTML page around that SVG.

    render_diagram.py SPEC.json -o diagram.svg             # for Markdown: ![Architecture](diagram.svg)
    render_diagram.py SPEC.json -o diagram.html            # standalone page with SVG/PNG/print buttons
    render_diagram.py SPEC.json -o diagram.svg --strict    # exit 2 when the layout has any warning
    render_diagram.py --list-icons

The spec format is in ../README.md. Python 3.9+ standard library only; it never touches the network.
"""
from __future__ import annotations

import argparse
import heapq
import json
import sys
import textwrap
from dataclasses import dataclass, field
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
ICON_DIR = HERE.parent / "icons"
TEMPLATE = HERE.parent / "assets" / "template.html"

KIND_COLORS = {
    "security": "#dd344c",
    "database": "#3b48cc",
    "storage": "#3b48cc",
    "compute": "#ed7100",
    "queue": "#e7157b",
    "networking": "#8c4fff",
    "analytics": "#8c4fff",
    "service": "#01a88d",
    "people": "#5a6b86",
    "vendor": "#7d8998",
    "reference": "#7d8998",
}
DEFAULT_ICONS = {
    "security": "shield",
    "database": "database",
    "storage": "bucket",
    "compute": "server",
    "queue": "queue",
    "networking": "network",
    "analytics": "chart",
    "service": "api",
    "people": "user",
    "vendor": "cloud",
    "reference": "book",
}
THEMES = {
    "light": {"bg": "#ffffff", "card": "#ffffff", "card_stroke": "#d0d7de", "ink": "#1f2328",
              "muted": "#59636e", "edge": "#59636e", "frame_fill": 0.05},
    "dark": {"bg": "#0d1117", "card": "#161b22", "card_stroke": "#3d444d", "ink": "#e6edf3",
             "muted": "#9198a1", "edge": "#9198a1", "frame_fill": 0.10},
}
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"

NODE_W, NODE_H, TILE, ICON = 200, 60, 40, 26
LABEL_SIZE, EDGE_LABEL_SIZE = 14, 11
BASE_COL_GAP = 56
FRAME_PAD, FRAME_HEADER = 16, 36
LANE_MARGIN, LANE_STEP, MIN_CLEAR = 30, 14, 84
PORT_GAP, PORT_INSET = 20, 16
ARROW_LEN, ARROW_HALF = 9, 4.5
MARGIN, TITLE_H, LEGEND_H = 28, 46, 40
MAX_LABEL_WORDS = 3
JOINERS = (",", "/", "+", "&", " and ")


class SpecError(Exception):
    """The spec can't be drawn as written."""


@dataclass
class Box:
    x: float
    y: float
    w: float
    h: float

    @property
    def r(self) -> float:
        return self.x + self.w

    @property
    def b(self) -> float:
        return self.y + self.h

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    def overlaps(self, other: "Box", pad: float = 0) -> bool:
        return (self.x - pad < other.r and other.x - pad < self.r
                and self.y - pad < other.b and other.y - pad < self.b)


@dataclass
class Route:
    edge: dict
    shape: str  # "straight", "z" (one turn in a gap), "detour" (down a free column gap) or "side"
    direction: str  # "down", "up" or "side"
    src_x: float = 0.0
    dst_x: float = 0.0
    channel: float = 0.0
    gaps: list = field(default_factory=list)
    lanes: list = field(default_factory=list)
    points: list = field(default_factory=list)

    def runs(self) -> list[tuple[int, float, float]]:
        """Each horizontal run as (gap, x where it meets the line from above, x where it meets the line below)."""
        down = self.direction == "down"
        if self.shape == "z":
            return [(self.gaps[0], *((self.src_x, self.dst_x) if down else (self.dst_x, self.src_x)))]
        if self.shape == "detour":
            first, second = (self.src_x, self.channel), (self.channel, self.dst_x)
            if not down:
                first, second = (self.channel, self.src_x), (self.dst_x, self.channel)
            return [(self.gaps[0], *first), (self.gaps[1], *second)]
        return []


def load_icons() -> dict[str, dict]:
    icons: dict[str, dict] = {}
    for path in sorted(ICON_DIR.glob("*.json")):
        icons.update(json.loads(path.read_text(encoding="utf-8")))
    return icons


def text_width(text: str, size: float, bold: bool = False) -> float:
    # Average Helvetica glyph width per point of font size; good enough to size boxes and pills.
    return len(text) * size * (0.6 if bold else 0.56)


def fmt(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".")


def tint(color: str, amount: float, base: str) -> str:
    """Mix `color` into `base`; `amount` is how much of the color shows."""
    c = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(base[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(bb + (cc - bb) * amount):02x}" for cc, bb in zip(c, b))


# ---------- spec ----------

class Diagram:
    def __init__(self, spec: dict, icons: dict[str, dict]) -> None:
        if not isinstance(spec, dict):
            raise SpecError("the spec must be a JSON object")
        self.title = spec.get("title") or ""
        self.theme_name = spec.get("theme", "light")
        if self.theme_name not in THEMES:
            raise SpecError(f"theme must be one of {sorted(THEMES)}")
        self.theme = THEMES[self.theme_name]
        self.cards = spec.get("cards") or []
        self.icons = icons
        self.warnings: list[str] = []
        self.nodes: dict[str, dict] = {}
        self.groups: dict[str, dict] = {}
        self.parent: dict[str, str] = {}
        for node in spec.get("nodes") or []:
            self._add_node(node)
        if not self.nodes:
            raise SpecError("the spec has no nodes")
        for group in spec.get("groups") or []:
            self._add_group(group)
        for group in self.groups.values():
            for member in group["contains"]:
                if member not in self.nodes and member not in self.groups:
                    raise SpecError(f"group {group['id']!r} contains unknown id {member!r}")
                if member in self.parent:
                    raise SpecError(f"{member!r} is in two groups ({self.parent[member]!r} and {group['id']!r}); "
                                    "nest one group inside the other instead")
                self.parent[member] = group["id"]
        for gid in self.groups:
            self._check_cycle(gid)
        self.edges = [self._check_edge(e) for e in spec.get("edges") or []]

    def _add_node(self, node: dict) -> None:
        nid = node.get("id")
        if not nid or nid in self.nodes:
            raise SpecError(f"node id missing or repeated: {nid!r}")
        label = node.get("label") or nid
        kind = node.get("kind", "service")
        if kind not in KIND_COLORS:
            raise SpecError(f"node {nid!r}: kind {kind!r} is not one of {sorted(KIND_COLORS)}")
        icon = node.get("icon") or DEFAULT_ICONS[kind]
        if icon not in self.icons:
            raise SpecError(f"node {nid!r}: unknown icon {icon!r} (run --list-icons)")
        if not isinstance(node.get("row"), int) or node["row"] < 0:
            raise SpecError(f"node {nid!r}: row must be a whole number, 0 at the top")
        col = node.get("col")
        if col is not None and not isinstance(col, (int, float)):
            raise SpecError(f"node {nid!r}: col must be a number")
        if len(label.split()) > MAX_LABEL_WORDS:
            self.warnings.append(f"node {nid!r}: label {label!r} is longer than {MAX_LABEL_WORDS} words")
        if any(j in f" {label.lower()} " for j in JOINERS):
            self.warnings.append(f"node {nid!r}: label {label!r} names several components; "
                                 "give each component its own node")
        self.nodes[nid] = {**node, "id": nid, "label": label, "kind": kind, "icon": icon}

    def _add_group(self, group: dict) -> None:
        gid = group.get("id")
        if not gid or gid in self.groups or gid in self.nodes:
            raise SpecError(f"group id missing or repeated: {gid!r}")
        if not group.get("contains"):
            raise SpecError(f"group {gid!r} contains nothing")
        kind = group.get("kind", "networking")
        if kind not in KIND_COLORS:
            raise SpecError(f"group {gid!r}: kind {kind!r} is not one of {sorted(KIND_COLORS)}")
        icon = group.get("icon")
        if icon and icon not in self.icons:
            raise SpecError(f"group {gid!r}: unknown icon {icon!r}")
        self.groups[gid] = {**group, "id": gid, "label": group.get("label") or gid, "kind": kind}

    def _check_cycle(self, gid: str) -> None:
        seen = {gid}
        cur = self.parent.get(gid)
        while cur:
            if cur in seen:
                raise SpecError(f"group {gid!r} is nested inside itself")
            seen.add(cur)
            cur = self.parent.get(cur)

    def _check_edge(self, edge: dict) -> dict:
        for end in ("from", "to"):
            if edge.get(end) not in self.nodes and edge.get(end) not in self.groups:
                raise SpecError(f"edge {edge}: unknown {end!r} id {edge.get(end)!r}")
        if edge["from"] == edge["to"]:
            raise SpecError(f"edge {edge}: from and to are the same")
        if edge["to"] in self.ancestors(edge["from"]) or edge["from"] in self.ancestors(edge["to"]):
            raise SpecError(f"edge {edge}: connects a group to something inside it")
        label = edge.get("label") or ""
        if len(label.split()) > 2:
            self.warnings.append(f"edge {edge['from']}->{edge['to']}: label {label!r} is longer than 2 words")
        return edge

    def ancestors(self, item: str) -> list[str]:
        out = []
        cur = self.parent.get(item)
        while cur:
            out.append(cur)
            cur = self.parent.get(cur)
        return out

    def descendants(self, gid: str) -> list[str]:
        out = []
        for member in self.groups[gid]["contains"]:
            out.extend(self.descendants(member) if member in self.groups else [member])
        return out


# ---------- layout ----------

class Layout:
    def __init__(self, d: Diagram, show_title: bool) -> None:
        self.d = d
        rows = sorted({n["row"] for n in d.nodes.values()})
        self.row_index = {r: i for i, r in enumerate(rows)}
        self.nrows = len(rows)
        self.node_row = {nid: self.row_index[n["row"]] for nid, n in d.nodes.items()}
        depth = max((len(d.ancestors(n)) for n in d.nodes), default=0)
        self.col_gap = max(BASE_COL_GAP, 2 * depth * FRAME_PAD + 24)
        self.left = MARGIN + depth * FRAME_PAD
        self.top = MARGIN + (TITLE_H if show_title and d.title else 0)
        self._place_columns()
        self.rows_of: dict[str, tuple[int, int]] = {nid: (r, r) for nid, r in self.node_row.items()}
        for gid in d.groups:
            members = [self.node_row[n] for n in d.descendants(gid)]
            self.rows_of[gid] = (min(members), max(members))
        self.xr = {nid: (self.node_x[nid], self.node_x[nid] + NODE_W) for nid in d.nodes}
        for gid in d.groups:
            self._group_x(gid)

    def _place_columns(self) -> None:
        by_row: dict[int, list[dict]] = {}
        for n in self.d.nodes.values():
            by_row.setdefault(self.node_row[n["id"]], []).append(n)
        explicit = [n["col"] for n in self.d.nodes.values() if n.get("col") is not None]
        widest = max(len(v) for v in by_row.values())
        centre = (min(explicit) + max(explicit)) / 2 if explicit else (widest - 1) / 2
        cols: dict[str, float] = {}
        for r, nodes in by_row.items():
            given = [n.get("col") is not None for n in nodes]
            if any(given) and not all(given):
                raise SpecError(f"row {r}: set col on every node in the row or on none")
            if all(given):
                for n in nodes:
                    cols[n["id"]] = float(n["col"])
            else:
                for i, n in enumerate(nodes):
                    cols[n["id"]] = centre + i - (len(nodes) - 1) / 2
            ordered = sorted(nodes, key=lambda n: cols[n["id"]])
            for a, b in zip(ordered, ordered[1:]):
                if cols[b["id"]] - cols[a["id"]] < 1:
                    raise SpecError(f"nodes {a['id']!r} and {b['id']!r} overlap in row {r}; "
                                    "space their col values at least 1 apart")
        low = min(cols.values())
        self.node_x = {nid: self.left + (c - low) * (NODE_W + self.col_gap) for nid, c in cols.items()}

    def _group_x(self, gid: str) -> tuple[float, float]:
        if gid not in self.xr:
            spans = [self._group_x(m) if m in self.d.groups else self.xr[m] for m in self.d.groups[gid]["contains"]]
            self.xr[gid] = (min(s[0] for s in spans) - FRAME_PAD, max(s[1] for s in spans) + FRAME_PAD)
        return self.xr[gid]

    def place_rows(self, lanes: dict[int, int]) -> None:
        d = self.d
        top_extra = [0] * self.nrows
        bottom_extra = [0] * self.nrows
        for nid, r in self.node_row.items():
            anc = d.ancestors(nid)
            top_extra[r] = max(top_extra[r], sum(1 for g in anc if self.rows_of[g][0] == r))
            bottom_extra[r] = max(bottom_extra[r], sum(1 for g in anc if self.rows_of[g][1] == r))
        self.row_y: list[float] = []
        self.clear: dict[int, tuple[float, float]] = {}
        y = self.top + top_extra[0] * FRAME_HEADER
        for r in range(self.nrows):
            self.row_y.append(y)
            y += NODE_H
            if r + 1 < self.nrows:
                n = lanes.get(r, 0)
                clear_h = max(MIN_CLEAR, 2 * LANE_MARGIN + max(n - 1, 0) * LANE_STEP)
                start = y + bottom_extra[r] * FRAME_PAD
                self.clear[r] = (start, start + clear_h)
                y = start + clear_h + top_extra[r + 1] * FRAME_HEADER
        self.boxes: dict[str, Box] = {
            nid: Box(self.node_x[nid], self.row_y[r], NODE_W, NODE_H) for nid, r in self.node_row.items()
        }
        for gid in d.groups:
            self._group_box(gid)
        self.content_bottom = self.row_y[-1] + NODE_H + bottom_extra[-1] * FRAME_PAD

    def _group_box(self, gid: str) -> Box:
        if gid not in self.boxes:
            inner = [self._group_box(m) if m in self.d.groups else self.boxes[m]
                     for m in self.d.groups[gid]["contains"]]
            x0, y0 = min(b.x for b in inner), min(b.y for b in inner)
            x1, y1 = max(b.r for b in inner), max(b.b for b in inner)
            self.boxes[gid] = Box(x0 - FRAME_PAD, y0 - FRAME_HEADER, x1 - x0 + 2 * FRAME_PAD,
                                  y1 - y0 + FRAME_HEADER + FRAME_PAD)
        return self.boxes[gid]

    def frame_title_box(self, gid: str) -> Box:
        b = self.boxes[gid]
        return Box(b.x + 8, b.y + 4, 34 + text_width(self.d.groups[gid]["label"], 13, bold=True), 28)


# ---------- routing ----------

def blocked(lay: Layout, x: float, rows: range, skip: set[str]) -> int:
    """How many nodes in `rows` a vertical line at `x` would run through."""
    return sum(1 for nid, r in lay.node_row.items()
               if r in rows and nid not in skip and lay.xr[nid][0] - 6 < x < lay.xr[nid][1] + 6)


def route_x(lay: Layout, d: Diagram) -> list[Route]:
    """Pick each edge's shape, ports and lane gap; everything here depends on x positions and rows only."""
    routes: list[Route] = []
    for e in d.edges:
        s, t = e["from"], e["to"]
        (s0, s1), (t0, t1) = lay.rows_of[s], lay.rows_of[t]
        (sl, sr), (tl, tr) = lay.xr[s], lay.xr[t]
        skip = {s, t}
        if not (t0 > s1 or s0 > t1):
            if not (tl >= sr or sl >= tr):
                raise SpecError(f"edge {s}->{t}: the two boxes share rows and overlap side to side")
            routes.append(Route(e, "side", "side"))
            continue
        down = t0 > s1
        between = range(s1 + 1, t0) if down else range(t1 + 1, s0)
        lo, hi = max(sl, tl) + PORT_INSET, min(sr, tr) - PORT_INSET
        r = Route(e, "z", "down" if down else "up")
        if hi - lo >= 8 and any(not blocked(lay, x, between, skip) for x in frange(lo, hi)):
            r.shape = "straight"
        else:
            make_turn(lay, r)
        routes.append(r)
    while not place_straight(lay, routes):
        pass
    assign_ports(lay, routes)
    return routes


def make_turn(lay: Layout, r: Route) -> None:
    """Route `r` with one turn in a gap, or down a free column gap when that turn would cross a box."""
    s, t = r.edge["from"], r.edge["to"]
    (s0, s1), (t0, t1) = lay.rows_of[s], lay.rows_of[t]
    (sl, sr), (tl, tr) = lay.xr[s], lay.xr[t]
    skip, down = {s, t}, r.direction == "down"
    scx, tcx = (sl + sr) / 2, (tl + tr) / 2
    guess_src = scx + (0.3 if tcx > scx else -0.3) * (sr - sl)
    if down:
        options = [(s1, range(s1 + 1, s1 + 1), range(s1 + 1, t0)),
                   (t0 - 1, range(s1 + 1, t0), range(t0, t0))]
    else:
        options = [(s0 - 1, range(s0, s0), range(t1 + 1, s0)),
                   (t1, range(t1 + 1, s0), range(t1 + 1, t1 + 1))]
    best = min(options, key=lambda o: blocked(lay, guess_src, o[1], skip) + blocked(lay, tcx, o[2], skip))
    r.shape, r.gaps = "z", [best[0]]
    if blocked(lay, guess_src, best[1], skip) + blocked(lay, tcx, best[2], skip):
        between = range(s1 + 1, t0) if down else range(t1 + 1, s0)
        channel = free_channel(lay, between, skip, (scx + tcx) / 2)
        if channel is not None:
            r.shape, r.channel = "detour", channel
            r.gaps = [s1, t0 - 1] if down else [s0 - 1, t1]


def frange(lo: float, hi: float, step: float = 4) -> list[float]:
    """Points from the middle of [lo, hi] outward."""
    mid, out = (lo + hi) / 2, []
    for k in range(int((hi - lo) / 2 / step) + 1):
        out += [mid - k * step, mid + k * step] if k else [mid]
    return [x for x in out if lo <= x <= hi]


def end_sides(r: Route) -> tuple[str, str]:
    return ("bottom", "top") if r.direction == "down" else ("top", "bottom")


def place_straight(lay: Layout, routes: list[Route]) -> bool:
    """Put each straight line where it leaves room on both boxes for the turning lines beside it.

    A straight line whose overlap has no such room becomes a turning line instead; returns False when that
    happened, so the caller places the rest again with the new counts.
    """
    turning: dict[tuple[str, str, bool], int] = {}
    for r in routes:
        if r.shape not in ("z", "detour"):
            continue
        s, t = r.edge["from"], r.edge["to"]
        scx, tcx = sum(lay.xr[s]) / 2, sum(lay.xr[t]) / 2
        towards_t, towards_s = (r.channel, r.channel) if r.shape == "detour" else (tcx, scx)
        src_side, dst_side = end_sides(r)
        turning[(s, src_side, towards_t < scx)] = turning.get((s, src_side, towards_t < scx), 0) + 1
        turning[(t, dst_side, towards_s < tcx)] = turning.get((t, dst_side, towards_s < tcx), 0) + 1
    used: dict[tuple[str, str], list[float]] = {}
    for r in routes:
        if r.shape != "straight":
            continue
        s, t = r.edge["from"], r.edge["to"]
        sides = end_sides(r)
        lo = max(lay.xr[s][0], lay.xr[t][0]) + PORT_INSET
        hi = min(lay.xr[s][1], lay.xr[t][1]) - PORT_INSET
        room_lo, room_hi = lo, hi
        for key, side in ((s, sides[0]), (t, sides[1])):
            room_lo = max(room_lo, lay.xr[key][0] + PORT_INSET + turning.get((key, side, True), 0) * PORT_GAP)
            room_hi = min(room_hi, lay.xr[key][1] - PORT_INSET - turning.get((key, side, False), 0) * PORT_GAP)
        taken = used.get((s, sides[0]), []) + used.get((t, sides[1]), [])
        between = range(lay.rows_of[s][1] + 1, lay.rows_of[t][0]) if r.direction == "down" \
            else range(lay.rows_of[t][1] + 1, lay.rows_of[s][0])
        ok = [x for x in frange(room_lo, room_hi)
              if not blocked(lay, x, between, {s, t}) and all(abs(x - u) >= PORT_GAP for u in taken)]
        if not ok:
            make_turn(lay, r)
            return False
        r.src_x = r.dst_x = ok[0]
        used.setdefault((s, sides[0]), []).append(r.src_x)
        used.setdefault((t, sides[1]), []).append(r.src_x)
    return True


def free_channel(lay: Layout, rows: range, skip: set[str], near: float) -> float | None:
    """The middle of a column gap that no box in `rows` covers, closest to `near`."""
    edges = {x for nid in lay.d.nodes for x in lay.xr[nid]}
    candidates = sorted({x - lay.col_gap / 2 for x in edges} | {x + lay.col_gap / 2 for x in edges},
                        key=lambda x: abs(x - near))
    return next((x for x in candidates if x >= MARGIN / 2 and not blocked(lay, x, rows, skip)), None)


def assign_ports(lay: Layout, routes: list[Route]) -> None:
    """Spread the endpoints on each box side so lines never share a port, in the order that avoids crossings."""
    sides: dict[tuple[str, str], list[tuple[float, bool, Route, str]]] = {}
    for r in routes:
        if r.shape == "side":
            continue
        s, t = r.edge["from"], r.edge["to"]
        src_side, dst_side = ("bottom", "top") if r.direction == "down" else ("top", "bottom")
        scx, tcx = sum(lay.xr[s]) / 2, sum(lay.xr[t]) / 2
        fixed = r.shape == "straight"
        towards_src, towards_dst = (r.channel, r.channel) if r.shape == "detour" else (scx, tcx)
        sides.setdefault((s, src_side), []).append((r.src_x if fixed else towards_dst, fixed, r, "src"))
        sides.setdefault((t, dst_side), []).append((r.dst_x if fixed else towards_src, fixed, r, "dst"))
    for (key, _side), ends in sides.items():
        left, right = lay.xr[key][0] + PORT_INSET, lay.xr[key][1] - PORT_INSET
        ends.sort(key=lambda e: (e[0], e[2].edge["to"] if e[3] == "src" else e[2].edge["from"]))
        run: list[tuple[float, bool, Route, str]] = []
        bound = left - PORT_GAP
        for end in ends + [(right + PORT_GAP, True, None, "")]:
            if not end[1]:
                run.append(end)
                continue
            place_run(run, bound + PORT_GAP, end[0] - PORT_GAP)
            run, bound = [], end[0]


def place_run(run: list, a: float, b: float) -> None:
    if not run:
        return
    k = len(run)
    if b - a < (k - 1) * PORT_GAP or b < a:
        xs = [a + (b - a) * (i + 0.5) / k for i in range(k)] if b > a else [(a + b) / 2] * k
    else:
        xs = [min(max(e[0], a), b) for e in run]
        for i in range(1, k):
            xs[i] = max(xs[i], xs[i - 1] + PORT_GAP)
        xs[-1] = min(xs[-1], b)
        for i in range(k - 2, -1, -1):
            xs[i] = min(xs[i], xs[i + 1] - PORT_GAP)
    for x, (_, _, route, end) in zip(xs, run):
        if end == "src":
            route.src_x = x
        else:
            route.dst_x = x


def assign_lanes(routes: list[Route]) -> dict[int, int]:
    """Give each horizontal run its own height in its gap so that no vertical part of one edge cuts another's run."""
    by_gap: dict[int, list[tuple[Route, int, float, float]]] = {}
    for r in routes:
        r.lanes = [0] * len(r.runs())
        for k, (gap, upper_x, lower_x) in enumerate(r.runs()):
            by_gap.setdefault(gap, []).append((r, k, upper_x, lower_x))
    counts: dict[int, int] = {}
    for gap, runs in by_gap.items():
        n = len(runs)
        upper = [run[2] for run in runs]
        lower = [run[3] for run in runs]
        span = [(min(u, b), max(u, b)) for u, b in zip(upper, lower)]
        above: list[set[int]] = [set() for _ in range(n)]  # above[i] = runs that must sit higher than run i
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                lo, hi = span[i]
                if lo + 0.5 < upper[j] < hi - 0.5:
                    above[i].add(j)
                if lo + 0.5 < lower[j] < hi - 0.5:
                    above[j].add(i)
        indeg = [len(a) for a in above]
        below: list[list[int]] = [[] for _ in range(n)]
        for i in range(n):
            for j in above[i]:
                below[j].append(i)
        heap = [(-(span[i][1] - span[i][0]), i) for i in range(n) if indeg[i] == 0]
        heapq.heapify(heap)
        order: list[int] = []
        done = [False] * n
        while len(order) < n:
            if not heap:  # constraint cycle: the crossing check reports it
                i = min((i for i in range(n) if not done[i]), key=lambda i: indeg[i])
                heap.append((0, i))
            _, i = heapq.heappop(heap)
            if done[i]:
                continue
            done[i] = True
            order.append(i)
            for j in below[i]:
                indeg[j] -= 1
                if indeg[j] == 0 and not done[j]:
                    heapq.heappush(heap, (-(span[j][1] - span[j][0]), j))
        lane = [0] * n
        placed: list[int] = []
        for i in order:
            lane[i] = max((lane[j] + 1 for j in placed
                           if j in above[i] or (span[j][0] - 10 < span[i][1] and span[i][0] - 10 < span[j][1])),
                          default=0)
            placed.append(i)
        for i, (r, k, _, _) in enumerate(runs):
            r.lanes[k] = lane[i]
        counts[gap] = max(lane) + 1
    return counts


def route_points(lay: Layout, routes: list[Route], counts: dict[int, int]) -> None:
    side_pairs: dict[tuple[str, str], list[Route]] = {}
    for r in routes:
        s, t = lay.boxes[r.edge["from"]], lay.boxes[r.edge["to"]]
        if r.shape == "side":
            side_pairs.setdefault(tuple(sorted((r.edge["from"], r.edge["to"]))), []).append(r)
            continue
        a_y, b_y = (s.b, t.y) if r.direction == "down" else (s.y, t.b)
        if r.shape == "straight" or (r.shape == "z" and abs(r.src_x - r.dst_x) < 1):
            r.points = [(r.src_x, a_y), (r.src_x, b_y)]
            continue
        ys = []
        for gap, lane in zip(r.gaps, r.lanes):
            c0, c1 = lay.clear[gap]
            ys.append((c0 + c1) / 2 - (counts[gap] - 1) * LANE_STEP / 2 + lane * LANE_STEP)
        if r.shape == "z":
            r.points = [(r.src_x, a_y), (r.src_x, ys[0]), (r.dst_x, ys[0]), (r.dst_x, b_y)]
        else:
            r.points = [(r.src_x, a_y), (r.src_x, ys[0]), (r.channel, ys[0]), (r.channel, ys[1]),
                        (r.dst_x, ys[1]), (r.dst_x, b_y)]
    for rs in side_pairs.values():
        for k, r in enumerate(rs):
            s, t = lay.boxes[r.edge["from"]], lay.boxes[r.edge["to"]]
            top, bottom = max(s.y, t.y), min(s.b, t.b)
            y = (top + bottom) / 2 + (k - (len(rs) - 1) / 2) * LANE_STEP
            r.points = [(s.r, y), (t.x, y)] if t.x >= s.r else [(s.x, y), (t.r, y)]


# ---------- checks ----------

def segments(points: list) -> list[tuple]:
    return list(zip(points, points[1:]))


def corners(b: Box) -> list[tuple]:
    return [(b.x, b.y), (b.r, b.y), (b.r, b.b), (b.x, b.b), (b.x, b.y)]


def seg_box(a: tuple, b: tuple) -> Box:
    return Box(min(a[0], b[0]), min(a[1], b[1]), abs(a[0] - b[0]), abs(a[1] - b[1]))


def seg_hits_box(a: tuple, b: tuple, box: Box) -> bool:
    sb = seg_box(a, b)
    return sb.x < box.r - 1 and box.x + 1 < sb.r and sb.y < box.b - 1 and box.y + 1 < sb.b


def segs_cross(p: tuple, q: tuple) -> bool:
    (a, b), (c, e) = p, q
    pv, qv = a[0] == b[0], c[0] == e[0]
    if pv == qv:
        if pv and abs(a[0] - c[0]) < 2:
            return min(max(a[1], b[1]), max(c[1], e[1])) - max(min(a[1], b[1]), min(c[1], e[1])) > 2
        if not pv and abs(a[1] - c[1]) < 2:
            return min(max(a[0], b[0]), max(c[0], e[0])) - max(min(a[0], b[0]), min(c[0], e[0])) > 2
        return False
    v, h = (p, q) if pv else (q, p)
    x, (y0, y1) = v[0][0], sorted((v[0][1], v[1][1]))
    y, (x0, x1) = h[0][1], sorted((h[0][0], h[1][0]))
    return x0 + 0.5 < x < x1 - 0.5 and y0 + 0.5 < y < y1 - 0.5


def name(r: Route) -> str:
    return f"{r.edge['from']}->{r.edge['to']}"


def check_layout(lay: Layout, routes: list[Route]) -> list[str]:
    d, warnings = lay.d, []
    for i, r in enumerate(routes):
        for q in routes[i + 1:]:
            if any(segs_cross(p, s) for p in segments(r.points) for s in segments(q.points)):
                warnings.append(f"edges {name(r)} and {name(q)} cross; move a box to another col")
        ends = {r.edge["from"], r.edge["to"]}
        for nid in d.nodes:
            if nid not in ends and any(seg_hits_box(a, b, lay.boxes[nid]) for a, b in segments(r.points)):
                warnings.append(f"edge {name(r)} runs through box {nid!r}; line the boxes up or move {nid!r}")
        for gid in d.groups:
            if gid not in ends and any(seg_hits_box(a, b, lay.frame_title_box(gid)) for a, b in segments(r.points)):
                warnings.append(f"edge {name(r)} runs through the title of group {gid!r}")
    for gid in d.groups:
        inside = set(d.descendants(gid))
        for nid in d.nodes:
            if nid not in inside and lay.boxes[gid].overlaps(lay.boxes[nid]):
                warnings.append(f"group {gid!r} covers box {nid!r}, which is not in it; move {nid!r} or the group")
        for other in d.groups:
            if other <= gid or other in d.ancestors(gid) or gid in d.ancestors(other):
                continue
            if lay.boxes[gid].overlaps(lay.boxes[other]):
                warnings.append(f"groups {gid!r} and {other!r} overlap; nest one in the other or move one")
    return warnings


# ---------- labels ----------

def place_labels(lay: Layout, routes: list[Route]) -> tuple[list[tuple[Box, str]], list[str]]:
    obstacles = [lay.boxes[n] for n in lay.d.nodes] + [lay.frame_title_box(g) for g in lay.d.groups]
    outlines = [s for g in lay.d.groups for s in segments(corners(lay.boxes[g]))]
    placed: list[tuple[Box, str]] = []
    warnings: list[str] = []
    for r in routes:
        label = r.edge.get("label")
        if not label:
            continue
        w, h = text_width(label, EDGE_LABEL_SIZE) + 12, 18
        best = None
        for a, b in segments(r.points):
            length = abs(a[0] - b[0]) + abs(a[1] - b[1])
            if length < (w if a[1] == b[1] else h) + 12:
                continue
            for t in (0.5, 0.35, 0.65, 0.2, 0.8):
                x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
                box = Box(x - w / 2, y - h / 2, w, h)
                if any(box.overlaps(o, 3) for o in obstacles) or any(box.overlaps(p, 3) for p, _ in placed):
                    continue
                cuts = sum(1 for q in routes if q is not r for s in segments(q.points) if seg_hits_box(*s, box))
                cuts += sum(1 for s in outlines if seg_hits_box(*s, box))
                score = (cuts, abs(t - 0.5), -length)
                if best is None or score < best[0]:
                    best = (score, box)
        if best is None:
            a, b = max(segments(r.points), key=lambda s: abs(s[0][0] - s[1][0]) + abs(s[0][1] - s[1][1]))
            x, y = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            best = ((0,), Box(x - w / 2, y - h / 2, w, h))
            warnings.append(f"edge {name(r)}: no free spot for label {label!r}; shorten it or space the boxes out")
        placed.append((best[1], label))
    return placed, warnings


# ---------- SVG ----------

def icon_markup(d: Diagram, icon: str, x: float, y: float, size: float) -> str:
    data = d.icons[icon]
    s = size / 24
    paint = ('fill="none" stroke="#ffffff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"'
             if data["style"] == "stroke" else 'fill="#ffffff"')
    return f'<g transform="translate({fmt(x)} {fmt(y)}) scale({s:.4f})" {paint}>{data["body"]}</g>'


def rounded_path(points: list, radius: float = 6) -> str:
    out = [f"M{fmt(points[0][0])} {fmt(points[0][1])}"]
    for i in range(1, len(points) - 1):
        (px, py), (cx, cy), (nx, ny) = points[i - 1], points[i], points[i + 1]
        r = min(radius, (abs(cx - px) + abs(cy - py)) / 2, (abs(nx - cx) + abs(ny - cy)) / 2)
        ax = cx - r * (cx > px) + r * (cx < px)
        ay = cy - r * (cy > py) + r * (cy < py)
        bx = cx + r * (nx > cx) - r * (nx < cx)
        by = cy + r * (ny > cy) - r * (ny < cy)
        out.append(f"L{fmt(ax)} {fmt(ay)}Q{fmt(cx)} {fmt(cy)} {fmt(bx)} {fmt(by)}")
    out.append(f"L{fmt(points[-1][0])} {fmt(points[-1][1])}")
    return "".join(out)


def arrowhead(tip: tuple, prev: tuple, color: str) -> tuple[str, tuple]:
    dx, dy = tip[0] - prev[0], tip[1] - prev[1]
    length = max(abs(dx), abs(dy)) or 1
    ux, uy = dx / length, dy / length
    bx, by = tip[0] - ux * ARROW_LEN, tip[1] - uy * ARROW_LEN
    pts = [(tip[0], tip[1]), (bx - uy * ARROW_HALF, by + ux * ARROW_HALF), (bx + uy * ARROW_HALF, by - ux * ARROW_HALF)]
    poly = " ".join(f"{fmt(x)},{fmt(y)}" for x, y in pts)
    return f'<polygon points="{poly}" fill="{color}"/>', (bx + ux, by + uy)


def node_lines(label: str) -> tuple[list[str], int]:
    for size in (LABEL_SIZE, 12):
        width = int((NODE_W - TILE - 32) / (size * 0.6))
        lines = textwrap.wrap(label, width=width) or [""]
        if len(lines) <= 2:
            return lines, size
    return lines[:3], 12


def render_svg(d: Diagram, show_title: bool = True) -> tuple[str, list[str]]:
    lay = Layout(d, show_title)
    routes = route_x(lay, d)
    counts = assign_lanes(routes)
    lay.place_rows(counts)
    route_points(lay, routes, counts)
    warnings = list(d.warnings) + check_layout(lay, routes)
    labels, label_warnings = place_labels(lay, routes)
    warnings += label_warnings
    th = d.theme

    all_boxes = list(lay.boxes.values()) + [b for b, _ in labels]
    width = max([b.r for b in all_boxes] + [x for r in routes for x, _ in r.points]) + MARGIN
    has_public = any(e.get("public") for e in d.edges) or any(
        x.get("public") for x in list(d.nodes.values()) + list(d.groups.values()))
    legend_y = max(b.b for b in all_boxes) + 22
    height = legend_y + (LEGEND_H if has_public or d.edges else 0) + MARGIN - 22

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{fmt(width)}" height="{fmt(height)}" '
        f'viewBox="0 0 {fmt(width)} {fmt(height)}" role="img" font-family="{escape(FONT)}">',
        f"<title>{escape(d.title or 'Architecture diagram')}</title>",
        f'<rect width="100%" height="100%" fill="{th["bg"]}"/>',
    ]
    if show_title and d.title:
        out.append(f'<text x="{MARGIN}" y="{MARGIN + 18}" font-size="20" font-weight="700" '
                   f'fill="{th["ink"]}">{escape(d.title)}</text>')

    for gid in sorted(d.groups, key=lambda g: len(d.ancestors(g))):
        g, b = d.groups[gid], lay.boxes[gid]
        color = KIND_COLORS[g["kind"]]
        dash = ' stroke-dasharray="8 5"' if g.get("public") else ""
        out.append(f'<rect x="{fmt(b.x)}" y="{fmt(b.y)}" width="{fmt(b.w)}" height="{fmt(b.h)}" rx="10" '
                   f'fill="{tint(color, th["frame_fill"], th["bg"])}" stroke="{color}" stroke-width="1.5"{dash}/>')
        tx = b.x + 12
        if g.get("icon"):
            out.append(f'<rect x="{fmt(b.x + 10)}" y="{fmt(b.y + 7)}" width="24" height="24" rx="5" fill="{color}"/>')
            out.append(icon_markup(d, g["icon"], b.x + 13, b.y + 10, 18))
            tx = b.x + 42
        out.append(f'<text x="{fmt(tx)}" y="{fmt(b.y + 24)}" font-size="13" font-weight="600" '
                   f'fill="{th["ink"]}">{escape(g["label"])}</text>')

    for r in routes:
        pts = list(r.points)
        dash = ' stroke-dasharray="6 4"' if r.edge.get("public") else ""
        head, pts[-1] = arrowhead(pts[-1], pts[-2], th["edge"])
        heads = [head]
        if r.edge.get("both"):
            tail, pts[0] = arrowhead(pts[0], pts[1], th["edge"])
            heads.append(tail)
        out.append(f'<path d="{rounded_path(pts)}" fill="none" stroke="{th["edge"]}" stroke-width="1.6"{dash}/>')
        out.extend(heads)

    for box, label in labels:
        out.append(f'<rect x="{fmt(box.x)}" y="{fmt(box.y)}" width="{fmt(box.w)}" height="{fmt(box.h)}" rx="9" '
                   f'fill="{th["bg"]}" stroke="{th["card_stroke"]}"/>')
        out.append(f'<text x="{fmt(box.cx)}" y="{fmt(box.cy + 3.8)}" font-size="{EDGE_LABEL_SIZE}" '
                   f'text-anchor="middle" fill="{th["muted"]}">{escape(label)}</text>')

    for nid, n in d.nodes.items():
        b = lay.boxes[nid]
        color = KIND_COLORS[n["kind"]]
        dash = ' stroke-dasharray="5 4"' if n.get("public") else ""
        out.append(f'<rect x="{fmt(b.x)}" y="{fmt(b.y)}" width="{NODE_W}" height="{NODE_H}" rx="8" '
                   f'fill="{th["card"]}" stroke="{th["card_stroke"]}" stroke-width="1.2"{dash}/>')
        ty = b.y + (NODE_H - TILE) / 2
        out.append(f'<rect x="{fmt(b.x + 10)}" y="{fmt(ty)}" width="{TILE}" height="{TILE}" rx="6" fill="{color}"/>')
        out.append(icon_markup(d, n["icon"], b.x + 10 + (TILE - ICON) / 2, ty + (TILE - ICON) / 2, ICON))
        lines, size = node_lines(n["label"])
        line_h = size * 1.25
        first = b.cy - (len(lines) - 1) * line_h / 2 + size * 0.35
        for i, line in enumerate(lines):
            out.append(f'<text x="{fmt(b.x + TILE + 22)}" y="{fmt(first + i * line_h)}" font-size="{size}" '
                       f'font-weight="600" fill="{th["ink"]}">{escape(line)}</text>')

    if has_public or d.edges:
        x = MARGIN
        entries = [("", "Private network")] + ([(' stroke-dasharray="6 4"', "Public internet")] if has_public else [])
        for dash, text in entries:
            y = legend_y + 6
            out.append(f'<path d="M{fmt(x)} {fmt(y)}H{fmt(x + 34)}" stroke="{th["edge"]}" stroke-width="1.6"{dash}/>')
            out.append(arrowhead((x + 42, y), (x, y), th["edge"])[0])
            out.append(f'<text x="{fmt(x + 52)}" y="{fmt(y + 4)}" font-size="12" fill="{th["muted"]}">'
                       f"{escape(text)}</text>")
            x += 52 + text_width(text, 12) + 32
    out.append("</svg>")
    return "\n".join(out) + "\n", warnings


def render_html(d: Diagram) -> tuple[str, list[str]]:
    svg, warnings = render_svg(d, show_title=False)
    cards = "".join(
        f'<section class="card"><h2>{escape(c.get("title", ""))}</h2><ul>'
        + "".join(f"<li>{escape(item)}</li>" for item in c.get("items", []))
        + "</ul></section>"
        for c in d.cards
    )
    page = (TEMPLATE.read_text(encoding="utf-8")
            .replace("{{title}}", escape(d.title or "Architecture diagram"))
            .replace("{{theme}}", d.theme_name)
            .replace("{{cards}}", f'<div class="cards">{cards}</div>' if cards else "")
            .replace("{{svg}}", svg))
    return page, warnings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", nargs="?", help="diagram spec, JSON")
    ap.add_argument("-o", "--output", help="output file; .svg or .html")
    ap.add_argument("--format", choices=("svg", "html"), help="defaults to the output file's extension")
    ap.add_argument("--strict", action="store_true", help="exit 2 when the layout has any warning")
    ap.add_argument("--list-icons", action="store_true", help="print the icon names by source and exit")
    args = ap.parse_args(argv)

    icons = load_icons()
    if args.list_icons:
        for path in sorted(ICON_DIR.glob("*.json")):
            print(f"{path.stem}: " + " ".join(sorted(json.loads(path.read_text(encoding="utf-8")))))
        return 0
    if not args.spec or not args.output:
        ap.error("spec and --output are required")
    fmt_name = args.format or Path(args.output).suffix.lstrip(".").lower()
    if fmt_name not in ("svg", "html"):
        ap.error("pass --format svg|html or use a .svg/.html output name")
    try:
        spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
        diagram = Diagram(spec, icons)
        text, warnings = render_html(diagram) if fmt_name == "html" else render_svg(diagram)
    except (SpecError, json.JSONDecodeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    Path(args.output).write_text(text, encoding="utf-8")
    for w in dict.fromkeys(warnings):
        print(f"warning: {w}", file=sys.stderr)
    print(f"wrote {args.output} ({len(diagram.nodes)} boxes, {len(diagram.edges)} edges, "
          f"{len(dict.fromkeys(warnings))} warnings)", file=sys.stderr)
    return 2 if args.strict and warnings else 0


if __name__ == "__main__":
    sys.exit(main())
