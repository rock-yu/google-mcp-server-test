# Google Drive MCP Server Setup Guide

This guide walks you through setting up the `@modelcontextprotocol/server-gdrive` MCP server
to access Google Drive (including Google Docs) from VS Code via GitHub Copilot.

---

## Prerequisites

- Node.js installed (v18+)
- VS Code with GitHub Copilot extension
- A Google account

---

## Step 1: Project Setup

```bash
mkdir google-mcp-server-test
cd google-mcp-server-test
npm init -y
npm install @modelcontextprotocol/server-gdrive
```

> **Corporate network tip:** If you get SSL certificate errors, first run:
> ```bash
> npm config set strict-ssl false
> ```
> Then re-run the `npm install` command.

---

## Step 2: Google Cloud OAuth Credentials

1. Go to [https://console.cloud.google.com/](https://console.cloud.google.com/)
2. **Create a new project** (or select an existing one)
3. Navigate to **APIs & Services → Library**
4. Search for **"Google Drive API"** and click **Enable**
5. Go to **APIs & Services → OAuth consent screen**
   - Choose **External** (or Internal if on Google Workspace)
   - Fill in the app name and your email
   - Under **Scopes**, add: `https://www.googleapis.com/auth/drive.readonly`
   - Under **Test users**, click **"+ Add Users"** and add your Google email
6. Go to **APIs & Services → Credentials**
   - Click **"Create Credentials" → OAuth client ID**
   - Application type: **Desktop app**
   - Click **Create**
7. Download the JSON file and rename it to `gcp-oauth.keys.json`
8. Place it in your project root:
   ```
   google-mcp-server-test/
   └── gcp-oauth.keys.json   ← here
   ```

---

## Step 3: Authenticate with Google

Run the following command from your project root:

```bash
NODE_TLS_REJECT_UNAUTHORIZED=0 \
GDRIVE_OAUTH_PATH="$(pwd)/gcp-oauth.keys.json" \
node node_modules/@modelcontextprotocol/server-gdrive/dist/index.js auth
```

This will:
1. Open a browser window with a Google sign-in page
2. Show a warning: *"You've been given access to an app that's currently being tested"* — click **Continue**
3. Ask you to grant Drive read permissions — click **Allow**
4. Print: `Credentials saved. You can now run the server.`

Credentials are saved to:
```
node_modules/.gdrive-server-credentials.json
```

> **Corporate network tip:** The `NODE_TLS_REJECT_UNAUTHORIZED=0` flag is required on networks
> with SSL inspection (e.g. corporate proxies). It disables TLS certificate validation for
> local development only — do not use in production.

### Common auth errors

| Error | Fix |
|-------|-----|
| `Error 403: access_denied` | Your Google account isn't added as a test user. Go to OAuth consent screen → Test users → add your email. |
| `UNABLE_TO_GET_ISSUER_CERT_LOCALLY` | Corporate SSL proxy. Add `NODE_TLS_REJECT_UNAUTHORIZED=0` to your command. |
| `"You've been given access to an app that's currently being tested"` | Not an error — just click **Continue**. |

---

## Step 4: Configure VS Code

Create the file `.vscode/mcp.json` in your project root with the following content:

```json
{
  "servers": {
    "gdrive": {
      "type": "stdio",
      "command": "node",
      "args": [
        "${workspaceFolder}/node_modules/@modelcontextprotocol/server-gdrive/dist/index.js"
      ],
      "env": {
        "NODE_TLS_REJECT_UNAUTHORIZED": "0",
        "GDRIVE_OAUTH_PATH": "${workspaceFolder}/gcp-oauth.keys.json",
        "GDRIVE_CREDENTIALS_PATH": "${workspaceFolder}/node_modules/.gdrive-server-credentials.json"
      }
    }
  }
}
```

---

## Step 5: Use in VS Code

1. Open the project folder in VS Code
2. Open **GitHub Copilot Chat** in Agent mode
3. Verify the server is running via **Command Palette** (`⌘⇧P` / `Ctrl⇧P`) → **"MCP: List Servers"**
4. Try prompts like:
   - *"Search my Google Drive for documents about architecture"*
   - *"List recent files in my Google Drive"*
   - *"Read the contents of [document name] from my Drive"*

---

## What the MCP server supports

| Feature | Details |
|---------|---------|
| **Search** | Search files by name/content via `query` string |
| **Read files** | Access via `gdrive:///<file_id>` |
| **Google Docs** | Auto-exported as Markdown |
| **Google Sheets** | Auto-exported as CSV |
| **Google Slides** | Auto-exported as plain text |
| **Google Drawings** | Auto-exported as PNG |
| **Other files** | Returned in native format |

---

## Project structure (after setup)

```
google-mcp-server-test/
├── .vscode/
│   └── mcp.json
├── node_modules/
│   └── .gdrive-server-credentials.json   ← saved after auth
├── gcp-oauth.keys.json                    ← your OAuth keys (keep secret!)
├── package.json
└── package-lock.json
```

> ⚠️ **Security:** Never commit `gcp-oauth.keys.json` or `.gdrive-server-credentials.json` to git.
> Add them to `.gitignore`.
