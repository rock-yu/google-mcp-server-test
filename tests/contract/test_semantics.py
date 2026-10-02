from __future__ import annotations

import json
import unittest
from pathlib import Path

from tests.support.contracts import allows_missing_value, load_json
from tests.support.mcp_session import fake_mcp_session

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


class SemanticConformanceTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = load_json(FIXTURES / "semantic_cases.json")
        cls.deviations = load_json(FIXTURES / "deviations.json")

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


if __name__ == "__main__":
    unittest.main()
