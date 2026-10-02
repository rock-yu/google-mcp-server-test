# Spec Delta

## MODIFIED Requirements

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

## ADDED Requirements

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
