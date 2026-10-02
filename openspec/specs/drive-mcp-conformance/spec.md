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
The repository SHALL define deterministic semantic cases for `search_files`,
`list_recent_files`, and `get_file_metadata`. Cases SHALL verify filtering, ordering,
pagination, hosted field names and values, optional-field behavior, and invalid-input
errors using logical fixture identities instead of environment-specific IDs.

#### Scenario: Search semantics are verified
- **WHEN** semantic cases exercise hosted query terms, operators, grouping, paging,
  trashed exclusion, and malformed expressions
- **THEN** local MCP results contain exactly the files and errors described by the
  deterministic dataset

#### Scenario: Unstable values use semantic assertions
- **WHEN** a result contains a page token, URL, timestamp, or environment-specific id
- **THEN** the suite verifies its usability or contract properties rather than
  requiring an unrelated literal hosted value

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
