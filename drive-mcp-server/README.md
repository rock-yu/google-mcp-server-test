# drive-mcp-server

A small, local **Google Drive MCP server** that speaks the Model Context
Protocol over **stdio**. It exposes a sample toolset modeled on Google's hosted
`drivemcp.googleapis.com` endpoint, but runs entirely on your machine and reuses
the OAuth + Drive logic from the sibling [`../gdrive-cli`](../gdrive-cli) module.

## Tools

The server exposes counterparts for the hosted `drivemcp.googleapis.com` server's
eight tools and adds one **local-only** extension (`update_file`). The three
metadata/listing tools below use the hosted input and output contracts exactly;
the remaining tools retain the local lightweight behavior documented here.

| Tool | Arguments | Behavior |
|------|-----------|----------|
| `search_files` | `query: str`, `pageSize: int = 10`, `pageToken: str = None`, `excludeContentSnippets: bool = false` | Searches with the hosted structured query dialect and returns `{files: File[], nextPageToken?: str}`. Trashed files are excluded. |
| `read_file_content` | `file_id: str` | Reads a file by id. Google Docs export to Markdown, Sheets to CSV, and Slides to plain text; other text files return their native text. Non-text binary files return an informative message. Unknown/inaccessible ids return an error result. |
| `list_recent_files` | `orderBy: "recency" \| "lastModified" \| "lastModifiedByMe" = "recency"`, `pageSize: int = 10`, `pageToken: str = None`, `excludeContentSnippets: bool = false` | Returns `{files: File[], nextPageToken?: str}` using the hosted sort and pagination contract. |
| `get_file_metadata` | `fileId: str`, `excludeContentSnippets: bool = false` | Returns one hosted-compatible structured `File`. Unknown/inaccessible ids return an error result. |
| `download_file_content` | `file_id: str`, `output_path: str = <file name>` | Saves the file's bytes (Google-native files are exported first) to a local path and returns the path and byte count. Unknown/inaccessible ids return an error result. |
| `create_file` | `name: str`, `content: str`, `mime_type: str = "text/plain"`, `parent_id: str = None` | **Write.** Creates a new file from text content, optionally in a parent folder. Returns the new file's id and name. Requires the `drive.file` scope. |
| `copy_file` | `file_id: str`, `name: str = None`, `parent_id: str = None` | **Write.** Copies an existing file, optionally with a new name and/or parent folder. Returns the new file's id and name. Requires the `drive.file` scope. |
| `get_file_permissions` | `file_id: str` | Lists a file's sharing permissions, one per line as `role type — grantee (id)`. Unknown/inaccessible ids return an error result. |
| `update_file` | `file_id: str`, `title: str = None`, `parent_id: str = None` | **Write, local-only extension.** Updates a file's metadata only — renames it via a non-empty `title` and/or moves it by replacing its current parent with `parent_id`. Content is never modified. At least one of `title`/`parent_id` is required. Requires the `drive.file` scope. The hosted server has no equivalent. |

### Hosted-compatible read contract

`search_files`, `list_recent_files`, and `get_file_metadata` return structured
`File` objects with the hosted field names:

`id`, `title`, `parentId`, `mimeType`, `fileSize`, `description`,
`fileExtension`, `contentSnippet`, `viewUrl`, `sharedWithMeTime`, `createdTime`,
`modifiedTime`, `viewedByMeTime`, `owner`, and `canAddChildren`.

Unavailable optional fields are omitted. Google generates `contentSnippet` inside
its hosted MCP service, but Drive v3 does not expose an equivalent value. The local
server therefore accepts and honors `excludeContentSnippets`, but omits
`contentSnippet` when no source value exists; this is the only known value-level
deviation for these three tools.

`search_files.query` supports the hosted terms and operators:

- `title` (`contains`, `=`, `!=`)
- `fullText` (`contains`)
- `mimeType` (`contains`, `=`, `!=`)
- `modifiedTime`, `viewedByMeTime`, `createdTime`
  (`<=`, `<`, `=`, `!=`, `>`, `>=`; RFC 3339 values)
- `parentId`, `owner`, `sharedWithMe` (`=`, `!=`)
- `and`, `or`, `not`, and parentheses

String values must be single-quoted. Use `parentId = 'root'` for My Drive and
`owner = 'me'` for the requesting user. A bare string remains supported as a local
convenience and is treated as `fullText contains '<string>'`.

### Scopes and write access

Read tools (`search_files`, `read_file_content`, `list_recent_files`,
`get_file_metadata`, `download_file_content`, `get_file_permissions`) work with
the **read-only** Drive scope (`drive.readonly`) inherited from your saved
credentials.

The **write** tools (`create_file`, `copy_file`, `update_file`) require the
`drive.file` scope. If your saved token only grants read access, these tools
return an actionable error asking you to re-authorize. To enable them,
re-run the OAuth flow (see [`../SETUP-GUIDE.md`](../SETUP-GUIDE.md) Step 3) so the
saved token includes `https://www.googleapis.com/auth/drive.file`; the refreshed
token is persisted and picked up automatically. `update_file` only changes
metadata (name/parent) and never overwrites file content.

### Local → hosted action mapping

| Local MCP tool | Hosted `drivemcp.googleapis.com/mcp/v1` capability | Drive v3 API | Scope |
|---|---|---|---|
| `search_files` | Search files | `files.list` (hosted query translated to Drive v3) | `drive.readonly` |
| `read_file_content` | Read file content | `files.get` / `files.export` | `drive.readonly` |
| `list_recent_files` | List recent files | `files.list` (`recency`, `modifiedTime`, or `modifiedByMeTime`) | `drive.readonly` |
| `get_file_metadata` | Retrieve metadata | `files.get` (hosted `File` fields) | `drive.readonly` |
| `download_file_content` | Download content | `files.get_media` / `files.export` | `drive.readonly` |
| `create_file` | Create files | `files.create` (media upload) | `drive.file` |
| `copy_file` | Copy a file | `files.copy` | `drive.file` |
| `get_file_permissions` | Inspect permissions | `permissions.list` | `drive.readonly` |
| `update_file` | _(none — local-only extension)_ | `files.update` (`name` / `addParents`+`removeParents`) | `drive.file` |

## Prerequisites

- **Python 3.10+**
- `gcp-oauth.keys.json` in the repository root (OAuth client ID/secret).
  See [`../SETUP-GUIDE.md`](../SETUP-GUIDE.md) Step 2.
- Saved user credentials (access/refresh tokens) produced by the auth flow in
  [`../SETUP-GUIDE.md`](../SETUP-GUIDE.md) Step 3. By default these are written
  to `../node_modules/.gdrive-server-credentials.json`.

## Setup

From this directory:

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## Configuration

The server reads the same environment variables as the CLI:

| Variable | Purpose | Default |
|----------|---------|---------|
| `GDRIVE_OAUTH_PATH` | Path to the OAuth client ID/secret JSON | `<repo>/gcp-oauth.keys.json` |
| `GDRIVE_CREDENTIALS_PATH` | Path to the saved user tokens | `<repo>/node_modules/.gdrive-server-credentials.json` |
| `DRIVE_MCP_READ_ONLY` | Omit tools that mutate Google Drive (`1`, `true`, `yes`, or `on`) | disabled |
| `NODE_TLS_REJECT_UNAUTHORIZED=0` | Dev-only: skip TLS verification behind a TLS-inspecting proxy | unset (verification on) |

If credentials are missing, the server exits at startup with an actionable
message instead of failing on the first tool call. Expired access tokens are
refreshed and persisted automatically.

`DRIVE_MCP_READ_ONLY` is read once when the process starts, so restart the server
after changing it. In this mode, `create_file`, `copy_file`, and `update_file` are
not registered. The six read/download tools retain exactly the same contracts.
`download_file_content` remains available because the mode prevents Drive mutation,
not local filesystem writes.

### MCP safety annotations

Every tool advertises all four standard MCP safety hints:

| Tool group | Read-only | Destructive | Idempotent | Open world |
|---|---:|---:|---:|---:|
| Search, read, recent, metadata, permissions | yes | no | yes | yes |
| Download to a local path | no | yes | no | yes |
| Create and copy | no | no | no | yes |
| Update metadata | no | yes | no | yes |

Download is destructive because it may overwrite a caller-selected path. Create and
copy are additive rather than destructive, while update can rename or move existing
state. These hints help MCP clients make safer choices but are advisory; Drive OAuth
scope checks and read-only tool omission remain the enforced controls.

## Run

The server communicates over stdio and is normally launched by an MCP client
(see VS Code integration below). To launch it directly:

```bash
.venv/bin/python server.py
```

## Verify (smoke test)

### Credential-free conformance suite

From the repository root, run the same hermetic command used by CI:

```bash
drive-mcp-server/.venv/bin/python verify.py
```

It runs unit tests, launches this registered server over real stdio with a
deterministic fake Drive backend, compares normalized `tools/list` schemas with
reviewed fixtures, exercises all nine tools through `tools/call`, compiles Python
sources, and strictly validates OpenSpec. It does not load OAuth files or access
the network.

The schema fixture covers all eight hosted counterparts; `update_file` is checked
as a local extension. Semantic parity cases cover all eight hosted counterparts: structured search,
recent files, metadata, native and Google-format reads/downloads, create/copy state
transitions, and permission serialization. They include optional inputs, binary
handling, overwrite behavior, authorization failures, inaccessible resources, and
controlled backend errors. The registered `contentSnippet` omission described above
remains the sole approved value-level deviation for the structured read tools.

Credentialed local and hosted checks are deliberately opt-in. Use only a
dedicated test account with non-sensitive fixture data:

```bash
RUN_LIVE_DRIVE_TESTS=1 \
  drive-mcp-server/.venv/bin/python -m unittest tests.live.test_live_drive -v

RUN_HOSTED_MCP_TESTS=1 HOSTED_MCP_BEARER_TOKEN='...' \
  drive-mcp-server/.venv/bin/python -m unittest tests.live.test_hosted_mcp -v
```

Run those commands from the repository root. Hosted drift capture and fixture
review instructions are in the root [`README.md`](../README.md). Normal tests
never update reviewed fixtures.

### Credentialed smoke test

From this directory, with your credential environment variables set, this lists
the advertised tools over a real stdio MCP session:

```bash
export GDRIVE_OAUTH_PATH="$(cd .. && pwd)/gcp-oauth.keys.json"
export GDRIVE_CREDENTIALS_PATH="$(cd .. && pwd)/node_modules/.gdrive-server-credentials.json"
.venv/bin/python - <<'PY'
import asyncio, os
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

async def main():
    params = StdioServerParameters(
        command=".venv/bin/python", args=["server.py"], env=dict(os.environ)
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            print("tools:", [t.name for t in tools])
            result = await session.call_tool(
                "search_files",
                {
                    "query": "parentId = 'root'",
                    "pageSize": 1,
                    "excludeContentSnippets": True,
                },
            )
            print("search:", result.structured_content)

asyncio.run(main())
PY
```

Expected output:

```
tools: ['search_files', 'read_file_content', 'list_recent_files', 'get_file_metadata', 'download_file_content', 'create_file', 'copy_file', 'get_file_permissions', 'update_file']
search: {'files': [...], 'nextPageToken': '...'}
```

## VS Code integration

The repository's [`.vscode/mcp.json`](../.vscode/mcp.json) registers this server
as `drive-mcp`:

```json
"drive-mcp": {
  "type": "stdio",
  "command": "${workspaceFolder}/drive-mcp-server/.venv/bin/python",
  "args": ["${workspaceFolder}/drive-mcp-server/server.py"],
  "env": {
    "NODE_TLS_REJECT_UNAUTHORIZED": "0",
    "GDRIVE_OAUTH_PATH": "${workspaceFolder}/gcp-oauth.keys.json",
    "GDRIVE_CREDENTIALS_PATH": "${workspaceFolder}/node_modules/.gdrive-server-credentials.json"
  }
}
```

Open **MCP: List Servers** in VS Code and start `drive-mcp` to use the tools.
