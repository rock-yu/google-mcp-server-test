# Spec Delta

## ADDED Requirements

### Requirement: List recent files tool
The `list_recent_files` tool SHALL return the user's most recently modified Drive files, bounded by an optional caller-provided maximum count. Each result SHALL include the file name, MIME type, id, and last modified time.

#### Scenario: Recent files returned
- **WHEN** the client calls `list_recent_files`
- **THEN** the server returns files ordered from most to least recently modified, each including name, MIME type, id, and last modified time

#### Scenario: Result limit honored
- **WHEN** the client calls `list_recent_files` with a maximum result count
- **THEN** the server returns no more than that many files

### Requirement: File metadata tool
The `get_file_metadata` tool SHALL return descriptive metadata for a Drive file identified by its id, including name, MIME type, size, owners, last modified time, and a web view link.

#### Scenario: Metadata returned
- **WHEN** the client calls `get_file_metadata` with a valid file id
- **THEN** the server returns the file's name, MIME type, size, owners, last modified time, and web view link

#### Scenario: Unknown or inaccessible file id
- **WHEN** the client calls `get_file_metadata` with an id that does not exist or the user cannot access
- **THEN** the server returns an error result describing the failure

### Requirement: Download file content tool
The `download_file_content` tool SHALL save the bytes of a Drive file to a caller-provided local output path (defaulting to the file's name) and return that path and the number of bytes written. Google-native formats SHALL be exported to a byte form before saving.

#### Scenario: Download a binary file
- **WHEN** the client calls `download_file_content` with a binary file id and an output path
- **THEN** the server writes the file's bytes to that path and returns the path and byte count

#### Scenario: Download a Google-native file
- **WHEN** the client calls `download_file_content` for a Google Docs, Sheets, or Slides file id
- **THEN** the server writes the exported bytes to the path and returns the path and byte count

#### Scenario: Unknown or inaccessible file id
- **WHEN** the client calls `download_file_content` with an id that does not exist or the user cannot access
- **THEN** the server returns an error result describing the failure

### Requirement: Create file tool
The `create_file` tool SHALL create a new file in the user's Drive from provided text content, a file name, and a MIME type, optionally within a specified parent folder, and SHALL return the new file's id and name. Creating a file requires write authorization.

#### Scenario: Create a text file
- **WHEN** the client calls `create_file` with a name, content, and MIME type
- **THEN** a new file is created in the user's Drive and the server returns its id and name

#### Scenario: Create within a parent folder
- **WHEN** the client calls `create_file` and supplies a parent folder id
- **THEN** the new file is created inside that folder

#### Scenario: Insufficient write scope
- **WHEN** the client calls `create_file` but the saved authorization lacks the `drive.file` write scope
- **THEN** the server returns an error result explaining that re-authorization with write access is required

### Requirement: Copy file tool
The `copy_file` tool SHALL create a copy of an existing Drive file identified by its id, optionally with a new name and parent folder, and SHALL return the new file's id and name. Copying a file requires write authorization.

#### Scenario: Copy a file
- **WHEN** the client calls `copy_file` with a source file id
- **THEN** a copy is created in the user's Drive and the server returns the new file's id and name

#### Scenario: Copy with a new name and parent
- **WHEN** the client calls `copy_file` and supplies a new name and a parent folder id
- **THEN** the copy is created with that name inside that folder

#### Scenario: Insufficient write scope
- **WHEN** the client calls `copy_file` but the saved authorization lacks the `drive.file` write scope
- **THEN** the server returns an error result explaining that re-authorization with write access is required

### Requirement: File permissions tool
The `get_file_permissions` tool SHALL list the sharing permissions of a Drive file identified by its id. Each entry SHALL include the permission id, role, and type, and the grantee identity when available.

#### Scenario: Permissions returned
- **WHEN** the client calls `get_file_permissions` with a valid file id
- **THEN** the server returns the file's permission entries, each including id, role, and type

#### Scenario: Unknown or inaccessible file id
- **WHEN** the client calls `get_file_permissions` with an id that does not exist or the user cannot access
- **THEN** the server returns an error result describing the failure

### Requirement: Update file metadata tool
The `update_file` tool SHALL update the metadata of an existing Drive file identified by its id, without modifying the file's content. The tool is a local-only extension beyond the hosted server's toolset. It SHALL accept an optional new `title` that, when provided, MUST be non-empty and renames the file, and an optional `parent_id` that moves the file by replacing its current parent folder. At least one of `title` or `parent_id` SHALL be provided. The tool SHALL return the updated file's id and name, and requires write authorization.

#### Scenario: Rename a file
- **WHEN** the client calls `update_file` with a file id and a non-empty new title
- **THEN** the file is renamed and the server returns the file's id and updated name

#### Scenario: Move a file to a new parent
- **WHEN** the client calls `update_file` with a file id and a new parent folder id
- **THEN** the file is moved so that the new parent replaces its current parent, and the server returns the file's id and name

#### Scenario: No updatable field provided
- **WHEN** the client calls `update_file` with neither a title nor a parent id (or with an empty title)
- **THEN** the server returns an error result explaining that a non-empty title or a parent id is required

#### Scenario: Insufficient write scope
- **WHEN** the client calls `update_file` but the saved authorization lacks the `drive.file` write scope
- **THEN** the server returns an error result explaining that re-authorization with write access is required

## MODIFIED Requirements

### Requirement: Local stdio MCP transport
The server SHALL run as a local process that speaks the Model Context Protocol over stdio, and SHALL advertise its available tools in response to an MCP `tools/list` request.

#### Scenario: Client launches the server
- **WHEN** an MCP client launches the server as a stdio subprocess
- **THEN** the server completes the MCP initialize handshake and is ready to receive tool calls

#### Scenario: Client lists tools
- **WHEN** an MCP client sends a `tools/list` request
- **THEN** the server returns tool specifications for `search_files`, `read_file_content`, `list_recent_files`, `get_file_metadata`, `download_file_content`, `create_file`, `copy_file`, `get_file_permissions`, and `update_file`, each with a name, description, and input schema

### Requirement: Google Drive authentication
The server SHALL authenticate to Google Drive using the user's existing OAuth 2.0 client credentials and saved tokens, operating with read access (`drive.readonly`) and, when authorized, write access (`drive.file`) used for file creation, copying, and metadata updates. When the saved access token is expired and a refresh token is available, the server SHALL refresh it and persist the refreshed token. When required credentials are missing, the server SHALL fail with an actionable message. When a write tool is invoked but the saved authorization lacks write scope, the server SHALL return an actionable error instead of failing abnormally.

#### Scenario: Valid credentials
- **WHEN** the server starts with valid OAuth client keys and saved tokens
- **THEN** it authenticates and serves tool calls against the user's Drive

#### Scenario: Expired access token
- **WHEN** the saved access token is expired and a refresh token is available
- **THEN** the server refreshes the access token and persists the refreshed token for reuse

#### Scenario: Missing credentials
- **WHEN** required OAuth client keys or saved tokens are not present
- **THEN** the server fails to start with a message explaining how to provide them

#### Scenario: Write attempted without write scope
- **WHEN** a write tool such as `create_file`, `copy_file`, or `update_file` is invoked but the saved authorization lacks the `drive.file` scope
- **THEN** the server returns an actionable error indicating that re-authorization with write access is required

## RENAMED Requirements

- FROM: `### Requirement: Read-only Google authentication`
- TO: `### Requirement: Google Drive authentication`
