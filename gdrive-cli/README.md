# Google Drive CLI (Python)

Standalone Python process that talks to Google Drive using the **same OAuth files** as the Node MCP server — no MCP protocol, no Node runtime.

## Setup

```bash
cd gdrive-cli
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Credentials must already exist from [SETUP-GUIDE.md](../SETUP-GUIDE.md) Step 3.

## Usage

```bash
# List recent files
python gdrive_cli.py list
python gdrive_cli.py list -n 20

# Search (same fullText query as MCP search tool)
python gdrive_cli.py search "blood pressure"

# Metadata
python gdrive_cli.py info FILE_ID

# Read/export (Docs→markdown, Sheets→csv, etc.)
python gdrive_cli.py read FILE_ID
python gdrive_cli.py read FILE_ID -o output.csv

# Interactive REPL
python gdrive_cli.py interactive
```

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `GDRIVE_OAUTH_PATH` | `<repo>/gcp-oauth.keys.json` | OAuth client ID/secret |
| `GDRIVE_CREDENTIALS_PATH` | `<repo>/node_modules/.gdrive-server-credentials.json` | User access/refresh tokens |
| `NODE_TLS_REJECT_UNAUTHORIZED=0` or `GDRIVE_INSECURE_SSL=1` | off | Disable TLS verify (corporate proxy only) |

If the access token is expired, the script refreshes it and **writes back** to `GDRIVE_CREDENTIALS_PATH` so the MCP server stays in sync.
