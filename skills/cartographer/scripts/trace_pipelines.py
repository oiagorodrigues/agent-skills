#!/usr/bin/env python3
"""
Phase 1.5: Trace functional pipelines from entry points through the call graph.

For each entry point (API endpoint handler, `main()`, `if __name__ == "__main__"`,
CLI commands, scheduled jobs), walk the resolved call graph and capture the
chain of internal calls. Output:

  - pipelines.json     — list of pipelines, each is a tree of call nodes
  - pipelines.svg      — combined call graph (one cluster per pipeline), rendered with Graphviz
  - pipelines/<name>.svg — per-pipeline call graph
  (each .svg has its .dot source next to it; without Graphviz only the .dot is written)

This is what gives the project a "functional UML": chains of `route_X →
service_Y → repository_Z → external_call`. Without it the project map is
just an import diagram, which doesn't tell you what calls what.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict, deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _diagrams import dot_quote, render_dot

MAX_DEPTH_DEFAULT = 6
MAX_NODES_PER_PIPELINE = 60


def build_indexes(pmap):
    sym_by_id = {s["id"]: s for s in pmap["symbols"]}
    calls_by_caller = defaultdict(list)
    for c in pmap.get("calls", []):
        if c.get("callee_id"):
            calls_by_caller[c["caller_id"]].append(c)
    return sym_by_id, calls_by_caller


def find_entry_points(pmap, sym_by_id):
    """Endpoints + main() + CLI handlers + Celery/RQ tasks.

    Returns a list of entry-point dicts: {kind, label, symbol_id}.
    """
    entries = []

    # 1. API endpoint handlers
    for ep in pmap.get("endpoints", []):
        if ep.get("handler_id") and ep["handler_id"] in sym_by_id:
            entries.append({
                "kind": "endpoint",
                "label": f"{ep['method']} {ep['path']}",
                "symbol_id": ep["handler_id"],
                "framework": ep.get("framework", ""),
            })

    # 2. main() functions in any file
    for s in pmap["symbols"]:
        if s["name"] == "main" and s["kind"] == "function":
            entries.append({
                "kind": "main",
                "label": f"main() in {s['file']}",
                "symbol_id": s["id"],
                "framework": "",
            })

    # 3. functions decorated as Celery/RQ tasks would have decorators —
    #    we don't currently capture decorators at AST level, so this is
    #    a heuristic via the call graph: any symbol that calls
    #    "celery.task" or whose caller_id is itself never called from
    #    anywhere internal AND lives in a workers/jobs/tasks directory.
    called_set = {c["callee_id"] for c in pmap.get("calls", []) if c.get("callee_id")}
    worker_dirs = ("workers/", "jobs/", "tasks/", "consumers/", "schedulers/")
    for s in pmap["symbols"]:
        if s["kind"] not in {"function", "method"}:
            continue
        if s["id"] in called_set:
            continue
        if any(d in s["file"] for d in worker_dirs):
            entries.append({
                "kind": "worker",
                "label": f"task {s['name']}() in {s['file']}",
                "symbol_id": s["id"],
                "framework": "",
            })

    # 4. dedupe by symbol id (keep first kind seen)
    seen = set()
    deduped = []
    for e in entries:
        if e["symbol_id"] in seen:
            continue
        seen.add(e["symbol_id"])
        deduped.append(e)
    return deduped


def trace_pipeline(start_id, sym_by_id, calls_by_caller,
                   max_depth=MAX_DEPTH_DEFAULT,
                   max_nodes=MAX_NODES_PER_PIPELINE):
    """BFS from start_id through call graph. Returns:
       {nodes: [symbol_ids], edges: [(caller, callee)], external_calls: [str]}.
    """
    nodes = set()
    edges = set()
    external = []
    visited = {start_id}
    queue = deque([(start_id, 0)])
    nodes.add(start_id)

    while queue and len(nodes) < max_nodes:
        node, depth = queue.popleft()
        if depth >= max_depth:
            continue
        for c in calls_by_caller.get(node, []):
            callee_id = c["callee_id"]
            if not callee_id:
                external.append(c.get("callee_name", ""))
                continue
            edges.add((node, callee_id))
            if callee_id not in visited:
                visited.add(callee_id)
                nodes.add(callee_id)
                queue.append((callee_id, depth + 1))

    # tally external calls
    ext_counter = defaultdict(int)
    for e in external:
        ext_counter[e] += 1
    return {
        "nodes": sorted(nodes),
        "edges": sorted(edges),
        "external_top": sorted(ext_counter.items(), key=lambda x: -x[1])[:15],
    }


def safe_id(s, max_len=50):
    return re.sub(r"\W+", "_", s)[:max_len]


GRAPH_HEADER = [
    "  rankdir=TB;",
    '  node [shape=box, style="rounded,filled", fillcolor="#ffffff", color="#d0d7de", '
    'fontname="Helvetica", fontsize=11];',
    '  edge [color="#59636e", arrowsize=0.7];',
]


def render_pipeline_dot(entry, trace, sym_by_id):
    """Graphviz source for one pipeline: the entry point on top, its call chain below."""
    lines = ["digraph pipeline {", *GRAPH_HEADER]
    for nid in trace["nodes"]:
        s = sym_by_id.get(nid)
        label = f"{s['name']}\n{s['file']}:{s['line']}" if s else nid
        lines.append(f"  {dot_quote(nid)} [label={dot_quote(label)}];")

    entry_id = entry["symbol_id"]
    lines.append(f'  {dot_quote(entry_id)} [fillcolor="#fef3c7", color="#d97706", penwidth=2];')

    nodes = set(trace["nodes"])
    for caller, callee in trace["edges"]:
        if caller in nodes and callee in nodes:
            lines.append(f"  {dot_quote(caller)} -> {dot_quote(callee)};")

    if trace["external_top"]:
        ext_label = "external:\n" + "\n".join(f"{n} ({c})" for n, c in trace["external_top"][:6])
        ext_id = f"ext_{safe_id(entry_id)}"
        lines.append(f'  {dot_quote(ext_id)} [label={dot_quote(ext_label)}, fillcolor="#fee2e2", '
                     f'color="#991b1b", style="rounded,filled,dashed"];')
        lines.append(f"  {dot_quote(entry_id)} -> {dot_quote(ext_id)} [style=dashed];")
    lines.append("}")
    return "\n".join(lines) + "\n"


def render_combined_dot(pipelines, sym_by_id, max_pipelines=10):
    """Combined graph: one cluster per pipeline (top N by node count)."""
    top = sorted(pipelines, key=lambda p: -len(p["trace"]["nodes"]))[:max_pipelines]
    lines = ["digraph pipelines {", *GRAPH_HEADER]
    for i, p in enumerate(top):
        lines.append(f"  subgraph cluster_{i} {{")
        lines.append(f'    label={dot_quote(p["entry"]["label"])}; color="#8c959f"; fontname="Helvetica";')
        for nid in p["trace"]["nodes"]:
            s = sym_by_id.get(nid)
            if not s:
                continue
            lines.append(f"    {dot_quote(f'P{i}_{nid}')} [label={dot_quote(s['name'])}];")
        for caller, callee in p["trace"]["edges"]:
            lines.append(f"    {dot_quote(f'P{i}_{caller}')} -> {dot_quote(f'P{i}_{callee}')};")
        lines.append("  }")
    lines.append("}")
    return "\n".join(lines) + "\n"


def pipeline_name(entry):
    label = entry["label"]
    # filename-safe: replace any non-[A-Za-z0-9_-.] (including / and { })
    label = re.sub(r"[^A-Za-z0-9_\-.]", "_", label)
    label = re.sub(r"_+", "_", label).strip("_")
    return label[:60] or "pipeline"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project_map", help="Path to project-map.json")
    ap.add_argument("--output-dir", "-o", default=".cartographer")
    ap.add_argument("--max-depth", type=int, default=MAX_DEPTH_DEFAULT)
    ap.add_argument("--max-nodes", type=int, default=MAX_NODES_PER_PIPELINE)
    args = ap.parse_args()

    pmap = json.loads(Path(args.project_map).read_text(encoding="utf-8"))
    sym_by_id, calls_by_caller = build_indexes(pmap)

    entries = find_entry_points(pmap, sym_by_id)
    print(f"Found {len(entries)} entry points "
          f"({sum(1 for e in entries if e['kind']=='endpoint')} endpoints, "
          f"{sum(1 for e in entries if e['kind']=='main')} mains, "
          f"{sum(1 for e in entries if e['kind']=='worker')} workers)",
          file=sys.stderr)

    pipelines = []
    for entry in entries:
        trace = trace_pipeline(entry["symbol_id"], sym_by_id, calls_by_caller,
                               max_depth=args.max_depth,
                               max_nodes=args.max_nodes)
        if len(trace["nodes"]) <= 1 and not trace["external_top"]:
            # entry point with no outgoing internal calls and no external —
            # not really a pipeline, just a stub. skip.
            continue
        pipelines.append({"entry": entry, "trace": trace})

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pipelines_dir = out_dir / "pipelines"
    pipelines_dir.mkdir(parents=True, exist_ok=True)

    # write pipelines.json
    out_data = {
        "pipelines": [
            {
                "entry": p["entry"],
                "node_count": len(p["trace"]["nodes"]),
                "edge_count": len(p["trace"]["edges"]),
                "external_top": p["trace"]["external_top"],
                "nodes": [
                    {
                        "id": nid,
                        "name": sym_by_id[nid]["name"] if nid in sym_by_id else nid,
                        "file": sym_by_id[nid]["file"] if nid in sym_by_id else "",
                        "line": sym_by_id[nid]["line"] if nid in sym_by_id else 0,
                    } for nid in p["trace"]["nodes"]
                ],
                "edges": [list(e) for e in p["trace"]["edges"]],
            } for p in pipelines
        ],
        "stats": {
            "total_pipelines": len(pipelines),
            "max_depth": args.max_depth,
            "max_nodes_per_pipeline": args.max_nodes,
        },
    }
    pj_path = out_dir / "pipelines.json"
    pj_path.write_text(json.dumps(out_data, indent=2), encoding="utf-8")

    for p in pipelines:
        nm = pipeline_name(p["entry"])
        render_dot(render_pipeline_dot(p["entry"], p["trace"], sym_by_id),
                   pipelines_dir / f"{nm}.svg")

    combined_path = out_dir / "pipelines.svg"
    if not render_dot(render_combined_dot(pipelines, sym_by_id), combined_path):
        combined_path = combined_path.with_suffix(".dot")

    print(f"\nWrote {pj_path}", file=sys.stderr)
    print(f"Wrote {combined_path}", file=sys.stderr)
    print(f"Wrote {len(pipelines)} pipeline diagrams to {pipelines_dir}/",
          file=sys.stderr)
    print(f"\nTop 10 pipelines by node count:", file=sys.stderr)
    for p in sorted(pipelines, key=lambda p: -len(p["trace"]["nodes"]))[:10]:
        print(f"  {len(p['trace']['nodes']):>3} nodes  "
              f"{p['entry']['kind']:<8}  {p['entry']['label']}",
              file=sys.stderr)


if __name__ == "__main__":
    main()
