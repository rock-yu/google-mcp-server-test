from __future__ import annotations

import socket
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER_DIR = ROOT / "drive-mcp-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import server
from tests.support.fake_drive import FakeDriveService, write_credentials


def _deny_network(*args, **kwargs):
    raise AssertionError("network access is forbidden in hermetic MCP tests")


def _deny_oauth(*args, **kwargs):
    raise AssertionError("OAuth loading is forbidden in hermetic MCP tests")


def main() -> None:
    socket.create_connection = _deny_network
    socket.socket.connect = _deny_network
    socket.socket.connect_ex = _deny_network
    server.gdrive_cli.drive_service_with_creds = _deny_oauth
    credentials = (
        type("ReadOnlyCredentials", (), {"scopes": [
            "https://www.googleapis.com/auth/drive.readonly"
        ]})()
        if os.environ.get("FAKE_DRIVE_READ_ONLY") == "1"
        else write_credentials()
    )
    server.configure_service(FakeDriveService(), credentials)
    server.main(authenticate=False)


if __name__ == "__main__":
    main()
