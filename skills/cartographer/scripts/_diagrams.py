"""SVG diagram output shared by the scripted phases.

Architecture-style overviews go through the system-design renderer (icon boxes, top-to-bottom flow).
Large dependency, call and class graphs go through Graphviz `dot`; without it the `.dot` source is still
written and a message says how to render it.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

RENDERER = Path.home() / ".agents/skills/system-design/topics/architecture-diagram/scripts/render_diagram.py"
DOT_TIMEOUT_SECONDS = 300
# Many unconnected classes or leaf files end up on one rank, which made a 10,780 x 448 px strip on
# llp-payment-hub. Staggering leaves over 6 ranks and chains of 8 brought it to 3,265 x 1,725.
UNFLATTEN_ARGS = ["-f", "-l", "6", "-c", "8"]
_dot_missing_reported = False


def dot_quote(text: str) -> str:
    return '"' + str(text).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def render_dot(source: str, svg_path: Path) -> bool:
    """Write `<name>.dot` next to `svg_path` and render it to SVG with Graphviz. True when the SVG was written."""
    global _dot_missing_reported
    svg_path = Path(svg_path)
    dot_path = svg_path.with_suffix(".dot")
    dot_path.write_text(source, encoding="utf-8")
    dot = shutil.which("dot")
    if not dot:
        if not _dot_missing_reported:
            print("Graphviz `dot` not found, so graph diagrams were written as .dot files only. "
                  "Install it with `brew install graphviz`, then render one with "
                  "`dot -Tsvg <file>.dot -o <file>.svg`.", file=sys.stderr)
            _dot_missing_reported = True
        return False
    try:
        layout_source = source
        unflatten = shutil.which("unflatten")
        if unflatten:
            layout_source = subprocess.run([unflatten, *UNFLATTEN_ARGS], input=source, check=True,
                                           timeout=DOT_TIMEOUT_SECONDS, capture_output=True,
                                           text=True).stdout
        subprocess.run([dot, "-Tsvg", "-o", str(svg_path)], input=layout_source, check=True,
                       timeout=DOT_TIMEOUT_SECONDS, capture_output=True, text=True)
    except subprocess.TimeoutExpired:
        print(f"dot took over {DOT_TIMEOUT_SECONDS}s on {dot_path}; render it by hand or trim the graph.",
              file=sys.stderr)
        return False
    except subprocess.CalledProcessError as exc:
        print(f"dot failed on {dot_path}: {exc.stderr.strip()}", file=sys.stderr)
        return False
    return True


def render_architecture(spec: dict, svg_path: Path) -> bool:
    """Write the spec as `<name>.diagram.json` and render it with the system-design renderer."""
    svg_path = Path(svg_path)
    spec_path = svg_path.with_suffix(".diagram.json")
    spec_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    if not RENDERER.exists():
        print(f"Architecture renderer not found at {RENDERER}; wrote {spec_path} only. "
              "Install the system-design skill to render it.", file=sys.stderr)
        return False
    result = subprocess.run([sys.executable, str(RENDERER), str(spec_path), "-o", str(svg_path)],
                            capture_output=True, text=True)
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)
    return result.returncode == 0
