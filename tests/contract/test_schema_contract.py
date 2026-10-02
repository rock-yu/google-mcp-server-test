from __future__ import annotations

import unittest
from pathlib import Path

from tests.support.contracts import (
    contract_diff,
    load_contract_fixture,
    normalize_tools,
)
from tests.support.mcp_session import fake_mcp_session

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


class SchemaContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_hosted_and_local_extension_contracts(self):
        expected_hosted = load_contract_fixture(
            FIXTURES / "hosted_tools_contract.json"
        )
        expected_extension = load_contract_fixture(
            FIXTURES / "local_extension_contract.json"
        )
        async with fake_mcp_session() as session:
            actual = normalize_tools((await session.list_tools()).tools)
        actual_hosted = {
            name: contract
            for name, contract in actual.items()
            if name != "update_file"
        }
        actual_extension = {"update_file": actual["update_file"]}
        self.assertEqual(
            expected_hosted,
            actual_hosted,
            contract_diff(expected_hosted, actual_hosted),
        )
        self.assertEqual(
            expected_extension,
            actual_extension,
            contract_diff(expected_extension, actual_extension),
        )

    async def test_annotations_classify_every_side_effect(self):
        async with fake_mcp_session() as session:
            actual = normalize_tools((await session.list_tools()).tools)
        self.assertEqual(
            actual["download_file_content"]["annotations"],
            {
                "destructiveHint": True,
                "idempotentHint": False,
                "openWorldHint": True,
                "readOnlyHint": False,
            },
        )
        for name in ("create_file", "copy_file"):
            self.assertFalse(actual[name]["annotations"]["readOnlyHint"])
            self.assertFalse(actual[name]["annotations"]["destructiveHint"])
            self.assertFalse(actual[name]["annotations"]["idempotentHint"])
        self.assertTrue(actual["update_file"]["annotations"]["destructiveHint"])

    async def test_drive_read_only_registration_and_retained_contracts(self):
        async with fake_mcp_session() as default_session:
            default_tools = normalize_tools((await default_session.list_tools()).tools)
        async with fake_mcp_session(drive_read_only=True) as read_only_session:
            read_only_tools = normalize_tools(
                (await read_only_session.list_tools()).tools
            )
            omitted_call = await read_only_session.call_tool(
                "create_file", {"name": "Denied.txt", "content": "denied"}
            )
        self.assertEqual(
            set(read_only_tools),
            {
                "search_files",
                "read_file_content",
                "list_recent_files",
                "get_file_metadata",
                "download_file_content",
                "get_file_permissions",
            },
        )
        self.assertEqual(
            read_only_tools,
            {name: default_tools[name] for name in read_only_tools},
        )
        self.assertTrue(omitted_call.is_error)


if __name__ == "__main__":
    unittest.main()
