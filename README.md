# omniagents

A Claude Code plugin suite — coding conventions, design patterns, and MCP
server integrations packaged as installable skills.

---

## Plugin catalogue

| Plugin                       | Type        | Skills                                                                                       | Requires           |
| ---------------------------- | ----------- | -------------------------------------------------------------------------------------------- | ------------------ |
| `omniagents-python`          | Skills      | `omniagents-python:typings`, `omniagents-python:docstrings`, `omniagents-python:performance` | —                  |
| `omniagents-typescript`      | Skills      | `omniagents-typescript:typings`, `omniagents-typescript:docstrings`                          | —                  |
| `omniagents-design-patterns` | Skills      | `omniagents-design-patterns:software`, `omniagents-design-patterns:system`                   | —                  |
| `omniagents-writing`         | Skills      | `omniagents-writing:measured-persuasion`, `omniagents-writing:markdown-conventions`          | —                  |
| `code-review-graph`          | MCP (stdio) | Tree-sitter knowledge graph tools                                                            | `uv` on PATH       |
| `context7`                   | MCP (HTTP)  | Library documentation lookup                                                                 | `CONTEXT7_API_KEY` |

---

## Prerequisites

- Claude Code CLI — `claude --version`
- For `code-review-graph`: `uv` installed — `uvx --version`
- For `context7`: a Context7 API key from <https://context7.com/dashboard>

---

## Installation

### Add the marketplace

```bash
claude plugin marketplace add gao-hongnan/omniagents
```

Or from inside Claude Code:

```text
/plugin marketplace add gao-hongnan/omniagents
```

### Install plugins

Install individually:

```bash
claude plugin install omniagents-python@omniagents
claude plugin install omniagents-typescript@omniagents
claude plugin install omniagents-design-patterns@omniagents
claude plugin install omniagents-writing@omniagents
claude plugin install code-review-graph@omniagents
claude plugin install context7@omniagents
```

### Scope options

| Flag              | Effect                                          |
| ----------------- | ----------------------------------------------- |
| _(none)_          | User scope — available across all projects      |
| `--scope project` | Project scope — committed to `.claude/`, shared |
| `--scope local`   | Local scope — gitignored, machine-local only    |

Example — install `omniagents-python` for the whole team:

```bash
claude plugin install omniagents-python@omniagents --scope project
```

---

## Uninstall

Remove a plugin with `claude plugin uninstall`. If you installed with a
specific scope, pass the same `--scope` flag:

```bash
claude plugin uninstall omniagents-python@omniagents
claude plugin uninstall omniagents-typescript@omniagents
claude plugin uninstall omniagents-design-patterns@omniagents
claude plugin uninstall omniagents-writing@omniagents
claude plugin uninstall code-review-graph@omniagents
claude plugin uninstall context7@omniagents
```

Example — remove a project-scoped plugin:

```bash
claude plugin uninstall omniagents-python@omniagents --scope project
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
claude plugin marketplace add ./omniagents
claude plugin install omniagents-python@omniagents --scope local
```

---

## License

MIT. See individual `plugin.json` files for per-plugin authorship.
