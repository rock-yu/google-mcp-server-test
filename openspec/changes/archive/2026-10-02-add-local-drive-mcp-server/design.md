# Design

## Context

See proposal.md - Why. The repo already contains `gdrive-cli/gdrive_cli.py`, which loads OAuth client credentials from `gcp-oauth.keys.json`, loads saved tokens from `.gdrive-server-credentials.json`, refreshes expired tokens (writing them back), and calls the Drive v3 REST API for list/search/read/export using `google-api-python-client` + `google-auth`. VS Code launches MCP servers declared in `.vscode/mcp.json` as stdio subprocesses (see the existing `gdrive` entry). The hosted `drivemcp.googleapis.com/mcp/v1` server is the reference model for tool naming and behavior only.

## Goals / Non-Goals

**Goals:**
- A small, readable Python MCP server exposing `search_files` and `read_file_content` over stdio.
- Reuse the existing credential and Drive REST logic rather than duplicating it.
- Launchable by Copilot/VS Code via a `.vscode/mcp.json` entry.

**Non-Goals:**
- Proxying to or calling the hosted `drivemcp.googleapis.com` endpoint.
- Write/create tools or any non-read-only scope.
- Packaging, distribution, multi-user hosting, or regional endpoints.

## Decisions

**1. Use the official MCP Python SDK over stdio.**
Register tools and run a stdio server with the `mcp` package. Rationale: it provides the stdio transport, initialize handshake, and `tools/list`/`tools/call` handling out of the box, matching the chosen Python runtime. Alternative considered: hand-rolled JSON-RPC over stdin/stdout — rejected as it reinvents the protocol and is error-prone.

**2. Reuse `gdrive-cli` logic via shared helpers.**
Place the server in a new `drive-mcp-server/` directory and share the credential-loading/refresh, search, and read/export functions with the existing CLI — refactoring `gdrive_cli.py`'s reusable pieces into an importable module if needed. Rationale: a single source of truth for OAuth refresh and export-MIME mapping. Alternative: copy-paste the logic — rejected due to drift risk. Trade-off: a light, backward-compatible refactor of `gdrive_cli.py`.

**3. Model tool contracts on the hosted server's names.**
Expose `search_files` and `read_file_content` to mirror the hosted `drivemcp.googleapis.com` toolset. Rationale: familiarity and easier future alignment if the project later swaps to the hosted endpoint.

**4. Configure via existing environment variables.**
Reuse `GDRIVE_OAUTH_PATH` and `GDRIVE_CREDENTIALS_PATH` (and the `GDRIVE_INSECURE_SSL` / `NODE_TLS_REJECT_UNAUTHORIZED` dev escape hatch) exactly as the CLI and `.vscode/mcp.json` already do. Rationale: consistency and no new secret-handling paths.

**5. Read-only Drive scope.**
The sample toolset only reads, so request `drive.readonly`. Rationale: least privilege.

## Risks / Trade-offs

- Refactoring `gdrive_cli.py` could break the existing CLI → keep public function signatures backward-compatible so the CLI keeps working.
- MCP tool results are text; large files could bloat the client context → bound `search_files` with a result limit and document that `read_file_content` returns text of the target file.
- Binary files cannot be returned as text → return an informative message (per spec) rather than failing the session.
- Token refresh writes back to the shared credentials file → reuse the CLI's existing write path so the Node server, CLI, and this server stay in sync.
- Corporate TLS-inspecting proxy → honor the existing `GDRIVE_INSECURE_SSL` / `NODE_TLS_REJECT_UNAUTHORIZED` dev-only flag as the CLI does.

## Migration Plan

Additive only. Add the `drive-mcp-server/` directory and a new stdio entry in `.vscode/mcp.json` alongside the existing `gdrive` server. Rollback is removing the new server entry; the existing Node server and Python CLI are unaffected.

## Open Questions

- Whether to later add `list_files` / `create_file` tools or switch to proxying the hosted endpoint — deferred; neither affects this sample's specs or tasks.
