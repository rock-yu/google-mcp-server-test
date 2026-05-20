# Setup Guide

## Prerequisites

- Node.js v18+ (`node --version` to check)
- VS Code with GitHub Copilot extension
- A Google account

---

## Step 1: Install dependencies

```bash
npm install
```

> **Corporate SSL proxy?** Run `npm config set strict-ssl false` first, then retry.

---

## Step 2: Create a Google Cloud OAuth App

### 2a — Create a project
1. Go to [https://console.cloud.google.com/](https://console.cloud.google.com/)
2. Project dropdown → **New Project** → name it → **Create**

### 2b — Enable Google Drive API
1. **APIs & Services → Library**
2. Search **"Google Drive API"** → **Enable**

### 2c — Configure OAuth consent screen
1. **APIs & Services → OAuth consent screen**
2. Choose **External** → fill in app name and your email → **Save and Continue**
3. **Test users** → **+ Add Users** → enter your Google email → **Save**

   > ⚠️ If you skip adding your email as a test user, you'll get `Error 403: access_denied` during auth.

### 2d — Create OAuth credentials
1. **APIs & Services → Credentials → Create Credentials → OAuth client ID**
2. Application type: **Desktop app** → **Create**
3. Download the JSON → rename to `gcp-oauth.keys.json` → place in project root

   > 🔒 Never commit this file — it's already in `.gitignore`.

---

## Step 3: Authenticate with Google

```bash
NODE_TLS_REJECT_UNAUTHORIZED=0 \
GDRIVE_OAUTH_PATH="$(pwd)/gcp-oauth.keys.json" \
node node_modules/@modelcontextprotocol/server-gdrive/dist/index.js auth
```

1. Browser opens → sign in with your Google account
2. *"You've been given access to an app currently being tested"* → click **Continue** (expected)
3. Grant Drive read access → **Allow**
4. Terminal prints: `Credentials saved. You can now run the server.`

| Error | Fix |
|-------|-----|
| `Error 403: access_denied` | Add your email to Test users (Step 2c) |
| `UNABLE_TO_GET_ISSUER_CERT_LOCALLY` | Add `NODE_TLS_REJECT_UNAUTHORIZED=0` to the command |
| *"app currently being tested"* warning | Not an error — click **Continue** |

---

## Step 4: Open in VS Code

```bash
code .
```

VS Code reads `.vscode/mcp.json` and starts the `gdrive` MCP server automatically.

Verify: **Command Palette** (`⌘⇧P` / `Ctrl⇧P`) → **"MCP: List Servers"** → `gdrive` should show green.

---

## Step 5: Try it in Copilot Chat

1. Open **GitHub Copilot Chat** → switch to **Agent mode**
2. Try:
   - *"Search my Google Drive for documents about architecture"*
   - *"Read the contents of [document name] from my Drive"*
