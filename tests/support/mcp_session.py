from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

ROOT = Path(__file__).resolve().parents[2]


@asynccontextmanager
async def fake_mcp_session(*, read_only: bool = False):
    env = dict(os.environ)
    env.update(
        {
            "GDRIVE_OAUTH_PATH": str(ROOT / "tests" / "fixtures" / "missing-oauth.json"),
            "GDRIVE_CREDENTIALS_PATH": str(
                ROOT / "tests" / "fixtures" / "missing-credentials.json"
            ),
        }
    )
    if read_only:
        env["FAKE_DRIVE_READ_ONLY"] = "1"
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "tests.support.fake_server"],
        cwd=ROOT,
        env=env,
    )
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


def text_content(result) -> str:
    return "\n".join(
        content.text for content in result.content if getattr(content, "type", None) == "text"
    )
