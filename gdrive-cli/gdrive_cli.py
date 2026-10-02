#!/usr/bin/env python3
"""
Google Drive CLI — isolated Python process using the same OAuth files as the MCP server.

Reads:
  GDRIVE_OAUTH_PATH        (default: <repo>/gcp-oauth.keys.json)
  GDRIVE_CREDENTIALS_PATH  (default: <repo>/node_modules/.gdrive-server-credentials.json)

Run the Node MCP auth flow first (SETUP-GUIDE Step 3) if credentials are missing.

Usage:
  python gdrive_cli.py list
  python gdrive_cli.py search "blood pressure"
  python gdrive_cli.py read <file_id>
  python gdrive_cli.py info <file_id>
  python gdrive_cli.py interactive
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import textwrap
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

DRIVE_READONLY = "https://www.googleapis.com/auth/drive.readonly"
DRIVE_FILE = "https://www.googleapis.com/auth/drive.file"
DRIVE_FULL = "https://www.googleapis.com/auth/drive"
WRITE_SCOPES = (DRIVE_FILE, DRIVE_FULL)
TOKEN_URI = "https://oauth2.googleapis.com/token"


def _insecure_ssl_enabled() -> bool:
    """Match MCP config when behind a corporate TLS-inspecting proxy (dev only)."""
    flag = os.environ.get("GDRIVE_INSECURE_SSL", os.environ.get("NODE_TLS_REJECT_UNAUTHORIZED", ""))
    return flag in ("0", "1", "true", "yes")


def _auth_request() -> Request:
    if not _insecure_ssl_enabled():
        return Request()
    import requests

    session = requests.Session()
    session.verify = False
    return Request(session=session)


EXPORT_MIME = {
    "application/vnd.google-apps.document": "text/markdown",
    "application/vnd.google-apps.spreadsheet": "text/csv",
    "application/vnd.google-apps.presentation": "text/plain",
    "application/vnd.google-apps.drawing": "image/png",
}

HOSTED_FILE_FIELDS = (
    "id,name,parents,mimeType,size,description,fileExtension,webViewLink,"
    "sharedWithMeTime,createdTime,modifiedTime,viewedByMeTime,"
    "owners(displayName,emailAddress),capabilities/canAddChildren"
)

RECENT_ORDER_BY = {
    "recency": "recency desc",
    "lastModified": "modifiedTime desc",
    "lastModifiedByMe": "modifiedByMeTime desc",
}

_QUERY_OPERATORS = {
    "title": {"contains", "=", "!="},
    "fullText": {"contains"},
    "mimeType": {"contains", "=", "!="},
    "modifiedTime": {"<=", "<", "=", "!=", ">", ">="},
    "viewedByMeTime": {"<=", "<", "=", "!=", ">", ">="},
    "createdTime": {"<=", "<", "=", "!=", ">", ">="},
    "parentId": {"=", "!="},
    "owner": {"=", "!="},
    "sharedWithMe": {"=", "!="},
}
_TIME_QUERY_TERMS = {"modifiedTime", "viewedByMeTime", "createdTime"}


def _present(value) -> bool:
    return value is not None and value != "" and value != []


def to_hosted_file(
    drive_file: dict, exclude_content_snippets: bool = False
) -> dict:
    """Map a Drive v3 file resource to the hosted Drive MCP File shape."""
    hosted: dict = {}
    direct_fields = {
        "id": "id",
        "name": "title",
        "mimeType": "mimeType",
        "size": "fileSize",
        "description": "description",
        "fileExtension": "fileExtension",
        "webViewLink": "viewUrl",
        "sharedWithMeTime": "sharedWithMeTime",
        "createdTime": "createdTime",
        "modifiedTime": "modifiedTime",
        "viewedByMeTime": "viewedByMeTime",
    }
    for source, target in direct_fields.items():
        value = drive_file.get(source)
        if _present(value):
            hosted[target] = value

    parents = drive_file.get("parents") or []
    if parents:
        hosted["parentId"] = parents[0]

    owners = drive_file.get("owners") or []
    if owners:
        owner = owners[0].get("emailAddress")
        if _present(owner):
            hosted["owner"] = owner

    capabilities = drive_file.get("capabilities") or {}
    if "canAddChildren" in capabilities:
        hosted["canAddChildren"] = capabilities["canAddChildren"]

    snippet = drive_file.get("contentSnippet")
    if not exclude_content_snippets and _present(snippet):
        hosted["contentSnippet"] = snippet

    return hosted


class _QueryToken(NamedTuple):
    kind: str
    raw: str
    value: str
    position: int


def _looks_like_structured_query(query: str) -> bool:
    """Return whether hosted query syntax occurs outside quoted strings."""
    index = 0
    in_string = False
    while index < len(query):
        char = query[index]
        if in_string:
            if char == "\\" and index + 1 < len(query):
                index += 2
                continue
            if char == "'":
                in_string = False
            index += 1
            continue
        if char == "'":
            in_string = True
            index += 1
            continue
        if char in "=<>!":
            return True
        if char.isalpha():
            end = index + 1
            while end < len(query) and query[end].isalnum():
                end += 1
            identifier = query[index:end]
            if identifier in _QUERY_OPERATORS or identifier in {
                "and",
                "or",
                "not",
                "contains",
            }:
                return True
            index = end
            continue
        index += 1
    return False


def _tokenize_query(query: str) -> list[_QueryToken]:
    tokens: list[_QueryToken] = []
    index = 0
    while index < len(query):
        char = query[index]
        if char.isspace():
            index += 1
            continue
        if char in "()":
            tokens.append(_QueryToken(char, char, char, index))
            index += 1
            continue
        if char == "'":
            start = index
            index += 1
            value: list[str] = []
            while index < len(query):
                if query[index] == "\\":
                    if index + 1 >= len(query) or query[index + 1] not in ("'", "\\"):
                        raise ValueError(
                            f"Invalid escape in search query at position {index}"
                        )
                    value.append(query[index + 1])
                    index += 2
                    continue
                if query[index] == "'":
                    index += 1
                    raw = query[start:index]
                    tokens.append(
                        _QueryToken("STRING", raw, "".join(value), start)
                    )
                    break
                value.append(query[index])
                index += 1
            else:
                raise ValueError(
                    f"Unterminated string in search query at position {start}"
                )
            continue
        if query.startswith(("!=", "<=", ">="), index):
            raw = query[index : index + 2]
            tokens.append(_QueryToken("OP", raw, raw, index))
            index += 2
            continue
        if char in "=<>":
            tokens.append(_QueryToken("OP", char, char, index))
            index += 1
            continue
        if char.isalpha():
            start = index
            index += 1
            while index < len(query) and query[index].isalnum():
                index += 1
            raw = query[start:index]
            kind = "BOOL" if raw in ("true", "false") else "IDENT"
            tokens.append(_QueryToken(kind, raw, raw, start))
            continue
        raise ValueError(
            f"Unexpected character {char!r} in search query at position {index}"
        )
    tokens.append(_QueryToken("EOF", "", "", len(query)))
    return tokens


def _validate_rfc3339(value: str, position: int) -> None:
    if not (value.endswith("Z") or (
        len(value) >= 6 and value[-6] in ("+", "-") and value[-3] == ":"
    )):
        raise ValueError(
            f"Time value at position {position} must be an RFC 3339 timestamp"
        )
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(
            f"Invalid RFC 3339 timestamp at position {position}: {value!r}"
        ) from error


class _QueryParser:
    def __init__(self, query: str):
        self.tokens = _tokenize_query(query)
        self.index = 0

    @property
    def current(self) -> _QueryToken:
        return self.tokens[self.index]

    def _accept(self, kind: str, value: str | None = None) -> _QueryToken | None:
        token = self.current
        if token.kind == kind and (value is None or token.value == value):
            self.index += 1
            return token
        return None

    def _expect(self, kind: str, description: str) -> _QueryToken:
        token = self._accept(kind)
        if token is None:
            raise ValueError(
                f"Expected {description} in search query at position "
                f"{self.current.position}"
            )
        return token

    def parse(self) -> str:
        translated = self._parse_or()
        if self.current.kind != "EOF":
            raise ValueError(
                f"Unexpected token {self.current.raw!r} in search query at "
                f"position {self.current.position}"
            )
        return translated

    def _parse_or(self) -> str:
        expression = self._parse_and()
        while self._accept("IDENT", "or"):
            expression = f"({expression} or {self._parse_and()})"
        return expression

    def _parse_and(self) -> str:
        expression = self._parse_not()
        while self._accept("IDENT", "and"):
            expression = f"({expression} and {self._parse_not()})"
        return expression

    def _parse_not(self) -> str:
        if self._accept("IDENT", "not"):
            return f"not ({self._parse_not()})"
        return self._parse_primary()

    def _parse_primary(self) -> str:
        if self._accept("("):
            expression = self._parse_or()
            if not self._accept(")"):
                raise ValueError(
                    f"Expected ')' in search query at position {self.current.position}"
                )
            return f"({expression})"
        return self._parse_clause()

    def _parse_clause(self) -> str:
        term_token = self._expect("IDENT", "a query term")
        term = term_token.value
        if term not in _QUERY_OPERATORS:
            raise ValueError(
                f"Unsupported search query term {term!r} at position "
                f"{term_token.position}"
            )

        if self._accept("IDENT", "contains"):
            operator = "contains"
        else:
            operator = self._expect("OP", "an operator").value
        if operator not in _QUERY_OPERATORS[term]:
            raise ValueError(
                f"Operator {operator!r} is not supported for search query term "
                f"{term!r}"
            )

        if term == "sharedWithMe":
            value = self._expect("BOOL", "true or false")
            positive = value.value == "true"
            if operator == "!=":
                positive = not positive
            return "sharedWithMe" if positive else "not sharedWithMe"

        value = self._expect("STRING", "a single-quoted string")
        if term in _TIME_QUERY_TERMS:
            _validate_rfc3339(value.value, value.position)
        if term == "parentId":
            clause = f"{value.raw} in parents"
            return clause if operator == "=" else f"not ({clause})"
        if term == "owner":
            clause = f"{value.raw} in owners"
            return clause if operator == "=" else f"not ({clause})"

        drive_term = "name" if term == "title" else term
        return f"{drive_term} {operator} {value.raw}"


def translate_query(hosted_query: str) -> str:
    """Translate the hosted search query dialect to a Drive v3 query."""
    if not hosted_query or not hosted_query.strip():
        raise ValueError("search query must not be empty")
    if _looks_like_structured_query(hosted_query):
        translated = _QueryParser(hosted_query).parse()
    else:
        escaped = hosted_query.replace("\\", "\\\\").replace("'", "\\'")
        translated = f"fullText contains '{escaped}'"
    return f"({translated}) and trashed = false"


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def oauth_keys_path() -> Path:
    return Path(os.environ.get("GDRIVE_OAUTH_PATH", project_root() / "gcp-oauth.keys.json"))


def saved_credentials_path() -> Path:
    return Path(
        os.environ.get(
            "GDRIVE_CREDENTIALS_PATH",
            project_root() / "node_modules" / ".gdrive-server-credentials.json",
        )
    )


def load_client_id_secret(path: Path) -> tuple[str, str]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    for section in ("installed", "web"):
        if section in data:
            block = data[section]
            return block["client_id"], block["client_secret"]
    raise ValueError(f"Expected 'installed' or 'web' in OAuth key file: {path}")


def load_credentials() -> Credentials:
    keys_path = oauth_keys_path()
    creds_path = saved_credentials_path()

    if not keys_path.is_file():
        sys.exit(f"OAuth client keys not found: {keys_path}")
    if not creds_path.is_file():
        sys.exit(
            f"Saved credentials not found: {creds_path}\n"
            "Run the MCP auth flow first (see SETUP-GUIDE.md Step 3)."
        )

    client_id, client_secret = load_client_id_secret(keys_path)
    with creds_path.open(encoding="utf-8") as f:
        token_data = json.load(f)

    expiry = None
    if token_data.get("expiry_date"):
        # google-auth compares expiry to naive UTC
        expiry = datetime.utcfromtimestamp(token_data["expiry_date"] / 1000)

    scopes = token_data.get("scope", DRIVE_READONLY)
    if isinstance(scopes, str):
        scopes = scopes.split()

    creds = Credentials(
        token=token_data.get("access_token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri=TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
        scopes=scopes,
        expiry=expiry,
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(_auth_request())
        _persist_credentials(creds_path, creds, scopes)

    return creds


def _persist_credentials(path: Path, creds: Credentials, scopes: list[str]) -> None:
    """Write refreshed tokens back so Node MCP and Python stay in sync."""
    payload = {
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_type": "Bearer",
        "scope": " ".join(scopes) if scopes else DRIVE_READONLY,
    }
    if creds.expiry:
        payload["expiry_date"] = int(creds.expiry.timestamp() * 1000)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f)


def has_write_scope(creds) -> bool:
    """True when the credentials grant Drive write access (drive.file or full drive)."""
    return any(scope in WRITE_SCOPES for scope in (creds.scopes or []))


def drive_service_with_creds():
    """Build an authenticated Drive service and return it alongside its credentials."""
    creds = load_credentials()
    if _insecure_ssl_enabled():
        import httplib2
        from google_auth_httplib2 import AuthorizedHttp

        http = httplib2.Http(disable_ssl_certificate_validation=True)
        authorized = AuthorizedHttp(creds, http=http)
        service = build("drive", "v3", http=authorized, cache_discovery=False)
    else:
        service = build("drive", "v3", credentials=creds, cache_discovery=False)
    return service, creds


def drive_service():
    service, _ = drive_service_with_creds()
    return service


def list_recent_files(
    service,
    page_size: int = 10,
    page_token: str | None = None,
    exclude_content_snippets: bool = False,
    order_by: str = "recency",
) -> dict:
    """Return a hosted-compatible page of recent files."""
    if order_by not in RECENT_ORDER_BY:
        supported = ", ".join(RECENT_ORDER_BY)
        raise ValueError(
            f"Unsupported orderBy {order_by!r}; expected one of: {supported}"
        )
    kwargs = {
        "q": "trashed = false",
        "pageSize": page_size,
        "fields": f"nextPageToken,files({HOSTED_FILE_FIELDS})",
        "orderBy": RECENT_ORDER_BY[order_by],
    }
    if page_token:
        kwargs["pageToken"] = page_token
    result = (
        service.files()
        .list(**kwargs)
        .execute()
    )
    response = {
        "files": [
            to_hosted_file(file, exclude_content_snippets)
            for file in result.get("files", [])
        ]
    }
    if result.get("nextPageToken"):
        response["nextPageToken"] = result["nextPageToken"]
    return response


def cmd_list(service, page_size: int) -> None:
    for file in list_recent_files(service, page_size)["files"]:
        size = file.get("fileSize", "")
        print(
            f"{file['id']}\t{file.get('modifiedTime', '')}\t"
            f"{file['mimeType']}\t{file['title']}\t{size}"
        )


def cmd_search(service, query: str, page_size: int) -> None:
    files = search_files(service, query, page_size)["files"]
    if not files:
        print("No files matched.")
        return
    for file in files:
        print(f"{file['title']} ({file['mimeType']}) — {file['id']}")


def search_files(
    service,
    query: str,
    page_size: int = 10,
    page_token: str | None = None,
    exclude_content_snippets: bool = False,
) -> dict:
    """Search Drive using the hosted dialect and return a structured page."""
    kwargs = {
        "q": translate_query(query),
        "pageSize": page_size,
        "fields": f"nextPageToken,files({HOSTED_FILE_FIELDS})",
    }
    if page_token:
        kwargs["pageToken"] = page_token
    result = (
        service.files()
        .list(**kwargs)
        .execute()
    )
    response = {
        "files": [
            to_hosted_file(file, exclude_content_snippets)
            for file in result.get("files", [])
        ]
    }
    if result.get("nextPageToken"):
        response["nextPageToken"] = result["nextPageToken"]
    return response


def get_file_metadata(
    service,
    file_id: str,
    exclude_content_snippets: bool = False,
) -> dict:
    """Return hosted-compatible metadata for a Drive file."""
    result = service.files().get(fileId=file_id, fields=HOSTED_FILE_FIELDS).execute()
    return to_hosted_file(result, exclude_content_snippets)


def cmd_info(service, file_id: str) -> None:
    meta = get_file_metadata(service, file_id)
    cli_fields = (
        ("id", meta.get("id")),
        ("name", meta.get("title")),
        ("mimeType", meta.get("mimeType")),
        ("modifiedTime", meta.get("modifiedTime")),
        ("size", meta.get("fileSize")),
        ("webViewLink", meta.get("viewUrl")),
        (
            "parents",
            [meta["parentId"]] if meta.get("parentId") else None,
        ),
    )
    for key, value in cli_fields:
        if _present(value):
            print(f"{key}: {value}")


def read_file(service, file_id: str) -> dict:
    """Read/export a Drive file.

    Returns a dict with: name, mimeType, is_binary, text (str or None),
    raw (bytes or None), and export_mime (when a Google-native export occurred).
    Google Docs -> Markdown, Sheets -> CSV, Slides -> text, Drawings -> PNG (binary).
    """
    meta = service.files().get(fileId=file_id, fields="id, name, mimeType").execute()
    mime = meta["mimeType"]
    name = meta.get("name", file_id)

    if mime.startswith("application/vnd.google-apps."):
        export_mime = EXPORT_MIME.get(mime, "text/plain")
        data = service.files().export(fileId=file_id, mimeType=export_mime).execute()
        if export_mime.startswith("image/"):
            raw = data if isinstance(data, bytes) else data.encode("utf-8")
            return {"name": name, "mimeType": mime, "is_binary": True, "text": None,
                    "raw": raw, "export_mime": export_mime}
        text = data.decode("utf-8", errors="replace") if isinstance(data, bytes) else data
        return {"name": name, "mimeType": mime, "is_binary": False, "text": text,
                "raw": None, "export_mime": export_mime}

    request = service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    raw = buffer.getvalue()

    if mime.startswith("text/") or mime == "application/json":
        return {"name": name, "mimeType": mime, "is_binary": False,
                "text": raw.decode("utf-8", errors="replace"), "raw": None}
    return {"name": name, "mimeType": mime, "is_binary": True, "text": None, "raw": raw}


def download_file(service, file_id: str, output_path: Path | None = None) -> tuple[Path, int]:
    """Save a file's bytes (or exported bytes for Google-native formats) to a path.

    Returns (path, byte_count). Defaults the path to the file's name.
    """
    info = read_file(service, file_id)
    data = info["raw"] if info["is_binary"] else (info["text"] or "").encode("utf-8")
    out = output_path or Path(info["name"])
    out.write_bytes(data)
    return out, len(data)


def create_file(service, name: str, content: str, mime_type: str, parent_id: str | None = None) -> dict:
    """Create a Drive file from text content; returns {id, name}. Requires write scope."""
    body: dict = {"name": name, "mimeType": mime_type}
    if parent_id:
        body["parents"] = [parent_id]
    media = MediaIoBaseUpload(io.BytesIO(content.encode("utf-8")), mimetype=mime_type, resumable=False)
    created = (
        service.files()
        .create(body=body, media_body=media, fields="id, name")
        .execute()
    )
    return {"id": created["id"], "name": created.get("name", name)}


def copy_file(service, file_id: str, name: str | None = None, parent_id: str | None = None) -> dict:
    """Copy an existing Drive file; returns the new {id, name}. Requires write scope."""
    body: dict = {}
    if name:
        body["name"] = name
    if parent_id:
        body["parents"] = [parent_id]
    copied = (
        service.files()
        .copy(fileId=file_id, body=body, fields="id, name")
        .execute()
    )
    return {"id": copied["id"], "name": copied.get("name")}


def list_permissions(service, file_id: str) -> list[dict]:
    """List a file's sharing permissions (id, role, type, and grantee when present)."""
    result = (
        service.permissions()
        .list(fileId=file_id, fields="permissions(id, role, type, emailAddress, displayName)")
        .execute()
    )
    return result.get("permissions", [])


def update_file(service, file_id: str, title: str | None = None, parent_id: str | None = None) -> dict:
    """Update a file's metadata only (rename and/or move); returns {id, name, parents}.

    Local-only extension beyond the hosted toolset. Requires write scope. At least
    one of ``title`` (non-empty) or ``parent_id`` must be provided. Content is never
    modified; a new ``parent_id`` replaces the file's current parent.
    """
    if title is not None and title == "":
        raise ValueError("title must not be empty when provided")
    if not title and not parent_id:
        raise ValueError("update_file requires a non-empty title and/or a parent_id")

    body: dict = {}
    if title:
        body["name"] = title
    kwargs: dict = {"fileId": file_id, "body": body, "fields": "id, name, parents"}
    if parent_id:
        current = service.files().get(fileId=file_id, fields="parents").execute()
        parents = current.get("parents", [])
        kwargs["addParents"] = parent_id
        if parents:
            kwargs["removeParents"] = ",".join(parents)
    updated = service.files().update(**kwargs).execute()
    return {"id": updated["id"], "name": updated.get("name"), "parents": updated.get("parents", [])}


def cmd_read(service, file_id: str, output: Path | None) -> None:
    info = read_file(service, file_id)
    name = info["name"]
    if info["is_binary"]:
        out = output or Path(name)
        out.write_bytes(info["raw"])
        print(f"Wrote binary ({len(info['raw'])} bytes) to {out}", file=sys.stderr)
    else:
        _write_output(info["text"], output, name)


def _write_output(text: str, output: Path | None, name: str) -> None:
    if output:
        output.write_text(text, encoding="utf-8")
        print(f"Wrote to {output}", file=sys.stderr)
    else:
        sys.stdout.write(text)
        if not text.endswith("\n"):
            sys.stdout.write("\n")


def cmd_interactive(service) -> None:
    print("Google Drive interactive mode. Commands: list, search <q>, read <id>, info <id>, help, quit")
    while True:
        try:
            line = input("gdrive> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        parts = line.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        try:
            if cmd in ("quit", "exit", "q"):
                break
            if cmd == "help":
                print(textwrap.dedent("""
                    list [n]           List recent files (default 10)
                    search <query>     Full-text search
                    read <file_id>     Export/download file to stdout or file
                    info <file_id>     File metadata
                    quit               Exit
                """).strip())
            elif cmd == "list":
                n = int(arg) if arg else 10
                cmd_list(service, n)
            elif cmd == "search":
                if not arg:
                    print("Usage: search <query>")
                    continue
                cmd_search(service, arg, 10)
            elif cmd == "read":
                if not arg:
                    print("Usage: read <file_id>")
                    continue
                cmd_read(service, arg.strip(), None)
            elif cmd == "info":
                if not arg:
                    print("Usage: info <file_id>")
                    continue
                cmd_info(service, arg.strip())
            else:
                print(f"Unknown command: {cmd}. Type 'help'.")
        except HttpError as e:
            print(f"API error: {e}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Google Drive CLI using existing MCP OAuth credentials (isolated Python process).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List recently modified files")
    p_list.add_argument("-n", "--page-size", type=int, default=10)

    p_search = sub.add_parser("search", help="Full-text search (same as MCP search tool)")
    p_search.add_argument("query")
    p_search.add_argument("-n", "--page-size", type=int, default=10)

    p_info = sub.add_parser("info", help="Show file metadata")
    p_info.add_argument("file_id")

    p_read = sub.add_parser("read", help="Read/export file content")
    p_read.add_argument("file_id")
    p_read.add_argument("-o", "--output", type=Path, help="Write to file instead of stdout")

    sub.add_parser("interactive", help="REPL for Drive commands")

    args = parser.parse_args()
    service = drive_service()

    try:
        if args.command == "list":
            cmd_list(service, args.page_size)
        elif args.command == "search":
            cmd_search(service, args.query, args.page_size)
        elif args.command == "info":
            cmd_info(service, args.file_id)
        elif args.command == "read":
            cmd_read(service, args.file_id, args.output)
        elif args.command == "interactive":
            cmd_interactive(service)
    except HttpError as e:
        sys.exit(f"Google Drive API error: {e}")


if __name__ == "__main__":
    main()
