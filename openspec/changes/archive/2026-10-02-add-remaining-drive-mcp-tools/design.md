# Design

## Context

See proposal.md - Why. The local `drive-mcp-server/server.py` is a stdio MCP server (SDK `MCPServer`) that today exposes `search_files` and `read_file_content` by delegating to reusable helpers in `gdrive-cli/gdrive_cli.py` (`search_files`, `read_file`). That module already loads OAuth client keys + saved tokens, refreshes/persists expired tokens, honors the `GDRIVE_INSECURE_SSL` / `NODE_TLS_REJECT_UNAUTHORIZED` dev flag, and builds a Drive v3 service. It also has `cmd_list` (recent files) and `cmd_info` (metadata) that currently inline their Drive calls, and `read_file` already returns `raw` bytes for binary content. The saved token is currently `drive.readonly` only. The hosted `drivemcp.googleapis.com/mcp/v1` server is the reference model for tool coverage and naming only; we never call it.

## Goals / Non-Goals

**Goals:**
- Add six tools — `list_recent_files`, `get_file_metadata`, `download_file_content`, `get_file_permissions` (read-only), and `create_file`, `copy_file` (write) — reusing shared `gdrive_cli` helpers, reaching parity with the hosted server's eight-tool set.
- Add one local-only `update_file` tool (write) for metadata-only updates — rename via `title` and/or folder-move via `parent_id` — explicitly beyond hosted parity; the hosted server exposes no equivalent.
- Keep the existing CLI (`list`, `info`, `read`, `search`) working with unchanged output.
- Make `create_file`, `copy_file`, and `update_file` surface an actionable error when the saved token lacks write scope, rather than crashing.
- Document a local→hosted action mapping.

**Non-Goals:**
- Proxying to or calling the hosted `drivemcp.googleapis.com` endpoint.
- A content-overwrite tool — the hosted server is intentionally non-destructive; the local-only `update_file` changes metadata (name/parent) only and never rewrites file content.
- Binary/base64 file creation — `create_file` accepts text content only.
- A new re-auth/OAuth consent flow in this server; obtaining a `drive.file` token is an operator step (documented), not code here.

## Decisions

**1. Reuse and extend `gdrive_cli` helpers; refactor the inline CLI commands to delegate.**
Add `list_recent_files(service, page_size)`, `get_file_metadata(service, file_id)`, `download_file(service, file_id, output_path=None)`, `create_file(service, name, content, mime_type, parent_id=None)`, `copy_file(service, file_id, name=None, parent_id=None)`, `list_permissions(service, file_id)`, and `update_file(service, file_id, title=None, parent_id=None)` to `gdrive_cli.py`, and refactor `cmd_list`/`cmd_info` to call the first two (as `cmd_search`/`cmd_read` already delegate). Rationale: one source of truth for Drive field lists and export logic; the server stays a thin adapter. Alternative: implement Drive calls directly in `server.py` — rejected (duplicates field/export logic, drift risk). Trade-off: a light, backward-compatible refactor validated by the existing CLI.

**2. `download_file_content` saves bytes to a path (no inline base64).**
Reuse `read_file`, which returns `raw` bytes for binary and `text` for text/exported Google-native files; write `raw` when binary else the UTF-8-encoded `text` to a caller-provided path (defaulting to the file's name), and return the path + byte count. Rationale: MCP results are text, so returning large binaries inline would bloat the client context; a path keeps results small and mirrors the CLI `read --output`. Alternative: base64 inline — rejected for context bloat (the user also chose save-to-path).

**3. `create_file`, `copy_file`, and `update_file` are the write tools and require the `drive.file` scope.**
Create via `files().create(body={name, mimeType, parents?}, media_body=MediaIoBaseUpload(BytesIO(content), mimetype))`, copy via `files().copy(fileId=..., body={name?, parents?})`, and update via `files().update(...)` (decision 6), each returning `id` and `name`. Rationale: `drive.file` grants per-file write access (least privilege) and matches the hosted server's write scope. Alternative: full `drive` scope — rejected as over-broad. `get_file_permissions` is a read via `permissions.list(fileId=..., fields="permissions(id,role,type,emailAddress,displayName)")` under `drive.readonly`.

**4. Detect missing write scope up front for a clear error.**
Before a create, copy, or update call, check whether the loaded credentials' granted scopes include `drive.file` (or full `drive`); if not, return a `ToolError` telling the operator to re-authorize with write access. Also wrap `HttpError` 403 `insufficientPermissions` from the API as the same actionable error. Rationale: the saved `scope` field gives a deterministic, friendly path for the spec's insufficient-scope scenario without a wasted API round-trip, while the `HttpError` fallback covers a stale scope string. Alternative: rely solely on the API 403 — kept as a fallback, but the pre-check yields a clearer message.

**5. Keep authentication config and the read-only default loader unchanged.**
The server still loads credentials via `gdrive_cli.drive_service()` and inherits whatever scopes the saved token carries; read tools need only `drive.readonly`. Expanding to `drive.file` is an operator re-auth step documented in the README. Rationale: no new secret-handling paths; write capability is opt-in via the token, and the server degrades to a clear error without it.

**6. `update_file` is a local-only metadata update verified against the hosted toolset.**
The hosted `drivemcp.googleapis.com/mcp/v1` reference (Google's MCP reference page) lists exactly eight tools and no `update_file` (nor any update/modify/move/rename tool), so this tool is a deliberate local-only extension, flagged as such in the proposal, spec, README, and mapping table. It maps to Drive v3 `files().update(fileId=..., body={"name": title}?, addParents=parent_id?, removeParents=<current parents>?, fields="id,name,parents")`; to move a file we first read its current parents via `files().get(fileId, fields="parents")` and pass them as `removeParents` so the new parent replaces the old. It validates that a provided `title` is non-empty and that at least one of `title`/`parent_id` is given (else `ToolError`), and never touches file content (metadata-only, consistent with the hosted server's non-destructive posture). Alternative: a content-overwrite `update` — rejected (out of scope; the user's contract is `fileId`/`parentId`/`title` only).

## Local → hosted action mapping

| Local MCP tool | Hosted `drivemcp.googleapis.com/mcp/v1` capability | Drive v3 API | Scope |
|---|---|---|---|
| `search_files` | Search files | `files.list` (`fullText contains`) | `drive.readonly` |
| `read_file_content` | Read file content | `files.get` / `files.export` | `drive.readonly` |
| `list_recent_files` | List recent files | `files.list` (`orderBy=modifiedTime desc`) | `drive.readonly` |
| `get_file_metadata` | Retrieve metadata | `files.get` (`fields=...`) | `drive.readonly` |
| `download_file_content` | Download content | `files.get_media` / `files.export` | `drive.readonly` |
| `create_file` | Create files | `files.create` (media upload) | `drive.file` |
| `copy_file` | Copy a file | `files.copy` | `drive.file` |
| `get_file_permissions` | Inspect permissions | `permissions.list` | `drive.readonly` |
| `update_file` | _(none — local-only extension)_ | `files.update` (`name` / `addParents`+`removeParents`) | `drive.file` |

Exact hosted tool names/schemas are discoverable by calling `tools/list` on the hosted endpoint (requires Workspace Developer Preview enrollment); the local server models the same capability coverage with descriptive names. `update_file` has no hosted counterpart — it is a local-only metadata-update extension. This table is reproduced in `drive-mcp-server/README.md`.

## Risks / Trade-offs

- Expanding scope to `drive.file` increases privilege → use per-file `drive.file` (not full `drive`); read tools are unaffected; the write tools (`create_file`, `copy_file`, `update_file`) fail closed with a clear re-auth message when the scope is absent.
- The saved token file is shared with the Node server and CLI; re-authing for write changes its granted scopes → document the re-auth step; the token's refresh/persist path is unchanged, so read tooling keeps working.
- Refactoring `cmd_list`/`cmd_info` could change CLI output → preserve their exact printed format and verify `list`/`info` after the refactor.
- `download_file_content` could overwrite an existing path → default to the file's name and document the overwrite behavior; keep the simple semantics the CLI already uses.
- Google-native files have no raw media → `download_file_content` reuses the export path in `read_file`, writing exported bytes.

## Migration Plan

Additive. Add helpers to `gdrive_cli.py`, register seven tools in `server.py` (six hosted-parity + the local-only `update_file`), and update `drive-mcp-server/README.md`. No change to `.vscode/mcp.json` (tools auto-discovered). To use `create_file`, `copy_file`, or `update_file`, the operator re-authorizes the saved token to include `drive.file`. Rollback: remove the new tool registrations (and helpers); read tools and the CLI are unaffected.
