# Tasks

## 1. Canonical test layout and existing coverage

- [x] 1.1 Create the `tests/unit`, `tests/contract`, `tests/live`,
  `tests/support`, and `tests/fixtures` package structure and verify standard-library
  test discovery imports every package without Drive credentials.
- [x] 1.2 Move or adapt `gdrive-cli/test_gdrive_cli.py` into `tests/unit` without
  reducing its 11 existing cases; verify the relocated suite passes from the
  repository root and the old duplicate is removed.

## 2. Deterministic Drive simulation

- [x] 2.1 Add a JSON Drive dataset containing root/nested folders, native and binary
  files, shared and trashed files, optional metadata gaps, permissions, multiple
  pages, and named failures; verify a fixture-validation test rejects duplicate ids,
  missing required fixture fields, and invalid references.
- [x] 2.2 Implement fake request/download primitives and the `files.list` /
  `files.get` / `files.get_media` / `files.export` operations used by read tools;
  verify unit tests cover filtering, ordering, pagination, media/export bytes,
  invalid tokens, and configured 404/403 failures.
- [x] 2.3 Implement fake `files.create` / `files.copy` / `files.update` and
  `permissions.list` operations, including mutable per-test state; verify unit tests
  cover all three write tools, permission results, parent replacement, and
  insufficient-scope behavior without touching the network or filesystem outside a
  test temporary directory.
- [x] 2.4 Add a network/OAuth tripwire to hermetic tests and verify the full fake
  backend suite fails if credential loading or an external HTTP connection is
  attempted.

## 3. Real stdio MCP harness

- [x] 3.1 Introduce the minimal server service/credential injection seam while
  preserving production startup defaults; verify the existing real-credential smoke
  path still constructs the normal Drive service when no test service is supplied.
- [x] 3.2 Add a dedicated fake-server stdio entrypoint plus reusable asynchronous MCP
  test session helper; verify it completes `initialize` and `tools/list` in a
  subprocess with intentionally missing OAuth files.
- [x] 3.3 Add an all-tools hermetic smoke suite invoking every local tool through
  `tools/call`; verify success and representative `is_error` paths are observed at
  the client protocol boundary and no tool function is called directly by tests.

## 4. Schema contract and deviations

- [x] 4.1 Add and unit-test a schema normalizer that retains names, JSON types,
  properties, required fields, defaults, enums, nested shapes, and annotations while
  removing only documented generated noise; verify mutations to every retained
  surface produce a diff.
- [x] 4.2 Check in the reviewed normalized eight-tool hosted contract and separate
  `update_file` local-extension fixture; verify `tools/list` from the fake stdio
  server matches them or emits a readable per-tool schema diff.
- [x] 4.3 Add the structured deviations registry with the generated
  `contentSnippet` value deviation and a strict matcher; verify the known deviation
  passes and an unregistered, expired, or over-broad deviation fails.

## 5. Semantic conformance cases

- [x] 5.1 Add JSON semantic cases and MCP tests for `search_files` covering every
  documented hosted query term/operator, grouping, parent/owner/shared filters,
  trashed exclusion, invalid input, optional snippets, and multi-page continuation;
  verify expected logical fixture identities and token usability.
- [x] 5.2 Add semantic MCP tests for `list_recent_files` covering all three sort
  modes, defaults, page size/token behavior, optional fields, and invalid ordering;
  verify deterministic result order and hosted field names.
- [x] 5.3 Add semantic MCP tests for `get_file_metadata` covering complete and sparse
  files, owner email semantics, snippet exclusion, and inaccessible ids; verify
  structured output and MCP error results.

## 6. Gated live observation

- [x] 6.1 Add opt-in local-Drive and hosted-MCP test entrypoints that skip unless
  their explicit enable flags and credentials are present; verify default discovery
  reports them skipped and makes no network request.
- [x] 6.2 Add a hosted `tools/list` capture/diff utility that redacts unstable or
  sensitive values and writes only to a caller-selected candidate output; verify it
  refuses to overwrite the curated fixture and produces a reviewable normalized
  diff from a recorded response.
- [x] 6.3 Document dedicated-account expectations, credential handling, fixture
  review, deviation updates, and manual drift observation; verify every documented
  non-live command runs without credentials.

## 7. Canonical verification and CI

- [x] 7.1 Add the cross-platform canonical verification script to run unit and
  hermetic contract suites, Python compile checks, and strict OpenSpec validation;
  verify one invocation succeeds from the repository root and propagates a failing
  subcheck's nonzero exit code.
- [x] 7.2 Add a pull-request CI workflow that installs pinned project dependencies
  and invokes only the canonical verification script, with no Drive/hosted secrets;
  verify the workflow definition contains no credential references and passes in a
  clean local workflow-equivalent environment.
- [x] 7.3 Update the repository and server READMEs with the test layers, canonical
  command, conformance meaning, known deviations, and opt-in live commands; verify a
  new contributor can follow the hermetic setup without OAuth files.

## 8. Final conformance validation

- [x] 8.1 Run the canonical verification command after removing Drive credential
  environment variables and confirm all unit, stdio contract, compile, and strict
  OpenSpec checks pass with no network or personal Drive access.
- [x] 8.2 Run `openspec validate add-drive-mcp-conformance-harness --strict` and
  confirm the completed change passes.
