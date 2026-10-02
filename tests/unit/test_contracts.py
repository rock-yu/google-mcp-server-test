import copy
import unittest
from pathlib import Path

from tests.support.contracts import (
    allows_missing_value,
    contract_diff,
    load_json,
    normalize_tool,
    validate_deviations,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


class SchemaNormalizerTests(unittest.TestCase):
    def setUp(self):
        self.tool = {
            "name": "example",
            "description": "generated prose",
            "inputSchema": {
                "title": "GeneratedModel",
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "mode": {
                        "title": "Mode",
                        "type": "string",
                        "default": "a",
                        "enum": ["a", "b"],
                    }
                },
                "required": ["mode"],
            },
            "outputSchema": {"type": "string"},
            "annotations": {"readOnlyHint": True},
        }

    def test_removes_only_documented_generated_noise(self):
        normalized = normalize_tool(self.tool)
        self.assertNotIn("description", normalized)
        self.assertNotIn("title", normalized["inputSchema"])
        self.assertNotIn("title", normalized["inputSchema"]["properties"]["mode"])
        self.assertEqual(
            normalized["inputSchema"]["properties"]["title"], {"type": "string"}
        )
        self.assertEqual(normalized["inputSchema"]["properties"]["mode"]["default"], "a")
        self.assertEqual(normalized["annotations"], {"readOnlyHint": True})

    def test_mutations_to_retained_surfaces_produce_a_diff(self):
        retained_mutations = (
            ("name", "changed"),
            ("inputSchema.type", "array"),
            ("inputSchema.required", []),
            ("inputSchema.properties.mode.type", "integer"),
            ("inputSchema.properties.mode.default", "b"),
            ("inputSchema.properties.mode.enum", ["a"]),
            ("outputSchema.type", "object"),
            ("annotations.readOnlyHint", False),
        )
        expected = normalize_tool(self.tool)
        for path, value in retained_mutations:
            with self.subTest(path=path):
                changed = copy.deepcopy(self.tool)
                target = changed
                parts = path.split(".")
                for part in parts[:-1]:
                    target = target[part]
                target[parts[-1]] = value
                self.assertTrue(contract_diff(expected, normalize_tool(changed)))


class DeviationTests(unittest.TestCase):
    def test_known_deviation_is_narrowly_accepted(self):
        registry = load_json(FIXTURES / "deviations.json")
        self.assertTrue(
            allows_missing_value(
                registry,
                tool="search_files",
                surface="result.files",
                field="contentSnippet",
            )
        )
        self.assertFalse(
            allows_missing_value(
                registry, tool="search_files", surface="result.files", field="owner"
            )
        )

    def test_expired_and_overbroad_deviations_fail(self):
        registry = load_json(FIXTURES / "deviations.json")
        expired = copy.deepcopy(registry)
        expired["deviations"][0]["expires"] = "2026-01-01"
        with self.assertRaisesRegex(ValueError, "expired"):
            validate_deviations(expired)
        broad = copy.deepcopy(registry)
        broad["deviations"][0]["rule"] = "ignore-tool"
        with self.assertRaisesRegex(ValueError, "over-broad"):
            validate_deviations(broad)


if __name__ == "__main__":
    unittest.main()
