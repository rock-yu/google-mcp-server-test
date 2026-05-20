# Google Drive MCP Server — Local Experiment

This repo lets you experiment with connecting **GitHub Copilot in VS Code** directly to your
**Google Drive** using the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/).

Once set up, you can ask Copilot things like:
- *"Search my Google Drive for architecture documents"*
- *"Read the contents of my meeting notes doc"*
- *"What's in the spreadsheet called Q1 Budget?"*

→ **To get started, follow [SETUP-GUIDE.md](./SETUP-GUIDE.md)**

---

## ⚠️ This is a locally-hosted MCP server — not a cloud-hosted one

| | **This setup (local)** | **Cloud-hosted MCP** |
|---|---|---|
| **Where it runs** | On your machine, spawned by VS Code | On a remote server (container, cloud function) |
| **Who starts it** | VS Code starts/stops it automatically | Always-on, accessed over HTTP/SSE |
| **Credentials** | Stored locally on your machine | Managed by the hosting environment |
| **Network** | stdin/stdout — no open port | Exposed via HTTPS endpoint |
| **Good for** | Local experimentation, personal use | Shared teams, production integrations |

**For this experiment:** your credentials never leave your machine. This is the simplest way to
explore MCP before committing to a hosted deployment.

> If you later want to share this with a team, move the server to a hosted environment and switch
> from `stdio` transport to `http`/`sse` in `.vscode/mcp.json`.

---

## How it works

```
VS Code (Copilot Chat)
       │
       │  MCP protocol (stdio)
       ▼
@modelcontextprotocol/server-gdrive   ← local Node.js process
       │
       │  Google Drive API (OAuth 2.0)
       ▼
  Your Google Drive
```

VS Code reads `.vscode/mcp.json` and spawns the MCP server as a background Node.js process when
you open this folder. Copilot Chat (in Agent mode) can then call its tools to search and read
files from your Drive.

---

## What the MCP server can do

| Capability | Output format |
|------------|---------------|
| Search files by name/content | File names + MIME types |
| Read Google Docs | Markdown |
| Read Google Sheets | CSV |
| Read Google Slides | Plain text |
| Read Google Drawings | PNG |
| Read other files | Native format |

---

## Project structure

```
google-mcp-server-test/
├── .vscode/
│   └── mcp.json                            ← VS Code MCP server config
├── node_modules/
│   └── .gdrive-server-credentials.json    ← saved after auth (gitignored 🔒)
├── .gitignore
├── gcp-oauth.keys.json                     ← your OAuth keys (gitignored 🔒)
├── package.json
├── README.md                               ← this file
└── SETUP-GUIDE.md                          ← step-by-step setup instructions
```

> 🔒 `gcp-oauth.keys.json` and `.gdrive-server-credentials.json` are in `.gitignore` — never commit them.
