import sys
import unittest
from os import environ
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

    def test_drive_read_only_environment_values(self):
        for value in ("1", "true", "YES", "on"):
            with self.subTest(value=value), patch.dict(
                environ, {"DRIVE_MCP_READ_ONLY": value}, clear=False
            ):
                self.assertTrue(server.drive_read_only_from_env())
        for value in ("", "0", "false", "NO", "off"):
            with self.subTest(value=value), patch.dict(
                environ, {"DRIVE_MCP_READ_ONLY": value}, clear=False
            ):
                self.assertFalse(server.drive_read_only_from_env())
        with patch.dict(
            environ, {"DRIVE_MCP_READ_ONLY": "sometimes"}, clear=False
        ), self.assertRaisesRegex(SystemExit, "must be one of"):
            server.drive_read_only_from_env()


if __name__ == "__main__":
    unittest.main()
