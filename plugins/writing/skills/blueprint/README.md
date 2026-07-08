# blueprint

Hand-author **format-clean** technical diagrams as a single self-contained
`.html` file with inline SVG — text that always fits its box, arrows that
actually connect, no overlaps, no drift. No renderer, no build step, no runtime
dependencies.

The trick isn't artistry, it's arithmetic: use a **monospace** font so a label's
width is `charCount × fontSize × 0.6` (computable, not guessed), plan a
**coordinate grid** before drawing so every position traces back to a named
constant, anchor each node at a single centered point, and **re-check the
geometry** before delivery. That is the discipline that lets an LLM produce a
carefully-tuned-looking diagram on the first try instead of one with spilling
text and floating arrows.

## Layout

- [`SKILL.md`](./SKILL.md) — the method (read this first).
- [`assets/template.html`](./assets/template.html) — copy-and-fill starter with
  the HTML wrapper, arrow-marker `defs`, the semantic color system, and a compact
  worked example.
- [`references/anatomy.md`](./references/anatomy.md) — recipes and exact values:
  the color palette, arrow-routing patterns, multi-line and nested-band handling,
  the manual self-review checklist, and a worked example.
- [`scripts/check_diagram.py`](./scripts/check_diagram.py) — a dependency-free
  geometry linter (standard library only) that fails on text overflow, node
  overlap, off-canvas boxes, and floating arrows:

  ```bash
  python3 scripts/check_diagram.py your-diagram.html
  ```

## Relationship to the `drawio` plugin

The sibling [`drawio`](../../../drawio) plugin authors native `.drawio` files
(from Mermaid or draw.io XML) that open and stay editable in draw.io /
diagrams.net. Reach for **blueprint** instead when you want a single
self-contained **HTML** file with hand-crafted SVG — full control over a dense or
custom layered-architecture layout, no external editor, and format-cleanliness
guaranteed by construction (the char-width formula + `check_diagram.py`) rather
than by a rendering app.
