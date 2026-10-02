# Proposal

## Why

Today this repo depends on the prebuilt Node package `@modelcontextprotocol/server-gdrive` (an opaque binary) for its MCP server, while its hackable Python code (`gdrive-cli`) is a plain CLI that already does OAuth and Drive REST calls but speaks no MCP. Having just mapped Google's hosted endpoint (`drivemcp.googleapis.com/mcp/v1`), we want a small local MCP server we fully control: a readable reference implementation that exposes a sample Drive toolset to Copilot over stdio, modeled on the hosted server's tool shape but calling the Drive REST API directly.

## What Changes

- Add a new local, standalone **Python MCP server** that speaks MCP over **stdio** (the transport VS Code / Copilot launches).
- Expose a **sample toolset of two tools**, modeled on the hosted `drivemcp.googleapis.com` tool contracts:
  - `search_files` — full-text search over the user's Drive, returning file name, MIME type, and id.
  - `read_file_content` — read/export a file by id (Google Docs → Markdown, Sheets → CSV, Slides → text, else native), returning text content.
- Authenticate with the existing **OAuth 2.0 client ID/secret** pattern, reusing `gcp-oauth.keys.json` and the saved token file (`.gdrive-server-credentials.json`), including silent refresh — read-only scope (`drive.readonly`).
- Reuse the credential-loading, refresh, and Drive REST logic already proven in `gdrive-cli/gdrive_cli.py`.
- Register the new server in `.vscode/mcp.json` so Copilot can launch it, and document setup.
- The hosted MCP server is the **reference model** for tool naming and behavior only; this change does not proxy to it.

## Capabilities

### New Capabilities
- `drive-mcp-server`: A locally hosted MCP server that authenticates to Google Drive with the user's OAuth credentials and exposes Drive capabilities (starting with full-text search and file-content reading) as MCP tools over stdio.

### Modified Capabilities
<!-- None: no existing specs change. -->

## Impact

- **New code**: a new `drive-mcp-server/` directory containing the Python MCP server and its dependency manifest.
- **Dependencies**: adds the Python MCP SDK; reuses the existing `google-api-python-client` / `google-auth*` stack already listed for `gdrive-cli`.
- **Configuration**: a new `stdio` server entry in `.vscode/mcp.json`; reuses the existing credential files and `GDRIVE_OAUTH_PATH` / `GDRIVE_CREDENTIALS_PATH` environment variables.
- **Credentials / security**: read-only Drive scope; no secrets committed (existing `.gitignore` entries already cover the credential files).
- **Docs**: setup instructions for running and connecting the new server.
