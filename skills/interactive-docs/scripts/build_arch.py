# -*- coding: utf-8 -*-
"""Build the INFRASTRUCTURE doc and the AI WORKFLOWS doc from one `arch.json`.

    python3 build_arch.py arch.json                       # -> both docs
    python3 build_arch.py arch.json --doc infra           # just the infra doc
    python3 build_arch.py arch.json --doc ai --out AI.html
    python3 build_arch.py arch.json --strict              # exit 2 if any diagram has a layout warning

Outputs are single self-contained theme-aware HTML files. Every diagram is drawn by the local
system-design renderer (~/.agents/skills/system-design/topics/architecture-diagram/scripts/
render_diagram.py) at build time and embedded as an SVG image, so the docs open offline with
no script library. Its spec format (nodes with row/col/kind/icon, groups, edges) is in that
folder's README.md.

--------------------------------------------------------------------------------------
arch.json — every key is OPTIONAL; sections you omit are simply not rendered.
Write only what you VERIFIED in the codebase. `src` fields are `path/to/file.py:42`.
--------------------------------------------------------------------------------------
{
  "project": "MyApp",
  "tagline": "3 containers, a self-hosted LLM and SSO, behind JWT.",
  "source_of_truth": "read from docker-compose.yml, api/config.py @ 4f2a1c9",

  "tiers": [ {"id":"client","label":"Client","color":"violet"},
             {"id":"delivery","label":"Delivery","color":"cyan"},
             {"id":"app","label":"Application","color":"green"},
             {"id":"data","label":"Data & AI","color":"amber"} ],

  "nodes": [
    {"id":"browser","tier":"client","name":"User's browser","tech":"React 18 SPA",
     "shape":"actor","icon":"🧑‍💻","role":"What it is / does, one line.",
     "kv":{"Talks_to":"web:8080","Auth":"JWT in localStorage"},
     "chips":["spa"], "src":"web/src/main.tsx:1",
     "external":false, "unused":false,
     "diagram":{"label":"Browser","kind":"people","icon":"browser","row":0,"col":1}}
  ],                                       # "diagram" is optional: overrides for the renderer node
  "edges": [ {"from":"browser","to":"web","label":"HTTPS","kind":"sync"},
             {"from":"api","to":"worker","label":"enqueue","kind":"async"},
             {"from":"api","to":"vector","label":"never called","kind":"inferred"} ],
  "flow_subgraphs": false,                 # true = frame each tier as a renderer group
  "flow_diagram": null,                    # optional: a full renderer spec drawn instead of
                                           # the one derived from tiers/nodes/edges

  "lifecycle":  ["Browser loads the SPA from nginx …", "…"],
  "containers": [{"service":"api","image":"myapp/api:1.4","port":"8000",
                  "depends":"db, redis","restart":"unless-stopped","src":"docker-compose.yml:20"}],
  "storage":    [{"name":"Postgres volume","what":"…","where":"pgdata:/var/lib/postgresql/data",
                  "backup":"pg_dump nightly","src":"docker-compose.yml:41"}],
  "external":   [{"name":"Okta","what":"SSO / OIDC","reached":"outbound HTTPS",
                  "required":"yes","src":"api/auth/oidc.py:18"}],

  "seeding": {
    "schema_source": "restore",            # create_all | migrations | restore | none
    "schema_note": "Schema AND first accounts come from db-backup.tar.gz; no create_all exists.",
    "steps": [{"what":"Bring the data tier up","cmd":"docker compose up -d db redis"},
              {"what":"Restore the dump (schema + first org/admin)",
               "cmd":"gunzip -c db-backup.sql.gz | docker compose exec -T db psql -U app app"},
              {"what":"Apply incremental migrations","cmd":"docker compose run --rm api alembic upgrade head"},
              {"what":"Seed reference data","cmd":"docker compose run --rm api python -m app.seed_reference"},
              {"what":"Demo data (DESTRUCTIVE, dev only)","cmd":"python -m app.seed_demo --wipe",
               "danger":true}],
    "backup": ["Postgres volume pgdata", "uploads volume", "vector index volume"],
    "tests": "pytest spins an isolated DB via testcontainers (tests/conftest.py:22)"
  },
  "security": ["JWT HS256, 12h expiry (api/auth/jwt.py:14)", "…"],
  "scaling":  ["4 uvicorn workers, CPU-bound scoring is the ceiling (…)", "…"],
  "deploy":   [{"what":"Build images","cmd":"docker compose build"},
               {"what":"Start","cmd":"docker compose up -d"}],

  "ai": {
    "present": true,
    "summary": "One paragraph: what the model is used for and what it is NOT used for.",
    "surface_diagram": null,                      # optional full renderer spec for the surface map
    "surface": {                                  # optional; auto-built from workflows if absent
      "nodes":[{"id":"grade","name":"Answer grading","tech":"gpt-4o-mini","shape":"model",
                "role":"…","kv":{},"src":"api/ai/grade.py:30"}],
      "edges":[{"from":"api","to":"grade","label":"sync call","kind":"sync"}]
    },
    "workflows": [
      {"id":"grade", "name":"Answer grading", "kind":"chain",
       "purpose":"…", "trigger":"POST /api/submissions/{id}/grade (api/routes/grade.py:44)",
       "model":"gpt-4o-mini", "chips":["temperature 0","json_schema output"],
       "diagram":{"label":"Answer grading"},  # optional: renderer overrides for the surface map box
       "diagrams":[
         {"title":"Pipeline","spec":{"nodes":[{"id":"A","label":"Submission","kind":"people","row":0},
                                              {"id":"B","label":"Extract text","kind":"compute","row":1}],
                                     "edges":[{"from":"A","to":"B","label":"upload"}]}},
         {"title":"One real turn","steps":["Client → API: POST …","API → model: grade(…)"],
          "note":"two model round-trips per submission"}
       ],                                  # "spec" = renderer spec; "steps" = one turn, in order
       "nodes":{"B":{"nm":"Extract text","role":"pdfplumber, no OCR",
                     "kv":{"File":"api/ai/extract.py:12","Budget":"12k chars, hard truncate"},
                     "chips":["lossy"]}},
       "io":{"label":"Contract","Input":"…","Output":"…","Latency":"p50 1.8s"},
       "failure":["429 → 3 retries, exponential backoff (api/ai/client.py:60)",
                  "still failing → status=needs_review, no fallback model"]}
    ],
    "prompts": [{"name":"grade_system","file":"api/prompts/grade.md","purpose":"…",
                 "vars":"rubric, answer_text","budget":"12k chars","model":"gpt-4o-mini"}],
    "models":  [{"name":"gpt-4o-mini","provider":"OpenAI","where":"grading","params":"temp 0, max 1200",
                 "src":"api/ai/client.py:9"}],
    "context": {"budget":"128k tokens", "note":"…",
                "composition":[{"part":"System + rubric","tokens":900},
                               {"part":"Submission text","tokens":3000},
                               {"part":"Reserved for output","tokens":1200}],
                "leaves_the_box":"Submission text + rubric go to OpenAI. No PII redaction today.",
                "retention":"OpenAI API, 30-day abuse-monitoring retention, no training."},
    "cost":    [{"what":"One grading call","math":"~4.1k in + 0.9k out","estimate":"$0.0009"}],
    "state_of_play": [
      {"claim":"Grading calls the model on every submit","status":"wired","evidence":"api/routes/grade.py:44"},
      {"claim":"Qdrant + bge-small are deployed for semantic search","status":"provisioned-unused",
       "evidence":"docker-compose.yml:70; no client import anywhere in api/"}
    ]
  }
}
"""
import os, re, sys, json, argparse, base64, html as _html

# The only diagram engine: the system-design renderer (JSON spec -> icon-based SVG).
RENDERER_DIR = os.path.expanduser("~/.agents/skills/system-design/topics/architecture-diagram/scripts")

PALETTE = {"cyan": "var(--cyan)", "green": "var(--green)", "amber": "var(--amber)",
           "violet": "var(--violet)", "pink": "var(--pink)", "red": "var(--red)"}

WARNED = []         # (diagram title, warning) pairs, reported at the end


def e(s):
    return _html.escape(str(s if s is not None else ""))


def sid(s):
    """A safe id for scopes and generated nodes."""
    s = re.sub(r"[^A-Za-z0-9_]", "_", str(s))
    return ("n_" + s) if not s or s[0].isdigit() else s


def load_renderer():
    path = os.path.join(RENDERER_DIR, "render_diagram.py")
    if not os.path.exists(path):
        sys.exit("error: the diagram renderer is missing at %s\n"
                 "  It ships with the system-design skill (~/.agents/skills/system-design)." % path)
    sys.path.insert(0, RENDERER_DIR)
    sys.dont_write_bytecode = True      # don't leave __pycache__ inside the system-design skill
    import render_diagram
    return render_diagram


RD = None


# ---------------------------------------------------------------- renderer specs

# arch.json `shape` -> renderer `kind` (colour family) and icon. A node's "diagram" object
# overrides any of these, and a full spec (flow_diagram, surface_diagram, a workflow
# diagram's "spec") replaces the derived one entirely.
KIND_BY_SHAPE = {"actor": "people", "db": "database", "store": "database", "queue": "queue",
                 "model": "compute", "ext": "vendor", "doc": "storage", "decision": "service",
                 "service": "service", "box": "compute"}
ICON_BY_SHAPE = {"actor": "users", "model": "bot", "store": "database"}


def layer_rows(nodes, edges):
    """Row per node when there are no tiers: steps from the nodes nothing points to (breadth
    first, so a loop edge back up doesn't push its target down)."""
    ids = [n["id"] for n in nodes]
    out = {i: [] for i in ids}
    has_in = set()
    for ed in edges or []:
        if ed.get("from") in out and ed.get("to") in out and ed["from"] != ed["to"]:
            out[ed["from"]].append(ed["to"])
            has_in.add(ed["to"])
    row = {}
    for root in [i for i in ids if i not in has_in] + ids:   # roots first; then anything in a pure cycle
        if root in row:
            continue
        row[root] = 0 if root not in has_in else max(row.values() or [0]) + 1
        queue = [root]
        while queue:
            cur = queue.pop(0)
            for nxt in out[cur]:
                if nxt not in row:
                    row[nxt] = row[cur] + 1
                    queue.append(nxt)
    return row


def derive_spec(nodes, edges, tiers=None, group_tiers=False, title=""):
    """Turn arch.json nodes/edges/tiers into a renderer spec, flowing top to bottom."""
    used_tiers = [t for t in (tiers or []) if any(n.get("tier") == t["id"] for n in nodes)]
    tier_row = {t["id"]: i for i, t in enumerate(used_tiers)}
    auto_row = layer_rows(nodes, edges) if not used_tiers else {}
    spec_nodes = []
    for n in nodes:
        shape = n.get("shape") or ("ext" if n.get("external") else "box")
        kind = "reference" if n.get("unused") else ("vendor" if n.get("external") else
                                                    KIND_BY_SHAPE.get(shape, "compute"))
        if used_tiers:
            row = tier_row.get(n.get("tier"), len(used_tiers))
        else:
            row = auto_row.get(n["id"], 0)
        sn = {"id": n["id"], "label": n.get("name", n["id"]), "kind": kind, "row": row}
        if ICON_BY_SHAPE.get(shape) and kind not in ("reference", "vendor"):
            sn["icon"] = ICON_BY_SHAPE[shape]
        sn.update(n.get("diagram") or {})
        sn["id"] = n["id"]
        spec_nodes.append(sn)
    ids = {n["id"] for n in nodes}
    spec_edges = [{k: v for k, v in (("from", ed["from"]), ("to", ed["to"]), ("label", ed.get("label")))
                   if v} for ed in edges or [] if ed.get("from") in ids and ed.get("to") in ids
                  and ed["from"] != ed["to"]]
    spec = {"title": title, "nodes": spec_nodes, "edges": spec_edges}
    if group_tiers and used_tiers:
        spec["groups"] = [{"id": "tier_" + sid(t["id"]), "label": t.get("label", t["id"]),
                           "contains": [n["id"] for n in nodes if n.get("tier") == t["id"]]}
                          for t in used_tiers]
    return spec


def render_spec(spec, title):
    """Render a spec to SVG text with the system-design renderer; collect its warnings."""
    global RD
    if RD is None:
        RD = load_renderer()
    try:
        d = RD.Diagram(spec, RD.load_icons())
        svg, warnings = RD.render_svg(d, show_title=False)
    except RD.SpecError as exc:
        sys.exit("error: diagram %r: %s" % (title or spec.get("title", ""), exc))
    for w in dict.fromkeys(warnings):
        WARNED.append((title or spec.get("title", ""), w))
    return svg, d


# ---------------------------------------------------------------- html fragments

class Doc(object):
    def __init__(self, title, project, tagline, source_of_truth=""):
        self.title, self.project = title, project
        self.tagline, self.sot = tagline, source_of_truth
        self.parts, self.toc, self.n = [], [], 0
        self.diagrams = 0           # rendered diagrams
        self.scopes = {}            # scope -> {key: detail dict}

    def section(self, label, sub=""):
        self.n += 1
        anchor = "s%02d" % self.n
        self.toc.append((anchor, label))
        self.parts.append('<h2 id="%s"><span class="n">%02d</span>%s</h2>' % (anchor, self.n, e(label)))
        if sub:
            self.parts.append('<p class="sub">%s</p>' % sub)
        return self

    def add(self, html):
        self.parts.append(html)
        return self

    def diagram(self, spec, title="", scope=None, details=None):
        """Render `spec` and embed it as an SVG image. With `scope`, add a detail panel and one
        button per entry in `details` (key -> detail dict) that fills it."""
        if not spec or not spec.get("nodes"):
            return self
        svg, d = render_spec(spec, title)
        self.diagrams += 1
        uri = "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")
        cap = '<div class="dg-t">%s</div>' % e(title) if title else ""
        picks = det = ""
        if scope:
            labels = {nid: n.get("label", nid) for nid, n in d.nodes.items()}
            btns = "".join('<button class="pick" data-node="%s|%s">%s</button>'
                           % (e(scope), e(k), e((v or {}).get("nm") or labels.get(k, k)))
                           for k, v in (details or {}).items())
            picks = '<div class="picks">%s</div>' % btns if btns else ""
            det = '<div class="detail" id="det-%s">Pick a step to inspect it.</div>' % e(scope)
        self.parts.append('<div class="diagram">%s<img class="dg-img" alt="%s" src="%s">%s%s</div>'
                          % (cap, e(title or spec.get("title") or "Diagram"), uri, picks, det))
        return self

    def steps(self, items, title="", note=""):
        """One turn written out in order, for what used to be a sequence diagram."""
        if not items:
            return self
        cap = '<div class="dg-t">%s</div>' % e(title) if title else ""
        lis = "".join("<li>%s</li>" % s for s in items)
        self.parts.append('<div class="diagram">%s<ol class="steps">%s</ol>%s</div>'
                          % (cap, lis, ('<div class="note">%s</div>' % note) if note else ""))
        return self

    def table(self, cols, rows):
        if not rows:
            return self
        th = "".join("<th>%s</th>" % e(c) for c in cols)
        body = []
        for r in rows:
            body.append("<tr>" + "".join("<td>%s</td>" % (r.get(c.lower().replace(" ", "_"), "") or "")
                                         for c in cols) + "</tr>")
        self.parts.append('<div class="tblwrap"><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>'
                          % (th, "".join(body)))
        return self


CSS = r"""
:root{
  --bg:#eef2f8; --panel:#fff; --panel2:#f4f7fb; --ink:#182031; --muted:#5a677d; --line:#dde4ee;
  --cyan:#0284c7; --green:#059669; --amber:#b45309; --violet:#7c3aed; --pink:#be185d; --red:#dc2626;
  --shadow:0 10px 30px rgba(20,30,55,.10); --shadow-sm:0 2px 10px rgba(20,30,55,.08);
  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  --sans:"Segoe UI",system-ui,-apple-system,BlinkMacSystemFont,Roboto,Helvetica,Arial,sans-serif;
}
:root[data-theme="dark"]{--bg:#0f1420;--panel:#161d2b;--panel2:#1b2434;--ink:#e8edf6;--muted:#93a0b6;--line:#273246;
  --cyan:#38bdf8;--green:#34d399;--amber:#f59e0b;--violet:#a78bfa;--pink:#f472b6;--red:#f87171;
  --shadow:0 10px 30px rgba(0,0,0,.45);--shadow-sm:0 2px 10px rgba(0,0,0,.35)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#0f1420;--panel:#161d2b;--panel2:#1b2434;--ink:#e8edf6;--muted:#93a0b6;--line:#273246;
  --cyan:#38bdf8;--green:#34d399;--amber:#f59e0b;--violet:#a78bfa;--pink:#f472b6;--red:#f87171;
  --shadow:0 10px 30px rgba(0,0,0,.45);--shadow-sm:0 2px 10px rgba(0,0,0,.35)}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);line-height:1.6;
  background-image:radial-gradient(circle at 1px 1px,rgba(120,140,180,.08) 1px,transparent 0);background-size:26px 26px}
.wrap{max-width:1120px;margin:0 auto;padding:30px 22px 100px}
header.hero{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;border:1px solid var(--line);
  border-radius:16px;padding:24px 26px;background:linear-gradient(180deg,var(--panel),var(--panel2));box-shadow:var(--shadow)}
header h1{margin:0 0 6px;font-size:26px} header h1 b{color:var(--cyan)}
header p{margin:0;color:var(--muted);font-size:14.5px;max-width:760px}
header .sot{font-family:var(--mono);font-size:11.5px;color:var(--muted);margin-top:9px;opacity:.85}
.themeb{background:var(--panel2);border:1px solid var(--line);color:var(--muted);border-radius:9px;
  padding:8px 12px;cursor:pointer;font:inherit;font-size:13px;height:fit-content}
.toc{display:flex;flex-wrap:wrap;gap:7px;margin:16px 0 4px}
.toc a{font-size:12px;font-family:var(--mono);color:var(--muted);text-decoration:none;border:1px solid var(--line);
  background:var(--panel);border-radius:20px;padding:3px 10px}
.toc a:hover{color:var(--ink);border-color:var(--cyan)}
h2{font-size:19px;margin:40px 0 6px;scroll-margin-top:16px} h2 .n{color:var(--cyan);font-family:var(--mono);font-size:14px;margin-right:8px}
h3.wf{font-size:17px;margin:26px 0 2px}
.sub{color:var(--muted);font-size:14px;margin:0 0 14px}
code{font-family:var(--mono);font-size:.85em;background:color-mix(in srgb,var(--cyan) 14%,transparent);padding:.1em .4em;border-radius:5px}
.src{font-family:var(--mono);font-size:11.5px;color:var(--muted)}
.diagram{border:1px solid var(--line);border-radius:16px;background:var(--panel);box-shadow:var(--shadow);
  padding:18px;margin-top:14px}
.dg-t{font-family:var(--mono);font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);
  margin-bottom:10px;padding-bottom:7px;border-bottom:1px dashed var(--line)}
.dg-img{display:block;max-width:100%;height:auto;margin:0 auto;border-radius:10px}
.picks{display:flex;flex-wrap:wrap;gap:7px;margin-top:12px}
.pick{font-family:var(--mono);font-size:12px;background:var(--panel2);border:1px solid var(--line);color:var(--ink);
  border-radius:20px;padding:4px 11px;cursor:pointer}
.pick:hover,.pick.active{border-color:var(--cyan)}
.tiers{display:grid;grid-template-columns:repeat(var(--tc,4),1fr);gap:10px;min-width:820px}
.tierwrap{overflow-x:auto}
.tier{display:flex;flex-direction:column;gap:12px}
.tier-h{font-family:var(--mono);font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);
  text-align:center;padding-bottom:6px;border-bottom:1px dashed var(--line)}
.node{position:relative;border:1px solid var(--line);border-left:3px solid var(--nc,var(--cyan));border-radius:12px;
  background:var(--panel2);padding:12px 13px;cursor:pointer;transition:transform .12s,box-shadow .15s;text-align:left}
.node:hover{transform:translateY(-2px);box-shadow:var(--shadow-sm)}
.node.active{box-shadow:0 0 0 2px color-mix(in srgb,var(--nc) 40%,transparent)}
.node.is-unused{opacity:.62;border-style:dashed}
.node .nm{font-weight:650;font-size:14px;margin:3px 0 2px} .node .tech{font-family:var(--mono);font-size:11px;color:var(--muted)}
.node .port{position:absolute;top:10px;right:10px;font-family:var(--mono);font-size:10.5px;color:var(--nc);
  background:color-mix(in srgb,var(--nc) 14%,transparent);padding:1px 6px;border-radius:20px}
.detail{margin-top:16px;border:1px solid var(--line);border-radius:14px;background:var(--panel2);
  box-shadow:var(--shadow-sm);padding:16px 18px;min-height:96px;text-align:left;color:var(--muted);font-size:14px}
.detail h3{margin:0 0 2px;font-size:16.5px;color:var(--ink)} .detail .role{color:var(--muted);font-size:13.5px;margin:0 0 12px}
.kv{display:grid;grid-template-columns:160px 1fr;gap:6px 14px;font-size:14px;color:var(--ink)}
.kv dt{color:var(--muted);font-family:var(--mono);font-size:12px} .kv dd{margin:0}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:9px}
.chip{font-family:var(--mono);font-size:11.5px;background:var(--panel);border:1px solid var(--line);padding:2px 8px;border-radius:20px;color:var(--muted)}
.chip.ok{border-color:color-mix(in srgb,var(--green) 55%,transparent);color:var(--green)}
.chip.warn{border-color:color-mix(in srgb,var(--amber) 55%,transparent);color:var(--amber)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px} @media(max-width:760px){.grid2{grid-template-columns:1fr}.tiers{--tc:1}}
.card{border:1px solid var(--line);border-radius:12px;background:var(--panel);box-shadow:var(--shadow-sm);padding:15px 17px;margin-top:14px}
.card h4{margin:0 0 7px;font-size:15px} .card p,.card li{font-size:14px} .card .m{color:var(--muted)}
.card.lead{border-left:3px solid var(--cyan)}
ol.steps,ul.plain{margin:0;padding-left:20px} ol.steps li,ul.plain li{margin:9px 0;font-size:14.5px}
pre.cmd{font-family:var(--mono);font-size:12.5px;background:var(--panel2);border:1px solid var(--line);
  border-left:3px solid var(--green);border-radius:8px;padding:9px 12px;margin:6px 0 0;overflow-x:auto;white-space:pre-wrap}
pre.cmd.danger{border-left-color:var(--red)}
.tblwrap{overflow-x:auto;border:1px solid var(--line);border-radius:12px;margin-top:12px;background:var(--panel)}
table{border-collapse:collapse;width:100%;font-size:13.5px;min-width:560px}
th,td{border-bottom:1px solid var(--line);padding:9px 12px;text-align:left;vertical-align:top}
th{background:var(--panel2);font-size:11.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
tr:last-child td{border-bottom:none}
.stack{display:flex;height:34px;border-radius:9px;overflow:hidden;border:1px solid var(--line);margin:12px 0 6px}
.stack i{display:grid;place-items:center;font-family:var(--mono);font-size:11px;color:#fff;font-style:normal;overflow:hidden;white-space:nowrap}
.legend{display:flex;flex-wrap:wrap;gap:14px;font-size:12.5px;color:var(--muted);margin-top:6px}
.legend b{font-weight:600;color:var(--ink)}
.badge{display:inline-block;font-family:var(--mono);font-size:11px;padding:2px 8px;border-radius:20px;border:1px solid var(--line)}
.badge.wired{color:var(--green);border-color:color-mix(in srgb,var(--green) 55%,transparent)}
.badge.provisioned-unused{color:var(--amber);border-color:color-mix(in srgb,var(--amber) 55%,transparent)}
.badge.inferred{color:var(--muted);border-style:dashed}
.badge.planned{color:var(--violet);border-color:color-mix(in srgb,var(--violet) 55%,transparent)}
.note{margin:14px 0 0;padding:12px 15px;border-radius:10px;border:1px solid var(--line);
  border-left:3px solid var(--amber);background:color-mix(in srgb,var(--amber) 8%,var(--panel));font-size:14px}
@media print{body{background:#fff}.themeb,.toc{display:none}.diagram,.card,.tblwrap{break-inside:avoid}}
"""

JS = r"""
function isDark(){var t=document.documentElement.getAttribute('data-theme');
  return t?t==='dark':matchMedia('(prefers-color-scheme:dark)').matches}
function cssv(n){return getComputedStyle(document.documentElement).getPropertyValue(n).trim()}
function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;')}

function pick(scope,key){
  var d=(SCOPES[scope]||{})[key]; var box=document.getElementById('det-'+scope); if(!box) return;
  document.querySelectorAll('[data-node]').forEach(function(n){
    if(n.dataset.node.split('|')[0]===scope) n.classList.toggle('active', n.dataset.node===scope+'|'+key)});
  if(!d){box.innerHTML='<p class="role">No recorded detail for <code>'+esc(key)+'</code>.</p>';return}
  var kv=Object.keys(d.kv||{}).map(function(k){
    return '<dt>'+esc(k.replace(/_/g,' '))+'</dt><dd>'+d.kv[k]+'</dd>'}).join('');
  var chips=(d.chips||[]).map(function(c){return '<span class="chip">'+esc(c)+'</span>'}).join('');
  box.innerHTML='<h3>'+(d.ico?d.ico+' ':'')+esc(d.nm||key)+'</h3>'
    +'<p class="role">'+(d.role||'')+'</p>'
    +(kv?'<dl class="kv">'+kv+'</dl>':'')
    +(d.src?'<div class="src" style="margin-top:9px">📄 '+esc(d.src)+'</div>':'')
    +(chips?'<div class="chips">'+chips+'</div>':'');
}

function toggleTheme(){
  var r=document.documentElement;
  r.setAttribute('data-theme', isDark()?'light':'dark');
}
document.querySelectorAll('[data-node]').forEach(function(n){
  n.addEventListener('click',function(){var p=n.dataset.node.split('|');pick(p[0],p.slice(1).join('|'))});
});
Object.keys(SCOPES).forEach(function(s){var k=Object.keys(SCOPES[s])[0]; if(k) pick(s,k)});
"""


def render(doc, out):
    d = os.path.dirname(os.path.abspath(out))
    if d:
        os.makedirs(d, exist_ok=True)   # --outdir should create its target, not traceback
    toc = "".join('<a href="#%s">%s</a>' % (a, e(t)) for a, t in doc.toc)
    html = ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<title>%s</title><style>%s</style></head><body><div class='wrap'>"
            "<header class='hero'><div><h1>%s — <b>%s</b></h1><p>%s</p>%s</div>"
            "<button class='themeb' onclick='toggleTheme()'>◐ Theme</button></header>"
            "<div class='toc'>%s</div>%s</div>"
            "<script>var SCOPES=%s;</script><script>%s</script></body></html>"
            % (e(doc.title), CSS, e(doc.project), e(doc.title.split("—")[-1].strip()),
               doc.tagline or "", ('<div class="sot">source of truth: %s</div>' % e(doc.sot)) if doc.sot else "",
               toc, "\n".join(doc.parts), json.dumps(doc.scopes), JS))
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("wrote %s  %d KB · sections: %d · diagrams: %d"
          % (out, os.path.getsize(out) // 1024, doc.n, doc.diagrams))


# ---------------------------------------------------------------- infra doc

def tier_grid(nodes, tiers):
    cols = []
    for t in tiers:
        members = [n for n in nodes if n.get("tier") == t["id"]]
        if not members:
            continue
        cells = []
        for n in members:
            color = PALETTE.get(t.get("color", "cyan"), "var(--cyan)")
            cells.append(
                '<div class="node%s" style="--nc:%s" data-node="infra|%s">%s'
                '<div class="nm">%s</div><div class="tech">%s</div></div>'
                % (" is-unused" if n.get("unused") else "", color, e(n["id"]),
                   ('<span class="port">:%s</span>' % e(n["port"])) if n.get("port") else "",
                   e(n.get("name", n["id"])), e(n.get("tech", ""))))
        cols.append('<div class="tier"><div class="tier-h">%s</div>%s</div>'
                    % (e(t.get("label", t["id"])), "".join(cells)))
    if not cols:
        return ""
    return ('<div class="diagram"><div class="tierwrap"><div class="tiers" style="--tc:%d">%s</div></div>'
            '<div class="detail" id="det-infra">Click a component to inspect it.</div></div>'
            % (len(cols), "".join(cols)))


def steps_list(items):
    out = []
    for s in items:
        if isinstance(s, str):
            out.append("<li>%s</li>" % s)
        else:
            cmd = ('<pre class="cmd%s">%s</pre>'
                   % (" danger" if s.get("danger") else "", e(s["cmd"]))) if s.get("cmd") else ""
            out.append("<li>%s%s%s</li>"
                       % (s.get("what", ""),
                          ' <span class="chip warn">destructive</span>' if s.get("danger") else "", cmd))
    return '<div class="card"><ol class="steps">%s</ol></div>' % "".join(out)


SCHEMA_NOTE = {
    "create_all": "The ORM creates the tables on startup — schema is automatic; seeding only adds rows.",
    "migrations": "Migrations build <i>and</i> seed the schema — apply them in order.",
    "restore": "The schema <b>and</b> the first accounts/org come from a database dump. "
               "The app does <b>not</b> auto-create tables — restore first, or nothing works.",
    "none": "No automated schema creation was found.",
}


def build_infra(a, out):
    nodes, tiers = a.get("nodes", []), a.get("tiers", [])
    doc = Doc("%s — Deployment Architecture" % a.get("project", "Project"),
              a.get("project", "Project"), a.get("tagline", ""), a.get("source_of_truth", ""))
    doc.scopes["infra"] = {n["id"]: {"nm": n.get("name", n["id"]), "ico": n.get("icon", ""),
                                     "role": n.get("role", ""), "kv": n.get("kv", {}),
                                     "chips": n.get("chips", []), "src": n.get("src", "")}
                           for n in nodes}

    if nodes:
        doc.section("Topology at a glance",
                    "Every component that actually exists. Dashed = external or provisioned-but-unused. "
                    "Click a box to inspect it.")
        doc.add(tier_grid(nodes, tiers))

    if a.get("edges"):
        doc.section("Request & data flow", "How the components actually talk to each other.")
        # The tier grid directly above already shows the tiering, so the flow is drawn without
        # tier frames unless the author asks for them (flow_subgraphs).
        doc.diagram(a.get("flow_diagram") or derive_spec(nodes, a["edges"], tiers, a.get("flow_subgraphs")),
                    "Data flow")
        byid = {n["id"]: n.get("name", n["id"]) for n in nodes}
        notes = ['<span><b>grey boxes</b> external or provisioned-but-unused</span>']
        for kind, label in (("async", "asynchronous / queued"), ("inferred", "inferred, not confirmed in code")):
            hits = ["%s → %s" % (e(byid.get(x["from"], x["from"])), e(byid.get(x["to"], x["to"])))
                    for x in a["edges"] if x.get("kind") == kind]
            if hits:
                notes.append("<span><b>%s:</b> %s</span>" % (label, "; ".join(hits)))
        doc.add('<div class="legend">%s</div>' % "".join(notes))

    if a.get("lifecycle"):
        doc.section("Request lifecycle", "One request, end to end.")
        doc.add(steps_list(a["lifecycle"]))

    if a.get("containers"):
        doc.section("Containers & images")
        doc.table(["Service", "Image", "Port", "Depends", "Restart", "Src"], a["containers"])

    if a.get("storage"):
        doc.section("Data & storage", "What is persisted, where it lives, how it is backed up.")
        doc.table(["Name", "What", "Where", "Backup", "Src"], a["storage"])

    if a.get("external"):
        doc.section("External services", "Anything outside the deployment boundary.")
        doc.table(["Name", "What", "Reached", "Required", "Src"], a["external"])

    seed = a.get("seeding")
    if seed:
        doc.section("Seed & initial data", "The from-zero runbook. Run these in order.")
        src = seed.get("schema_source")
        if src:
            doc.add('<div class="card lead"><h4>How the schema is created: <code>%s</code></h4>'
                    '<p class="m">%s</p>%s</div>'
                    % (e(src), SCHEMA_NOTE.get(src, ""),
                       ("<p>%s</p>" % seed["schema_note"]) if seed.get("schema_note") else ""))
        if seed.get("steps"):
            doc.add(steps_list(seed["steps"]))
        if seed.get("backup"):
            doc.add('<div class="card"><h4>Back these up</h4><ul class="plain">%s</ul></div>'
                    % "".join("<li>%s</li>" % s for s in seed["backup"]))
        if seed.get("tests"):
            doc.add('<div class="card"><h4>Test data</h4><p>%s</p></div>' % seed["tests"])

    for key, label, sub in (("security", "Security & hardening", "Each claim tied to a file."),
                            ("scaling", "Scaling & operations", "Where it breaks first.")):
        if a.get(key):
            doc.section(label, sub)
            doc.add('<div class="card"><ul class="plain">%s</ul></div>'
                    % "".join("<li>%s</li>" % s for s in a[key]))

    if a.get("deploy"):
        doc.section("Deploy steps")
        doc.add(steps_list(a["deploy"]))

    ai = a.get("ai") or {}
    if ai.get("present"):
        doc.add('<div class="note"><b>AI workflows live in their own document.</b> '
                'The boxes above only show where models and stores are <i>deployed</i>; '
                'how they are actually called — prompts, context budgets, retries, cost — is in '
                '<code>AI_WORKFLOWS.html</code>.</div>')

    render(doc, out)


# ---------------------------------------------------------------- ai doc

KIND_HINT = {
    "chain": "Prompt chain — fixed sequence of model calls.",
    "agent": "Agent loop — the model chooses tools and iterates until a stop condition.",
    "rag": "Retrieval-augmented — an index path and a query path.",
    "multi-agent": "Multiple agents over shared state.",
    "streaming": "Streamed / async — the response arrives incrementally or via a worker.",
    "guardrail": "Guardrail / eval — a check that gates or scores another output.",
    "classify": "Single-shot classification or extraction.",
}


def build_ai(a, out):
    ai = a.get("ai") or {}
    if not ai.get("present"):
        print("arch.json says ai.present is false — no AI doc built.")
        return
    doc = Doc("%s — AI Workflows" % a.get("project", "Project"),
              a.get("project", "Project"), ai.get("summary", a.get("tagline", "")),
              a.get("source_of_truth", ""))

    wfs = ai.get("workflows", [])

    # 01 surface map -----------------------------------------------------------
    surf = ai.get("surface")
    if not surf and wfs:
        # No hand-authored map: derive one. A bare list of workflow boxes with no edges
        # renders as disconnected rectangles, so hang them off an application hub — that
        # is also the honest shape (the app is what calls each of them).
        hub = sid("app_hub")
        surf = {"nodes": [{"id": hub, "name": a.get("project", "Application"),
                           "tech": "calls each workflow", "shape": "box",
                           "role": "The application code — every model call below starts here.",
                           "kv": {"Derived": "auto-generated map; add ai.surface to draw the real one"}}]
                         + [{"id": w["id"], "name": w.get("name", w["id"]),
                             "tech": w.get("model", ""), "shape": "model",
                             "role": w.get("purpose", ""), "src": w.get("trigger", ""),
                             "kv": {"Kind": w.get("kind", ""), "Trigger": w.get("trigger", "")},
                             "chips": w.get("chips", []),
                             "unused": w.get("unused", False),
                             "diagram": w.get("diagram")} for w in wfs],
                "edges": [{"from": hub, "to": w["id"], "label": w.get("kind", ""),
                           "kind": "async" if (w.get("kind") == "rag" and "async" in
                                               [c.lower() for c in (w.get("chips") or [])])
                                   else "sync"} for w in wfs]}
    if surf and surf.get("nodes"):
        doc.scopes["surf"] = {n["id"]: {"nm": n.get("name", n["id"]), "ico": n.get("icon", ""),
                                        "role": n.get("role", ""), "kv": n.get("kv", {}),
                                        "chips": n.get("chips", []), "src": n.get("src", "")}
                              for n in surf["nodes"]}
        doc.section("AI surface map",
                    "Every place this system calls a model. Click a box for the model, the call site "
                    "and the parameters.")
        doc.diagram(ai.get("surface_diagram") or derive_spec(surf["nodes"], surf.get("edges", [])),
                    "Where models are called", scope="surf", details=doc.scopes["surf"])

    # 02 per-workflow ----------------------------------------------------------
    if wfs:
        doc.section("Workflows in detail",
                    "One block per workflow. The diagram kind follows the workflow's actual shape.")
        for w in wfs:
            scope = "wf_" + sid(w["id"])
            doc.scopes[scope] = {k: dict(v) for k, v in (w.get("nodes") or {}).items()}
            chips = "".join('<span class="chip">%s</span>' % e(c) for c in (w.get("chips") or []))
            if w.get("model"):
                chips = '<span class="chip ok">%s</span>' % e(w["model"]) + chips
            doc.add('<h3 class="wf">%s</h3>'
                    '<p class="sub">%s%s</p>'
                    % (e(w.get("name", w["id"])),
                       e(KIND_HINT.get(w.get("kind", ""), w.get("kind", ""))),
                       (" &nbsp;·&nbsp; trigger: <code>%s</code>" % e(w["trigger"])) if w.get("trigger") else ""))
            if w.get("purpose"):
                doc.add('<div class="card lead"><p>%s</p>%s</div>'
                        % (w["purpose"], ('<div class="chips">%s</div>' % chips) if chips else ""))
            first = True
            for d in w.get("diagrams") or []:
                if d.get("spec"):
                    doc.diagram(d["spec"], d.get("title", ""), scope=scope if first else None,
                                details=doc.scopes[scope])
                    first = False
                elif d.get("steps"):
                    doc.steps(d["steps"], d.get("title", ""), d.get("note", ""))
                else:
                    sys.exit("error: workflow %r: each diagram needs a renderer \"spec\" or a \"steps\" "
                             "list (diagram source code is not supported)" % w["id"])
            if w.get("io"):
                io = w["io"]
                rows = "".join('<dt>%s</dt><dd>%s</dd>' % (e(k.replace("_", " ")), io[k])
                               for k in io if k != "label")
                doc.add('<div class="card"><h4>%s</h4><dl class="kv">%s</dl></div>'
                        % (e(io.get("label", "Contract")), rows))
            if w.get("failure"):
                doc.add('<div class="card"><h4>When it fails</h4><ul class="plain">%s</ul></div>'
                        % "".join("<li>%s</li>" % s for s in w["failure"]))

    # 03..07 tables ------------------------------------------------------------
    if ai.get("prompts"):
        doc.section("Prompt inventory",
                    "Every prompt that ships, where it lives, what gets injected into it, and what "
                    "happens when the input does not fit.")
        doc.table(["Name", "File", "Purpose", "Vars", "Budget", "Model"], ai["prompts"])

    if ai.get("models"):
        doc.section("Models & parameters")
        doc.table(["Name", "Provider", "Where", "Params", "Src"], ai["models"])

    ctx = ai.get("context")
    if ctx:
        doc.section("Context & data path",
                    "What is assembled into the context window, and what leaves the machine.")
        comp = ctx.get("composition") or []
        if comp:
            total = sum(float(c.get("tokens", 0)) for c in comp) or 1
            cols = ["var(--cyan)", "var(--green)", "var(--amber)", "var(--violet)", "var(--pink)"]
            bars = "".join('<i style="flex:%s;background:%s" title="%s: %s">%s</i>'
                           % (c.get("tokens", 0), cols[i % len(cols)], e(c.get("part", "")),
                              e(c.get("tokens", "")),
                              e(c.get("part", "")) if float(c.get("tokens", 0)) / total > .12 else "")
                           for i, c in enumerate(comp))
            doc.add('<div class="card"><h4>What fills the context window%s</h4><div class="stack">%s</div>'
                    '<div class="legend">%s</div></div>'
                    % ((" (budget %s)" % e(ctx["budget"])) if ctx.get("budget") else "", bars,
                       "".join('<span><b>%s</b> %s</span>' % (e(c.get("part", "")), e(c.get("tokens", "")))
                               for c in comp)))
        for k, label in (("note", "Notes"), ("leaves_the_box", "What leaves the machine"),
                         ("retention", "Retention &amp; training")):
            if ctx.get(k):
                doc.add('<div class="card"><h4>%s</h4><p>%s</p></div>' % (label, ctx[k]))

    if ai.get("cost"):
        doc.section("Cost", "Real token arithmetic, not vibes.")
        doc.table(["What", "Math", "Estimate"], ai["cost"])

    if ai.get("state_of_play"):
        doc.section("State of play", "Wired and running vs. deployed but never called.")
        rows = "".join('<tr><td>%s</td><td><span class="badge %s">%s</span></td>'
                       '<td class="src">%s</td></tr>'
                       % (s.get("claim", ""), e(s.get("status", "inferred")),
                          e(s.get("status", "inferred")), e(s.get("evidence", "")))
                       for s in ai["state_of_play"])
        doc.add('<div class="tblwrap"><table><thead><tr><th>Claim</th><th>Status</th>'
                '<th>Evidence</th></tr></thead><tbody>%s</tbody></table></div>' % rows)

    render(doc, out)


# ---------------------------------------------------------------- cli

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--doc", choices=["infra", "ai", "both"], default="both")
    ap.add_argument("--out", help="output file (only with --doc infra|ai)")
    ap.add_argument("--outdir", default=".")
    ap.add_argument("--strict", action="store_true", help="exit 2 if any diagram has a layout warning")
    args = ap.parse_args()

    try:
        with open(args.spec, encoding="utf-8") as f:
            spec = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        sys.exit("error: cannot read %s: %s" % (args.spec, exc))

    if args.doc in ("infra", "both"):
        out = args.out if (args.out and args.doc == "infra") else \
            os.path.join(args.outdir, "ARCHITECTURE_INFRASTRUCTURE.html")
        build_infra(spec, out)
    if args.doc in ("ai", "both"):
        out = args.out if (args.out and args.doc == "ai") else \
            os.path.join(args.outdir, "AI_WORKFLOWS.html")
        build_ai(spec, out)
    for title, w in WARNED:
        print("warning: diagram %r: %s" % (title, w), file=sys.stderr)
    if args.strict and WARNED:
        sys.exit(2)
