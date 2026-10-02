# Tasks

## 1. Shared hosted-file foundation

- [x] 1.1 Add `to_hosted_file(drive_file)` to `gdrive-cli/gdrive_cli.py` mapping Drive v3
  fields to the hosted `File` names per design D1, omitting fields whose source value
  is absent; verify with a unit check that a sample Drive dict (with and without
  `parents`/`description`/`owners`) produces the expected hosted keys and omits the
  missing ones.
- [x] 1.2 Define the shared inner `HOSTED_FILE_FIELDS` mask; use it directly for
  `files().get(fields=...)` and wrap it as `nextPageToken,files(...)` for
  `files().list(fields=...)`; verify both call shapes return the mapped fields against
  a real file id.

## 2. search_files full hosted parity (priority)

- [x] 2.1 Add `translate_query(hosted_query) -> drive_v3_query` to `gdrive_cli.py` per
  design D3a: tokenize with single-quote/`\'` awareness, rename `title`→`name`, rewrite
  `parentId`/`owner` `=`/`!=` clauses to `in parents`/`in owners` (and `not (...)`),
  pass through `fullText`/`mimeType`/time terms/`sharedWithMe`/combinators, apply the
  bare-term `fullText contains` fallback, then wrap and append `and trashed = false`;
  verify unit tests cover each documented hosted example (title, compound mimeType+time,
  `parentId = '...'`, `parentId = 'root'`, `owner = 'me'`, `sharedWithMe = true`,
  `sharedWithMe = false`, `fullText contains`, and a bare term), plus malformed syntax,
  unknown terms, invalid operator combinations, and quoted field-name literals.
- [x] 2.2 Update `gdrive_cli.search_files` to accept `page_size`, `page_token`,
  `exclude_content_snippets`, build its query via `translate_query`, request the shared
  mask, and return `{"files": [to_hosted_file(...)], "nextPageToken": ...}`; verify a
  live `parentId = '<folderId>'` query returns only that folder's files, hosted-named,
  with no trashed files.
- [x] 2.3 Update the `search_files` `@mcp.tool` in `drive-mcp-server/server.py` to expose
  the exact hosted inputs `query`, `pageSize`, `pageToken`, `excludeContentSnippets`
  and return the structured result (dict); verify `tools/list` uses those exact property
  names and the call result contains `files[]` + `nextPageToken`.
- [x] 2.4 Verify pagination and snippet control: a two-page live search returns a
  `nextPageToken` on page 1 that fetches distinct results on page 2, and
  `excludeContentSnippets=true` yields file objects without a `contentSnippet` key.

## 3. list_recent_files parity

- [x] 3.1 Update `gdrive_cli.list_recent_files` to map hosted `orderBy` values
  (`recency`, `lastModified`, `lastModifiedByMe`) to the Drive v3 orderings in design
  D3, accept paging/snippet controls, apply `trashed = false`, and return structured
  `{files, nextPageToken}`; verify all three sort values and rejection of an unknown
  value.
- [x] 3.2 Update the `list_recent_files` `@mcp.tool` to expose the exact hosted inputs
  `orderBy`, `pageSize`, `pageToken`, `excludeContentSnippets` and return the structured
  result; verify `tools/list` and live calls use those exact names.

## 4. get_file_metadata parity

- [x] 4.1 Update `gdrive_cli.get_file_metadata` to request the shared mask and return a
  single `to_hosted_file(...)` dict, honoring `exclude_content_snippets`; verify a live
  call on a known id returns hosted fields (`title`, `fileSize`, `owner`, `viewUrl`,
  `parentId`).
- [x] 4.2 Update the `get_file_metadata` `@mcp.tool` to expose the exact hosted inputs
  `fileId` and `excludeContentSnippets` and return the structured `File` dict,
  preserving the existing error result for an unknown/inaccessible id; verify
  `tools/list`, success (structured), and error (`is_error`) paths via an MCP client.

## 5. CLI output preservation

- [x] 5.1 Update `cmd_search`, `cmd_list`, and `cmd_info` to read the new hosted-named
  structured results while printing the same columns as before; verify each CLI command's
  output matches the pre-change format on a sample file (diff against current output).

## 6. Documentation

- [x] 6.1 Update `drive-mcp-server/README.md`: revise the tool table and local→hosted
  mapping for the three tools (new inputs, structured output, `contentSnippet` deviation
  from design D4); verify the documented smoke-test/example invocations match the new
  signatures.

## 7. Integration verification

- [x] 7.1 Launch the MCP server over stdio and confirm `tools/list` advertises the three
  tools with their new input schemas, then exercise one happy-path call per tool and
  confirm structured content; verify no regression in the other six tools.
- [x] 7.2 Run `openspec validate align-read-tools-hosted-contract --strict` and confirm
  it passes.
