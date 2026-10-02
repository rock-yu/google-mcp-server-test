# Design

## Context

See proposal.md - Why. The repository currently has one `unittest` module with 11
tests for query translation, hosted-file mapping, and selected `files.list` /
`files.get` request arguments. The real MCP boundary, six tool paths, output-schema
serialization, and error mapping are verified only through transient live scripts.
The server creates and caches its authenticated Drive service globally, so a stdio
subprocess currently cannot receive a fake service without credentials.

Google's hosted Drive MCP server is a Developer Preview. Its schemas can drift, while
live responses contain unstable ids, timestamps, URLs, and page tokens and require
managed authorization. Normal CI therefore cannot use the hosted service as a direct,
automatic oracle.

## Goals / Non-Goals

**Goals:**
- Make the default verification path deterministic, offline after dependency
  installation, and credential-free.
- Exercise the real stdio protocol and registered tool schemas.
- Distinguish exact schema parity, semantic parity, and approved deviations.
- Detect hosted contract drift without allowing an external preview service to
  rewrite repository truth automatically.

**Non-Goals:**
- Completing hosted parity for tools that currently have lightweight local behavior.
- Reorganizing the application into a distributable Python package.
- Emulating every undocumented Google Drive behavior.
- Running credentialed tests for untrusted pull requests.

## Decisions

### D1: Three verification layers

Use three explicitly separated layers:

1. **Unit tests** validate pure mapping, query translation, and request construction.
2. **Hermetic MCP conformance tests** start the real stdio server with a deterministic
   Drive backend and use only MCP client operations.
3. **Live observation tests** target real Drive or the hosted MCP server only when
   explicitly selected and configured.

Only layers 1 and 2 are required by the canonical command and pull-request CI.

*Alternative:* use live Drive as the main integration environment. Rejected because
it is nondeterministic, credentialed, quota-dependent, and unavailable to forks.

### D2: Minimal subprocess injection seam

Keep the production server's default authentication path unchanged. Extract server
construction/service configuration just enough for a dedicated test entrypoint to
install a fake service and fake credentials before running the same registered
`MCPServer` over stdio. Do not add a production environment variable that imports an
arbitrary factory by name.

The test subprocess therefore exercises the same tool registration and protocol
stack while avoiding OAuth startup.

*Alternative:* call decorated Python functions in-process. Rejected because it does
not verify `tools/list`, JSON schema generation, MCP serialization, or `is_error`.

### D3: Deterministic fake Drive at the googleapiclient boundary

Implement the subset of resource/request methods consumed by the code:

```text
FakeDriveService
  files()
    list / get / get_media / export / create / copy / update
  permissions()
    list
```

Requests retain their keyword arguments for assertions and return deterministic
fixtures from `execute()` / download chunks. The dataset includes nested/root
folders, native and binary files, shared and trashed files, missing optional fields,
permissions, enough files for paging, and named failure cases.

This boundary minimizes application changes and lets existing Drive helpers run
unchanged. It is not intended to be a general Drive API emulator.

### D4: Standard-library tests and JSON fixtures

Retain `unittest` and use JSON for datasets, contract snapshots, semantic cases, and
deviations. This avoids adding a test framework or YAML parser solely for the
harness. Use `IsolatedAsyncioTestCase` for MCP client sessions.

Organize new material under:

```text
tests/
  unit/
  contract/
  live/
  support/
  fixtures/
```

Move or adapt the existing helper tests into the canonical discovery path without
reducing their coverage.

### D5: Normalize schemas before comparison

Store a reviewed snapshot for the eight hosted tools and a separate local-extension
snapshot for `update_file`. Normalization preserves behaviorally meaningful values:
property names, JSON types, required fields, defaults, enum values, nested shapes,
and MCP annotations. It removes unstable or non-contractual noise such as generated
model titles, definition ordering, and description prose.

Schema comparison is exact after normalization. Local differences require a named
entry in the deviations registry; tests cannot update snapshots.

### D6: Semantic cases, not literal hosted responses

Represent expectations with logical fixture identities and predicates. Compare exact
tool behavior where deterministic, but treat page tokens as opaque usable values,
validate timestamp/URL formats, and map fixture identities instead of comparing
unrelated hosted and local file ids.

Initial semantic coverage targets the three tools whose local contracts intentionally
match hosted behavior. The other tools receive schema and regression coverage but no
new parity claim.

### D7: Reviewed fixture plus drift observation

Normal tests read the checked-in hosted snapshot. A separate capture utility can call
the hosted server, normalize `tools/list`, and write a candidate artifact or diff to
a temporary/output location. It MUST NOT modify the reviewed fixture directly.

A manual workflow is sufficient initially; scheduling it later does not change the
contract. Hosted credentials are never available to pull-request jobs.

### D8: One Python verification entrypoint

Provide a cross-platform repository script as the canonical command. It runs unit and
hermetic contract discovery, compile checks, and `openspec validate --all --strict`
as subprocesses, stops on failure, and returns one exit code. CI invokes that same
entrypoint so local and CI behavior cannot drift.

## Risks / Trade-offs

- [Fake behavior diverges from Google] -> Keep the fake deliberately narrow; verify
  outbound request construction in unit tests and retain opt-in live observations.
- [Snapshot becomes stale] -> Hosted capture produces a reviewable drift diff; never
  silently bless new schemas.
- [Normalization hides a meaningful change] -> Maintain an allowlist of removed
  fields and test the normalizer itself with behaviorally significant mutations.
- [Test injection accidentally changes production startup] -> Keep production
  defaults unchanged and use a dedicated test entrypoint, not dynamic import config.
- [Semantic parity claims exceed coverage] -> Report conformance by surface and tool;
  register deviations explicitly and scope initial semantic cases to three tools.
- [Live tests expose secrets or private metadata] -> Require dedicated test accounts,
  redact captured values, and keep live outputs out of version control.

## Migration Plan

1. Introduce the injection seam and fake backend while retaining existing tests.
2. Add hermetic MCP schema and semantic cases, then move existing unit coverage into
   canonical discovery.
3. Add fixtures, deviation handling, and the verification command.
4. Enable credential-free CI only after the command passes from a clean checkout.
5. Add hosted observation as an opt-in workflow; no production deployment migration
   is required.

Rollback consists of removing the test-only harness, CI workflow, and injection seam;
the production Drive/OAuth path remains the default throughout.
