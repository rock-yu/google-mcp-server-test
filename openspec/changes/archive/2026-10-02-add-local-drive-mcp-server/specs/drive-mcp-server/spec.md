# Spec Delta

## Purpose

A locally hosted MCP server that exposes the user's Google Drive to AI clients over stdio, starting with full-text search and file-content reading, using the user's read-only OAuth credentials.

## ADDED Requirements

### Requirement: Local stdio MCP transport
The server SHALL run as a local process that speaks the Model Context Protocol over stdio, and SHALL advertise its available tools in response to an MCP `tools/list` request.

#### Scenario: Client launches the server
- **WHEN** an MCP client launches the server as a stdio subprocess
- **THEN** the server completes the MCP initialize handshake and is ready to receive tool calls

#### Scenario: Client lists tools
- **WHEN** an MCP client sends a `tools/list` request
- **THEN** the server returns tool specifications for `search_files` and `read_file_content`, each with a name, description, and input schema

### Requirement: Full-text file search tool
The `search_files` tool SHALL perform a full-text search over the authenticated user's Drive and return matching files. Each result SHALL include the file name, MIME type, and file id. The number of results SHALL be bounded by an optional caller-provided maximum.

#### Scenario: Matches found
- **WHEN** the client calls `search_files` with a query that matches files
- **THEN** the server returns a list of matches, each including name, MIME type, and id

#### Scenario: No matches
- **WHEN** the client calls `search_files` with a query that matches no files
- **THEN** the server returns a result indicating that no files matched

#### Scenario: Result limit honored
- **WHEN** the client calls `search_files` with a maximum result count
- **THEN** the server returns no more than that many files

### Requirement: Read file content tool
The `read_file_content` tool SHALL return the content of a Drive file identified by its id. Google-native formats SHALL be exported to text: Google Docs to Markdown, Google Sheets to CSV, and Google Slides to plain text. Other text files SHALL be returned as their native text.

#### Scenario: Read a Google Doc
- **WHEN** the client calls `read_file_content` for a Google Docs file id
- **THEN** the server returns the document content as Markdown text

#### Scenario: Read a Google Sheet
- **WHEN** the client calls `read_file_content` for a Google Sheets file id
- **THEN** the server returns the sheet content as CSV text

#### Scenario: Non-text binary file
- **WHEN** the client calls `read_file_content` for a non-text binary file, such as an image
- **THEN** the server returns a message indicating the content is binary and cannot be returned as text

#### Scenario: Unknown or inaccessible file id
- **WHEN** the client calls `read_file_content` with an id that does not exist or the user cannot access
- **THEN** the server returns an error result describing the failure

### Requirement: Read-only Google authentication
The server SHALL authenticate to Google Drive using the user's existing OAuth 2.0 client credentials and saved tokens, operating with read-only Drive scope. When the saved access token is expired and a refresh token is available, the server SHALL refresh it and persist the refreshed token. When required credentials are missing, the server SHALL fail with an actionable message.

#### Scenario: Valid credentials
- **WHEN** the server starts with valid OAuth client keys and saved tokens
- **THEN** it authenticates and serves tool calls against the user's Drive

#### Scenario: Expired access token
- **WHEN** the saved access token is expired and a refresh token is available
- **THEN** the server refreshes the access token and persists the refreshed token for reuse

#### Scenario: Missing credentials
- **WHEN** required OAuth client keys or saved tokens are not present
- **THEN** the server fails to start with a message explaining how to provide them
