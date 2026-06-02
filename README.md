# omniagents

A Claude Code plugin suite — coding conventions, design patterns, and MCP server
integrations packaged as installable skills.

---

## Plugin catalogue

| Plugin                       | Type             | Skills / Tools                                                                                                   | Requires                                                                                        |
| ---------------------------- | ---------------- | ---------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `omniagents-python`          | Skills           | `omniagents-python:typings`, `omniagents-python:docstrings`, `omniagents-python:performance`                     | —                                                                                               |
| `omniagents-typescript`      | Skills           | `omniagents-typescript:typings`, `omniagents-typescript:docstrings`                                              | —                                                                                               |
| `omniagents-design-patterns` | Skills           | `omniagents-design-patterns:software`, `omniagents-design-patterns:system`                                       | —                                                                                               |
| `omniagents-writing`         | Skills           | `omniagents-writing:measured-persuasion`, `omniagents-writing:markdown-conventions`                              | —                                                                                               |
| `omniagents-reviewer`        | Skills + Command | `/omniagents-reviewer:review` — parallel correctness, security, performance, design, testing agents + verifier   | `code-review-graph`, `omniagents-python`, `omniagents-typescript`, `omniagents-design-patterns` |
| `code-review-graph`          | MCP (stdio)      | Tree-sitter knowledge graph tools                                                                                | `uv` on PATH                                                                                    |
| `context7`                   | MCP (HTTP)       | Library documentation lookup                                                                                     | `CONTEXT7_API_KEY`                                                                              |
| `google-workspace`           | MCP (stdio)      | Gmail, Drive, Calendar, Docs, Contacts, Tasks, Chat                                                              | `uv` on PATH + Google OAuth creds                                                               |
| `notifications`              | Hooks            | macOS banner + sound when Claude needs attention                                                                 | macOS                                                                                           |
| `doc-drift`                  | Hooks            | Prompts Claude to review docs for drift after code changes (broken refs, stale line numbers, snippets, diagrams) | `git` + `bash`                                                                                  |

---

## Prerequisites

- Claude Code CLI — `claude --version`
- For `code-review-graph` and `google-workspace`: `uv` installed —
  `uvx --version`
- For `context7`: a Context7 API key from <https://context7.com/dashboard>
- For `google-workspace`: Google OAuth credentials — see
  `plugins/google-workspace/README.md`
- For `notifications`: macOS (uses built-in `osascript`)
- For `doc-drift`: `git` and `bash` (standard on macOS/Linux)

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
claude plugin install omniagents-reviewer@omniagents
claude plugin install code-review-graph@omniagents
claude plugin install context7@omniagents
claude plugin install google-workspace@omniagents
claude plugin install notifications@omniagents
claude plugin install doc-drift@omniagents
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

## Updating installed plugins

If a plugin is already installed, running `claude plugin install ...` again is
expected to report that it is already installed. Install is not the update path.

Marketplace update only refreshes the catalogue; it does not install plugins
that are not already installed.

Refresh the marketplace, then update the installed plugin:

```bash
claude plugin marketplace update omniagents
claude plugin update omniagents-python@omniagents
claude plugin update omniagents-typescript@omniagents
claude plugin update omniagents-design-patterns@omniagents
claude plugin update omniagents-writing@omniagents
claude plugin update omniagents-reviewer@omniagents
claude plugin update code-review-graph@omniagents
claude plugin update context7@omniagents
claude plugin update google-workspace@omniagents
claude plugin update notifications@omniagents
claude plugin update doc-drift@omniagents
```

Inside Claude Code, the equivalent commands are:

```text
/plugin marketplace update omniagents
/plugin update omniagents-python@omniagents
/plugin update omniagents-typescript@omniagents
/reload-plugins
```

Claude Code uses the plugin version as the cache key. Because these plugins set
`version` in each `.claude-plugin/plugin.json`, maintainers must bump that
version whenever published skill contents change. Pushing new commits without a
version bump will make updates look current to already-installed users. For
fast-moving internal plugins, omit `version` from both `plugin.json` and the
marketplace entry so Claude Code uses the git commit SHA as the version.

---

## Uninstall

The default scope is `user`. A bare uninstall command removes from user scope
without needing a flag. Add `--prune` to also drop any orphaned auto-installed
dependencies left behind:

```bash
claude plugin uninstall omniagents-python@omniagents --prune
claude plugin uninstall omniagents-typescript@omniagents --prune
claude plugin uninstall omniagents-design-patterns@omniagents --prune
claude plugin uninstall omniagents-writing@omniagents --prune
claude plugin uninstall omniagents-reviewer@omniagents --prune
claude plugin uninstall code-review-graph@omniagents --prune
claude plugin uninstall context7@omniagents --prune
claude plugin uninstall google-workspace@omniagents --prune
claude plugin uninstall notifications@omniagents --prune
claude plugin uninstall doc-drift@omniagents --prune
```

If the plugin was installed with a non-default scope, pass the matching
`--scope` flag:

```bash
claude plugin uninstall omniagents-python@omniagents --scope project --prune
claude plugin uninstall omniagents-python@omniagents --scope local --prune
```

Use `--keep-data` to preserve the plugin's data directory if you plan to
reinstall:

```bash
claude plugin uninstall omniagents-python@omniagents --prune --keep-data
```

---

## MCP server setup

### code-review-graph

The plugin starts the server automatically via `uvx code-review-graph serve`. No
extra configuration is needed beyond having `uv` on your PATH.

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

### google-workspace

The plugin starts the MCP server via `uvx workspace-mcp`. Three environment
variables must be exported before launching Claude Code:

```bash
export GOOGLE_OAUTH_CLIENT_ID="<your-client-id>.apps.googleusercontent.com"
export GOOGLE_OAUTH_CLIENT_SECRET="<your-client-secret>"
export USER_GOOGLE_EMAIL="your.email@gmail.com"
```

Full credential setup (Google Cloud project, OAuth consent screen, client ID) is
documented in `plugins/google-workspace/README.md`.

On first run the server opens a browser for the OAuth consent flow. The token is
cached locally; subsequent starts do not prompt again.

Verify:

```bash
claude mcp get google_workspace
```

Expected output:

```text
Scope: Project config (shared via .mcp.json)
Type: stdio
Command: uvx
Args: workspace-mcp
```

### notifications

No configuration is required beyond installing the plugin on macOS. The hook
fires automatically via `osascript` whenever Claude Code needs your attention.

Grant notification permission to your terminal app the first time it fires:
**System Settings → Notifications → [Terminal / iTerm2]**.

Validate the plugin structure:

```bash
claude plugin validate ./plugins/notifications
```

### doc-drift

No configuration is required. A single **Stop** hook checks `git diff` for
uncommitted source-file changes; if found, it prompts Claude to review
documentation for stale references and fix any drift.

Requirements: `git` and `bash` (standard on macOS/Linux).

Validate the plugin structure:

```bash
claude plugin validate ./plugins/doc-drift
```

---

## Verification

List all active MCP servers:

```bash
claude mcp list
```

All MCP plugins should appear. Inside Claude Code, smoke-test context7 with:

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
