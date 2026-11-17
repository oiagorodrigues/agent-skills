---
name: architecture-diagram
description: This skill should be used when a system design needs a diagram — "draw the architecture", "diagram this system", "show the components", "make an architecture/infrastructure/topology diagram", or visualizing boxes-and-arrows, data flow, network boundaries or failure paths for a design. It renders a JSON spec into one self-contained SVG with real service and vendor icons, for embedding in Markdown, or into an HTML page around that SVG. Use it whenever the `system-design` orchestrator or a building block reaches the "draw it" step, even if the user doesn't say "diagram".
---

# Architecture Diagram

`scripts/render_diagram.py` turns a small JSON spec (components, the groups that
frame them, and the connections between them) into an AWS-style architecture
diagram: one icon box per component, flowing top to bottom, with orthogonal
arrows. It is the diagram engine for the whole plugin; the orchestrator and the
building blocks hand off here when it's time to draw.

The script needs Python 3.9+ and nothing else. The skill stores no icons: the
first render that uses an icon downloads it from its official source into a
local cache, so that render needs the network (see "Icons"). The SVG carries its
own background, so it reads the same in light and dark Markdown viewers.

## When to reach for this

At step 3 (high-level design) and step 6 (deep-dive) of the reasoning loop, and
any time the component list and their connections are known. Also for failure
paths (step 5), because a design's degradation flow is part of the design.

Don't draw before the design has stabilized (failure mode #7). A quick ASCII
sketch in the conversation is fine for early thinking.

## How to build a diagram

1. Write the spec as JSON (format below), one node per component.
2. Render it.
   ```bash
   R=~/.agents/skills/system-design/topics/architecture-diagram/scripts/render_diagram.py
   python3 $R design.json -o docs/architecture.svg    # for Markdown
   python3 $R design.json -o architecture.html        # standalone page
   python3 $R design.json -o docs/architecture.svg --offline   # use only cached icons
   ```
   In Markdown, embed the SVG as an image: `![Checkout architecture](architecture.svg)`.
   It renders on GitHub, in VS Code and in Obsidian, because it has no scripts,
   no `foreignObject` and no external references.
3. Fix every warning. The script prints a warning for crossing lines, a line
   running through a box or a group title, a group covering a box that isn't in
   it, overlapping groups, a label with more than three words, a label that names
   several components, and an edge label with no free spot. Run with `--strict`
   to make any warning exit with code 2. Most fixes are a `col` change. An icon
   that can't be fetched (offline, or a name the source doesn't have) is left
   out of its box with a warning; that warning doesn't count for `--strict`.
4. Look at the result before handing it over. `sips` renders the SVG at its real
   size (`qlmanage -t` crops to a square), then open the PNG with the Read tool.
   ```bash
   sips -s format png docs/architecture.svg --out /tmp/architecture.png
   ```
   `sips` ignores bold text, so labels look lighter than in a browser.

The HTML page has SVG, PNG and PDF (print) buttons that run in the browser with
no CDN script, and shows the spec's `cards` (key decisions and trade-offs) under
the diagram.

## Spec format

```json
{
  "title": "Checkout on AWS",
  "theme": "light",
  "nodes": [
    {"id": "buyers", "label": "Buyers", "kind": "people", "icon": "users", "row": 0, "col": 1, "public": true},
    {"id": "api", "label": "Checkout API", "kind": "compute", "icon": "aws-ecs", "row": 1, "col": 1},
    {"id": "db", "label": "Orders DB", "kind": "database", "icon": "aws-rds", "row": 2, "col": 1}
  ],
  "groups": [{"id": "vpc", "label": "VPC", "kind": "networking", "icon": "aws", "contains": ["api", "db"]}],
  "edges": [
    {"from": "buyers", "to": "api", "label": "https", "public": true},
    {"from": "api", "to": "db", "label": "app_user"}
  ],
  "cards": [{"title": "Why one database", "items": ["Writes stay under 500/s"]}]
}
```

- A node has `id`, `label` (three words or fewer), `kind`, `row` (0 at the top)
  and optionally `icon`, `col` and `public`. Without `icon` it gets the kind's
  default. `col` can be a fraction (1.5 centers a box under two others); set it
  on every node of a row or on none, and a row without it is centered.
- A group has `id`, `label`, `contains` (node or group ids, so groups nest) and
  optionally `kind` (default `networking`), `icon` and `public`. It draws a frame
  around its boxes. An edge can end on a group id to point at the whole frame.
- An edge has `from`, `to` and optionally `label` (protocol or credential, one or
  two words), `public` and `both` (arrowheads at both ends).
- `public: true` draws a dashed line or border and means the link or component is
  on the public internet. Solid means a private network. Mark something public
  only when the design or the infrastructure code shows it.
- `theme` is `light` (default) or `dark`. `cards` appear only in the HTML page.

Kinds and their colors, the same in every diagram:

| Kind | Color | For |
|---|---|---|
| `security` | `#dd344c` | identity providers, WAF, secrets, auth |
| `database`, `storage` | `#3b48cc` | databases, caches, buckets |
| `compute` | `#ed7100` | services, containers, functions, workers |
| `queue` | `#e7157b` | queues, streams, event buses |
| `networking`, `analytics` | `#8c4fff` | CDN, load balancers, DNS, VPC frames, warehouses |
| `service` | `#01a88d` | internal services and APIs |
| `people` | `#5a6b86` | users and operators |
| `vendor`, `reference` | `#7d8998` | SaaS vendors, outside systems |

## Layout rules

The diagram answers one question: what talks to what, over which network.

- One box per component. Never put several services in one box; a group frame
  can surround several boxes.
- Flow top to bottom in the order a request or the data travels: callers in row
  0, then the edge (CDN, load balancer, identity provider), then the app, then
  what it calls, then vendors. Put a reader of a database or queue below it.
- Line boxes up so lines run straight. Two boxes that overlap side to side get one
  straight line. Otherwise the line makes one right-angle turn in the gap below
  its source, and an edge that would run through a box detours down a free
  column gap instead.
- Draw network boundaries (account, VPC, subnets, cluster) as nested groups.
- Leave out boxes with no connections unless a reader would look for them.
- Keep a high-level view to about 8 to 15 boxes, and zoom into one subsystem for a
  deep-dive instead of cramming everything into one picture.

## Icons

`python3 $R --list-icons` prints every catalog key by family. A node or group
`icon` is either a catalog key or `family:name`, which reaches any icon of a
family without a catalog entry.

- `aws`: AWS Architecture Icons, full color. Keys such as `aws-lambda`,
  `aws-s3`, `aws-rds`, `aws-sqs`, `aws-ecs`, `aws-eks`, `aws-api-gateway`,
  `aws-dynamodb`, `aws-elasticache`, `aws-cognito`, `aws-cloudwatch`,
  `aws-route53`, `aws-elb`, and `aws` (the AWS Cloud logo for a group). Any
  other service: `aws:Arch_Amazon-Aurora_64`.
- `azure` and `gcp`: the Azure and Google Cloud architecture icons, full color,
  by file name, such as `azure:10023-icon-service-Kubernetes-Services` and
  `gcp:BigQuery-512-color`. `microsoftazure` and `googlecloudstorage` are keys.
- `simple-icons`: vendor logos by Simple Icons slug, drawn white on the kind
  tile, such as `stripe`, `auth0`, `datadog`, `sentry`, `postgresql`, `redis`,
  `apachekafka`, `docker`, `kubernetes`, `github`, `cloudflare`.
- `logos`: full-color logos from gilbarbara/logos for vendors Simple Icons
  lacks: `openai`, `salesforce`, `sendgrid`, `slack`, `twilio`.
- `lucide` (and `tabler` for `bucket`): line glyphs drawn white on the kind
  tile, such as `user`, `users`, `browser`, `mobile`, `server`, `database`,
  `cache`, `queue`, `stream`, `cdn`, `load-balancer`, `dns`, `gateway`,
  `lambda`, `container`, `scheduler`, `email`, `webhook`, `lock`, `key`,
  `shield`, `monitoring`, `logs`, `bot`.

Full-color icons (AWS, Azure, Google Cloud, `logos`) replace the kind tile and
keep their own colors; the box border and edges still follow the kind. One-color
glyphs sit white on the tile.

`scripts/fetch_icons.py` does the fetching; the renderer calls it for every icon
the spec uses.

- The cache is `$SYSTEM_DESIGN_ICON_CACHE`, else
  `${XDG_CACHE_HOME:-~/.cache}/agents/system-design-icons`, with one
  `<family>/<version>/` folder per icon set. Each holds `downloads/` (each download in its own folder; the AWS, Azure and
  Google zips are downloaded once), `extracted/` (the SVGs taken from a zip)
  and `icons/<name>.json` (the converted icon with its source URL and version).
- Downloads are untrusted: zips are only read, SVGs with a DOCTYPE or entity
  declaration are refused, and only plain shapes, gradients and same-document
  references are kept.
- `F=$(dirname $R)/fetch_icons.py`, then `python3 $F --list aws` lists the names
  in an archive family (also `azure`, `gcp`, `gcp-category`), and
  `python3 $F aws-lambda aws:Arch_Amazon-Aurora_64` fetches icons ahead of a
  render, for example before going offline.

To add a key, add `"key": "family:name"` to `icons/catalog.json`.
`icons/SOURCES.md` lists each family's official source, pinned version, terms
and how a name maps to a file.

## Example

`assets/examples/web-app.json` is a full spec. The rendered output isn't kept in
the repo because it would embed AWS icons; render it to see it.

## Interactive / collaborative mode (optional)

For iterating with the user, an interactive variant adds layer toggles,
connection-type filters, zoom, and click-to-comment that builds a feedback prompt
with a Copy button. See `references/interactive.md`.

## Related building blocks

- `topics/system-design/README.md` invokes this at the "draw it" steps.
- Every building block whose "Diagram" section points here. This skill owns
  diagram generation, so the blocks don't ship their own.

## References

- `references/design-system.md`: what the renderer draws and why (sizes, colors,
  routing, checks). Read it before changing the script.
- `references/interactive.md`: the optional interactive diagram pattern.
- `icons/SOURCES.md`: icon sources, versions and terms.
