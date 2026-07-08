---
name: blueprint
description: >-
  Generate standalone HTML + inline-SVG technical diagrams that come out
  format-clean every time — text that always fits its box, arrows that actually
  connect, no overlaps, no drift. Works by planning a coordinate grid first and
  sizing every box with monospace arithmetic instead of guessing pixels, then
  self-checking the geometry before delivery. Output is a single self-contained
  .html file (no build step, no dependencies) that opens in any browser.
when_to_use: >-
  Use whenever the user asks you to draw, generate, build, or hand-code a
  diagram as HTML or SVG — architecture diagrams, layered system maps,
  flowcharts, box-and-arrow diagrams, pipelines, data flows, network topology,
  request lifecycles, or a "diagram in HTML". Reach for it ESPECIALLY when the
  user has been fighting format problems in generated diagrams (text spilling
  out of boxes, arrows landing in empty space, overlapping nodes, messy
  alignment), wants a single copy-paste HTML file rather than a rendered tool,
  or wants to reproduce / extend a dense hand-authored SVG diagram. Prefer this
  over free-hand SVG whenever geometric precision matters.
disable-model-invocation: false
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
model: inherit
license: MIT
metadata:
  version: "0.1.0"
  author: GAO Hongnan
---

# Blueprint

Hand-author **format-clean** technical diagrams as a single self-contained
`.html` file with inline SVG. No renderer, no build step, no runtime
dependencies — just disciplined geometry that the model can get right on the
first try, plus a checker that proves it did.

## Why diagrams come out broken — and the one idea that fixes it

When you free-hand an SVG diagram, the geometry is a pile of guesses. You write
`<rect width="140">` and hope the label fits. You write an arrow ending at
`700,190` and hope that's the top edge of a box. In a **proportional** font the
rendered width of `OTLPMetricExporter` is genuinely unknowable without a layout
engine, so the guess is usually wrong — text spills out, or floats in a box
that's too big; arrows end in empty space. That is the entire root cause of
"ill-formatted" diagrams.

Blueprint removes the guessing with four moves:

1. **Monospace font → text width becomes arithmetic.** In a monospace font every
   glyph has the *same* advance. At font-size `F`, one character is `F × 0.6`
   pixels wide (a deliberate slight over-estimate, so boxes are never too small).
   A 25-character label at 11px is `25 × 6.6 = 165px` — a computed number, not a
   guess. Box width is now a formula.
2. **A coordinate grid declared up front.** Every position comes from a named
   constant (column centers, row bands), not an ad-hoc number. Arrows connect
   because both endpoints derive from the *same* constants as the boxes.
3. **A centered node convention.** Each node is one group anchored at `(cx, cy)`;
   the rect, the text, and every arrow endpoint derive from that single point.
   Fewer independent numbers means fewer things to get wrong.
4. **A self-check that recomputes the arithmetic** after you draw, and fails on
   any box that can't fit its text, any overlap, any floating arrow — before a
   human ever sees it.

Follow the method below and the output looks like a carefully hand-tuned
diagram, because the discipline that makes hand-tuning work has been made
mechanical.

## The method

Work in this order. **Do the arithmetic before you write any SVG** — that single
habit is what prevents overflow.

### 1. Write the content first (plain text, no SVG yet)

List the **nodes** (each with its exact label text and a semantic type) and the
**edges** (`from → to`, plus any label). This is the diagram's meaning; settle it
before you touch geometry.

### 2. Group into layers and columns

Decide the horizontal **columns** and the vertical **layers/rows**. Diagrams read
top-to-bottom or left-to-right; keep a consistent flow direction. Nodes that are
peers (same layer) share a row; a pipeline of steps marches across columns.

### 3. Size every box with the formula — in a scratch table

Pick `F = 11` (label font size) ⇒ `CHAR_W = 6.6`. For **each** node compute:

```
textWidth = charCount(longest line) × 6.6
boxWidth  = textWidth + 2 × PAD        (PAD = 20; never below 16)   → round up to even
boxHeight = 36 for 1 line, 54 for 2 lines, +18 per extra line
```

Write this as an actual table before drawing — it is your proof that every box
fits:

| label | chars | textWidth | boxWidth |
|-------|-------|-----------|----------|
| `MeterProvider` | 13 | 86 | 132 |
| `OTLP Receiver (gRPC/HTTP)` | 25 | 165 | 216 |

For a tidy column, size all its nodes to the column's **widest** label. If a
label is very long, either widen the column or wrap it onto two lines (see
`tspan` in the template).

### 4. Declare the coordinate reference

Choose **column centers** (`cx`) evenly spaced and wide enough that the widest
box in adjacent columns leaves a ≥ 24px gap. Choose **row y-bands** (`cy`) with a
≥ 40px vertical gap between rows so arrows (and their labels) have a channel to
run through. Write these as a comment block at the top of the SVG so every later
number traces back to it:

```
<!-- COORDINATE REFERENCE
     columns: cx = 280 | 700 | 1120
     rows:    App y=80  Facade y=148  Providers y=240  Exporters y=436
     gap between rows ≥ 40 (arrow channel)   -->
```

### 5. Emit the diagram from the template

Copy `assets/template.html` and fill it in. It already contains the HTML wrapper,
the arrow-marker `<defs>`, and the CSS class system. Emit in this order:

1. **Layer bands** — dashed rounded rects (`.band`) behind groups of nodes, with
   a small label in the top-left. Pad ~30px around their contents; bands may nest.
2. **Nodes** — one group each, using the centered convention exactly:
   ```svg
   <g class="node backend" transform="translate(700,240)">
     <rect x="-62" y="-18" width="124" height="36"/>
     <text>MeterProvider</text>
   </g>
   ```
   `x = -boxWidth/2`, `y = -boxHeight/2`. The CSS centers the text
   (`text-anchor:middle; dominant-baseline:central`) so you never position it by
   hand. Two-line labels use `<tspan x="0" dy="-7">…</tspan><tspan x="0" dy="14">…</tspan>`.
3. **Edges** — orthogonal paths (horizontal/vertical segments only), drawn last
   so arrowheads sit crisply on top. Rules that keep them connected:
   - Leave from an edge **midpoint** of the source and arrive at an edge midpoint
     of the target: down-arrow is `M cx,(cy+h/2) … L tx,(ty−h/2)`.
   - Route the horizontal jog through the **gap** between rows, never across a
     box: `M sx,sy+h/2  L sx,midY  L tx,midY  L tx,ty−h/2`.
   - When several arrows share one node, **fan them out**: offset each endpoint's
     x by ±8 so they don't stack on the same line.
   - Pair the path with `marker-end="url(#arrow)"`. Use the dashed variant
     (`.edge-dashed` + `#arrow-open`) for secondary/async flows.
   - **Edge labels** get a white background rect (`.edge-label-bg`) behind the
     text, sized with the same char formula, so the line never strikes through
     the glyphs.

### 6. Size the viewBox to the content

After everything is placed, set the `<svg>` `width`/`height`/`viewBox` to
`maxX + 30` by `maxY + 30`, where `maxX`/`maxY` are the farthest box/band edges.
The container has `overflow:auto`, so large diagrams scroll rather than clip.

### 7. Self-check before delivering — do not skip this

This is the reliability gate. Run the bundled checker, which re-derives the
geometry and fails on the exact bugs this skill exists to prevent:

```bash
python3 scripts/check_diagram.py <your-output>.html
```

It verifies, for every node: the label fits its box (recomputed from char
count), no two node boxes overlap, every arrow endpoint lands on a real box or
band edge (not empty space), and the viewBox contains everything. It exits
non-zero and prints the offending element if anything is wrong. **Fix what it
reports and re-run until it passes.** If Python isn't available, walk the
"Manual self-review" list in `references/anatomy.md` instead.

Optional visual confirmation when a browser is available: open the file (or use
a headless browser / Playwright to screenshot it) and eyeball spacing and flow —
the checker catches geometry bugs, but only your eye judges whether the layout
*reads* well.

## Reference material

- **`assets/template.html`** — the starter file. Copy it, keep the `<defs>`,
  `<style>`, and wrapper, replace the example body. Read it before your first
  diagram; its worked two-layer example shows every convention in miniature.
- **`references/anatomy.md`** — the deep dive: the full semantic color palette
  (fills + strokes per node type), arrow-routing recipes for the common cases
  (straight, jog, merge, fan-out, back-edge), multi-line and nested-band
  handling, the manual self-review checklist, and a fully worked example. Read it
  when you need a specific recipe or the exact palette values.
- **`scripts/check_diagram.py`** — the validator from step 7 (standard library
  only; no install).

## Design defaults

Light theme, monospace type, pastel semantic fills with saturated strokes,
dashed layer bands, dark neutral text — a clean, technical, print-friendly look.
Keep colors in the **CSS class system** (semantic classes like `.backend`,
`.database`), never inline `fill="#..."` on nodes; that keeps the palette
consistent and makes restyling a one-line change. The full palette lives in
`references/anatomy.md`.
