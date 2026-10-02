import os
import tempfile
import unittest
from pathlib import Path

from tests.live.capture_hosted_contract import CURATED_FIXTURE, DEFAULT_URL, capture


@unittest.skipUnless(
    os.environ.get("RUN_HOSTED_MCP_TESTS") == "1"
    and bool(os.environ.get("HOSTED_MCP_BEARER_TOKEN")),
    "set RUN_HOSTED_MCP_TESTS=1 and HOSTED_MCP_BEARER_TOKEN",
)
class HostedMcpTests(unittest.IsolatedAsyncioTestCase):
    async def test_capture_current_tools_list(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "hosted-candidate.json"
            await capture(DEFAULT_URL, output, CURATED_FIXTURE)
            self.assertTrue(output.is_file())


if __name__ == "__main__":
    unittest.main()
