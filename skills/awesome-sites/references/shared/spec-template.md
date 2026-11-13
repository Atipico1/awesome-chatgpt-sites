# App spec template

Every file in `references/apps/` follows this layout, in this order. A spec states decisions so the builder does not have to invent product behavior. It contains instructions, schemas, and contracts, never application source code.

## Conventions every spec inherits (do not repeat them)

- **IDs:** `TEXT` primary keys holding a random UUID, except where a human-readable id is specified.
- **Time:** `INTEGER` Unix epoch milliseconds in UTC, column names ending `_at`. Dates without a time (`due_date`) are `TEXT` `YYYY-MM-DD`.
- **Money:** `INTEGER` minor units plus a 3-letter `currency`.
- **Booleans:** `INTEGER` 0 or 1.
- **JSON:** `TEXT` with `CHECK (json_valid(col))`.
- **Emails:** stored lowercase.
- **Errors:** every API error is `{ "error": { "code": "<snake_case>", "message": "<one sentence a user can read>" } }`. Standard codes: `unauthorized` 401, `forbidden` 403, `not_found` 404, `invalid_input` 422, `conflict` 409, `rate_limited` 429, `quota_exhausted` 429, `not_configured` 503 (missing key), `upstream_error` 502.
- **Pagination:** `?limit=` (default 50, max 200) and `?cursor=` (opaque), returning `{ "items": [], "next_cursor": null }`.
- **Writes:** validate on the server, return the saved object, and never trust totals, counts, or status sent by the browser.
- **Migrations:** one initial migration containing every table and index below, following the starter's migration convention.

## Sections

### 1. Header

Title, one sentence of what it builds, and `Resembles:` the commercial products. Then three labelled lines:

- `Read first:` the shared files that apply.
- `Access:` one of the patterns in `baseline.md`, plus the recommended audience from `access-and-domains.md`.
- `Keys:` secrets needed, from `api-keys.md`, and what stays disabled without each.

### 2. Data

Complete SQLite DDL in a code block: column types, `NOT NULL`, defaults, `CHECK` constraints, foreign keys, unique constraints, and every index that a query below needs. Add short comments for non-obvious columns. Then bullet any invariant that needs a transaction or a batch.

### 3. API contract

A table with one row per route: method and path, auth (`public`, `signed-in`, `owner`, or `token`), request (fields and limits), success response (shape and status), and error codes. Page routes that only render HTML are listed in Screens, not here.

### 4. LLM contract (only when the app calls an LLM or other AI API)

- **Inputs** assembled from what, in what order, with what size caps.
- **System prompt rules** as a numbered list the builder turns into the prompt (the rules, not a polished prompt).
- **Output schema** as a JSON schema or typed field list, with enums.
- **Validation and repair:** what to check, one retry on failure, what the user sees if it still fails.
- **Grounding checks** done in code after the call (for example: cited ids exist, quotes appear verbatim).
- **Token and size caps**, and which calls are cached.

### 5. Screens and states

For each screen: route, what it shows, controls, and the exact behavior of **loading**, **empty** (with the sentence shown), and **error** states. Add keyboard shortcuts only where they help a power user. Mention mobile layout where it changes behavior.

### 6. MCP tools (optional)

Include when ChatGPT or Codex using the app is natural, not for every app. List each tool: name, inputs, output fields, read-only or write. Read tools are marked read-only. Tool discovery exposes no private data. Say how auth works for the tool (owner only for private data). Enabled with `capabilities: ["mcp"]`. If the app is public, the MCP tools still act only for the owner.

### 7. Limits and defaults

A table of every number the builder would otherwise guess: caps, timeouts, TTLs, rate limits, page sizes, file types and sizes. If a number depends on a Sites limit that is not documented, write "choose from what the deployed site accepts, record it in the report".

### 8. Verification

A numbered script a person or agent runs against the deployed site. Each step has the input and the expected result. Include: the golden path, at least three edge cases, at least two failure cases (missing key, quota exhausted, bad input, unauthorized), and a persistence check after reload. For apps with an LLM, include fixed sample inputs (say what they are and what a correct output must contain). Where a result depends on an external provider, state what to check and accept any correct output rather than exact text.

### 9. Out of scope

Features the builder must refuse to add, with the smaller alternative where one exists.

## Writing rules

- Decide, do not offer options. Use "must", "default", and numbers.
- Do not copy facts about Sites or a provider that may change; link to `baseline.md`, `api-keys.md`, `access-and-domains.md`, or `usage-guard.md`.
- No marketing language. Plain sentences.
