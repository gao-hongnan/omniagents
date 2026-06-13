# Playwright MCP Plugin

This plugin adds Microsoft's [Playwright MCP](https://github.com/microsoft/playwright-mcp)
server to Claude Code, giving agents browser automation driven by Playwright's
accessibility tree — navigate, click, type, and capture structured page
snapshots without screenshots or vision models.

## Configuration

The plugin MCP config is in `.mcp.json`:

```json
{
  "mcpServers": {
    "playwright": {
      "type": "stdio",
      "command": "npx",
      "args": ["@playwright/mcp@latest"]
    }
  }
}
```

`@playwright/mcp@latest` is fetched and launched by `npx` on demand, so there is
no global install to maintain. The server speaks `stdio`.

## Prerequisites

- **Node.js 18 or newer** on PATH — `node --version`
- On first launch Playwright downloads the browser it drives (Chromium by
  default); this needs network access and a few hundred MB of disk.

No API key or environment variable is required.

## Common flags

Append flags to the `args` array to customize behavior:

| Flag                    | Effect                                                         |
| ----------------------- | -------------------------------------------------------------- |
| `--headless`            | Run the browser headless (headed by default)                   |
| `--browser <name>`      | `chrome`, `firefox`, `webkit`, or `msedge`                     |
| `--isolated`            | Keep the browser profile in memory; nothing is written to disk |
| `--user-data-dir <dir>` | Persist the browser profile at a chosen path                   |
| `--viewport-size <wxh>` | Set viewport, e.g. `1280x720`                                  |

Example — headless Chromium with an isolated profile:

```json
{
  "mcpServers": {
    "playwright": {
      "type": "stdio",
      "command": "npx",
      "args": ["@playwright/mcp@latest", "--headless", "--isolated"]
    }
  }
}
```

## Verification

From the repository root, check that Claude Code sees the server:

```bash
claude mcp get playwright
```

Expected details include:

```text
Scope: Project config (shared via .mcp.json)
Type: stdio
Command: npx
Args: @playwright/mcp@latest
```

Then check health:

```bash
claude mcp list
```

Inside Claude Code, smoke-test with a prompt such as:

```text
use the playwright mcp to open https://example.com and snapshot the page
```

## References

- [Playwright MCP repository](https://github.com/microsoft/playwright-mcp)
- [Claude Code MCP configuration](https://code.claude.com/docs/en/mcp)
