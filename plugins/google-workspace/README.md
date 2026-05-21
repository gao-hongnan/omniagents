# Google Workspace MCP Plugin

This plugin adds the `workspace-mcp` MCP server to Claude Code so agents can
read and manage Gmail, Google Drive, Google Calendar, and Google Docs.

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
    "google_workspace": {
      "type": "stdio",
      "command": "uvx",
      "args": ["workspace-mcp"],
      "env": {
        "GOOGLE_OAUTH_CLIENT_ID": "${GOOGLE_OAUTH_CLIENT_ID}",
        "GOOGLE_OAUTH_CLIENT_SECRET": "${GOOGLE_OAUTH_CLIENT_SECRET}",
        "USER_GOOGLE_EMAIL": "${USER_GOOGLE_EMAIL}"
      }
    }
  }
}
```

All three environment variables must be set before launching Claude Code. See
[Credentials](#credentials) below.

## Credentials

This server uses Google OAuth 2.0. You need to create credentials in Google
Cloud Console and export them as environment variables.

### 1. Create a Google Cloud project

Go to <https://console.cloud.google.com/> and create or select a project.

### 2. Enable the required APIs

In your project, enable each of these APIs:

- <https://console.cloud.google.com/apis/library/gmail.googleapis.com>
- <https://console.cloud.google.com/apis/library/drive.googleapis.com>
- <https://console.cloud.google.com/apis/library/calendar-json.googleapis.com>
- <https://console.cloud.google.com/apis/library/docs.googleapis.com>

### 3. Configure the OAuth consent screen

Google requires an OAuth consent screen before you can create the Desktop app
OAuth client. For personal testing with your own Google account, configure the
app as an external test app:

1. Go to **Google Auth platform → Branding**.
2. If prompted that the Google Auth platform is not configured, click
   **Get Started**.
3. Under **App Information**:
   - Set **App name** to `workspace-mcp`.
   - Set **User support email** to your Google email, ideally the same address
     you will use for `USER_GOOGLE_EMAIL`.
4. Under **Audience**:
   - Choose **External**.
   - Keep the app in **Testing** mode.
5. Under **Contact Information**, enter your Google email again for project and
   app notices.
6. Under **Finish**, accept the Google API Services User Data Policy and click
   **Create**.
7. If you chose **External**, go to **Google Auth platform → Audience** and add
   your Google email as a **Test user**.

See the official Google Workspace guide for detail:
<https://developers.google.com/workspace/guides/configure-oauth-consent>

### 4. Create an OAuth 2.0 Client ID

After the consent screen exists:

1. Go to **APIs & Services → Credentials → Create Credentials →
   OAuth client ID**.
2. Choose **Desktop app** as the application type.
3. Name it `workspace-mcp`.
4. Click **Create** and note the **Client ID** and **Client Secret**.

See the official guide for screenshots and detail:
<https://developers.google.com/identity/protocols/oauth2/native-app>

### 5. Export the environment variables

Add these lines to your shell profile (`~/.zshrc` on macOS with zsh):

```bash
export GOOGLE_OAUTH_CLIENT_ID="<your-client-id>.apps.googleusercontent.com"
export GOOGLE_OAUTH_CLIENT_SECRET="<your-client-secret>"
export USER_GOOGLE_EMAIL="your.email@gmail.com"
```

Then reload:

```bash
source ~/.zshrc
```

### 6. Authenticate on first run

On first launch the server opens a browser for the OAuth consent flow. Approve
access; the token is cached locally and subsequent starts do not prompt again.

## Verification

From the repository root, check that Claude Code sees the server:

```bash
claude mcp get google_workspace
```

Expected details include:

```text
Scope: Project config (shared via .mcp.json)
Type: stdio
Command: uvx
Args: workspace-mcp
```

Then check health:

```bash
claude mcp list
```

Inside Claude Code, test with a prompt such as:

```text
List my 5 most recent Gmail threads.
```

If the server is listed but fails to connect, run the launch command directly
to see any startup errors:

```bash
uvx workspace-mcp
```

## References

- [workspace-mcp on PyPI](https://pypi.org/project/workspace-mcp/)
- [google_workspace_mcp source and docs](https://github.com/taylorwilsdon/google_workspace_mcp)
- [Google OAuth consent screen configuration](https://developers.google.com/workspace/guides/configure-oauth-consent)
- [Google OAuth 2.0 for Desktop Apps](https://developers.google.com/identity/protocols/oauth2/native-app)
- [Google Cloud Console credentials](https://console.cloud.google.com/apis/credentials)
- [Claude Code MCP configuration](https://docs.anthropic.com/en/docs/claude-code/mcp)
- [uv tools guide](https://docs.astral.sh/uv/guides/tools/)
