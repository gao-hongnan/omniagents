# archify (vendored)

Generate professional architecture, workflow, sequence, data-flow, and
lifecycle/state diagrams as **self-contained HTML files** — inline SVG, a
dark/light theme toggle that persists in `localStorage`, and a one-click export
menu (PNG / JPEG / WebP up to 4×, plus a dual-theme SVG ideal for GitHub
READMEs). It accepts plain-language descriptions or pasted Mermaid
(`flowchart`, `sequenceDiagram`, `stateDiagram`) and lays the diagram out from
scratch in archify style.

The skill instructions live in [`SKILL.md`](./SKILL.md); the rest of this
folder is the renderer toolkit it drives.

## Credit

This skill is **vendored from [tt-a1i/archify](https://github.com/tt-a1i/archify)**
(MIT, v2.6 by **tt-a1i**), which is itself based on
[Cocoon-AI/architecture-diagram-generator](https://github.com/Cocoon-AI) (MIT, v1.0).
Full credit to the upstream authors — we copied their work and intend to build
on it. The original [`LICENSE`](./LICENSE) is preserved here unchanged, as MIT
requires.

If you find this useful, star the upstream repo: <https://github.com/tt-a1i/archify>.

## What we changed when vendoring

- Adapted `SKILL.md` frontmatter to omniagents-writing conventions
  (`when_to_use`, `disable-model-invocation`, `user-invocable`, `allowed-tools`,
  `model: inherit`) while preserving the upstream `license` and `metadata`
  attribution block.
- Dropped the upstream `test/`, `docs/`, `experiments/`, and rendered
  `examples/*.html` — none are needed at skill runtime. The schemas, JSON
  examples, renderers, and `assets/template.html` are kept intact.

The renderer source under `renderers/`, `schemas/`, `examples/`, and
`assets/template.html` is unmodified from upstream.

## Using the renderers

The four typed renderers validate JSON against `schemas/` via `ajv`. Validation
is **optional** — without it the renderers still run, print a warning, and fall
back to their own layout checks:

```bash
npm install            # one-time, from this folder; enables ajv schema validation
node renderers/<type>/render-<type>.mjs <input>.json <output>.html
```

`<type>` is one of `architecture`, `workflow`, `sequence`, `dataflow`,
`lifecycle`. The generated HTML has **zero runtime dependencies**. When no shell
is available, hand-place SVG into `assets/template.html` per the Design System
in `SKILL.md`. `node_modules/` is intentionally **not** vendored.
