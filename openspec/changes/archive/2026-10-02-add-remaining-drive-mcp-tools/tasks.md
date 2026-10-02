# Tasks

## 1. Shared Drive helpers (`gdrive-cli/gdrive_cli.py`)

- [x] 1.1 Add `list_recent_files(service, page_size=10)` returning file dicts (id, name, mimeType, modifiedTime, size) ordered by most recently modified, and refactor `cmd_list` to delegate to it; verify `python gdrive_cli.py list` prints the same tab-separated columns as before against the live account.
- [x] 1.2 Add `get_file_metadata(service, file_id)` returning a metadata dict (id, name, mimeType, size, owners, modifiedTime, webViewLink, parents), and refactor `cmd_info` to delegate to it; verify `python gdrive_cli.py info <id>` prints the same fields for a real id.
- [x] 1.3 Add `download_file(service, file_id, output_path=None)` that reuses `read_file`, writes `raw` bytes (binary) or UTF-8-encoded `text` (text/exported) to the path (defaulting to the file's name), and returns `(path, byte_count)`; verify it writes a known binary file (e.g. a PDF) and returns the correct byte count.
- [x] 1.4 Add `create_file(service, name, content, mime_type, parent_id=None)` using `MediaIoBaseUpload` over `files().create`, returning `{id, name}`; verify (with a `drive.file`-scoped token) it creates a text file that then appears via `search`/`list`, and delete the test file afterward. If no write token is available, verify the call raises the Drive 403 insufficient-permissions error that task 3.1 maps to a clear message.
- [x] 1.5 Add `copy_file(service, file_id, name=None, parent_id=None)` over `files().copy`, returning `{id, name}`; verify (with a `drive.file`-scoped token) it copies a real file — optionally with a new name/parent — and delete the copy afterward. If no write token is available, verify the call raises the Drive 403 insufficient-permissions error.
- [x] 1.6 Add `list_permissions(service, file_id)` over `permissions.list` returning entries (id, role, type, and grantee when present); verify it returns the permission entries for a real file id.
- [x] 1.7 Add `update_file(service, file_id, title=None, parent_id=None)` (local-only extension) that updates metadata only: when `title` is given it must be non-empty and sets the name; when `parent_id` is given it reads the file's current parents via `files().get(fields="parents")` and calls `files().update(addParents=parent_id, removeParents=<current parents>)` to move it; require at least one of `title`/`parent_id` (else raise a clear error); return `{id, name, parents}`. Verify (with a `drive.file`-scoped token) a rename and a move on a throwaway file, then restore/delete it; if no write token is available, verify the call raises the Drive 403 insufficient-permissions error.

## 2. MCP tools (`drive-mcp-server/server.py`)

- [x] 2.1 Register the `list_recent_files` tool (optional `max_results`) over the helper; verify a `tools/list` call includes it and a `tools/call` returns recent files each with name, MIME type, id, and modified time.
- [x] 2.2 Register the `get_file_metadata` tool; verify a valid id returns name/MIME/size/owners/modified time/web link, and an unknown or inaccessible id returns an error result (`is_error`).
- [x] 2.3 Register the `download_file_content` tool (`file_id`, optional `output_path`) returning the written path and byte count; verify a binary file and a Google-native file each write bytes and report the path/count, and an unknown id returns an error result.
- [x] 2.4 Register the `create_file` tool (`name`, `content`, `mime_type`, optional `parent_id`) returning the new id and name; verify a successful create with a write-scoped token (then delete the file), and that a failed create (e.g. invalid parent) returns an error result.
- [x] 2.5 Register the `copy_file` tool (`file_id`, optional `name`, optional `parent_id`) returning the new id and name; verify a successful copy with a write-scoped token (then delete the copy), and that a failed copy (e.g. unknown source id) returns an error result.
- [x] 2.6 Register the `get_file_permissions` tool (`file_id`) returning permission entries; verify a valid id returns entries (id, role, type) and an unknown or inaccessible id returns an error result.
- [x] 2.7 Register the `update_file` tool (`file_id`, optional `title`, optional `parent_id`; local-only extension) returning the updated id and name; verify a rename and a move with a write-scoped token (then restore/delete the test file), and that calling with neither field (or an empty title) returns an error result.
- [x] 2.8 Update the `tools/list` advertisement so all nine tools (`search_files`, `read_file_content`, `list_recent_files`, `get_file_metadata`, `download_file_content`, `create_file`, `copy_file`, `get_file_permissions`, `update_file`) appear with input schemas; verify a `tools/list` call lists exactly those nine tools.

## 3. Write-scope authentication

- [x] 3.1 Add a write-scope pre-check (loaded credentials include `drive.file` or full `drive`) plus an `HttpError` 403 `insufficientPermissions` fallback so `create_file`, `copy_file`, and `update_file` return an actionable "re-authorize with write access" error instead of failing abnormally; verify that calling `create_file` with the current `drive.readonly`-only token returns that actionable error result (no crash).

## 4. Documentation

- [x] 4.1 Update `drive-mcp-server/README.md` to document the seven new tools and their arguments (flagging `update_file` as a local-only extension beyond hosted parity), the `drive.file` re-authorization step required for `create_file`, `copy_file`, and `update_file`, and the local→hosted action mapping table from design.md; verify the documented `tools/list` smoke test lists all nine tools exactly as written.

## 5. End-to-end verification

- [x] 5.1 Launch the server over stdio against the real Drive account, call `tools/list`, then call `list_recent_files`, `get_file_metadata`, `download_file_content`, and `get_file_permissions` for real ids, plus `create_file`, `copy_file`, and `update_file` when a write-scoped token is available (otherwise confirm their insufficient-scope error), confirming each response matches its spec scenarios; clean up any created or copied test file and restore any renamed/moved file.
