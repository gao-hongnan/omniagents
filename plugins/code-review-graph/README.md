# Code Review Graph MCP Plugin

This plugin adds the `code-review-graph` MCP server to Claude Code. The server
builds a tree-sitter-backed knowledge graph for code review, impact analysis,
and structural navigation.

## Requirements

The MCP server is launched with `uvx`, so `uv` must be installed and available
on `PATH` before Claude Code starts.

Check locally with:

```bash
uvx --version
```

## Configuration

The plugin MCP config is in `.mcp.json`:

```json
{
  "mcpServers": {
    "code-review-graph": {
      "type": "stdio",
      "command": "uvx",
      "args": ["code-review-graph==2.3.9", "serve"]
    }
  }
}
```

`type: "stdio"` makes the transport explicit for Claude Code. Claude starts the
server process with `uvx code-review-graph==2.3.9 serve`.

The version is pinned (`==2.3.9`) so every launch runs the exact release
this marketplace shipped and starts immediately from cache. Upgrades happen
deliberately, as version bumps in a normal release PR — see the README bump
policy.

To force an upgrade outside of Claude:

```bash
uv tool upgrade code-review-graph
```

## Verification

From the repository root, check that Claude Code sees the server:

```bash
claude mcp get code-review-graph
```

Expected details include:

```text
Scope: Project config (shared via .mcp.json)
Type: stdio
Command: uvx
Args: code-review-graph==2.3.9 serve
```

Then check health:

```bash
claude mcp list
```

If Claude says `Server "code-review-graph" not found`, the project `.mcp.json`
was not loaded or approved. Restart Claude Code from the repository root and
approve the project-scoped MCP server if prompted.

If the server is found but fails to connect, run the launch command directly:

```bash
uvx code-review-graph==2.3.9 serve
```

Common causes are `uvx` not being on `PATH`, network access being unavailable
for the first package download, or the `code-review-graph` package failing to
start.

## References

- [Claude Code MCP configuration](https://code.claude.com/docs/en/mcp)
- [uv tools guide](https://docs.astral.sh/uv/guides/tools/)
- [code-review-graph package](https://pypi.org/project/code-review-graph/)
