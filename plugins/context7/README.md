# Context7 MCP Plugin

This plugin adds the hosted Context7 MCP server to Claude Code so agents can look up current library and framework documentation.

## Configuration

The plugin MCP config is in `.mcp.json`:

```json
{
  "mcpServers": {
    "context7": {
      "type": "http",
      "url": "https://mcp.context7.com/mcp",
      "headers": {
        "CONTEXT7_API_KEY": "${CONTEXT7_API_KEY}"
      }
    }
  }
}
```

`type: "http"` is required for Claude Code to recognize this as a remote HTTP MCP server.

## API Key

Context7 can work without an API key at lower rate limits, but this plugin is configured to use one. Create a key from:

https://context7.com/dashboard

Keep the key out of this repository. Set it in your shell before launching Claude Code:

```bash
export CONTEXT7_API_KEY="ctx7sk-your-key-here"
claude
```

For zsh on macOS, you can make it persistent with:

```bash
echo 'export CONTEXT7_API_KEY="ctx7sk-your-key-here"' >> ~/.zshrc
source ~/.zshrc
```

## Verification

From the repository root, check that Claude Code sees the server:

```bash
claude mcp get context7
```

Expected details include:

```text
Scope: Project config (shared via .mcp.json)
Type: http
URL: https://mcp.context7.com/mcp
```

Then check health:

```bash
claude mcp list
```

Inside Claude Code, test with a prompt such as:

```text
use context7 mcp to search pydantic
```
