import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "drive-mcp-server"))

import server


class ServerInjectionTests(unittest.TestCase):
    def tearDown(self):
        server._service = None
        server._creds = None

    def test_default_path_constructs_normal_drive_service(self):
        service = object()
        credentials = object()
        with patch.object(
            server.gdrive_cli,
            "drive_service_with_creds",
            return_value=(service, credentials),
        ) as build:
            self.assertIs(server._get_service(), service)
        build.assert_called_once_with()
        self.assertIs(server._creds, credentials)

    def test_configured_service_bypasses_oauth(self):
        service = object()
        credentials = object()
        server.configure_service(service, credentials)
        with patch.object(
            server.gdrive_cli,
            "drive_service_with_creds",
            side_effect=AssertionError("OAuth must not run"),
        ):
            self.assertIs(server._get_service(), service)


if __name__ == "__main__":
    unittest.main()
