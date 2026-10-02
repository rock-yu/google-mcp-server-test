import json
import tempfile
import unittest
from pathlib import Path

from tests.live.capture_hosted_contract import write_candidate
from tests.support.contracts import load_contract_fixture

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


class HostedCaptureTests(unittest.TestCase):
    def test_recorded_tools_produce_candidate_and_reviewable_diff(self):
        curated = FIXTURES / "hosted_tools_contract.json"
        tools = list(load_contract_fixture(curated).values())
        tools[0]["inputSchema"]["properties"]["drift"] = {"type": "string"}
        tools[0]["authorization"] = "secret"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "candidate.json"
            diff = write_candidate(tools, output, curated)
            candidate = json.loads(output.read_text())
        self.assertIn("+", diff)
        self.assertIn("drift", diff)
        self.assertNotIn("authorization", json.dumps(candidate).lower())

    def test_refuses_to_overwrite_curated_fixture(self):
        curated = FIXTURES / "hosted_tools_contract.json"
        with self.assertRaisesRegex(ValueError, "must not overwrite"):
            write_candidate([], curated, curated)


if __name__ == "__main__":
    unittest.main()
