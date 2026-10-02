# Tasks

## 1. Authoritative Tool Registration and Annotations

- [x] 1.1 Refactor tool registration behind one reusable server-construction boundary while preserving the default nine-tool names, descriptions, input schemas, output schemas, and production authentication path; verify existing schema-contract and server-injection tests pass
- [x] 1.2 Attach the design's exact four MCP annotation values to every tool and update reviewed contract fixtures/normalization to retain them; verify a stdio `tools/list` contract test asserts every tool's complete annotation object
- [x] 1.3 Add focused tests proving download is classified as a destructive local write, create/copy as additive non-idempotent writes, and update as destructive; verify annotation mutations produce readable contract failures
- [x] 1.4 Document the tool annotation policy and its advisory security limits in `drive-mcp-server/README.md`; verify the documented classifications match the reviewed fixture

## 2. Drive Read-Only Registration Mode

- [x] 2.1 Parse `DRIVE_MCP_READ_ONLY` once at startup and construct a server that omits `create_file`, `copy_file`, and `update_file` only when enabled; verify default construction still advertises all nine tools
- [x] 2.2 Extend the fake stdio entrypoint/session helper to launch either registration mode without credentials; verify independent sessions do not leak registration state
- [x] 2.3 Add stdio contract tests proving read-only `tools/list` contains the six retained tools, retained contracts are identical across modes, and omitted write-tool calls fail as unknown tools
- [x] 2.4 Document configuration, restart semantics, retained download behavior, and the distinction between Drive read-only mode and local filesystem safety; verify the README launch example works with the environment setting

## 3. Read and Download Semantic Conformance

- [x] 3.1 Extend deterministic fixtures with named native-text, Docs, Sheets, Slides, binary, missing, inaccessible, default-download-path, explicit-path, and overwrite cases; verify fixture validation rejects incomplete or contradictory cases
- [x] 3.2 Add real-stdio semantic tests for `read_file_content` covering exact export formats, binary responses, missing files, inaccessible files, and controlled backend errors; verify every case asserts MCP error state and returned content
- [x] 3.3 Add real-stdio semantic tests for `download_file_content` covering binary and Google-native bytes, default and explicit paths, byte counts, overwrite behavior, missing/inaccessible files, and backend errors; verify temporary outputs are isolated and cleaned up
- [x] 3.4 Update conformance documentation to state the reviewed read/download behaviors and any narrowly approved deviations; verify no test weakens normalization to accept an unregistered difference

## 4. Create and Copy Semantic Conformance

- [x] 4.1 Extend the fake Drive backend and semantic fixtures to expose deterministic created/copied records and configured create/copy failures without bypassing the MCP boundary; verify focused fake-backend tests cover the new controls
- [x] 4.2 Add real-stdio `create_file` cases for default and explicit MIME types, root and explicit parents, returned identity, persisted content, insufficient write scope, and backend failure; verify each success asserts resulting fake Drive state
- [x] 4.3 Add real-stdio `copy_file` cases for inherited and explicit names/parents, copied content and metadata, inaccessible sources, insufficient write scope, and backend failure; verify each success asserts source immutability and resulting fake Drive state
- [x] 4.4 Document the confirmed hosted create/copy semantics and any explicit deviations; verify the semantic fixture and README describe the same optional-input behavior

## 5. Permission Semantic Conformance

- [x] 5.1 Extend permission fixtures with multiple grantee types, sparse identities, empty results, inaccessible files, and controlled backend failures; verify dataset validation checks every referenced file and failure
- [x] 5.2 Add real-stdio `get_file_permissions` cases asserting deterministic ordering and serialization for complete, sparse, and empty permissions plus MCP errors for inaccessible and failing requests
- [x] 5.3 Document the reviewed permission output semantics and deviations, if any; verify the documentation matches protocol-level expected values

## 6. Integrated Verification

- [x] 6.1 Run `drive-mcp-server/.venv/bin/python verify.py` with all Drive and hosted credential/live-test environment variables unset and verify unit tests, both stdio registration modes, all eight hosted semantic suites, compile checks, and strict OpenSpec validation pass
- [x] 6.2 Run `git diff --check` and inspect normalized contract diffs to verify the default tool schemas and outputs changed only by the planned annotations and expanded conformance evidence
