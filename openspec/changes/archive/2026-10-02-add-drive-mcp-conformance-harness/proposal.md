# Proposal

## Why

The local Drive MCP server has focused helper tests and has been verified manually
against live Drive and hosted documentation, but it lacks a repeatable way to prove
that its public MCP contract remains compatible. A hermetic conformance harness is
needed so schema and behavior regressions are caught without personal credentials,
network access, hosted-service availability, or manual scripts.

## What Changes

- Add a deterministic fake Drive backend covering list/get/read/export/download,
  write, permission, pagination, optional-metadata, and API-error behavior.
- Add a subprocess-level MCP harness that starts the real stdio server against the
  fake backend and exercises `initialize`, `tools/list`, and `tools/call`.
- Check in a reviewed, normalized hosted-contract fixture for all eight hosted tool
  schemas, plus regression expectations for the local-only `update_file` extension.
- Add semantic conformance cases for the currently hosted-aligned
  `search_files`, `list_recent_files`, and `get_file_metadata` tools, including
  paging, query filtering, structured output, errors, and known deviations.
- Add an explicit deviations registry, initially recording that Drive v3 cannot
  reproduce the hosted service's generated `contentSnippet` value.
- Separate hermetic tests (required by default) from credentialed local-Drive and
  hosted-MCP observation tests (explicitly opt-in).
- Add a canonical verification command and CI workflow that run hermetic tests,
  compile checks, and strict OpenSpec validation without credentials.
- Document a manual or scheduled hosted-observation workflow that detects contract
  drift and produces a reviewable diff; it SHALL NOT silently rewrite the curated
  fixture or run in ordinary pull-request CI.
- No runtime tool behavior or hosted parity for the remaining five hosted tools is
  added by this change. Packaging and broad source-tree refactoring are also out of
  scope; only the minimum service-injection seam required for hermetic MCP tests is
  introduced.

## Capabilities

### New Capabilities

- `drive-mcp-conformance`: Deterministic verification of local MCP schemas and
  behavior against reviewed hosted contracts, with explicit deviations and
  separately gated live observation.

### Modified Capabilities

<!-- none -->

## Impact

- **Testing:** replaces ad hoc live scripts as the primary evidence for MCP
  compatibility while retaining optional live checks.
- **Server composition:** introduces a narrow, test-only-capable Drive service
  injection seam; public tool contracts remain unchanged.
- **Repository:** adds test support, contract fixtures, conformance cases, a
  deviations registry, CI configuration, and a canonical verification entrypoint.
- **Operations:** normal CI remains network- and credential-free; hosted drift
  observation requires separately managed credentials and explicit execution.
