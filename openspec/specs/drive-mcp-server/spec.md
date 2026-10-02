# drive-mcp-server Specification

## Purpose

A locally hosted MCP server that exposes the user's Google Drive to AI clients over stdio, starting with full-text search and file-content reading, using the user's read-only OAuth credentials.

## Requirements

### Requirement: Local stdio MCP transport
The server SHALL run as a local process that speaks the Model Context Protocol over stdio, and SHALL advertise its available tools in response to an MCP `tools/list` request.

#### Scenario: Client launches the server
- **WHEN** an MCP client launches the server as a stdio subprocess
- **THEN** the server completes the MCP initialize handshake and is ready to receive tool calls

#### Scenario: Client lists tools
- **WHEN** an MCP client sends a `tools/list` request
- **THEN** the server returns tool specifications for `search_files`, `read_file_content`, `list_recent_files`, `get_file_metadata`, `download_file_content`, `create_file`, `copy_file`, `get_file_permissions`, and `update_file`, each with a name, description, and input schema

### Requirement: Hosted-compatible structured file representation
The read tools that return Drive files (`search_files`, `list_recent_files`,
`get_file_metadata`) SHALL represent each file as a structured object (not a
formatted string) using the hosted `drivemcp.googleapis.com/mcp/v1` contract's
field names: `id`, `title`, `parentId`, `mimeType`, `fileSize`, `description`,
`fileExtension`, `contentSnippet`, `viewUrl`, `sharedWithMeTime`, `createdTime`,
`modifiedTime`, `viewedByMeTime`, `owner`, and `canAddChildren`. A field SHALL be
present when the Drive API supplies a corresponding value and MAY be omitted
otherwise.

#### Scenario: Fields use hosted contract names
- **WHEN** any of the three read tools returns a file
- **THEN** the file object exposes the hosted field names (for example `title`,
  `fileSize`, `parentId`), not the raw Drive v3 names (`name`, `size`, `parents`)

#### Scenario: Owner uses the hosted value semantics
- **WHEN** Drive supplies an owner email address for a returned file
- **THEN** the file object's `owner` field contains that email address rather than
  the owner's display name

#### Scenario: Unavailable fields are omitted
- **WHEN** the Drive API does not supply a value for an optional field such as
  `description` or `parentId`
- **THEN** that field is omitted from the returned file object rather than emitted
  as an empty value

#### Scenario: Content snippet can be excluded
- **WHEN** a caller requests results with content snippets excluded
- **THEN** the returned file objects omit the `contentSnippet` field

### Requirement: Full-text file search tool
The `search_files` tool SHALL search the authenticated user's Drive, excluding
trashed files, and SHALL return a structured result containing a list of matching
files under `files` and an optional continuation token under `nextPageToken`. Each
file SHALL use the hosted-compatible structured file representation. The tool SHALL
accept a required structured `query` expression and the optional MCP inputs
`pageSize`, `pageToken`, and `excludeContentSnippets`, using those exact names.

The `query` SHALL support the hosted query dialect: the terms `title`, `fullText`,
`mimeType`, `modifiedTime`, `createdTime`, `viewedByMeTime`, `parentId`, `owner`,
and `sharedWithMe`, their documented operators (`contains`, `=`, `!=`, and the
ordered comparisons for time terms), the combinators `and`/`or`/`not` with
parentheses, and single-quoted string values (with `\'` escaping). `parentId` SHALL
accept `'root'` for My Drive and `owner` SHALL accept `'me'` for the requesting user.

#### Scenario: Matches found
- **WHEN** the client calls `search_files` with a query that matches files
- **THEN** the server returns a result whose `files` list contains each match as a
  structured file object, and a `nextPageToken` for continuation when another page
  exists

#### Scenario: Structured operator query honored
- **WHEN** the client calls `search_files` with a compound query such as
  `title contains 'report' and mimeType contains 'image/'`
- **THEN** the server applies every term and combinator and returns only files
  satisfying the whole expression

#### Scenario: Parent folder filter honored
- **WHEN** the client calls `search_files` with `parentId = '<folderId>'` (or
  `parentId = 'root'`)
- **THEN** the server returns only files whose parent is that folder

#### Scenario: Owner filter honored
- **WHEN** the client calls `search_files` with `owner = 'me'` (or a specific
  address)
- **THEN** the server returns only files owned by that user

#### Scenario: No matches
- **WHEN** the client calls `search_files` with a query that matches no files
- **THEN** the server returns a result whose `files` list is empty and does not
  fabricate a continuation token

#### Scenario: Invalid query rejected
- **WHEN** the client calls `search_files` with malformed syntax, an unsupported
  term, or an operator not supported for that term
- **THEN** the server returns an error result describing the invalid query

#### Scenario: Result limit honored
- **WHEN** the client calls `search_files` with `pageSize`
- **THEN** the server returns no more than that many files in the `files` list

#### Scenario: Pagination with a page token
- **WHEN** the client calls `search_files` again with the `nextPageToken` from a
  prior response
- **THEN** the server returns the next page of matches, and omits or empties
  `nextPageToken` when no further pages remain

#### Scenario: Content snippets excluded
- **WHEN** the client calls `search_files` with `excludeContentSnippets` set to true
- **THEN** the returned file objects omit the `contentSnippet` field

#### Scenario: Trashed files excluded
- **WHEN** a matching file is in the trash
- **THEN** that file is not included in the results

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

### Requirement: List recent files tool
The `list_recent_files` tool SHALL return the authenticated user's recently modified
Drive files, excluding trashed files, as a structured result containing a list of
files under `files` and an optional continuation token under `nextPageToken`. Each
file SHALL use the hosted-compatible structured file representation. The tool SHALL
accept the optional MCP inputs `orderBy`, `pageSize`, `pageToken`, and
`excludeContentSnippets`, using those exact names. `orderBy` SHALL accept `recency`,
`lastModified`, and `lastModifiedByMe`, and SHALL default to `recency`.

#### Scenario: Recent files returned
- **WHEN** the client calls `list_recent_files`
- **THEN** the server returns a result whose `files` list holds structured file
  objects ordered by `recency`, plus a `nextPageToken` when another page exists

#### Scenario: Sort order honored
- **WHEN** the client calls `list_recent_files` with `orderBy` set to `recency`,
  `lastModified`, or `lastModifiedByMe`
- **THEN** the server orders the returned files by that order instead of the default

#### Scenario: Unsupported sort order rejected
- **WHEN** the client calls `list_recent_files` with any other `orderBy` value
- **THEN** the server returns an error result describing the unsupported sort order

#### Scenario: Result limit honored
- **WHEN** the client calls `list_recent_files` with `pageSize`
- **THEN** the server returns no more than that many files in the `files` list

#### Scenario: Pagination with a page token
- **WHEN** the client calls `list_recent_files` again with the `nextPageToken`
  from a prior response
- **THEN** the server returns the next page of files, and omits or empties
  `nextPageToken` when no further pages remain

#### Scenario: Content snippets excluded
- **WHEN** the client calls `list_recent_files` with `excludeContentSnippets` set
  to true
- **THEN** the returned file objects omit the `contentSnippet` field

### Requirement: File metadata tool
The `get_file_metadata` tool SHALL return a single structured file object for a Drive
file identified by its id, using the hosted-compatible structured file
representation. The tool SHALL accept an optional flag to exclude the content
snippet. Its MCP inputs SHALL be named `fileId` and `excludeContentSnippets` exactly.

#### Scenario: Metadata returned
- **WHEN** the client calls `get_file_metadata` with a valid file id
- **THEN** the server returns a structured file object exposing the hosted fields
  (including `title`, `mimeType`, `fileSize`, `owner`, `modifiedTime`, `viewUrl`,
  and `parentId`) when the Drive API supplies them

#### Scenario: Content snippet excluded
- **WHEN** the client calls `get_file_metadata` with `excludeContentSnippets` set
  to true
- **THEN** the returned file object omits the `contentSnippet` field

#### Scenario: Unknown or inaccessible file id
- **WHEN** the client calls `get_file_metadata` with an id that does not exist or the
  user cannot access
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
