# Proposal

## Why

The local `drive-mcp-server` currently exposes only `search_files` and `read_file_content` — a subset of the hosted `drivemcp.googleapis.com/mcp/v1` reference server, which exposes eight tools (also listing recent files, returning metadata, downloading content, creating and copying files, and inspecting permissions). Reaching parity lets local AI clients fully browse, inspect, download, copy, and create Drive files, and gives us a documented local→hosted action mapping. Beyond parity, we also add one local-only `update_file` tool for metadata updates (rename and folder-move) that the hosted server does not expose.

## What Changes

- Add `list_recent_files` (read-only): return recently modified files with id, name, MIME type, modified time, and size.
- Add `get_file_metadata` (read-only): return a file's metadata (name, MIME type, size, owners, modified time, web link, parents).
- Add `download_file_content` (read-only): save a file's bytes — or exported bytes for Google-native formats — to a local output path and return that path plus the byte count.
- Add `create_file` (write): create a new Drive file from provided text content, name, and MIME type, optionally under a parent folder.
- Add `copy_file` (write): copy an existing Drive file, optionally with a new name and parent folder.
- Add `get_file_permissions` (read-only): list a file's sharing/permission entries (role, type, and grantee).
- Add `update_file` (write, **local-only extension beyond hosted parity**): update an existing file's metadata — rename it via a non-empty `title` and/or move it to a new parent folder via `parent_id` (replacing its current parent). Content is never modified. The hosted server exposes no equivalent.
- Modify the `tools/list` advertisement to include all eight hosted-parity tools plus the local-only `update_file` (nine tools total), each with input schemas.
- **BREAKING** (read-only guarantee): expand authentication from `drive.readonly` to `drive.readonly` + `drive.file` so `create_file`, `copy_file`, and `update_file` can write; read tools are unaffected, and write tools return a clear permission error when the saved token lacks the write scope.
- Document the local→hosted action mapping in `design.md` and `drive-mcp-server/README.md`.

## Capabilities

### New Capabilities

<!-- none -->

### Modified Capabilities

- `drive-mcp-server`: add six hosted-parity tools (`list_recent_files`, `get_file_metadata`, `download_file_content`, `create_file`, `copy_file`, `get_file_permissions`) plus one local-only `update_file` tool (metadata rename/move, beyond hosted parity), advertise all nine tools in `tools/list`, and expand authentication to include the `drive.file` write scope required by `create_file`, `copy_file`, and `update_file`.

## Impact

- **Code**: `drive-mcp-server/server.py` (seven new tool handlers); `gdrive-cli/gdrive_cli.py` (reusable `list_recent_files`, `get_file_metadata`, `download_file`, `create_file`, `copy_file`, `list_permissions`, and `update_file` helpers, keeping existing CLI signatures backward-compatible); `drive-mcp-server/README.md` (tool docs + mapping table).
- **Auth / scope**: the saved token must be re-authorized to include `drive.file`; the current token is `drive.readonly` only, so `create_file`, `copy_file`, and `update_file` fail with an actionable insufficient-scope message until re-auth. Read tools keep working unchanged.
- **Dependencies**: none new — `google-api-python-client` (including `MediaIoBaseUpload` for create) is already pinned.
- **Config**: `.vscode/mcp.json` launch entry is unchanged; new tools are auto-discovered via `tools/list`.
