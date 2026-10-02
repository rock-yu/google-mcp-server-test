from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from tests.support.contracts import contract_diff, load_contract_fixture, normalize_tools

DEFAULT_URL = "https://drivemcp.googleapis.com/mcp/v1"
CURATED_FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "hosted_tools_contract.json"
)
SENSITIVE_KEYS = {"authorization", "token", "access_token", "refresh_token", "secret"}


def redact(value):
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, dict):
        return {
            key: ("[REDACTED]" if key.lower() in SENSITIVE_KEYS else redact(item))
            for key, item in value.items()
        }
    return value


def write_candidate(tools, output: Path, curated: Path = CURATED_FIXTURE) -> str:
    if output.resolve() == curated.resolve():
        raise ValueError("candidate output must not overwrite the curated fixture")
    normalized = redact(normalize_tools(tools))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(normalized, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    expected = load_contract_fixture(curated)
    return contract_diff(expected, normalized)


async def capture(url: str, output: Path, curated: Path) -> str:
    token = os.environ.get("HOSTED_MCP_BEARER_TOKEN")
    if not token:
        raise RuntimeError("HOSTED_MCP_BEARER_TOKEN is required")
    import httpx2

    async with httpx2.AsyncClient(
        headers={"Authorization": f"Bearer {token}"}
    ) as http_client:
        async with streamable_http_client(url, http_client=http_client) as streams:
            read, write = streams[:2]
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = (await session.list_tools()).tools
    return write_candidate(tools, output, curated)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Capture a review candidate; never updates the curated fixture."
    )
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--curated", type=Path, default=CURATED_FIXTURE)
    args = parser.parse_args()
    diff = asyncio.run(capture(args.url, args.output, args.curated))
    print(diff or "No normalized contract differences.")


if __name__ == "__main__":
    main()
