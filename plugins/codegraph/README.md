# CodeGraph MCP Plugin

This plugin adds the [`codegraph`](https://github.com/colbymchenry/codegraph)
MCP server to Claude Code. It parses your codebase with tree-sitter into a
local, persistent knowledge graph — symbols, call paths, and imports — so
agents get structural answers (callers, callees, blast radius) in one tool
call instead of repeated file discovery. The index auto-syncs on file changes
via a background watcher.

## Requirements

The server is launched with `npx`, so Node.js and npm must be on `PATH` before
Claude Code starts. The CLI and MCP server ship as a self-contained bundled
runtime (no minimum Node version is required to run them); `npx` itself still
needs a working Node/npm install to resolve and execute the package.

Check locally with:

```bash
npx --version
```

## Configuration

The plugin MCP config is in `.mcp.json`:

```json
{
  "mcpServers": {
    "codegraph": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@colbymchenry/codegraph", "serve", "--mcp"]
    }
  }
}
```

`type: "stdio"` makes the transport explicit for Claude Code. `npx -y
@colbymchenry/codegraph` resolves and runs the package on demand — there is no
global install to maintain, and each launch picks up the latest published
version (npx checks the registry, then uses its local cache if already
current). To force a specific version instead, pin it in `args`:
`"@colbymchenry/codegraph@1.2.0"`.

`serve --mcp` starts the server in MCP mode over stdio. Two optional flags can
be appended to `args` if needed:

| Flag                | Effect                                                                          |
| -------------------- | -------------------------------------------------------------------------------- |
| `-p, --path <path>` | Project path to index. Optional in MCP mode — the server uses the client's `rootUri` when omitted. |
| `--no-watch`         | Disable the file watcher (no auto-sync). Useful on slow filesystems such as WSL2 `/mnt` drives. |

## CLI beyond MCP

The same package is a standalone CLI — useful for inspecting or repairing the
index without going through an agent: `codegraph status`, `codegraph explore
<query>`, `codegraph callers <symbol>`, `codegraph impact <symbol>`, `codegraph
uninit` (deletes the local `.codegraph/` index), and more. Run `npx
@colbymchenry/codegraph --help` for the full command list.

## Telemetry

The CLI collects anonymous usage telemetry (commands, tools, languages) by
default. Check or change this with:

```bash
npx @colbymchenry/codegraph telemetry status
npx @colbymchenry/codegraph telemetry off
```

## Verification

From the repository root, check that Claude Code sees the server:

```bash
claude mcp get codegraph
```

Expected details include:

```text
Scope: Project config (shared via .mcp.json)
Type: stdio
Command: npx
Args: -y @colbymchenry/codegraph serve --mcp
```

Then check health:

```bash
claude mcp list
```

If Claude says `Server "codegraph" not found`, the project `.mcp.json` was not
loaded or approved. Restart Claude Code from the repository root and approve
the project-scoped MCP server if prompted.

If the server is found but fails to connect, run the launch command directly:

```bash
npx -y @colbymchenry/codegraph serve --mcp
```

Common causes are `npx`/Node.js not being on `PATH`, or network access being
unavailable for the first package download. A stdio MCP server prints nothing
on a successful start (any startup banner would corrupt the JSON-RPC stream)
and exits cleanly once its stdin closes — that silence is expected, not a
hang.

## References

- [CodeGraph repository](https://github.com/colbymchenry/codegraph)
- [CodeGraph on npm](https://www.npmjs.com/package/@colbymchenry/codegraph)
- [Claude Code MCP configuration](https://code.claude.com/docs/en/mcp)
