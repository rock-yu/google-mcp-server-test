from __future__ import annotations

import base64
import json
import tempfile
import unittest
from pathlib import Path

from tests.support.contracts import (
    allows_missing_value,
    load_json,
    validate_semantic_cases,
)
from tests.support.mcp_session import fake_mcp_session, text_content

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


class SemanticConformanceTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = load_json(FIXTURES / "semantic_cases.json")
        cls.deviations = load_json(FIXTURES / "deviations.json")
        validate_semantic_cases(
            cls.cases, load_json(FIXTURES / "drive_dataset.json")
        )

    async def test_search_semantic_cases(self):
        async with fake_mcp_session() as session:
            for case in self.cases["search"]:
                with self.subTest(case=case["name"]):
                    result = await session.call_tool(
                        "search_files", {"query": case["query"], "pageSize": 100}
                    )
                    self.assertFalse(result.is_error)
                    self.assertEqual(
                        sorted(file["id"] for file in result.structured_content["files"]),
                        sorted(case["ids"]),
                    )
                    for file in result.structured_content["files"]:
                        self.assertIn("title", file)
                        self.assertNotIn("name", file)
                        if "contentSnippet" not in file:
                            self.assertTrue(
                                allows_missing_value(
                                    self.deviations,
                                    tool="search_files",
                                    surface="result.files",
                                    field="contentSnippet",
                                )
                            )

    async def test_search_paging_and_invalid_inputs(self):
        async with fake_mcp_session() as session:
            first = await session.call_tool(
                "search_files", {"query": "title != 'none'", "pageSize": 2}
            )
            token = first.structured_content["nextPageToken"]
            second = await session.call_tool(
                "search_files",
                {"query": "title != 'none'", "pageSize": 2, "pageToken": token},
            )
            invalid_results = [
                await session.call_tool("search_files", {"query": query})
                for query in self.cases["invalidSearch"]
            ]
            bad_token = await session.call_tool(
                "search_files",
                {
                    "query": "title != 'none'",
                    "pageToken": "not-a-token",
                },
            )
        first_ids = {file["id"] for file in first.structured_content["files"]}
        second_ids = {file["id"] for file in second.structured_content["files"]}
        self.assertTrue(token)
        self.assertFalse(first_ids & second_ids)
        self.assertTrue(all(result.is_error for result in invalid_results))
        self.assertTrue(bad_token.is_error)

    async def test_recent_sorts_defaults_and_paging(self):
        async with fake_mcp_session() as session:
            default = await session.call_tool("list_recent_files", {})
            for order, expected in self.cases["recent"].items():
                with self.subTest(order=order):
                    result = await session.call_tool(
                        "list_recent_files", {"orderBy": order, "pageSize": 100}
                    )
                    self.assertEqual(
                        [file["id"] for file in result.structured_content["files"]],
                        expected,
                    )
            first = await session.call_tool(
                "list_recent_files", {"orderBy": "recency", "pageSize": 2}
            )
            second = await session.call_tool(
                "list_recent_files",
                {
                    "orderBy": "recency",
                    "pageSize": 2,
                    "pageToken": first.structured_content["nextPageToken"],
                },
            )
            invalid = await session.call_tool(
                "list_recent_files", {"orderBy": "modifiedTime desc"}
            )
        self.assertEqual(
            [file["id"] for file in default.structured_content["files"]],
            self.cases["recent"]["recency"],
        )
        sparse = next(
            file
            for file in default.structured_content["files"]
            if file["id"] == "sparse-epsilon"
        )
        self.assertNotIn("parentId", sparse)
        self.assertNotIn("viewUrl", sparse)
        self.assertTrue(all("name" not in file for file in default.structured_content["files"]))
        self.assertFalse(
            {file["id"] for file in first.structured_content["files"]}
            & {file["id"] for file in second.structured_content["files"]}
        )
        self.assertTrue(invalid.is_error)

    async def test_metadata_complete_sparse_and_inaccessible(self):
        async with fake_mcp_session() as session:
            complete = await session.call_tool(
                "get_file_metadata", {"fileId": "doc-alpha"}
            )
            sparse = await session.call_tool(
                "get_file_metadata",
                {"fileId": "sparse-epsilon", "excludeContentSnippets": True},
            )
            inaccessible = await session.call_tool(
                "get_file_metadata", {"fileId": "inaccessible"}
            )
        self.assertEqual(complete.structured_content["owner"], "me@example.test")
        self.assertEqual(complete.structured_content["title"], "Report Alpha")
        self.assertNotIn("parentId", sparse.structured_content)
        self.assertNotIn("viewUrl", sparse.structured_content)
        self.assertNotIn("contentSnippet", sparse.structured_content)
        self.assertTrue(inaccessible.is_error)

    async def test_read_file_content_semantic_cases(self):
        async with fake_mcp_session() as session:
            for case in self.cases["read"]:
                with self.subTest(case=case["name"]):
                    result = await session.call_tool(
                        "read_file_content", {"file_id": case["fileId"]}
                    )
                    value = text_content(result)
                    if "errorContains" in case:
                        self.assertTrue(result.is_error)
                        self.assertIn(case["errorContains"], value)
                    else:
                        self.assertFalse(result.is_error)
                        if "text" in case:
                            self.assertEqual(value, case["text"])
                        else:
                            self.assertIn(case["contains"], value)

    async def test_download_file_content_semantic_cases(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            async with fake_mcp_session(cwd=root) as session:
                for case in self.cases["download"]:
                    with self.subTest(case=case["name"]):
                        arguments = {"file_id": case["fileId"]}
                        if "path" in case:
                            path = root / case["path"]
                            path.write_bytes(b"replace me")
                            arguments["output_path"] = str(path)
                        elif "defaultPath" in case:
                            path = root / case["defaultPath"]
                        else:
                            path = None
                        result = await session.call_tool(
                            "download_file_content", arguments
                        )
                        value = text_content(result)
                        if "errorContains" in case:
                            self.assertTrue(result.is_error)
                            self.assertIn(case["errorContains"], value)
                            continue
                        self.assertFalse(result.is_error)
                        self.assertTrue(path.is_file())
                        expected = (
                            base64.b64decode(case["bytesBase64"])
                            if "bytesBase64" in case
                            else case["text"].encode()
                        )
                        self.assertEqual(path.read_bytes(), expected)
                        self.assertIn(f"Wrote {len(expected)} bytes", value)
                        self.assertIn(
                            str(path) if "path" in case else path.name,
                            value,
                        )

    async def test_create_file_semantic_cases(self):
        with tempfile.TemporaryDirectory() as directory:
            audit_path = Path(directory) / "audit.json"
            async with fake_mcp_session(audit_path=audit_path) as session:
                for case in self.cases["create"]:
                    with self.subTest(case=case["name"]):
                        result = await session.call_tool(
                            "create_file", case["arguments"]
                        )
                        value = text_content(result)
                        if "errorContains" in case:
                            self.assertTrue(result.is_error)
                            self.assertIn(case["errorContains"], value)
                            continue
                        self.assertFalse(result.is_error)
                        record = json.loads(audit_path.read_text())[-1]
                        self.assertEqual(record["operation"], "create")
                        file = record["file"]
                        self.assertEqual(file["name"], case["arguments"]["name"])
                        self.assertEqual(file["content"], case["arguments"]["content"])
                        self.assertEqual(file["mimeType"], case["expectedMimeType"])
                        self.assertEqual(file["parents"], case["expectedParents"])
                        self.assertIn(file["id"], value)
            async with fake_mcp_session(read_only=True) as read_only_session:
                denied = await read_only_session.call_tool(
                    "create_file", {"name": "Denied.txt", "content": "denied"}
                )
            self.assertTrue(denied.is_error)
            self.assertIn("needs write access", text_content(denied))

    async def test_copy_file_semantic_cases(self):
        with tempfile.TemporaryDirectory() as directory:
            audit_path = Path(directory) / "audit.json"
            async with fake_mcp_session(audit_path=audit_path) as session:
                for case in self.cases["copy"]:
                    with self.subTest(case=case["name"]):
                        result = await session.call_tool(
                            "copy_file", case["arguments"]
                        )
                        value = text_content(result)
                        if "errorContains" in case:
                            self.assertTrue(result.is_error)
                            self.assertIn(case["errorContains"], value)
                            continue
                        self.assertFalse(result.is_error)
                        record = json.loads(audit_path.read_text())[-1]
                        self.assertEqual(record["operation"], "copy")
                        file = record["file"]
                        self.assertEqual(file["name"], case["expectedName"])
                        self.assertEqual(file["parents"], case["expectedParents"])
                        self.assertNotEqual(file["id"], case["sourceId"])
                        self.assertEqual(record["source"]["id"], case["sourceId"])
                        self.assertNotEqual(record["source"]["id"], file["id"])
                        self.assertIn(file["id"], value)
            async with fake_mcp_session(read_only=True) as read_only_session:
                denied = await read_only_session.call_tool(
                    "copy_file", {"file_id": "doc-alpha"}
                )
            self.assertTrue(denied.is_error)
            self.assertIn("needs write access", text_content(denied))

    async def test_file_permission_semantic_cases(self):
        async with fake_mcp_session() as session:
            for case in self.cases["permissions"]:
                with self.subTest(case=case["name"]):
                    result = await session.call_tool(
                        "get_file_permissions", {"file_id": case["fileId"]}
                    )
                    value = text_content(result)
                    if "errorContains" in case:
                        self.assertTrue(result.is_error)
                        self.assertIn(case["errorContains"], value)
                    else:
                        self.assertFalse(result.is_error)
                        self.assertEqual(value, case["text"])


if __name__ == "__main__":
    unittest.main()
