from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.support.mcp_session import fake_mcp_session, text_content

TOOL_NAMES = {
    "search_files",
    "read_file_content",
    "list_recent_files",
    "get_file_metadata",
    "download_file_content",
    "create_file",
    "copy_file",
    "get_file_permissions",
    "update_file",
}


class StdioContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_tools_list_exposes_all_tools_and_structured_read_schemas(self):
        async with fake_mcp_session() as session:
            tools = (await session.list_tools()).tools
        self.assertEqual({tool.name for tool in tools}, TOOL_NAMES)
        by_name = {tool.name: tool for tool in tools}
        for name in ("search_files", "list_recent_files", "get_file_metadata"):
            with self.subTest(tool=name):
                self.assertIsNotNone(by_name[name].output_schema)
                self.assertEqual(by_name[name].input_schema["type"], "object")

    async def test_read_tools_return_real_protocol_results(self):
        async with fake_mcp_session() as session:
            search = await session.call_tool(
                "search_files",
                {
                    "query": "parentId = 'root' and title contains 'Report'",
                    "pageSize": 1,
                },
            )
            metadata = await session.call_tool(
                "get_file_metadata", {"fileId": "doc-alpha"}
            )
            content = await session.call_tool(
                "read_file_content", {"file_id": "doc-alpha"}
            )
            recent = await session.call_tool(
                "list_recent_files", {"orderBy": "lastModified", "pageSize": 2}
            )
            permissions = await session.call_tool(
                "get_file_permissions", {"file_id": "doc-alpha"}
            )
        self.assertFalse(search.is_error)
        self.assertEqual(search.structured_content["files"][0]["id"], "doc-alpha")
        self.assertEqual(metadata.structured_content["id"], "doc-alpha")
        self.assertIn("Architecture notes", text_content(content))
        self.assertEqual(len(recent.structured_content["files"]), 2)
        self.assertIn("permission-owner", text_content(permissions))

    async def test_write_download_and_local_update_tools(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "download.jpg"
            async with fake_mcp_session() as session:
                created = await session.call_tool(
                    "create_file",
                    {
                        "name": "Created.txt",
                        "content": "created body",
                        "parent_id": "folder-a",
                    },
                )
                copied = await session.call_tool(
                    "copy_file",
                    {"file_id": "doc-alpha", "name": "Copied report"},
                )
                updated = await session.call_tool(
                    "update_file",
                    {
                        "file_id": "text-gamma",
                        "title": "Renamed notes",
                        "parent_id": "root",
                    },
                )
                downloaded = await session.call_tool(
                    "download_file_content",
                    {"file_id": "image-beta", "output_path": str(output)},
                )
            downloaded_bytes = output.read_bytes()
            self.assertFalse(created.is_error)
            self.assertFalse(downloaded.is_error, text_content(downloaded))
            self.assertIn("created-1", text_content(created))
            self.assertIn("copy-2", text_content(copied))
            self.assertIn("Renamed notes", text_content(updated))
            self.assertIn("8 bytes", text_content(downloaded))
            self.assertEqual(downloaded_bytes, b"JPEGDATA")

    async def test_invalid_inputs_and_backend_failures_are_tool_errors(self):
        async with fake_mcp_session() as session:
            invalid_query = await session.call_tool(
                "search_files", {"query": "unknown = 'x'"}
            )
            invalid_sort = await session.call_tool(
                "list_recent_files", {"orderBy": "modifiedTime desc"}
            )
            missing_argument = await session.call_tool("get_file_metadata", {})
            inaccessible = await session.call_tool(
                "get_file_metadata", {"fileId": "inaccessible"}
            )
            missing = await session.call_tool(
                "get_file_metadata", {"fileId": "missing"}
            )
        for result in (
            invalid_query,
            invalid_sort,
            missing_argument,
            inaccessible,
            missing,
        ):
            self.assertTrue(result.is_error)
        self.assertIn("needs write access", text_content(inaccessible))
        self.assertIn("HTTP 404", text_content(missing))

    async def test_read_only_credentials_reject_write_tools(self):
        async with fake_mcp_session(read_only=True) as session:
            result = await session.call_tool(
                "create_file", {"name": "Denied.txt", "content": "no write"}
            )
        self.assertTrue(result.is_error)
        self.assertIn("needs write access", text_content(result))


if __name__ == "__main__":
    unittest.main()
