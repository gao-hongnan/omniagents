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
                "NOTION_TOKEN": "${NOTION_TOKEN}"
            }
        }
    }
}
```

## Setup

### 1. Create a Notion internal integration

1. Go to <https://www.notion.so/profile/integrations>
2. Click **"New integration"** → select your workspace
3. Under **Configuration**, note the **Internal Integration Secret** (format
   `ntn_****`)
4. Under **Access**, select the pages and databases the integration should be
   able to access

### 2. Export the token

Add to your shell profile (`~/.zshrc`, `~/.bashrc`, etc.):

```bash
export NOTION_TOKEN="ntn_your_secret_here"
```

Then reload:

```bash
source ~/.zshrc
```

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
