# Proposal

## Why

The conformance harness verifies schemas for all hosted counterparts but only proves
response semantics for three read tools, leaving five tools protected by smoke tests
rather than an explicit compatibility contract. The server also advertises Drive and
local-filesystem side effects without machine-readable MCP safety annotations or a
way to expose a strictly non-mutating Drive toolset.

## What Changes

- Extend deterministic semantic conformance through the real stdio MCP boundary to
  `read_file_content`, `download_file_content`, `create_file`, `copy_file`, and
  `get_file_permissions`.
- Cover hosted success behavior, Google-native export behavior, binary handling,
  optional inputs, returned values, authorization failures, inaccessible resources,
  and controlled backend failures for those tools.
- Register explicit MCP tool annotations that distinguish non-mutating Drive reads,
  local filesystem writes, additive Drive writes, and destructive metadata updates.
- Add a configurable read-only server mode that omits Drive-mutating tools from
  `tools/list` and rejects calls to their names because they are not registered.
- Keep the current default mode and all existing tool input/output contracts
  unchanged.
- Document the annotation policy, read-only configuration, and the expanded meaning
  of semantic conformance.
- Keep download-path sandboxing, credential-storage hardening, packaging changes,
  and hosted fixture auto-approval outside this change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `drive-mcp-server`: Add machine-readable side-effect classifications and an
  optional read-only registration mode while preserving the default nine-tool
  interface.
- `drive-mcp-conformance`: Require deterministic semantic cases for all eight hosted
  counterparts and verification of safety annotations and mode-dependent tool
  registration over stdio.

## Impact

- Affected runtime: `drive-mcp-server/server.py` tool registration and startup
  configuration.
- Affected test infrastructure: fake Drive failure cases, semantic fixtures,
  normalized hosted/local contracts, stdio session helpers, and contract tests.
- Affected documentation: root and server README configuration, safety model, and
  conformance scope.
- No new network dependency, OAuth scope, hosted credential, or default behavior is
  introduced.
