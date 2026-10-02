# Local Google Drive MCP server

This repository contains a Python stdio MCP server modeled on Google's hosted
Drive MCP endpoint. It exposes the hosted server's eight tools plus the local-only
`update_file` metadata extension. See
[`drive-mcp-server/README.md`](drive-mcp-server/README.md) for tool contracts,
OAuth setup, and VS Code integration.

## Credential-free verification

Create the server virtual environment and install the pinned dependencies:

```bash
python -m venv drive-mcp-server/.venv
drive-mcp-server/.venv/bin/python -m pip install \
  -r drive-mcp-server/requirements.txt
drive-mcp-server/.venv/bin/python verify.py
```

`verify.py` is the canonical local and CI command. It runs:

1. Standard-library unit tests.
2. Hermetic contract tests against the real MCP server over stdio.
3. Python compile checks.
4. Strict validation of every OpenSpec change and specification.

No Google OAuth files, Drive account, hosted MCP credential, or external network
access is needed. The test server injects a deterministic fake at the
`googleapiclient` boundary and denies OAuth/network fallback.

## What conformance means

The harness checks all nine local tools across the MCP protocol boundary. It
compares the eight hosted counterparts with the reviewed normalized contract in
[`tests/fixtures/hosted_tools_contract.json`](tests/fixtures/hosted_tools_contract.json);
`update_file` has a separate local-extension fixture. Semantic parity cases cover
`search_files`, `list_recent_files`, and `get_file_metadata`.

Semantic cases cover all eight hosted counterparts. They verify structured search,
recent-file and metadata behavior; native and Google-format reads and downloads;
create/copy state transitions and authorization failures; and permission
serialization and errors. Google's hosted layer generates `contentSnippet`, while
Drive API v3 does not expose an equivalent. Its absent local value is the only
approved read-tool deviation and is registered narrowly in
[`tests/fixtures/deviations.json`](tests/fixtures/deviations.json).

The suite also checks MCP safety annotations and both tool-registration modes.
Set `DRIVE_MCP_READ_ONLY=1` before starting the server to omit the three tools that
mutate Drive (`create_file`, `copy_file`, and `update_file`). Download remains
available because this mode protects Drive state, not the local filesystem;
`download_file_content` is annotated as destructive because it may overwrite its
selected local path.

## Opt-in live checks

Live checks are excluded from normal verification and should use a dedicated test
account containing no personal or production data.

```bash
# Local Drive API smoke test; uses the normal GDRIVE_* credential paths.
RUN_LIVE_DRIVE_TESTS=1 \
  drive-mcp-server/.venv/bin/python -m unittest \
  tests.live.test_live_drive -v

# Hosted tools/list smoke test.
RUN_HOSTED_MCP_TESTS=1 \
HOSTED_MCP_BEARER_TOKEN='...' \
  drive-mcp-server/.venv/bin/python -m unittest \
  tests.live.test_hosted_mcp -v
```

To create a review candidate when the hosted schema may have drifted:

```bash
HOSTED_MCP_BEARER_TOKEN='...' \
  drive-mcp-server/.venv/bin/python -m tests.live.capture_hosted_contract \
  --output /tmp/hosted-drive-contract-candidate.json
```

The capture command redacts recognized credential fields, writes only to the
caller-selected path, prints a normalized diff, and refuses to overwrite the
curated fixture. Review the hosted documentation and diff before manually
updating the fixture or deviations registry. Never commit tokens, captured
private metadata, or unreviewed snapshots.

## Repository layout

```text
drive-mcp-server/   Python MCP server and pinned runtime dependencies
gdrive-cli/         Shared OAuth and Drive API helpers
tests/unit/         Pure helper, fake backend, and normalizer tests
tests/contract/     Real stdio MCP schema and semantic tests
tests/live/         Explicitly enabled credentialed observations
tests/support/      Fake Drive, MCP session, and contract utilities
tests/fixtures/     Reviewed contracts, deviations, and semantic data
openspec/           Runtime specification and change history
verify.py           Canonical credential-free verification entrypoint
```

For OAuth provisioning, follow [`SETUP-GUIDE.md`](SETUP-GUIDE.md). OAuth client
keys and user tokens remain local and are ignored by Git.
