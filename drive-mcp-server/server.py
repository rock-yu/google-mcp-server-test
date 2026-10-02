#!/usr/bin/env python3
"""Local Google Drive MCP server (stdio transport).

Exposes a toolset modeled on Google's hosted ``drivemcp.googleapis.com`` server,
reaching parity with its eight tools plus one local-only extension:

- ``search_files``            - full-text search over the user's Drive
- ``read_file_content``       - read/export a file's content as text
- ``list_recent_files``       - list recently modified files
- ``get_file_metadata``       - return a file's descriptive metadata
- ``download_file_content``   - save a file's bytes to a local path
- ``create_file``             - create a file from text content (write)
- ``copy_file``               - copy an existing file (write)
- ``get_file_permissions``    - list a file's sharing permissions
- ``update_file``             - rename/move a file's metadata (write, local-only)

Credential handling and Drive REST logic are reused from the sibling
``../gdrive-cli/gdrive_cli.py`` module. Configure with the same environment
variables as the CLI:

- ``GDRIVE_OAUTH_PATH``       - OAuth client ID/secret JSON
- ``GDRIVE_CREDENTIALS_PATH`` - saved user tokens (access/refresh)

Read tools need only ``drive.readonly``; the write tools require the
``drive.file`` scope and return an actionable error when it is absent.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import NotRequired, TypedDict

# The Drive helpers live in a hyphenated directory, so add it to sys.path
# before importing the module by its underscore name.
_GDRIVE_CLI_DIR = Path(__file__).resolve().parent.parent / "gdrive-cli"
if str(_GDRIVE_CLI_DIR) not in sys.path:
    sys.path.insert(0, str(_GDRIVE_CLI_DIR))

import gdrive_cli  # noqa: E402
from googleapiclient.errors import HttpError  # noqa: E402
from mcp.server.mcpserver import MCPServer  # noqa: E402
from mcp.server.mcpserver.exceptions import ToolError  # noqa: E402
from mcp.types import ToolAnnotations  # noqa: E402

_service = None
_creds = None

_WRITE_REAUTH_MESSAGE = (
    "This operation needs write access to your Google Drive, but the saved "
    "credentials only grant read access. Re-authorize the Drive MCP token with "
    "the 'drive.file' scope (see drive-mcp-server/README.md) and try again."
)


def configure_service(service, credentials) -> None:
    """Install an already-created service and credentials before serving tools."""
    global _service, _creds
    _service = service
    _creds = credentials


class HostedFile(TypedDict):
    id: str
    title: str
    parentId: NotRequired[str]
    mimeType: NotRequired[str]
    fileSize: NotRequired[str]
    description: NotRequired[str]
    fileExtension: NotRequired[str]
    contentSnippet: NotRequired[str]
    viewUrl: NotRequired[str]
    sharedWithMeTime: NotRequired[str]
    createdTime: NotRequired[str]
    modifiedTime: NotRequired[str]
    viewedByMeTime: NotRequired[str]
    owner: NotRequired[str]
    canAddChildren: NotRequired[bool]


class HostedFilePage(TypedDict):
    files: list[HostedFile]
    nextPageToken: NotRequired[str]


def _get_service():
    """Build (once) and return an authenticated Drive service.

    Delegates to the shared credential loader, which refreshes and persists
    expired tokens and exits with an actionable message if credentials are
    missing. Caches both the service and its credentials for scope checks.
    """
    global _service, _creds
    if _service is None:
        _service, _creds = gdrive_cli.drive_service_with_creds()
    return _service


def _require_write_scope():
    """Return the service, raising a ToolError if the token lacks write scope."""
    service = _get_service()
    if not gdrive_cli.has_write_scope(_creds):
        raise ToolError(_WRITE_REAUTH_MESSAGE)
    return service


def _tool_error(action: str, error: HttpError) -> ToolError:
    """Map a Drive HttpError to an actionable ToolError.

    A 403 for insufficient permissions is reported as a re-authorization prompt;
    everything else passes through the HTTP status and message.
    """
    status = getattr(getattr(error, "resp", None), "status", None)
    detail = str(error)
    if status == 403 and "insufficientPermissions" in detail:
        return ToolError(_WRITE_REAUTH_MESSAGE)
    return ToolError(
        f"{action} failed" + (f" (HTTP {status})" if status else "") + f": {error}"
    )


def search_files(
    query: str,
    pageSize: int = 10,
    pageToken: str | None = None,
    excludeContentSnippets: bool = False,
) -> HostedFilePage:
    """Search Drive files with the hosted query dialect.

    Args:
        query: Structured hosted search expression.
        pageSize: Maximum files to return in this page.
        pageToken: Optional token from a prior response.
        excludeContentSnippets: Omit content snippets when true.
    """
    service = _get_service()
    try:
        return gdrive_cli.search_files(
            service,
            query,
            page_size=pageSize,
            page_token=pageToken,
            exclude_content_snippets=excludeContentSnippets,
        )
    except ValueError as error:
        raise ToolError(str(error))
    except HttpError as error:
        raise _tool_error("Searching files", error)


def read_file_content(file_id: str) -> str:
    """Read/export the content of a Drive file.

    Args:
        file_id: The Drive file id to read.
    """
    service = _get_service()
    try:
        info = gdrive_cli.read_file(service, file_id)
    except HttpError as error:
        status = getattr(getattr(error, "resp", None), "status", None)
        raise ToolError(
            f"Could not read file '{file_id}'"
            + (f" (HTTP {status})" if status else "")
            + f": {error}"
        )

    if info["is_binary"]:
        return (
            f"'{info['name']}' ({info['mimeType']}) is binary content and cannot "
            "be returned as text."
        )
    return info["text"] or ""


def list_recent_files(
    orderBy: str = "recency",
    pageSize: int = 10,
    pageToken: str | None = None,
    excludeContentSnippets: bool = False,
) -> HostedFilePage:
    """List recently modified Drive files.

    Args:
        orderBy: recency, lastModified, or lastModifiedByMe.
        pageSize: Maximum files to return in this page.
        pageToken: Optional token from a prior response.
        excludeContentSnippets: Omit content snippets when true.
    """
    service = _get_service()
    try:
        return gdrive_cli.list_recent_files(
            service,
            page_size=pageSize,
            page_token=pageToken,
            exclude_content_snippets=excludeContentSnippets,
            order_by=orderBy,
        )
    except ValueError as error:
        raise ToolError(str(error))
    except HttpError as error:
        raise _tool_error("Listing recent files", error)


def get_file_metadata(
    fileId: str, excludeContentSnippets: bool = False
) -> HostedFile:
    """Return metadata for a Drive file.

    Args:
        fileId: The Drive file id to describe.
        excludeContentSnippets: Omit the content snippet when true.
    """
    service = _get_service()
    try:
        return gdrive_cli.get_file_metadata(
            service, fileId, exclude_content_snippets=excludeContentSnippets
        )
    except HttpError as error:
        raise _tool_error(f"Getting metadata for '{fileId}'", error)


def download_file_content(file_id: str, output_path: str | None = None) -> str:
    """Save a Drive file's bytes to a local path.

    Args:
        file_id: The Drive file id to download.
        output_path: Where to write the bytes (defaults to the file's name).
    """
    service = _get_service()
    try:
        path, count = gdrive_cli.download_file(
            service, file_id, Path(output_path) if output_path else None
        )
    except HttpError as error:
        raise _tool_error(f"Downloading '{file_id}'", error)
    return f"Wrote {count} bytes to {path}"


def create_file(
    name: str, content: str, mime_type: str = "text/plain", parent_id: str | None = None
) -> str:
    """Create a Drive file from text content.

    Args:
        name: The new file's name.
        content: The text content to store.
        mime_type: The file's MIME type (default ``text/plain``).
        parent_id: Optional parent folder id.
    """
    service = _require_write_scope()
    try:
        created = gdrive_cli.create_file(service, name, content, mime_type, parent_id)
    except HttpError as error:
        raise _tool_error(f"Creating '{name}'", error)
    return f"Created '{created['name']}' (id: {created['id']})"


def copy_file(file_id: str, name: str | None = None, parent_id: str | None = None) -> str:
    """Copy an existing Drive file.

    Args:
        file_id: The source file id to copy.
        name: Optional name for the copy.
        parent_id: Optional parent folder id for the copy.
    """
    service = _require_write_scope()
    try:
        copied = gdrive_cli.copy_file(service, file_id, name, parent_id)
    except HttpError as error:
        raise _tool_error(f"Copying '{file_id}'", error)
    return f"Copied to '{copied['name']}' (id: {copied['id']})"


def get_file_permissions(file_id: str) -> str:
    """List a Drive file's sharing permissions.

    Args:
        file_id: The Drive file id to inspect.
    """
    service = _get_service()
    try:
        perms = gdrive_cli.list_permissions(service, file_id)
    except HttpError as error:
        raise _tool_error(f"Getting permissions for '{file_id}'", error)
    if not perms:
        return "No permissions found."
    lines = []
    for p in perms:
        grantee = p.get("displayName") or p.get("emailAddress") or p.get("type", "")
        lines.append(f"{p.get('role', '')} {p.get('type', '')} — {grantee} ({p.get('id', '')})")
    return "\n".join(lines)


def update_file(file_id: str, title: str | None = None, parent_id: str | None = None) -> str:
    """Update a Drive file's metadata (rename and/or move).

    Args:
        file_id: The Drive file id to update.
        title: Optional new name (must be non-empty when provided).
        parent_id: Optional new parent folder id (replaces the current parent).
    """
    service = _require_write_scope()
    try:
        updated = gdrive_cli.update_file(service, file_id, title, parent_id)
    except ValueError as error:
        raise ToolError(str(error))
    except HttpError as error:
        raise _tool_error(f"Updating '{file_id}'", error)
    parents = ", ".join(updated.get("parents", [])) or "—"
    return f"Updated '{updated['name']}' (id: {updated['id']}; parents: {parents})"


_READ_ANNOTATIONS = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=True,
)
_DOWNLOAD_ANNOTATIONS = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=True,
    idempotent_hint=False,
    open_world_hint=True,
)
_ADDITIVE_WRITE_ANNOTATIONS = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=False,
    idempotent_hint=False,
    open_world_hint=True,
)
_DESTRUCTIVE_WRITE_ANNOTATIONS = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=True,
    idempotent_hint=False,
    open_world_hint=True,
)

_TOOL_DEFINITIONS = (
    (
        search_files,
        "search_files",
        "Search Google Drive using the hosted structured query dialect. Returns "
        "hosted-compatible File objects and an optional nextPageToken.",
        _READ_ANNOTATIONS,
        False,
    ),
    (
        read_file_content,
        "read_file_content",
        "Read a Google Drive file by id. Google Docs export to Markdown, Sheets "
        "to CSV, and Slides to plain text; other text files return their native "
        "text. Binary files cannot be returned as text.",
        _READ_ANNOTATIONS,
        False,
    ),
    (
        list_recent_files,
        "list_recent_files",
        "List recent Google Drive files using hosted sort and pagination options. "
        "Returns hosted-compatible File objects and an optional nextPageToken.",
        _READ_ANNOTATIONS,
        False,
    ),
    (
        get_file_metadata,
        "get_file_metadata",
        "Return hosted-compatible structured metadata for a Google Drive file.",
        _READ_ANNOTATIONS,
        False,
    ),
    (
        download_file_content,
        "download_file_content",
        "Download a Drive file's bytes to a local path (Google-native files are "
        "exported first). The path defaults to the file's name. Returns the path "
        "and the number of bytes written.",
        _DOWNLOAD_ANNOTATIONS,
        False,
    ),
    (
        create_file,
        "create_file",
        "Create a new Google Drive file from text content, optionally within a "
        "parent folder. Requires write access (the 'drive.file' scope). Returns "
        "the new file's id and name.",
        _ADDITIVE_WRITE_ANNOTATIONS,
        True,
    ),
    (
        copy_file,
        "copy_file",
        "Copy an existing Google Drive file, optionally with a new name and/or "
        "parent folder. Requires write access (the 'drive.file' scope). Returns "
        "the new file's id and name.",
        _ADDITIVE_WRITE_ANNOTATIONS,
        True,
    ),
    (
        get_file_permissions,
        "get_file_permissions",
        "List the sharing permissions of a Drive file by id. Returns one "
        "permission per line as 'role type — grantee (id)'.",
        _READ_ANNOTATIONS,
        False,
    ),
    (
        update_file,
        "update_file",
        "Update an existing Drive file's metadata only — rename it via a "
        "non-empty 'title' and/or move it to a new parent folder via 'parent_id' "
        "(replacing its current parent). Content is never modified. Local-only "
        "extension beyond the hosted toolset. Requires write access (the "
        "'drive.file' scope).",
        _DESTRUCTIVE_WRITE_ANNOTATIONS,
        True,
    ),
)


def drive_read_only_from_env() -> bool:
    value = os.environ.get("DRIVE_MCP_READ_ONLY", "").strip().lower()
    if value in {"", "0", "false", "no", "off"}:
        return False
    if value in {"1", "true", "yes", "on"}:
        return True
    raise SystemExit(
        "DRIVE_MCP_READ_ONLY must be one of: 1, true, yes, on, 0, false, no, off"
    )


def create_mcp_server(*, drive_read_only: bool = False) -> MCPServer:
    server = MCPServer("drive-mcp-server")
    for function, name, description, annotations, mutates_drive in _TOOL_DEFINITIONS:
        if drive_read_only and mutates_drive:
            continue
        server.tool(
            name=name,
            description=description,
            annotations=annotations,
        )(function)
    return server


mcp = create_mcp_server(drive_read_only=drive_read_only_from_env())


def main(authenticate: bool = True) -> None:
    # Authenticate up front so missing credentials fail fast with a clear
    # message instead of on the first tool call.
    if authenticate:
        _get_service()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
