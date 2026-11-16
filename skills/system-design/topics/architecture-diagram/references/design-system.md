# Diagram design system

What `scripts/render_diagram.py` draws and the rules behind it. Read this before
changing the script; to draw a diagram, the README is enough.

## Look

- AWS-style boxes: a 200x60 white card (dark theme: `#161b22`) with a 40px tile
  in the kind color on the left, a white 26px icon on the tile, and the label in
  14px semibold system sans-serif (`-apple-system, BlinkMacSystemFont, 'Segoe UI',
  Helvetica, Arial, sans-serif`). Labels wrap to two lines, or three at 12px.
  A full-color vendor icon (AWS, Azure, Google Cloud) takes the tile's place at
  40px with its own colors; Azure's terms ask for icons as they appear in Azure.
  An icon that couldn't be fetched leaves the tile empty.
- Group frames: a rounded rectangle in the group's kind color with a 5% tint fill
  (10% in dark), the title at the top left after an optional 24px icon tile, or
  a 24px full-color icon.
  Nested frames add 16px of padding per level and 36px for each title.
- Edges: 1.6px lines in a muted gray with rounded corners and a filled triangle
  arrowhead drawn as a polygon, so no SVG markers are needed. Labels sit in a
  pill with the background color.
- Dashed means public internet: `6 4` on lines, `5 4` on boxes, `8 5` on frames.
- Every SVG starts with a full-size background rect, which keeps it readable in
  both light and dark Markdown viewers.

## Layout

- Rows come from the spec, top to bottom. Columns are 200px boxes with a gap of
  at least 56px, wider when nested frames need room between columns.
- The gap between two rows holds the turns of the lines that leave the upper row.
  It is at least 84px and grows by 14px for each extra lane it needs.
- Everything is computed from the spec, so the same spec always produces the same
  file and a diff of the SVG shows what changed.

## Routing

1. Boxes in different rows that overlap side to side get one straight vertical
   line, at a spot inside the overlap that no box in between covers and that no
   other line on those sides uses.
2. Otherwise the line leaves the source, turns once in a gap, and enters the
   target (a Z shape): the gap below the source by default, or the gap above the
   target when that keeps the line out of boxes in between.
3. When both Z shapes would run through a box, the line detours: it turns in the
   gap below the source, runs down the nearest free column gap, and turns again
   in the gap above the target.
4. Boxes in the same row get one horizontal line between their facing sides.
5. Ports on each box side are spread at least 20px apart and ordered by where the
   other end is, so lines leaving one side don't cross each other.
6. In each gap, every horizontal run gets a lane height chosen so that no other
   edge's vertical part crosses it, and runs that don't overlap share a lane.

## Checks

After routing, the script warns about crossing or overlapping lines, a line
through a box or a group title, a group covering a box that isn't in it,
overlapping groups that aren't nested, labels with more than three words or
that join several components (`,`, `/`, `+`, `&`, `and`), edge labels longer than
two words, and edge labels with no free spot. `--strict` turns any warning into
exit code 2. Spec errors (unknown ids, kinds or icons, two nodes in one spot, a
node in two groups) exit with code 1.

## HTML page

`assets/template.html` is the page shell. The script fills in the title, theme,
SVG and cards. Its SVG and PNG buttons serialize the inline SVG in the browser
(the PNG through a canvas at 2x), and PDF uses the browser's print dialog, so
the page loads no external script.
