# Google Drive MCP Server — Experiment Setup Guide

## What is this?

This repo lets you experiment with connecting **GitHub Copilot in VS Code** directly to your
**Google Drive** using the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/).

Once set up, you can ask Copilot things like:
- *"Search my Google Drive for architecture documents"*
- *"Read the contents of my meeting notes doc"*
- *"What's in the spreadsheet called Q1 Budget?"*

Copilot will call the MCP server, which talks to Google Drive on your behalf and returns the
content — all without you leaving your editor.

---

## ⚠️ This is a locally-hosted MCP server — not a cloud-hosted one

It's important to understand **where this MCP server runs**, because it affects security,
performance, and how you'd productionise it.

| | **This setup (local)** | **Cloud-hosted MCP** |
|---|---|---|
| **Where it runs** | On your own machine, spawned by VS Code | On a remote server (e.g. a container, cloud function) |
| **Who starts it** | VS Code starts/stops it automatically per session | Always-on, accessed over HTTP/SSE |
| **Credentials** | Stored locally on your machine | Managed by the hosting environment (secrets manager, etc.) |
| **Network** | Communicates via stdin/stdout (no open port) | Exposed via HTTPS endpoint |
| **Good for** | Local experimentation, personal use | Shared teams, production integrations |
| **Latency** | Near-zero (local process) | Network round-trip |

**For this experiment:** you are running the MCP server as a local Node.js process on your
laptop. Your Google credentials never leave your machine. This is the simplest and safest way
to explore MCP capabilities before committing to a cloud-hosted deployment.

If you later want to share this with a team or run it in CI/CD, you would move the server to
a hosted environment and switch from `stdio` transport to `http`/`sse` transport in the config.

---

## How it works (big picture)

```
VS Code (Copilot Chat)
       │
       │  speaks MCP protocol (stdio)
       ▼
@modelcontextprotocol/server-gdrive   ← local Node.js process
       │
       │  Google Drive API (OAuth 2.0)
       ▼
  Your Google Drive
```

The MCP server runs as a local background process. VS Code spawns it automatically when you open
the project. Your credentials never leave your machine — they are stored locally and used to make
API calls directly to Google.

---

## Prerequisites

Before you start, make sure you have:

- **Node.js v18+** — the MCP server runs on Node (`node --version` to check)
- **VS Code** with the **GitHub Copilot** extension installed and signed in
- A **Google account** with some files in Google Drive to experiment with

---

## Step 1: Install the MCP Server Package

**What you're doing:** Installing the Google Drive MCP server as a local Node.js dependency.
This is the bridge between VS Code/Copilot and the Google Drive API.

```bash
cd google-mcp-server-test
npm install
```

> **Why `npm install` and not `npm install @modelcontextprotocol/server-gdrive`?**
> The package is already declared in `package.json` in this repo — `npm install` restores it.

> **Corporate network tip:** If you get `UNABLE_TO_GET_ISSUER_CERT_LOCALLY` errors, your
> network uses SSL inspection. Run this first, then retry:
> ```bash
> npm config set strict-ssl false
> npm install
> ```

---

## Step 2: Create a Google Cloud OAuth App

**What you're doing:** Registering a "Desktop App" in Google Cloud so the MCP server has
permission to read your Google Drive on your behalf. Think of this as creating an API key
with an identity that Google can trust.

**Why is this needed?** Google Drive requires OAuth 2.0 — you can't just use a username/password.
OAuth lets you grant limited, revocable access (read-only Drive in this case) without exposing
your Google credentials to the app.

### 2a — Create a Google Cloud Project

1. Go to [https://console.cloud.google.com/](https://console.cloud.google.com/)
2. Click the project dropdown at the top → **"New Project"**
3. Give it any name (e.g. `google-drive-mcp-test`) and click **Create**

### 2b — Enable the Google Drive API

This tells Google that your project is allowed to make Drive API calls.

1. Go to **APIs & Services → Library**
2. Search for **"Google Drive API"** → click it → click **Enable**

### 2c — Configure the OAuth Consent Screen

This is the sign-in screen users see when granting access. For experiments, you only need
a minimal setup.

1. Go to **APIs & Services → OAuth consent screen**
2. Choose **External** (allows any Google account; choose Internal if on Google Workspace)
3. Fill in:
   - **App name**: anything (e.g. `Google Drive MCP Test`)
   - **User support email**: your email
   - **Developer contact email**: your email
4. Click **Save and Continue** through the Scopes screen (you'll add the scope next)
5. On the **Test users** screen → click **"+ Add Users"** → enter your Google email → **Save**

   > ⚠️ **This step is critical.** Until you publish the app (which requires Google review),
   > only email addresses listed here can sign in. If you skip this, you'll get `Error 403: access_denied`.

### 2d — Create OAuth Credentials

This generates the client ID + secret the MCP server uses to identify itself to Google.

1. Go to **APIs & Services → Credentials**
2. Click **"Create Credentials" → OAuth client ID**
3. Application type: **Desktop app**
4. Click **Create**
5. Click **"Download JSON"** on the confirmation dialog (or download it later from the credentials list)
6. Rename the downloaded file to `gcp-oauth.keys.json`
7. Place it in this project root:
   ```
   google-mcp-server-test/
   └── gcp-oauth.keys.json   ← here
   ```

   > 🔒 This file contains your client secret. It is listed in `.gitignore` and must never be committed.

---

## Step 3: Authenticate — Link Your Google Account

**What you're doing:** Running a one-time auth flow that opens your browser, asks you to sign
in with Google, and saves a token locally. After this step, the MCP server can make Drive API
calls without asking you to sign in again.

Run this from the project root:

```bash
NODE_TLS_REJECT_UNAUTHORIZED=0 \
GDRIVE_OAUTH_PATH="$(pwd)/gcp-oauth.keys.json" \
node node_modules/@modelcontextprotocol/server-gdrive/dist/index.js auth
```

**What happens:**
1. Your browser opens to a Google sign-in page
2. You see: *"You've been given access to an app that's currently being tested"* — click **Continue**
   (this is expected — your app is in test mode)
3. Google asks you to grant **read-only Drive access** — click **Allow**
4. The terminal prints: `Credentials saved. You can now run the server.`

A token file is now saved at `node_modules/.gdrive-server-credentials.json`. This is what
the server uses on every subsequent run — you won't need to sign in again unless it expires.

> **Why `NODE_TLS_REJECT_UNAUTHORIZED=0`?** On networks with SSL inspection (corporate proxies),
> the proxy intercepts HTTPS traffic with its own certificate, which Node.js rejects by default.
> This flag disables that check for local development only. Do **not** use in production.

### Common auth errors

| Error | What it means | Fix |
|-------|---------------|-----|
| `Error 403: access_denied` | Your Google account isn't on the test users list | Go to OAuth consent screen → Test users → add your email |
| `UNABLE_TO_GET_ISSUER_CERT_LOCALLY` | Corporate SSL proxy intercepting the token exchange | Add `NODE_TLS_REJECT_UNAUTHORIZED=0` to your command |
| *"You've been given access to an app that's currently being tested"* | Normal warning for test-mode apps | Just click **Continue** — it's not an error |

---

## Step 4: Configure VS Code to Use the MCP Server

**What you're doing:** Telling VS Code how to start the MCP server when you open this project.
The `.vscode/mcp.json` file is already in this repo — you don't need to create it.

Open `.vscode/mcp.json` to understand what it does:

```json
{
  "servers": {
    "gdrive": {
      "type": "stdio",               // VS Code communicates with the server via stdin/stdout
      "command": "node",             // runs the server as a Node.js process
      "args": [
        "${workspaceFolder}/node_modules/@modelcontextprotocol/server-gdrive/dist/index.js"
      ],
      "env": {
        "NODE_TLS_REJECT_UNAUTHORIZED": "0",          // handles corporate SSL proxies
        "GDRIVE_OAUTH_PATH": "${workspaceFolder}/gcp-oauth.keys.json",
        "GDRIVE_CREDENTIALS_PATH": "${workspaceFolder}/node_modules/.gdrive-server-credentials.json"
      }
    }
  }
}
```

VS Code reads this file automatically when you open the folder and starts the `gdrive` server
in the background. No manual server startup needed.

---

## Step 5: Try It in VS Code

**What you're doing:** Using GitHub Copilot Chat (in Agent mode) to query your Google Drive
through the MCP server.

1. Open this folder in VS Code: `code .`
2. Verify the server registered: **Command Palette** (`⌘⇧P` / `Ctrl⇧P`) → **"MCP: List Servers"**
   — you should see `gdrive` with a green status
3. Open **GitHub Copilot Chat** → switch to **Agent mode** (the `@` icon or agent selector)
4. Try these prompts:
   - *"Search my Google Drive for documents about architecture"*
   - *"List recent files in my Google Drive"*
   - *"Read the contents of [your document name] from my Drive"*

Copilot will call the MCP server tool, which fetches from Drive and returns the content inline
in the chat — no copy-pasting needed.

---

## What the MCP Server Can Do

| Capability | How it works |
|------------|--------------|
| **Search files** | Accepts a search query, returns matching file names and types |
| **Read Google Docs** | Fetches the doc and converts it to **Markdown** |
| **Read Google Sheets** | Fetches the sheet and converts it to **CSV** |
| **Read Google Slides** | Fetches the presentation as **plain text** |
| **Read Google Drawings** | Returns as **PNG** |
| **Read other files** | Returns in native format (PDF, images, etc.) |

Files are accessed via the URI scheme `gdrive:///<file_id>`.

---

## Project Structure

```
google-mcp-server-test/
├── .vscode/
│   └── mcp.json                             ← VS Code MCP server config (committed)
├── node_modules/
│   └── .gdrive-server-credentials.json     ← saved after auth (gitignored 🔒)
├── .gitignore                               ← excludes credentials and node_modules
├── gcp-oauth.keys.json                      ← your OAuth keys (gitignored 🔒)
├── package.json                             ← declares the MCP server dependency
└── SETUP-GUIDE.md                           ← this file
```

> ⚠️ **Security reminder:** `gcp-oauth.keys.json` and `.gdrive-server-credentials.json` are
> both listed in `.gitignore`. Never commit them — they contain secrets that grant access to
> your Google Drive.
