# Notion MCP Plugin

Official Notion MCP server providing access to Notion pages, databases, and
workspace content via the
[@notionhq/notion-mcp-server](https://github.com/makenotion/notion-mcp-server)
package.

## Requirements

- [Node.js](https://nodejs.org/) (v18+) and `npm` — required for `npx`
- Verify with: `npx --version`

## Configuration

The MCP server is defined in [`.mcp.json`](./.mcp.json):

```json
{
    "mcpServers": {
        "notionApi": {
            "command": "npx",
            "args": ["-y", "@notionhq/notion-mcp-server"],
            "env": {
                "NOTION_TOKEN": "${user_config.notion_token}"
            }
        }
    }
}
```

## Setup

### 1. Create a Notion connection

1. Go to <https://app.notion.com/developers/connections>
2. Click **"+ New connection"**
3. Enter a **Connection name**, select **Access token** as the authentication
   method, confirm your workspace in **Installable in**, then click **"Create
   connection"**
4. Copy the token (format `ntn_****`)

### 2. Provide the token via `userConfig`

The plugin declares the token as `userConfig` (`sensitive: true`) in
`.claude-plugin/plugin.json`. Claude Code prompts for it when the plugin is
enabled, stores it in the OS keychain, and substitutes it into the server's
environment — nothing goes into your shell profile:

```bash
claude plugin install notion@omniagents --config notion_token="ntn_your_secret_here"
```

To change it later: `/plugin configure notion@omniagents`.

### 3. Verify

```bash
# Check the server is registered
claude mcp list
claude mcp get notionApi
```

Restart your Claude Code session — `mcp__notionApi__*` tools should appear.

## Available Tools (v2.0.0)

The server exposes **22 tools** including:

| Tool                         | Description                       |
| ---------------------------- | --------------------------------- |
| `create-a-page`              | Create a new page                 |
| `retrieve-a-page`            | Get page properties               |
| `update-a-page-properties`   | Update page properties            |
| `archive-a-page`             | Archive (delete) a page           |
| `move-page`                  | Move a page to a different parent |
| `query-data-source`          | Query a data source (database)    |
| `retrieve-a-data-source`     | Get data source metadata          |
| `create-a-data-source`       | Create a new data source          |
| `update-a-data-source`       | Update a data source              |
| `list-data-source-templates` | List available templates          |
| `search`                     | Full-text search across pages     |
| `retrieve-a-block`           | Get block content                 |
| `retrieve-block-children`    | List child blocks                 |
| `append-block-children`      | Append blocks to a page           |

## References

- [Notion MCP Server (GitHub)](https://github.com/makenotion/notion-mcp-server)
- [Notion API Documentation](https://developers.notion.com/)
- [Claude Code MCP Configuration](https://docs.anthropic.com/en/docs/claude-code/mcp)
