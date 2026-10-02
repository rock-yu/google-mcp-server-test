# Proposal

## Why

The local `search_files`, `list_recent_files`, and `get_file_metadata` tools are
faithful but lightweight mirrors of Google's hosted `drivemcp.googleapis.com/mcp/v1`
server: they emit human-readable strings with 3-8 thin fields, offer no pagination,
and omit inputs the hosted contract defines. A client coded against the hosted
contract cannot consume their output. This change closes that gap — with
`search_files` reaching full hosted parity as the priority — so the local server is
contract-compatible, not just human-legible.

## What Changes

- **`search_files` — hosted contract parity (priority):**
  - Accept the exact hosted MCP input names: `query`, `pageSize`, `pageToken`,
    `excludeContentSnippets`.
  - Return a structured response (`files[]` + `nextPageToken`) instead of a joined string.
  - Each file is the hosted `File` shape with hosted field names: `id`, `title`,
    `parentId`, `mimeType`, `fileSize`, `description`, `fileExtension`,
    `contentSnippet`, `viewUrl`, `sharedWithMeTime`, `createdTime`, `modifiedTime`,
    `viewedByMeTime`, `owner`, `canAddChildren`.
  - Exclude trashed files by default (`trashed = false`).
  - Document query semantics: `query` is the **hosted query dialect** (terms
    `title`, `fullText`, `mimeType`, `modifiedTime`, `createdTime`, `viewedByMeTime`,
    `parentId`, `owner`, `sharedWithMe` with their operators, `and`/`or`/`not` +
    parentheses). The server translates this dialect into the equivalent Drive v3
    query (e.g. `parentId = 'X'` → `'X' in parents`, `title` → `name`,
    `owner = 'me'` → `'me' in owners`), rather than treating the input as an opaque
    full-text term.
  - Preserve one explicit value-level deviation: Google's generated
    `contentSnippet` text is unavailable from Drive v3, so local results omit that
    optional field when no equivalent value exists. The input/output schema and all
    other search behavior still match the hosted contract.
- **Shared structured `File` foundation:** a single helper maps a Drive v3 file
  resource to the hosted `File` representation (field renames + snippet handling),
  reused by all three read tools so output stays consistent.
- **`list_recent_files` — adopt the foundation:** add the exact hosted inputs
  `orderBy`, `pageToken`, `pageSize`, `excludeContentSnippets`; map the hosted sort
  values `recency`, `lastModified`, and `lastModifiedByMe` to Drive v3 ordering; return
  structured `files[]` + `nextPageToken` of `File` objects (replacing string lines).
- **`get_file_metadata` — adopt the foundation:** expose the exact hosted inputs
  `fileId` and `excludeContentSnippets`;
  return a structured `File` object (replacing the string block).
- **BREAKING:** the three tools' return payloads change from formatted strings to
  structured JSON, and field names move to the hosted vocabulary (`title`/`fileSize`/
  `parentId`). Out of scope: the other tools (`read_file_content`, `download_file_content`,
  `create_file`, `copy_file`, `get_file_permissions`, `update_file`).

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `drive-mcp-server`: The *Full-text file search tool*, *List recent files tool*, and
  *File metadata tool* requirements change their inputs and output shape to match the
  hosted `drivemcp.googleapis.com/mcp/v1` contract (structured `File` objects,
  pagination, content-snippet control, trashed exclusion).

## Impact

- **Code:** `gdrive-cli/gdrive_cli.py` (search/list helpers gain paging + snippet
  params and a shared `File` mapper), `drive-mcp-server/server.py` (the three tool
  wrappers return structured data), `drive-mcp-server/README.md` (tool docs + mapping
  table), and the `drive-mcp-server` spec.
- **Consumers:** any caller parsing the old string output must switch to the
  structured payload — this is the intended compatibility improvement.
- **CLI:** `gdrive_cli` command-line output (`cmd_search`, `cmd_list`, `cmd_info`)
  is preserved; only the reusable helpers and the MCP tool layer change shape.
