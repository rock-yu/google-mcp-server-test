# Design

## Context

See proposal.md — Why. The three read tools currently return joined strings via
`gdrive_cli.search_files` / `list_recent_files` / `get_file_metadata`, each
requesting a thin Drive v3 `fields` mask and formatting results in
`drive-mcp-server/server.py`. The hosted `drivemcp.googleapis.com/mcp/v1` contract
(confirmed from its per-tool reference pages) returns structured JSON: a `File`
object with 15 named fields, list responses wrapped as `{ files[], nextPageToken }`,
and inputs for pagination, sort order, and content-snippet control.

Constraints: the MCP server reuses `gdrive-cli/gdrive_cli.py`, which also backs a
standalone CLI (`cmd_search`, `cmd_list`, `cmd_info`). The MCP SDK is v2
(`@mcp.tool` derives schema from return/param type hints). Drive access is via the
googleapiclient `files()` resource.

## Goals / Non-Goals

**Goals:**
- `search_files` matches the hosted contract on inputs, output shape, field names,
  pagination, and trashed exclusion (the priority).
- One shared Drive-v3 → hosted `File` mapper reused by all three read tools.
- Preserve the existing `gdrive_cli` CLI output.

**Non-Goals:**
- No changes to the other six tools (`read_file_content`, `download_file_content`,
  `create_file`, `copy_file`, `get_file_permissions`, `update_file`).
- No attempt to reproduce the hosted server's generated `contentSnippet` text.

## Decisions

### D1: A single `to_hosted_file()` mapper
Add one helper in `gdrive_cli.py` that converts a Drive v3 file resource into the
hosted `File` dict. All three tools request the same wide `fields` mask and run it
through this mapper, so field naming and omission rules live in one place.

Drive v3 → hosted field mapping:

| Hosted field       | Drive v3 source                         |
|--------------------|-----------------------------------------|
| `id`               | `id`                                    |
| `title`            | `name`                                  |
| `parentId`         | `parents[0]` (omit if none)             |
| `mimeType`         | `mimeType`                              |
| `fileSize`         | `size`                                  |
| `description`      | `description`                           |
| `fileExtension`    | `fileExtension`                         |
| `contentSnippet`   | — (see D4)                              |
| `viewUrl`          | `webViewLink`                           |
| `sharedWithMeTime` | `sharedWithMeTime`                      |
| `createdTime`      | `createdTime`                           |
| `modifiedTime`     | `modifiedTime`                          |
| `viewedByMeTime`   | `viewedByMeTime`                        |
| `owner`            | `owners[0].emailAddress`                 |
| `canAddChildren`   | `capabilities.canAddChildren`           |

A field is included only when its source value is present (satisfies the spec's
"omitted when unavailable" rule).

Define one inner `HOSTED_FILE_FIELDS` mask:
`id,name,parents,mimeType,size,description,fileExtension,webViewLink,sharedWithMeTime,createdTime,modifiedTime,viewedByMeTime,owners(displayName,emailAddress),capabilities/canAddChildren`.
`files.get` uses that mask directly; `files.list` wraps it as
`nextPageToken,files(<HOSTED_FILE_FIELDS>)`.

*Alternative considered:* map inline per tool — rejected, duplicates naming logic
three times and drifts.

### D2: Helpers return a structured result; the MCP layer returns it as-is
`search_files` and `list_recent_files` return `{"files": [<hosted File>...],
"nextPageToken": <str|None>}`; `get_file_metadata` returns a single hosted `File`
dict. The `@mcp.tool` wrappers return these Python objects directly (type hints
become `dict`), letting the MCP SDK serialize structured content instead of a string.

The MCP SDK derives input-schema property names from Python parameter names. The
three public tool functions therefore use the hosted camelCase names directly
(`pageSize`, `pageToken`, `excludeContentSnippets`, `orderBy`, `fileId`) and
immediately translate them to snake_case when calling internal helpers. This is a
deliberate boundary exception to the project's normal Python naming convention.

*Alternative considered:* keep returning formatted strings with more fields —
rejected; strings are not machine-parseable and were the core gap.

### D3: Pagination and sort pass-through
Internal helpers accept `page_token` and `page_size`, threaded into
`files().list(pageToken=, pageSize=)`; the MCP boundary exposes `pageToken` and
`pageSize`. Responses preserve `nextPageToken` exactly.

`list_recent_files.orderBy` is a hosted enum, not a raw Drive ordering expression:

| Hosted `orderBy` value | Drive v3 `orderBy` |
|------------------------|--------------------|
| `recency` (default)    | `recency desc`     |
| `lastModified`         | `modifiedTime desc` |
| `lastModifiedByMe`     | `modifiedByMeTime desc` |

Other values raise `ToolError`. Trashed files are excluded by wrapping the final query and
appending `trashed = false` (see D3a for `search_files`; `list_recent_files` simply
uses `trashed = false`).

### D3a: Translate the hosted query dialect to a Drive v3 query
`search_files` must accept the hosted `query` dialect, which is *not* identical to
the Drive v3 query language. A `translate_query(hosted) -> drive_v3` helper in
`gdrive_cli.py` tokenizes the expression (respecting single-quoted strings and `\'`
escapes so field names inside quotes are never rewritten) and applies:

| Hosted term/clause            | Drive v3 equivalent            |
|-------------------------------|--------------------------------|
| `title` (contains/=/!=)       | `name`                         |
| `fullText contains 'x'`       | unchanged                      |
| `mimeType` (contains/=/!=)    | unchanged                      |
| `modifiedTime`/`createdTime`/`viewedByMeTime` (<= < = != > >=) | unchanged (RFC 3339) |
| `sharedWithMe = true`         | `sharedWithMe`                 |
| `sharedWithMe = false`        | `not sharedWithMe`             |
| `and` / `or` / `not` / `( )`  | unchanged                      |
| `parentId = 'X'`              | `'X' in parents`               |
| `parentId != 'X'`             | `not ('X' in parents)`         |
| `owner = 'X'` (incl. `'me'`)  | `'X' in owners`                |
| `owner != 'X'`                | `not ('X' in owners)`          |

The translated expression is wrapped in parentheses and `and trashed = false` is
appended, so trashed exclusion holds even when the caller's query has a top-level
`or`. Malformed syntax, unknown terms, invalid term/operator combinations, and
unquoted string values raise a `ToolError`; the translator never sends a partly
understood expression to Drive.

**Convenience (local superset):** if the input contains none of the recognized field
tokens, it is treated as `fullText contains '<escaped>'`, preserving the old
bare-term behavior. Because this only *adds* acceptance beyond the hosted dialect, it
does not break parity for structured queries.

*Alternatives considered:* (a) pass the query straight through as Drive v3 — rejected,
`parentId`/`title`/`owner` would silently fail or mismatch the hosted dialect; (b)
keep hardwiring `fullText contains` — rejected, that is the gap this change closes.

### D4: `contentSnippet` is accepted but best-effort (known deviation)
Drive's REST API does not return the hosted server's generated content snippet, so
local results omit `contentSnippet`. The `excludeContentSnippets` input is still
accepted for contract compatibility and, when true, guarantees the field is absent;
when false the field is still absent because no equivalent source value exists. This
is the sole documented value-level deviation: the contract surface (schema, names,
query language, pagination, and trashed handling) remains exact.

*Alternative considered:* synthesize a snippet from `description` or the first bytes
of file content — rejected; extra per-result API calls, not equivalent to the hosted
snippet, and potentially misleading.

### D5: Preserve CLI output
`cmd_search`, `cmd_list`, and `cmd_info` are updated to read hosted field names from
the structured results (`title`, `fileSize`, …) while printing the same columns as
today, so the CLI's human output is unchanged.

## Risks / Trade-offs

- [Structured return changes the tools' output type] → Intended BREAKING change;
  called out in the proposal and README; the other six tools are untouched.
- [`contentSnippet` not reproducible] → D4: accept the input, document the deviation;
  the field's absence is spec-conformant ("omitted when unavailable").
- [CLI regression from reusing changed helpers] → D5: update the three `cmd_*`
  formatters and verify CLI output byte-for-byte against current behavior.
- [Query-dialect translation edge cases (quoting, `parentId`/`owner` rewrites,
  top-level `or` vs trashed wrapping)] → D3a: tokenize with quote-awareness, wrap
  before appending `trashed = false`, and cover every documented hosted example with
  unit tests.
- [MCP SDK structured-content serialization] → Verify during apply that returning
  `dict`/`list` from `@mcp.tool` produces structured content and a valid output
  schema; fall back to an explicit return-type model if needed.
