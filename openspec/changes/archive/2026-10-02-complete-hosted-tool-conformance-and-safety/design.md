# Design

## Context

The server currently registers nine tools directly on one module-level `MCPServer`.
The conformance harness starts that real registration over stdio with an injected
fake Drive service. Contract fixtures retain tool schemas but semantic fixtures cover
only three tools, while one broad stdio smoke test exercises the remaining tools.
See `proposal.md` for motivation and the delta specs for observable requirements.

The MCP SDK supports standard tool annotations on registration. Read-only mode must
change the public `tools/list` surface without changing the default mode or bypassing
the production authentication path.

## Goals / Non-Goals

**Goals:**

- Make one registration policy authoritative for tool availability and annotations.
- Exercise every hosted counterpart through real stdio with deterministic expected
  state transitions, returned values, and errors.
- Preserve existing default tool names, schemas, outputs, and OAuth behavior.
- Keep normal verification credential-free and network-free.

**Non-Goals:**

- Restricting or rewriting caller-selected download paths.
- Moving OAuth tokens or changing Drive scopes.
- Repackaging the sibling Python modules.
- Automatically accepting hosted observations as reviewed fixtures.
- Claiming semantic parity for the local-only `update_file` extension.

## Decisions

### D1: Build each MCP server from one declarative registration policy

Introduce a server-construction/registration boundary that applies each tool's
function, description, and `ToolAnnotations` together. Production startup and the
fake stdio entrypoint will both use this boundary; default construction registers all
nine tools.

This avoids separate conditional logic around decorators and makes it impossible for
read-only mode and annotations to use different tool inventories. Keeping the current
module-level decorators and removing tools after registration was rejected because it
depends on SDK internals and makes repeated test construction unsafe.

### D2: Configure Drive read-only mode at process startup

Use one documented environment setting, `DRIVE_MCP_READ_ONLY`, parsed with the
repository's normal explicit boolean rules. When enabled, registration excludes
`create_file`, `copy_file`, and `update_file`. The setting is fixed for the process
lifetime; changing it requires restarting the stdio server.

`download_file_content` remains available because this mode governs Google Drive
mutation, not all host-side effects. Its local filesystem risk is exposed through
annotations. Inferring mode solely from OAuth scopes was rejected because operators
need to suppress write tools even when credentials are capable of writes.

### D3: Use conservative standard MCP annotations

The registration policy will publish all four standard hints:

| Tool group | readOnly | destructive | idempotent | openWorld |
|---|---:|---:|---:|---:|
| Search, read, recent, metadata, permissions | true | false | true | true |
| Download to local path | false | true | false | true |
| Create and copy | false | false | false | true |
| Update metadata | false | true | false | true |

`download_file_content` is classified as destructive because it may overwrite an
existing path. All tools are open-world because results depend on Google Drive or
write to the caller's environment. Conservative false values are preferred where
backend state can change between identical calls.

### D4: Make semantic cases data-driven and state-aware

Extend the semantic fixture with named cases for the five remaining hosted tools.
Assertions will cover both MCP results and fake-backend state where a tool writes.
Generated ids and temporary paths will be checked by relationship and properties,
not fixed machine-specific strings.

The fake backend will gain narrowly scoped failure and inspection support only where
the cases require it. Tests will continue to call through `ClientSession`; direct
helper tests remain supplemental and cannot satisfy semantic conformance.

### D5: Test both registration modes with the same stdio helper

The stdio session helper will accept an explicit read-only setting and pass it to the
fake server subprocess. Contract tests will compare retained tools between the
default and read-only `tools/list` results and will attempt an omitted tool call to
prove absence is enforced by MCP registration rather than a runtime scope check.

### D6: Keep hosted evidence reviewed and deviations narrow

Expected behavior will be grounded in the checked-in hosted contract, published
hosted documentation, and explicitly reviewed observations. Any confirmed
hosted/local mismatch must be represented as a specific deviation or resolved in the
runtime; tests must not normalize away semantic differences or broaden existing
deviations.

## Risks / Trade-offs

- **[Risk] Refactoring registration changes generated schemas.** → Snapshot normalized
  `tools/list` before and after and require the default fixture comparison to remain
  unchanged except for newly asserted annotations.
- **[Risk] MCP hints are advisory, not authorization.** → Keep OAuth scope checks and
  enforce read-only mode by omitting registrations rather than trusting clients.
- **[Risk] “Read-only” could imply no local writes.** → Name and document it as Drive
  read-only mode, retain download deliberately, and mark download destructive.
- **[Risk] Fake semantics could encode local behavior instead of hosted behavior.** →
  tie each case to reviewed hosted evidence and require explicit deviations for
  confirmed differences.
- **[Risk] Import-time state leaks between mode tests.** → construct independent
  server instances or subprocesses from immutable registration metadata.

## Migration Plan

1. Add annotation and mode-aware registration while keeping default mode enabled.
2. Update fake stdio startup and contract fixtures; verify default schemas remain
   compatible.
3. Add deterministic semantic cases and any required fake-backend controls.
4. Update documentation and run the canonical credential-free verifier.
5. Roll back by restoring unconditional registration; no persisted data or API
   migration is involved.
