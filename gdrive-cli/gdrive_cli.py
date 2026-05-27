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

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

DRIVE_READONLY = "https://www.googleapis.com/auth/drive.readonly"
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


def drive_service():
    creds = load_credentials()
    if _insecure_ssl_enabled():
        import httplib2
        from google_auth_httplib2 import AuthorizedHttp

        http = httplib2.Http(disable_ssl_certificate_validation=True)
        authorized = AuthorizedHttp(creds, http=http)
        return build("drive", "v3", http=authorized, cache_discovery=False)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def cmd_list(service, page_size: int) -> None:
    result = (
        service.files()
        .list(
            pageSize=page_size,
            fields="files(id, name, mimeType, modifiedTime, size)",
            orderBy="modifiedTime desc",
        )
        .execute()
    )
    for f in result.get("files", []):
        size = f.get("size", "")
        print(f"{f['id']}\t{f.get('modifiedTime', '')}\t{f['mimeType']}\t{f['name']}\t{size}")


def cmd_search(service, query: str, page_size: int) -> None:
    escaped = query.replace("\\", "\\\\").replace("'", "\\'")
    q = f"fullText contains '{escaped}'"
    result = (
        service.files()
        .list(
            q=q,
            pageSize=page_size,
            fields="files(id, name, mimeType, modifiedTime, size)",
        )
        .execute()
    )
    files = result.get("files", [])
    if not files:
        print("No files matched.")
        return
    for f in files:
        print(f"{f['name']} ({f['mimeType']}) — {f['id']}")


def cmd_info(service, file_id: str) -> None:
    meta = (
        service.files()
        .get(fileId=file_id, fields="id, name, mimeType, modifiedTime, size, webViewLink, parents")
        .execute()
    )
    for key, value in meta.items():
        print(f"{key}: {value}")


def cmd_read(service, file_id: str, output: Path | None) -> None:
    meta = service.files().get(fileId=file_id, fields="id, name, mimeType").execute()
    mime = meta["mimeType"]
    name = meta.get("name", file_id)

    if mime.startswith("application/vnd.google-apps."):
        export_mime = EXPORT_MIME.get(mime, "text/plain")
        data = service.files().export(fileId=file_id, mimeType=export_mime).execute()
        if isinstance(data, bytes):
            text = data.decode("utf-8", errors="replace")
        else:
            text = data
        _write_output(text, output, name)
        return

    request = service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()

    raw = buffer.getvalue()
    if mime.startswith("text/") or mime == "application/json":
        _write_output(raw.decode("utf-8", errors="replace"), output, name)
    else:
        out = output or Path(name)
        out.write_bytes(raw)
        print(f"Wrote binary ({len(raw)} bytes) to {out}", file=sys.stderr)


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
