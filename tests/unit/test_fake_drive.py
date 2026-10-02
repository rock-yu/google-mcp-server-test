import copy
import json
import tempfile
import unittest
from pathlib import Path

from tests.support.fake_drive import FakeDriveService, load_dataset, validate_dataset

ROOT = Path(__file__).resolve().parents[2]
import sys

sys.path.insert(0, str(ROOT / "gdrive-cli"))
import gdrive_cli


class DatasetTests(unittest.TestCase):
    def test_fixture_is_valid_and_covers_required_shapes(self):
        data = load_dataset()
        mime_types = {file["mimeType"] for file in data["files"]}
        self.assertIn("application/vnd.google-apps.document", mime_types)
        self.assertIn("image/jpeg", mime_types)
        self.assertTrue(any(file.get("sharedWithMe") for file in data["files"]))
        self.assertTrue(any(file.get("trashed") for file in data["files"]))
        self.assertTrue(any("parents" not in file for file in data["files"]))

    def test_validator_rejects_duplicate_ids(self):
        data = load_dataset()
        data["files"].append(copy.deepcopy(data["files"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate file id"):
            validate_dataset(data)

    def test_validator_rejects_missing_fields_and_invalid_permission_refs(self):
        missing = load_dataset()
        del missing["files"][0]["mimeType"]
        with self.assertRaisesRegex(ValueError, "lacks"):
            validate_dataset(missing)
        invalid_ref = load_dataset()
        invalid_ref["permissions"]["unknown"] = []
        with self.assertRaisesRegex(ValueError, "invalid permissions"):
            validate_dataset(invalid_ref)
        invalid_failure = load_dataset()
        del invalid_failure["failures"]["permission-failure"]["reason"]
        with self.assertRaisesRegex(ValueError, "lacks reason"):
            validate_dataset(invalid_failure)


class FakeDriveTests(unittest.TestCase):
    def setUp(self):
        self.service = FakeDriveService()

    def test_search_boolean_parent_owner_and_trash_filtering(self):
        result = gdrive_cli.search_files(
            self.service,
            "(parentId = 'root' and owner = 'me') and "
            "(title contains 'Report' or mimeType contains 'spreadsheet')",
        )
        self.assertEqual(
            {file["id"] for file in result["files"]},
            {"doc-alpha", "sheet-delta"},
        )

    def test_pagination_and_recent_sort_are_deterministic(self):
        first = gdrive_cli.list_recent_files(self.service, page_size=2)
        second = gdrive_cli.list_recent_files(
            self.service, page_size=2, page_token=first["nextPageToken"]
        )
        self.assertEqual([file["id"] for file in first["files"]], ["sheet-delta", "image-beta"])
        self.assertFalse(
            {file["id"] for file in first["files"]}
            & {file["id"] for file in second["files"]}
        )

    def test_read_native_text_and_binary_and_download(self):
        self.assertIn("Architecture notes", gdrive_cli.read_file(self.service, "doc-alpha")["text"])
        self.assertEqual(gdrive_cli.read_file(self.service, "text-gamma")["text"], "hello notes")
        self.assertEqual(gdrive_cli.read_file(self.service, "image-beta")["raw"], b"JPEGDATA")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "image.jpg"
            written, count = gdrive_cli.download_file(self.service, "image-beta", path)
            self.assertEqual((written, count, path.read_bytes()), (path, 8, b"JPEGDATA"))

    def test_create_copy_update_and_permissions(self):
        created = gdrive_cli.create_file(
            self.service, "New.txt", "new body", "text/plain", "folder-a"
        )
        copied = gdrive_cli.copy_file(self.service, created["id"], "Copy.txt", "root")
        updated = gdrive_cli.update_file(
            self.service, copied["id"], "Renamed.txt", "folder-a"
        )
        permissions = gdrive_cli.list_permissions(self.service, "doc-alpha")
        self.assertEqual(created["name"], "New.txt")
        self.assertEqual(updated["name"], "Renamed.txt")
        self.assertEqual(updated["parents"], ["folder-a"])
        self.assertEqual(permissions[0]["role"], "owner")

    def test_mutation_audit_and_configured_operation_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            audit_path = Path(directory) / "audit.json"
            service = FakeDriveService(audit_path=audit_path)
            created = gdrive_cli.create_file(
                service, "Audited.txt", "body", "text/plain"
            )
            audit = json.loads(audit_path.read_text())
            self.assertEqual(audit[-1]["file"]["id"], created["id"])
            with self.assertRaises(Exception) as raised:
                gdrive_cli.create_file(
                    service, "Create Failure.txt", "body", "text/plain"
                )
            self.assertEqual(raised.exception.resp.status, 500)
            copied = gdrive_cli.copy_file(
                service, "doc-alpha", "Audited copy", "folder-a"
            )
            audit = json.loads(audit_path.read_text())
            self.assertEqual(audit[-1]["file"]["id"], copied["id"])
            self.assertEqual(audit[-1]["source"]["id"], "doc-alpha")
            with self.assertRaises(Exception) as raised:
                gdrive_cli.copy_file(
                    service, "doc-alpha", "Copy Failure"
                )
            self.assertEqual(raised.exception.resp.status, 500)

    def test_http_failures_are_reproducible(self):
        for file_id, status in (("inaccessible", 403), ("missing", 404)):
            with self.subTest(file_id=file_id):
                with self.assertRaises(Exception) as raised:
                    gdrive_cli.get_file_metadata(self.service, file_id)
                self.assertEqual(raised.exception.resp.status, status)

    def test_invalid_page_token_is_a_400(self):
        with self.assertRaises(Exception) as raised:
            gdrive_cli.search_files(
                self.service, "title contains 'Report'", page_token="invalid"
            )
        self.assertEqual(raised.exception.resp.status, 400)


if __name__ == "__main__":
    unittest.main()
