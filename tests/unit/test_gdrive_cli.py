import unittest
import sys
from pathlib import Path

GDRIVE_CLI_DIR = Path(__file__).resolve().parents[2] / "gdrive-cli"
if str(GDRIVE_CLI_DIR) not in sys.path:
    sys.path.insert(0, str(GDRIVE_CLI_DIR))

import gdrive_cli


class FakeRequest:
    def __init__(self, result):
        self.result = result

    def execute(self):
        return self.result


class FakeFiles:
    def __init__(self, list_result=None, get_result=None):
        self.list_result = list_result or {}
        self.get_result = get_result or {}
        self.list_kwargs = None
        self.get_kwargs = None

    def list(self, **kwargs):
        self.list_kwargs = kwargs
        return FakeRequest(self.list_result)

    def get(self, **kwargs):
        self.get_kwargs = kwargs
        return FakeRequest(self.get_result)


class FakeService:
    def __init__(self, files):
        self._files = files

    def files(self):
        return self._files


class HostedFileTests(unittest.TestCase):
    def test_maps_hosted_fields_and_omits_missing_values(self):
        mapped = gdrive_cli.to_hosted_file(
            {
                "id": "file-1",
                "name": "Report",
                "parents": ["folder-1", "folder-2"],
                "mimeType": "text/plain",
                "size": "42",
                "description": "",
                "webViewLink": "https://example.test/file-1",
                "owners": [
                    {"displayName": "Owner Name", "emailAddress": "owner@example.test"}
                ],
                "capabilities": {"canAddChildren": False},
                "contentSnippet": "match context",
            }
        )

        self.assertEqual(
            mapped,
            {
                "id": "file-1",
                "title": "Report",
                "parentId": "folder-1",
                "mimeType": "text/plain",
                "fileSize": "42",
                "contentSnippet": "match context",
                "viewUrl": "https://example.test/file-1",
                "owner": "owner@example.test",
                "canAddChildren": False,
            },
        )

    def test_excludes_content_snippet_and_absent_optional_fields(self):
        mapped = gdrive_cli.to_hosted_file(
            {
                "id": "file-1",
                "name": "Report",
                "contentSnippet": "match context",
                "owners": [],
                "parents": [],
            },
            exclude_content_snippets=True,
        )

        self.assertEqual(mapped, {"id": "file-1", "title": "Report"})


class QueryTranslationTests(unittest.TestCase):
    def assert_translation_contains(self, query, *parts):
        translated = gdrive_cli.translate_query(query)
        for part in parts:
            self.assertIn(part, translated)
        self.assertTrue(translated.endswith("and trashed = false"))

    def test_documented_hosted_examples(self):
        examples = (
            (
                "title contains 'hello' and title contains 'goodbye'",
                ("name contains 'hello'", "name contains 'goodbye'"),
            ),
            (
                "modifiedTime > '2024-01-01T00:00:00Z' and "
                "(mimeType contains 'image/' or mimeType contains 'video/')",
                (
                    "modifiedTime > '2024-01-01T00:00:00Z'",
                    "mimeType contains 'image/'",
                    "mimeType contains 'video/'",
                ),
            ),
            ("parentId = '1234567'", ("'1234567' in parents",)),
            ("parentId = 'root'", ("'root' in parents",)),
            ("fullText contains 'hello'", ("fullText contains 'hello'",)),
            ("owner = 'test@example.org'", ("'test@example.org' in owners",)),
            ("owner = 'me'", ("'me' in owners",)),
            ("sharedWithMe = true", ("sharedWithMe",)),
            ("sharedWithMe = false", ("not sharedWithMe",)),
        )
        for query, parts in examples:
            with self.subTest(query=query):
                self.assert_translation_contains(query, *parts)

    def test_negative_owner_parent_and_shared_filters(self):
        self.assert_translation_contains(
            "parentId != 'folder'", "not ('folder' in parents)"
        )
        self.assert_translation_contains(
            "owner != 'me'", "not ('me' in owners)"
        )
        self.assert_translation_contains(
            "sharedWithMe != false", "sharedWithMe"
        )

    def test_bare_term_uses_full_text_fallback(self):
        self.assertEqual(
            gdrive_cli.translate_query("quarterly report"),
            "(fullText contains 'quarterly report') and trashed = false",
        )

    def test_field_names_inside_strings_are_not_rewritten(self):
        translated = gdrive_cli.translate_query(
            "fullText contains 'title parentId owner'"
        )
        self.assertIn(
            "fullText contains 'title parentId owner'",
            translated,
        )

    def test_rejects_invalid_structured_queries(self):
        invalid = (
            "",
            "title > 'x'",
            "parentId contains 'x'",
            "owner = me",
            "sharedWithMe = 'true'",
            "modifiedTime > 'not-a-time'",
            "title contains 'unterminated",
            "title contains 'x' and",
            "unknown = 'x'",
            "unknown contains 'x'",
            "unknown = 'x' and title = 'x'",
        )
        for query in invalid:
            with self.subTest(query=query):
                with self.assertRaises(ValueError):
                    gdrive_cli.translate_query(query)


class DriveHelperTests(unittest.TestCase):
    def test_search_uses_shared_fields_pagination_and_mapping(self):
        files = FakeFiles(
            list_result={
                "files": [{"id": "1", "name": "One", "mimeType": "text/plain"}],
                "nextPageToken": "next",
            }
        )
        result = gdrive_cli.search_files(
            FakeService(files),
            "parentId = 'folder'",
            page_size=2,
            page_token="current",
            exclude_content_snippets=True,
        )

        self.assertEqual(
            result,
            {
                "files": [
                    {"id": "1", "title": "One", "mimeType": "text/plain"}
                ],
                "nextPageToken": "next",
            },
        )
        self.assertEqual(files.list_kwargs["pageSize"], 2)
        self.assertEqual(files.list_kwargs["pageToken"], "current")
        self.assertIn("'folder' in parents", files.list_kwargs["q"])
        self.assertEqual(
            files.list_kwargs["fields"],
            f"nextPageToken,files({gdrive_cli.HOSTED_FILE_FIELDS})",
        )

    def test_recent_order_values_map_to_drive(self):
        for hosted, drive in gdrive_cli.RECENT_ORDER_BY.items():
            files = FakeFiles()
            gdrive_cli.list_recent_files(
                FakeService(files), order_by=hosted, page_token="page"
            )
            self.assertEqual(files.list_kwargs["orderBy"], drive)
            self.assertEqual(files.list_kwargs["pageToken"], "page")
            self.assertEqual(files.list_kwargs["q"], "trashed = false")

    def test_recent_rejects_unknown_order(self):
        with self.assertRaisesRegex(ValueError, "Unsupported orderBy"):
            gdrive_cli.list_recent_files(
                FakeService(FakeFiles()), order_by="modifiedTime desc"
            )

    def test_metadata_uses_inner_fields_mask_and_maps_result(self):
        files = FakeFiles(
            get_result={
                "id": "1",
                "name": "One",
                "parents": ["folder"],
                "owners": [{"emailAddress": "owner@example.test"}],
            }
        )
        result = gdrive_cli.get_file_metadata(FakeService(files), "1")

        self.assertEqual(
            result,
            {
                "id": "1",
                "title": "One",
                "parentId": "folder",
                "owner": "owner@example.test",
            },
        )
        self.assertEqual(
            files.get_kwargs,
            {"fileId": "1", "fields": gdrive_cli.HOSTED_FILE_FIELDS},
        )


if __name__ == "__main__":
    unittest.main()
