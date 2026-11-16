# Diagramming a design

Diagrams represent components as boxes and communication/data flow as arrows. Use
them to *think*, not just to present.

**The diagram engine is `topics/architecture-diagram/README.md`.** Its `scripts/render_diagram.py` turns a JSON spec into one self-contained, icon-based SVG (to embed in Markdown) or an HTML page around it, with no network access. Hand off to it once the design is clear enough to draw.

For *early* thinking in the conversation, a quick ASCII sketch is fine — it's
disposable and keeps momentum. Render properly with `architecture-diagram` once
the components have earned their place (drawing boxes you can't justify is failure
mode #7).

## What to draw at each loop step

- **Step 3 (high-level):** one diagram of the whole system — clients, load
  balancer, stateless services, stores, caches, queues, CDN — with the API entry.
  Keep it to ~8–15 components; this is the buy-in artifact.
- **Step 6 (deep-dive):** zoom into one subsystem (the critical request path or a
  data-partitioning view), with the concrete API/keys from `api-design` /
  `data-storage`. Don't cram the whole system into the deep-dive picture.
- **Step 5 (failure):** draw the degradation path — e.g. gateway → fallback cache
  when a service times out. A design's failure behavior is part of the design.

## Conventions (handled by the architecture-diagram skill)

The `topics/architecture-diagram/README.md` encodes these; summarized here so the orchestrator
can specify a diagram precisely:

- **One icon box per component**, labeled in three words or fewer. Never put several services in one box; a frame can surround several boxes.
- **Color by kind** (security, database/storage, compute, queue, networking/analytics, service, people, vendor/reference). Full palette in `topics/architecture-diagram/references/design-system.md`.
- **Top to bottom in request or data order**: callers, then the edge (CDN, load balancer, identity provider), then the app, then what it calls, then vendors.
- **Line style is the network**: dashed crosses the public internet, solid stays on a private network. Edge labels name the protocol or credential in a word or two.
- **Frames are network or trust boundaries** (account, VPC, region, subnet) and can nest.

## Specifying a diagram to the skill

Hand `topics/architecture-diagram/README.md` three things from the design doc:
1. **Components**: each with a short name, a kind (sets the color) and an icon, and the row it sits in.
2. **Connections**: directed, with a protocol or credential label, and marked public when they cross the internet.
3. **Groupings**: accounts, VPCs, regions or trust boundaries to frame.

That is exactly what the design-doc template's "High-level design" section
captures, so the handoff is mechanical.

## Optional collaborative mode
For iterating *with* the user, `topics/architecture-diagram/README.md` also documents an
interactive variant (layer toggles, click-to-comment → feedback prompt). Use it
when the design is contested and you want the user to mark up components directly.
It falls back to a Copy-Prompt button and needs nothing external.
