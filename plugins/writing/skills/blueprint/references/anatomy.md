# Blueprint anatomy — recipes and exact values

The deep-dive companion to `SKILL.md`. Read a section when you need its recipe.

## Contents

1. [Box-sizing math](#1-box-sizing-math)
2. [Multi-line labels](#2-multi-line-labels)
3. [Semantic color palette](#3-semantic-color-palette)
4. [Arrow-routing recipes](#4-arrow-routing-recipes)
5. [Edge labels](#5-edge-labels)
6. [Layer bands and nesting](#6-layer-bands-and-nesting)
7. [viewBox sizing](#7-viewbox-sizing)
8. [Manual self-review checklist](#8-manual-self-review-checklist)
9. [Worked example](#9-worked-example)

---

## 1. Box-sizing math

The whole method rests on one fact: **in a monospace font every glyph is the same
width**, so a label's rendered width is `charCount × fontSize × advance`. Use
`advance = 0.6` — real monospace advances are ~0.58–0.60em, so 0.6 slightly
*over*-estimates, which means a box sized from it is never too small. Text can't
overflow a box you sized this way.

```
CHAR_W    = fontSize × 0.6          # 6.6 at the default 11px
textWidth = charCount × CHAR_W      # use the LONGEST line for multi-line labels
boxWidth  = textWidth + 2 × PAD     # PAD = 20 (never below 16); round up to even
boxHeight = 36 (1 line) | 54 (2 lines) | +18 per extra line
```

`charCount` is the count of visible characters (an emoji or CJK glyph counts as
~2 monospace cells — widen for those). Round `boxWidth` up to an even number so
`x = -boxWidth/2` is a clean integer.

**Column consistency.** Boxes in the same column look tidier at a shared width —
size them all to the column's widest label, not each to its own text. Reserve
per-node widths for standalone nodes.

**Node group shape** (the rect is centered on the group's translate anchor, so
you never place text by hand):

```svg
<g class="node backend" transform="translate(700,240)">
  <rect x="-62" y="-18" width="124" height="36"/>   <!-- x=-w/2, y=-h/2 -->
  <text>MeterProvider</text>                          <!-- CSS centers it -->
</g>
```

---

## 2. Multi-line labels

Two lines share one `<text>`; each line is a `<tspan>` re-anchored to `x="0"`
(the group center) with a vertical `dy`. Give the box the two-line height (54)
and set `y="-27"`:

```svg
<g class="node database" transform="translate(310,364)">
  <rect x="-60" y="-27" width="120" height="54"/>
  <text><tspan x="0" dy="-7">PostgreSQL</tspan><tspan x="0" dy="14">:5432</tspan></text>
</g>
```

`dy="-7"` lifts the first line half a line-height above center; `dy="14"` drops
the second below it. For three lines use `dy="-15" / "14" / "14"` and height 72.
Width is driven by the **longest** line.

Prefer two short lines over one long line when a label carries a name plus an
address/port — it keeps columns narrow and the diagram compact.

---

## 3. Semantic color palette

Fills are Tailwind-ish `50` shades (pastel, print-friendly); strokes are the
matching `600` (crisp border). Text is always `#1f2937`. Keep these in the
`<style>` block as classes — never inline them on a node, so a re-theme is a
one-line edit and the checker can trust the structure.

| class | role | fill | stroke |
|-------|------|------|--------|
| `.frontend` | clients, UI, browsers | `#eff6ff` | `#2563eb` |
| `.backend` | services, APIs, handlers | `#ecfdf5` | `#16a34a` |
| `.database` | databases, caches, stores | `#fffbeb` | `#d97706` |
| `.messagebus` | queues, brokers, topics | `#f5f3ff` | `#7c3aed` |
| `.compute` | jobs, workers, processing | `#fff7ed` | `#ea580c` |
| `.security` | auth, secrets, policy | `#fef2f2` | `#e11d48` |
| `.external` | third parties, SaaS | `#f8fafc` | `#64748b` |
| `.neutral` | default / unspecified | `#f9fafb` | `#6b7280` |

Bands and edges are neutral slate so they never compete with node color:
band stroke `#cbd5e1` (dashed), band label `#475569`, edge stroke `#64748b`,
dashed-edge stroke `#94a3b8`, edge-label text `#64748b`.

Need a type not listed? Add a class following the same 50/600 recipe rather than
inlining a color.

---

## 4. Arrow-routing recipes

Arrows are **orthogonal** — horizontal and vertical segments only, no diagonals
— and they connect **edge midpoints**, routing through the gaps between rows so
they never cross a box. Draw them after the nodes so the arrowheads sit on top.
`h` is the source/target box height; endpoints use `cy ± h/2`.

**Straight down** — same column, adjacent rows:
```svg
<path class="edge" d="M310,246 L310,337"/>          <!-- source bottom → target top -->
```

**Elbow / jog** — different columns; turn in the gap (`midY` between the rows):
```svg
<path class="edge" d="M180,114 L180,158 L302,158 L302,210"/>
```

**Fan-out** — several arrows leaving one node; offset each exit `x` by ±8 so they
don't stack on one line:
```svg
<path class="edge" d="M272,258 L272,300 L120,300 L120,320"/>   <!-- left  child -->
<path class="edge" d="M288,258 L288,300 L520,300 L520,320"/>   <!-- right child -->
```

**Fan-in / merge** — several arrows entering one node; offset each *entry* `x` by
±8 and stagger the `midY` a few px so the horizontal runs don't coincide:
```svg
<path class="edge" d="M180,114 L180,158 L302,158 L302,210"/>   <!-- into left of target -->
<path class="edge" d="M420,114 L420,166 L318,166 L318,210"/>   <!-- into right of target -->
```

**Side-to-side** — same row: leave a side midpoint, enter the other side:
```svg
<path class="edge" d="M446,815 L850,815"/>          <!-- right edge → left edge -->
```

**Back-edge / loop** — route *outside* the column stack (out to a channel beside
everything, up, and back in) so it doesn't cut through the forward flow:
```svg
<path class="edge" d="M760,240 L820,240 L820,90 L742,90"/>
```

**Secondary / async** — same paths, dashed style + open arrowhead:
```svg
<path class="edge-dashed" d="M288,454 L288,510 L925,510 L925,537"/>
```

Reserve labels for cross-layer transitions; leave adjacent-step arrows bare.

---

## 5. Edge labels

A label sitting on a line gets a white plate behind it so the stroke doesn't run
through the glyphs. Size the plate with the char formula at the 9px edge-label
size (`CHAR_W ≈ 5.4`) plus a few px, and center both on the segment:

```svg
<rect class="edge-label-bg" x="783" y="1028" width="60" height="14" rx="2"/>
<text class="edge-label" x="813" y="1035">Trace Data</text>
```

`"Trace Data"` is 10 chars → `10 × 5.4 ≈ 54` → plate width 60. Center the text `x`
on the plate; the plate `x` is `textCenter − width/2`.

---

## 6. Layer bands and nesting

A band is a dashed rounded rect drawn **before** its contents, with a small bold
label near its top-left. Pad ~30px around the nodes it groups; give it enough
top room that the label clears the first row of nodes.

```svg
<rect class="band" x="48" y="176" width="524" height="92"/>
<text class="band-label" x="68" y="194">Services</text>
```

Bands nest: an outer domain band (e.g. "OpenTelemetry Collector") can contain
inner sub-bands ("Receivers", "Processors", "Exporters"), each with its own
label and ~30px padding inside the parent. A faint tint helps big regions read —
`style="fill:rgba(124,58,237,0.02)"` on the band rect is fine (bands may tint;
nodes may not). The checker treats bands as attachment surfaces, so an arrow may
legitimately end on a band edge (e.g. entering a region).

---

## 7. viewBox sizing

After every element is placed, compute the farthest edges and add a 30px margin:

```
maxX = max over all boxes/bands of (right edge)
maxY = max over all boxes/bands of (bottom edge)
<svg width="{maxX+30}" height="{maxY+30}" viewBox="0 0 {maxX+30} {maxY+30}">
```

The container's `overflow:auto` lets a large diagram scroll instead of clipping.
Keep a 30px margin on the top/left too (start your first band at x,y ≥ 30).

---

## 8. Manual self-review checklist

Run `scripts/check_diagram.py <file>.html` when Python is available — it does all
of this mechanically. When it isn't, walk this list by hand before delivering:

1. **Text fits.** For each node, recompute `charCount × 6.6`; confirm it is ≤ the
   box width minus ~16px each side. This is the #1 bug — check every node.
2. **No overlaps.** No two node boxes share area. Adjacent columns/rows keep
   ≥ 24px between box edges.
3. **Arrows connect.** Every path starts on a source box's edge midpoint (±8 fan)
   and ends on a target box's edge midpoint. No endpoint floats in blank space.
4. **Arrows route through gaps**, not across boxes; jogs turn in the row gaps.
5. **Edge labels are plated.** Every on-line label has a white `edge-label-bg`
   rect behind it.
6. **Nothing clips.** Every box/band is inside the viewBox with a ~30px margin.
7. **Colors are classed.** No inline `fill="#…"`/`stroke="#…"` on node rects; a
   node's color comes from its semantic class. (Band tints are allowed.)
8. **Flow is consistent.** The diagram reads one way (top→bottom or left→right);
   back-edges route around, not through, the forward flow.

---

## 9. Worked example

The canonical full-scale exemplar is a 5-layer OpenTelemetry architecture:
~30 nodes across nested Application / Protocol / Collector / Backends /
Visualization bands, 40 orthogonal edges with plated cross-layer labels,
two-line address nodes, and solid/dashed gRPC/HTTP variants — all sized by the
formula and passing the checker. If you have it on hand, study
`observability/assets/flow.html`; it is the look and density this skill targets.

For a minimal end-to-end example that exercises every convention (computed box
widths, a two-line node, straight + fanned jog arrows, a plated edge label,
three stacked bands), read `assets/template.html` — it is small enough to hold in
your head and is the fastest way to internalize the shapes.
