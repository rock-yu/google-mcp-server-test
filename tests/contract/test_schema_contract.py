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


if __name__ == "__main__":
    unittest.main()
