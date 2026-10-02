from __future__ import annotations

import difflib
import json
from pathlib import Path

SCHEMA_NOISE_FIELDS = {"title", "description"}


def normalize_schema(value, *, property_map: bool = False):
    if isinstance(value, list):
        return [normalize_schema(item) for item in value]
    if not isinstance(value, dict):
        return value
    if property_map:
        return {
            key: normalize_schema(value[key])
            for key in sorted(value)
        }
    return {
        key: normalize_schema(
            value[key],
            property_map=key in {"properties", "$defs"},
        )
        for key in sorted(value)
        if key not in SCHEMA_NOISE_FIELDS
    }


def normalize_tool(tool) -> dict:
    if hasattr(tool, "model_dump"):
        tool = tool.model_dump(by_alias=True, exclude_none=True)
    normalized = {
        "name": tool["name"],
        "inputSchema": normalize_schema(
            tool.get("inputSchema", tool.get("input_schema", {}))
        ),
    }
    output = tool.get("outputSchema", tool.get("output_schema"))
    if output is not None:
        normalized["outputSchema"] = normalize_schema(output)
    annotations = tool.get("annotations")
    if annotations:
        normalized["annotations"] = normalize_schema(annotations)
    return normalized


def normalize_tools(tools) -> dict:
    return {
        tool["name"]: tool
        for tool in sorted((normalize_tool(tool) for tool in tools), key=lambda item: item["name"])
    }


def contract_diff(expected: dict, actual: dict) -> str:
    expected_text = json.dumps(expected, indent=2, sort_keys=True).splitlines()
    actual_text = json.dumps(actual, indent=2, sort_keys=True).splitlines()
    return "\n".join(
        difflib.unified_diff(
            expected_text,
            actual_text,
            fromfile="reviewed-contract",
            tofile="local-tools-list",
            lineterm="",
        )
    )


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_contract_fixture(path: Path) -> dict:
    fixture = load_json(path)
    common = fixture.get("commonSchemas", {})
    result = {}
    for name, contract in fixture["tools"].items():
        expanded = {"name": name, "inputSchema": contract["inputSchema"]}
        if "outputSchemaRef" in contract:
            expanded["outputSchema"] = common[contract["outputSchemaRef"]]
        elif "outputSchema" in contract:
            expanded["outputSchema"] = contract["outputSchema"]
        if "annotations" in contract:
            expanded["annotations"] = contract["annotations"]
        result[name] = normalize_tool(expanded)
    return result


def validate_deviations(registry: dict) -> None:
    required = {"id", "tool", "surface", "rationale", "rule", "expires"}
    seen: set[str] = set()
    for deviation in registry.get("deviations", []):
        missing = required - deviation.keys()
        if missing:
            raise ValueError(f"deviation lacks fields: {', '.join(sorted(missing))}")
        if deviation["id"] in seen:
            raise ValueError(f"duplicate deviation id: {deviation['id']}")
        seen.add(deviation["id"])
        if deviation["expires"] is not None:
            raise ValueError(f"expired deviation: {deviation['id']}")
        if deviation["rule"] != "allow-missing-value":
            raise ValueError(f"over-broad deviation rule: {deviation['rule']}")


def allows_missing_value(
    registry: dict, *, tool: str, surface: str, field: str
) -> bool:
    validate_deviations(registry)
    matches = [
        deviation
        for deviation in registry["deviations"]
        if deviation["tool"] == tool
        and deviation["surface"] == surface
        and deviation.get("field") == field
    ]
    if len(matches) != 1:
        return False
    return matches[0]["rule"] == "allow-missing-value"
