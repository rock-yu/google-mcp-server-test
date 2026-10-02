#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def verification_commands() -> list[list[str]]:
    return [
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-p",
            "test*.py",
            "-v",
        ],
        [
            sys.executable,
            "-m",
            "compileall",
            "-q",
            "drive-mcp-server",
            "gdrive-cli",
            "tests",
            "verify.py",
        ],
        ["openspec", "validate", "--all", "--strict"],
    ]


def run_commands(commands, runner=subprocess.run) -> int:
    for command in commands:
        print(f"+ {' '.join(command)}", flush=True)
        completed = runner(command, cwd=ROOT)
        if completed.returncode:
            return completed.returncode
    return 0


def main() -> int:
    return run_commands(verification_commands())


if __name__ == "__main__":
    raise SystemExit(main())
