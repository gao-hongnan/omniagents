# Claude Code Plugin: drawio

A Claude Code plugin that ships the `drawio` skill: it generates native
`.drawio` files, authored either as Mermaid (converted + laid out by the draw.io
desktop CLI) or as draw.io XML directly, with optional ELK `--layout` for XML,
export to PNG/SVG/PDF (with embedded XML) via the desktop CLI, or a browser URL
that opens the diagram directly at `app.diagrams.net`. No MCP server required.

Previously distributed as a bare `SKILL.md` users copied into
`~/.claude/skills/`; now packaged as a real plugin so it loads via
`claude --plugin-dir ./plugins/claude-code` and is distributed through the
[`drawio` marketplace](../../.claude-plugin/marketplace.json) at the repo root
(`/plugin install drawio@drawio`).

## Key Files

| File                                    | Purpose                                                                                                                                                  |
| --------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `.claude-plugin/plugin.json`            | Plugin manifest — the single source of truth for name, version, description, author, license                                                             |
| `skills/drawio/SKILL.md`                | The skill itself (its folder name `drawio` becomes the second half of the `/drawio:drawio` invocation)                                                   |
| `README.md`                             | Installation and usage documentation                                                                                                                     |
| `../../.claude-plugin/marketplace.json` | Marketplace manifest at the repo root; lists this plugin with `source: "./plugins/claude-code"` and inherits the rest of its metadata from `plugin.json` |

## How It Works

Everything becomes a native `.drawio` file first, then is delivered in the
requested output format.

1. User invokes `/drawio:drawio` or Claude detects a diagram request
2. Claude picks an authoring route:
    - **Mermaid** (preferred for standard types when the desktop CLI is present)
      — writes a `.mmd` file, then `drawio -x -f xml -o name.drawio name.mmd`
      converts and lays it out; the `.mmd` is deleted
    - **XML** — writes mxGraphModel XML to `name.drawio`; optionally
      `drawio -x -f xml --layout <preset|json> -o name.drawio name.drawio`
      applies an ELK layout (reading and overwriting the same path is supported)
3. Format-specific handling (identical for both routes, since both produce a
   `.drawio`):
    - **png/svg/pdf** — the draw.io CLI exports to `.drawio.png` / `.drawio.svg`
      / `.drawio.pdf` with `--embed-diagram`, then deletes the source `.drawio`
      file
    - **url** — a `node -e` one-liner reads the `.drawio` file, compresses it
      with `zlib.deflateRawSync` + base64, builds
      `https://app.diagrams.net/?...#create={type,compressed,data}`, and opens
      it in the browser. The `.drawio` file is kept for persistence.
    - **default** — no extra step, the `.drawio` file is the output
4. The result is opened for viewing (`open` / `xdg-open` / `start`; on
   Windows/WSL2, `url` mode uses a temp `.url` file because `cmd.exe` strips the
   `#create=...` fragment)

Default output is `.drawio` (no export). The user requests another output mode
by mentioning the format: `/drawio:drawio png ...`, `/drawio:drawio svg: ...`,
`/drawio:drawio url ...`, etc.

**Mermaid → PNG caveat:** direct `.mmd` → PNG with `-e` crashes in current
draw.io Desktop (`writePngWithText` receives an undefined `args.xml` at the
embed step in `electron.js`). The skill always converts Mermaid to `.drawio`
first and exports that, which sidesteps the bug and yields a correct embed. The
layout names, JSON schema, and CLI verification are documented in `SKILL.md`.

## URL Mode Compatibility

The `url` mode produces the exact same `https://app.diagrams.net/#create=...`
URL format as the MCP Tool Server (`mcp-tool-server/src/index.js`). Node.js's
built-in `zlib.deflateRawSync` and `pako.deflateRaw` both implement RFC 1951, so
their outputs are interchangeable. No external npm dependencies are added to the
skill — only Node.js built-ins (`zlib`, `child_process`, `fs`, `os`, `path`).

## draw.io CLI Locations

- **macOS**: `/Applications/draw.io.app/Contents/MacOS/draw.io`
- **Linux**: `drawio` (on PATH via snap/apt/flatpak)
- **Windows**: `"C:\Program Files\draw.io\draw.io.exe"`
- **WSL2**: `"/mnt/c/Program Files/draw.io/draw.io.exe"` (detect via
  `grep -qi microsoft /proc/version`)

The skill tries `drawio` first, then falls back to the platform-specific path.
On WSL2, use `wslpath -w` to convert paths when opening files with
`cmd.exe /c start`.

## Authoring routes

A `.drawio` file is native mxGraphModel XML. The skill produces one two ways:
**Mermaid** (converted to `.drawio` by the desktop CLI, `-f xml`) or **XML**
(generated directly). Both need no server — Mermaid conversion and ELK layout
run locally in the desktop app's headless export path. When no desktop CLI is
available, only the XML route is usable (`.drawio` file or `url`); Mermaid
conversion, ELK layout, and image export all require the desktop app.

## References

Two shared references live at the repo root (single source of truth for all
prompts); `SKILL.md` fetches each via its GitHub raw URL so they work after
install without copying extra files:

- `shared/xml-reference.md` — draw.io XML generation guide (used when authoring
  XML)
- `shared/mermaid-reference.md` — Mermaid syntax for all supported diagram types
  (used when authoring Mermaid)

## Coding Conventions

- **Allman brace style**: Opening braces go on their own line for all control
  structures, functions, objects, and callbacks.
- Prefer `function()` expressions over arrow functions for callbacks.
- See the root `CLAUDE.md` for examples.
