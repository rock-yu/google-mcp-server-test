# Tasks

## 1. Scaffolding and dependencies

- [x] 1.1 Create the `drive-mcp-server/` directory and a `requirements.txt` pinning the MCP Python SDK (`mcp`) plus the existing `google-api-python-client` / `google-auth` / `google-auth-httplib2` / `google-auth-oauthlib` stack; verify `pip install -r drive-mcp-server/requirements.txt` completes without errors in a clean virtualenv.

## 2. Shared Drive helpers

- [x] 2.1 Refactor `gdrive-cli/gdrive_cli.py` so credential loading/refresh (`load_credentials`, `drive_service`, `_persist_credentials`) is importable without triggering the CLI, keeping public signatures backward-compatible; verify `python gdrive-cli/gdrive_cli.py list` still runs unchanged.
- [x] 2.2 Expose reusable functions for search (query + max results → list of `{name, mimeType, id}`) and read (file id → text plus a binary/unsupported indicator), reusing the existing export-MIME mapping; verify a small script importing these functions returns the expected fields for a known file id and query.

## 3. MCP server implementation

- [x] 3.1 Implement `drive-mcp-server/server.py` as a stdio MCP server using the `mcp` SDK that completes the initialize handshake; verify launching it and sending a `tools/list` request returns a successful response (Spec: Local stdio MCP transport).
- [x] 3.2 Register and advertise `search_files` and `read_file_content` with names, descriptions, and input schemas; verify the `tools/list` response includes both tools with their input schemas.
- [x] 3.3 Implement the `search_files` tool over the shared search helper with an optional maximum-results argument and a clear "no files matched" result; verify a matching query returns name/MIME/id entries, a non-matching query returns the no-match result, and the maximum is respected (Spec: Full-text file search tool).
- [x] 3.4 Implement the `read_file_content` tool over the shared read helper — export Google Docs→Markdown, Sheets→CSV, Slides→text, return native text otherwise, return an informative message for non-text binary files, and return an error result for unknown/inaccessible ids; verify each case with representative file ids (Spec: Read file content tool).
- [x] 3.5 Wire read-only (`drive.readonly`) authentication through the shared credential loader so expired tokens are refreshed and persisted, and startup fails with an actionable message when credentials are missing; verify with (a) valid credentials, (b) a simulated expired token, and (c) credentials absent (Spec: Read-only Google authentication).

## 4. Client integration and docs

- [x] 4.1 Add a `drive-mcp` stdio server entry to `.vscode/mcp.json` that launches the Python server with the existing `GDRIVE_OAUTH_PATH` / `GDRIVE_CREDENTIALS_PATH` env vars; verify the file is valid JSON and VS Code "MCP: List Servers" shows the new server green.
- [x] 4.2 Add `drive-mcp-server/README.md` documenting setup, required env vars, and the two tools; verify the documented launch command runs the server and a `tools/list` request succeeds exactly as written.

## 5. End-to-end verification

- [x] 5.1 Launch the server over stdio against a real Drive account, call `tools/list`, then call `search_files` and `read_file_content` for a real file id, confirming the responses match the spec scenarios.
