# drive-mcp-conformance Specification

## Purpose

Provide deterministic, reviewable evidence that the local Drive MCP server's public
schemas and observable behavior remain compatible with the hosted contract without
requiring credentials or network access in normal development and CI.

## Requirements

### Requirement: Hermetic Drive simulation
The repository SHALL provide a deterministic Drive simulation that supports every
Drive operation used by the nine local tools. The simulation SHALL model files,
folders, content, pagination, permissions, writes, optional metadata, and controlled
API failures without accessing Google APIs, credentials, or the network.

#### Scenario: Full toolset can run without credentials
- **WHEN** the hermetic suite exercises each local MCP tool
- **THEN** every Drive operation is served by deterministic test data without reading
  OAuth files or making network requests

#### Scenario: Error behavior is deterministic
- **WHEN** a conformance case requests a configured inaccessible file, insufficient
  scope, invalid page token, or other simulated API failure
- **THEN** the local server returns the expected MCP error result consistently

### Requirement: Real stdio MCP boundary verification
The conformance suite SHALL launch the actual registered MCP server over stdio with
the simulated Drive backend and SHALL verify behavior through MCP `initialize`,
`tools/list`, and `tools/call` operations rather than calling tool functions directly.

#### Scenario: Public schemas are observed through tools/list
- **WHEN** the conformance suite requests `tools/list`
- **THEN** it verifies each tool's public name, input schema, output schema when
  applicable, defaults, required fields, and annotations

#### Scenario: Structured calls cross the protocol boundary
- **WHEN** the suite invokes a structured read tool with `tools/call`
- **THEN** it validates the serialized structured content and MCP error flag exposed
  to a client

### Requirement: Reviewed hosted contract fixture
The repository SHALL contain a normalized, human-reviewable fixture representing the
hosted server's eight tool contracts. Normal conformance tests SHALL compare local
schemas with this checked-in fixture and SHALL not contact the hosted service.

#### Scenario: Schema regression fails hermetically
- **WHEN** a local tool's normalized schema differs from the reviewed hosted fixture
  outside an approved deviation
- **THEN** the hermetic conformance suite fails with a readable contract diff

#### Scenario: Local-only extension is checked separately
- **WHEN** the suite validates `update_file`
- **THEN** it verifies the tool against an explicit local-extension fixture rather
  than treating its absence from the hosted fixture as a failure

### Requirement: Semantic conformance cases
The repository SHALL define deterministic semantic cases for all eight hosted tool
counterparts. Cases SHALL verify hosted success behavior, optional inputs, output
values, format-specific behavior, authorization failures, inaccessible resources,
and controlled backend failures using logical fixture identities instead of
environment-specific IDs.

#### Scenario: Search semantics are verified
- **WHEN** semantic cases exercise hosted query terms, operators, grouping, paging,
  trashed exclusion, and malformed expressions
- **THEN** local MCP results contain exactly the files and errors described by the
  deterministic dataset

#### Scenario: Unstable values use semantic assertions
- **WHEN** a result contains a page token, URL, timestamp, generated id, or
  environment-specific path
- **THEN** the suite verifies its usability or contract properties rather than
  requiring an unrelated literal hosted value

#### Scenario: Content reading semantics are verified
- **WHEN** semantic cases read native text, Google Docs, Sheets, Slides, binary
  content, missing files, and inaccessible files
- **THEN** the returned text, export form, binary response, and MCP errors match the
  reviewed hosted behavior

#### Scenario: Download semantics are verified
- **WHEN** semantic cases download binary and Google-native files with default and
  caller-selected paths
- **THEN** the written bytes, returned path properties, byte count, overwrite
  behavior, and MCP errors match the reviewed contract

#### Scenario: Create semantics are verified
- **WHEN** semantic cases create text with default and explicit MIME types, with and
  without a parent, and with insufficient write scope or backend failure
- **THEN** the resulting Drive record and MCP result or error match the reviewed
  contract

#### Scenario: Copy semantics are verified
- **WHEN** semantic cases copy a file with default and explicit names and parents,
  including inaccessible sources, insufficient write scope, and backend failure
- **THEN** the resulting Drive record and MCP result or error match the reviewed
  contract

#### Scenario: Permission semantics are verified
- **WHEN** semantic cases inspect files with multiple, sparse, empty, inaccessible,
  or failing permission results
- **THEN** the serialized identities and MCP results or errors match the reviewed
  contract

### Requirement: Safety contract conformance
The hermetic stdio suite SHALL verify tool annotations and mode-dependent
registration as public MCP contract surfaces. The checks SHALL fail when a tool is
misclassified, a Drive mutation tool appears in read-only mode, or a retained tool's
schema changes between modes.

#### Scenario: Default annotations match policy
- **WHEN** the suite requests `tools/list` in default mode
- **THEN** every local tool exposes the exact reviewed read-only, destructive,
  idempotent, and open-world annotation values

#### Scenario: Read-only registration is enforced
- **WHEN** the suite launches the server in Drive read-only mode
- **THEN** the three Drive mutation tools are absent and calls to their names fail
  as unknown tools

#### Scenario: Retained contracts do not drift between modes
- **WHEN** the suite compares tools present in both default and read-only modes
- **THEN** their descriptions, schemas, and annotations are identical

#### Scenario: Safety checks remain credential-free
- **WHEN** the canonical verification command exercises both registration modes
- **THEN** the checks use the deterministic Drive simulation without OAuth files or
  network access

### Requirement: Explicit conformance deviations
The repository SHALL maintain a structured registry of intentional hosted/local
differences. Each deviation SHALL identify the tool, contract surface, rationale,
and comparison rule, and the conformance suite SHALL fail on an unregistered
difference.

#### Scenario: Generated content snippet is registered
- **WHEN** read-tool results are compared with the hosted contract
- **THEN** absence of Google's generated `contentSnippet` value is accepted only
  through its named deviation entry

#### Scenario: Unknown difference fails
- **WHEN** local behavior differs from the reviewed contract and no matching
  deviation exists
- **THEN** the conformance suite reports a failure rather than silently weakening
  the comparison

### Requirement: Gated live observation
Credentialed local-Drive tests and hosted-MCP observation SHALL be opt-in and
separate from the default hermetic suite. Hosted observation SHALL produce a
reviewable normalized diff and SHALL never directly overwrite the curated contract
fixture.

#### Scenario: Default verification is offline
- **WHEN** a developer or pull-request job runs the canonical verification command
- **THEN** no credentialed or network-dependent test is executed

#### Scenario: Hosted contract drift is observed
- **WHEN** an authorized operator explicitly runs hosted observation
- **THEN** the process captures current hosted schemas and reports their normalized
  differences from the curated fixture for human review

### Requirement: Canonical automated verification
The repository SHALL provide one documented verification command that runs the
hermetic unit and MCP conformance suites, Python compile checks, and strict OpenSpec
validation. Pull-request CI SHALL run that command without repository secrets.

#### Scenario: Clean checkout passes verification
- **WHEN** dependencies are installed in a clean checkout and the canonical command
  is run without credentials
- **THEN** all required checks execute and report a single success or failure status

#### Scenario: CI requires no Drive secrets
- **WHEN** the verification workflow runs for a pull request
- **THEN** it does not request OAuth keys, user tokens, hosted credentials, or network
  access beyond dependency installation
