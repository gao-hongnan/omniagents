# omniagents

A Claude Code plugin suite — coding conventions, design patterns, and MCP
server integrations packaged as installable skills.

---

## Plugin catalogue

| Plugin              | Type        | Skills / tools                                                | Requires           |
| ------------------- | ----------- | ------------------------------------------------------------- | ------------------ |
| `python`            | Skills      | `python-typings`, `python-docstrings`, `python-performance`   | —                  |
| `typescript`        | Skills      | `typescript-typings`, `typescript-docstrings`                 | —                  |
| `design-patterns`   | Skills      | `design-patterns:software`, `design-patterns:system`          | —                  |
| `writing`           | Skills      | `writing:measured-persuasion`, `writing:markdown-conventions` | —                  |
| `code-review-graph` | MCP (stdio) | Tree-sitter knowledge graph tools                             | `uv` on PATH       |
| `context7`          | MCP (HTTP)  | Library documentation lookup                                  | `CONTEXT7_API_KEY` |

---

## Prerequisites

- Claude Code CLI — `claude --version`
- For `code-review-graph`: `uv` installed — `uvx --version`
- For `context7`: a Context7 API key from <https://context7.com/dashboard>

---

## Installation

### Add the marketplace

```bash
claude plugin marketplace add github:gao-hongnan/omniagents
```

Or from inside Claude Code:

```text
/plugin marketplace add github:gao-hongnan/omniagents
```

### Install plugins

Install individually:

```bash
claude plugin install python@omniagents
claude plugin install typescript@omniagents
claude plugin install design-patterns@omniagents
claude plugin install writing@omniagents
claude plugin install code-review-graph@omniagents
claude plugin install context7@omniagents
```

### Scope options

| Flag              | Effect                                          |
| ----------------- | ----------------------------------------------- |
| _(none)_          | User scope — available across all projects      |
| `--scope project` | Project scope — committed to `.claude/`, shared |
| `--scope local`   | Local scope — gitignored, machine-local only    |

Example — install `python` for the whole team:

```bash
claude plugin install python@omniagents --scope project
```

---

## MCP server setup

### code-review-graph

The plugin starts the server automatically via `uvx code-review-graph serve`.
No extra configuration is needed beyond having `uv` on your PATH.

Verify:

```bash
claude mcp get code-review-graph
```

Expected output:

```text
Scope: Project config (shared via .mcp.json)
Type: stdio
Command: uvx
Args: code-review-graph serve
```

If the server is found but fails to connect, run the launch command directly to
diagnose:

```bash
uvx code-review-graph serve
```

Common causes are `uvx` not on PATH or a first-run package download failure.

### context7

Set the API key in your shell before launching Claude Code:

```bash
export CONTEXT7_API_KEY="ctx7sk-your-key-here"
claude
```

To make it persistent on zsh/macOS:

```bash
echo 'export CONTEXT7_API_KEY="ctx7sk-your-key-here"' >> ~/.zshrc
source ~/.zshrc
```

Verify:

```bash
claude mcp get context7
```

Expected output:

```text
Scope: Project config (shared via .mcp.json)
Type: http
URL: https://mcp.context7.com/mcp
```

Context7 works without an API key at reduced rate limits, but the plugin is
configured to send one when present.

---

## Verification

List all active MCP servers:

```bash
claude mcp list
```

Both MCP plugins should appear. Inside Claude Code, smoke-test context7 with:

```text
use context7 mcp to search pydantic
```

---

## Development install

To install from a local clone instead of GitHub:

```bash
git clone https://github.com/gao-hongnan/omniagents
/plugin marketplace add ./omniagents
claude plugin install python@omniagents --scope local
```

---

## License

MIT. See individual `plugin.json` files for per-plugin authorship.
