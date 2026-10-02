# Spec Delta

## MODIFIED Requirements

### Requirement: Local stdio MCP transport
The server SHALL run as a local process that speaks the Model Context Protocol over stdio, and SHALL advertise its available tools in response to an MCP `tools/list` request.

#### Scenario: Client launches the server
- **WHEN** an MCP client launches the server as a stdio subprocess
- **THEN** the server completes the MCP initialize handshake and is ready to receive tool calls

#### Scenario: Client lists tools
- **WHEN** an MCP client sends a `tools/list` request without read-only mode enabled
- **THEN** the server returns tool specifications for `search_files`, `read_file_content`, `list_recent_files`, `get_file_metadata`, `download_file_content`, `create_file`, `copy_file`, `get_file_permissions`, and `update_file`, each with a name, description, input schema, and safety annotations

## ADDED Requirements

### Requirement: MCP tool side-effect annotations
Every advertised tool SHALL include MCP annotations that conservatively identify
whether it is read-only, destructive, and idempotent. A tool that writes to the
local filesystem or Google Drive SHALL NOT be marked read-only, and a tool that can
overwrite or mutate existing state SHALL be marked destructive.

#### Scenario: Drive read tools are classified as read-only
- **WHEN** a client lists `search_files`, `read_file_content`,
  `list_recent_files`, `get_file_metadata`, or `get_file_permissions`
- **THEN** each tool is annotated as read-only, non-destructive, and idempotent

#### Scenario: Download exposes its local side effect
- **WHEN** a client lists `download_file_content`
- **THEN** the tool is not annotated as read-only and is marked destructive because
  it can overwrite a caller-selected local path

#### Scenario: Additive Drive writes are classified conservatively
- **WHEN** a client lists `create_file` or `copy_file`
- **THEN** each tool is not annotated as read-only or idempotent and is annotated as
  non-destructive because it creates a new Drive resource

#### Scenario: Metadata update exposes destructive mutation
- **WHEN** a client lists `update_file`
- **THEN** the tool is not annotated as read-only or idempotent and is marked
  destructive because it renames or moves an existing Drive resource

### Requirement: Configurable Drive read-only mode
The server SHALL support an opt-in Drive read-only mode that does not register
tools capable of mutating Google Drive. The mode SHALL preserve read and download
tools, SHALL be observable through `tools/list`, and SHALL leave the current
nine-tool registration as the default.

#### Scenario: Read-only mode omits Drive mutation tools
- **WHEN** the server starts with Drive read-only mode enabled
- **THEN** `tools/list` omits `create_file`, `copy_file`, and `update_file`

#### Scenario: Read tools remain available
- **WHEN** the server runs in Drive read-only mode
- **THEN** `search_files`, `read_file_content`, `list_recent_files`,
  `get_file_metadata`, `download_file_content`, and `get_file_permissions` remain
  registered with their normal contracts

#### Scenario: Omitted write tool cannot be called
- **WHEN** a client calls the name of a Drive mutation tool while read-only mode is
  enabled
- **THEN** the MCP server rejects the request because that tool is not registered

#### Scenario: Default mode remains compatible
- **WHEN** the read-only setting is absent or disabled
- **THEN** all nine existing local tools remain registered with unchanged input and
  output contracts
