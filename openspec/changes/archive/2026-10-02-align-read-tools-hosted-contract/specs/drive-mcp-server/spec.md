# Spec Delta

## ADDED Requirements

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

## MODIFIED Requirements

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
