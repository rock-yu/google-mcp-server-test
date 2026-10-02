from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

ROOT = Path(__file__).resolve().parents[2]


@asynccontextmanager
async def fake_mcp_session(
    *,
    read_only: bool = False,
    drive_read_only: bool = False,
    cwd: Path | None = None,
    audit_path: Path | None = None,
):
    env = dict(os.environ)
    env.update(
        {
            "GDRIVE_OAUTH_PATH": str(ROOT / "tests" / "fixtures" / "missing-oauth.json"),
            "GDRIVE_CREDENTIALS_PATH": str(
                ROOT / "tests" / "fixtures" / "missing-credentials.json"
            ),
        }
    )
    env.pop("FAKE_DRIVE_READ_ONLY", None)
    env.pop("DRIVE_MCP_READ_ONLY", None)
    env.pop("FAKE_DRIVE_AUDIT_PATH", None)
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, (str(ROOT), env.get("PYTHONPATH")))
    )
    if read_only:
        env["FAKE_DRIVE_READ_ONLY"] = "1"
    if drive_read_only:
        env["DRIVE_MCP_READ_ONLY"] = "1"
    if audit_path:
        env["FAKE_DRIVE_AUDIT_PATH"] = str(audit_path)
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "tests.support.fake_server"],
        cwd=cwd or ROOT,
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
