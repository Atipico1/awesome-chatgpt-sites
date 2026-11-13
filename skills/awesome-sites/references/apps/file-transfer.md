# File Transfer on Sites

Builds a send-a-file page: upload files, get a link with an expiry, optional password, and a download limit.

Resembles: WeTransfer, Send Anywhere.

Read first: `../shared/baseline.md`, `../shared/access-and-domains.md`, `../shared/usage-guard.md`.
Access: public site with owner admin (baseline). Audience: Anyone on the internet, because recipients have no ChatGPT login. Uploading requires SIWC; downloading needs only the link.
Keys: none. Needs R2 (bind as `FILES`) and D1 (`DB`).

## Data

```sql
CREATE TABLE transfers (
  id TEXT PRIMARY KEY,
  token TEXT NOT NULL UNIQUE,              -- 22+ random URL-safe chars
  owner_email TEXT NOT NULL,
  title TEXT NOT NULL DEFAULT '' CHECK (length(title) <= 120),
  message TEXT NOT NULL DEFAULT '' CHECK (length(message) <= 1000),
  password_hash TEXT,                      -- PBKDF2-SHA256, base64; NULL = no password
  password_salt TEXT,                      -- per-record random, base64
  failed_attempts INTEGER NOT NULL DEFAULT 0,
  locked_until INTEGER,
  expires_at INTEGER NOT NULL,
  max_downloads INTEGER CHECK (max_downloads IS NULL OR max_downloads BETWEEN 1 AND 1000),
  download_count INTEGER NOT NULL DEFAULT 0,
  total_size INTEGER NOT NULL DEFAULT 0,
  finalized_at INTEGER,                    -- link is valid only after this is set
  created_at INTEGER NOT NULL,
  deleted_at INTEGER
);
CREATE INDEX idx_transfers_owner ON transfers(owner_email, created_at DESC);
CREATE INDEX idx_transfers_expires ON transfers(expires_at);
CREATE TABLE files (
  id TEXT PRIMARY KEY,
  transfer_id TEXT NOT NULL REFERENCES transfers(id) ON DELETE CASCADE,
  name TEXT NOT NULL,                      -- sanitized: no slashes, max 200 chars
  size INTEGER NOT NULL CHECK (size > 0),
  content_type TEXT NOT NULL,
  r2_key TEXT NOT NULL UNIQUE,             -- transfers/<transfer id>/<file id>
  created_at INTEGER NOT NULL
);
CREATE INDEX idx_files_transfer ON files(transfer_id);
```

- Download counting is one conditional statement: `UPDATE transfers SET download_count = download_count + 1 WHERE token = ? AND deleted_at IS NULL AND finalized_at IS NOT NULL AND expires_at > ? AND (max_downloads IS NULL OR download_count < max_downloads)`. One changed row means allowed. Zero changed rows means refuse.
- One download is one file request. There is no zip.

## API contract

| Route | Auth | Request | Success | Errors |
| --- | --- | --- | --- | --- |
| `POST /api/transfers` | signed-in | `{title?, message?, expires_in_days: 1\|7\|30, password?, max_downloads?}` | 201 draft `{id, token}` | `invalid_input`, `rate_limited` |
| `PUT /api/transfers/:id/files?name=` | owner of transfer | raw body, `Content-Type` header, size within caps | 201 `{id, name, size}` | `invalid_input` (empty name, over cap), `not_found`, `forbidden` |
| `POST /api/transfers/:id/finalize` | owner of transfer | none; needs at least 1 file | 200 `{url}` where `url = SITE_URL/t/<token>` | `invalid_input` (no files), `conflict` (already finalized) |
| `GET /api/t/:token` | public | none | 200 `{title, message, expires_at, requires_password, files: [{id, name, size}]}` | `not_found` (expired, deleted, unknown, exhausted: one message) |
| `GET /api/t/:token/files/:fileId` | public | unprotected transfers only | file stream, attachment | `not_found`, `forbidden` (password set) |
| `POST /api/t/:token/files/:fileId` | public | form field `password` | file stream, attachment | `forbidden` (wrong password), `rate_limited` (locked), `not_found` |
| `GET /api/transfers` | signed-in | standard pagination | own transfers with status and counts | none |
| `DELETE /api/transfers/:id` | owner of transfer | none | 200 `{deleted: true}` | `not_found` |
| `POST /api/admin/purge` | owner | none | 200 `{purged: n}` | `forbidden` |

- Download order: look up row, check state, head the R2 object, run the conditional UPDATE, then stream with `Content-Disposition: attachment` and `X-Content-Type-Options: nosniff`. A missing R2 object returns 404 without counting.
- Wrong password adds 1 to `failed_attempts`; 5 failures set `locked_until` to now + 15 minutes and reset the count. A correct password resets it.
- Stripping slashes and control characters from `name` is required. Never use the name in the R2 key.

## Screens and states

- `/`: signed out shows "Sign in with ChatGPT to send files" and the sign-in link. Signed in shows the drop zone, expiry select (default 7 days), optional password, optional download limit, then **Create link**. Upload shows per-file progress. Over-cap file: "That file is over the 100 MB limit." Failure mid-upload: "Upload failed. Nothing was shared. Try again." Done: the link, a **Copy link** button, and the expiry date.
- `/t/[token]`: loading shows "Checking link". Valid shows title, message, file list with sizes, **Download** per file, and "Expires on <date>". With a password a field appears above the list. Wrong password: "Wrong password." Locked: "Too many tries. Try again in 15 minutes." Expired, deleted, exhausted, unknown: "This link is not available." and nothing else.
- `/mine`: table of title, status (`active`, `expired`, `exhausted`), downloads used/limit, expiry, **Delete**. Empty: "You have not sent anything yet." with a link to `/`.
- `/admin`: counts of expired transfers and their size, **Purge expired** button, result line "Purged <n> transfers."
- Every page footer: "No malware or illegal content. The owner can remove any transfer."
- Mobile: single column; the drop zone becomes a file-picker button.

## Limits and defaults

| Item | Value |
| --- | --- |
| Total size per transfer | default 100 MB; confirm against what the deployed site accepts and record it in the report |
| Single file | same as per transfer |
| Files per transfer | 20 |
| Transfers per user per day | 20 |
| Expiry choices | 1, 7, 30 days; default 7 |
| Max downloads | none by default; range 1 to 1000 |
| Password | 4 to 64 chars; PBKDF2-SHA256, 100,000 iterations |
| Draft cleanup | unfinalized drafts older than 24 hours are removed by purge |

## Verification

1. Signed out, open `/`: the sign-in prompt shows and no upload control.
2. Sign in, upload a 1 MB text file with expiry 1 day, no password: finalize returns a URL starting with `SITE_URL/t/`. Open it in a private window: the file lists and downloads with the original bytes.
3. Reload the link page: the file is still listed; `/mine` shows `download_count` 1.
4. Edge: create a transfer with `max_downloads` 2; download twice, then a third time: the third returns "This link is not available."
5. Edge: create a transfer with password `hunter22`; download with `wrong` five times: the fifth shows the lock message, and `hunter22` is also refused until the lock ends.
6. Edge: set `expires_at` in the past with the D1 console; open the link: neutral page, R2 object gone, row has `deleted_at`.
7. Edge: upload a file named `../../x.txt`: stored name has no slashes.
8. Failure: upload 1 byte over the chosen cap: error message above, no file stored.
9. Failure: call `POST /api/admin/purge` as a non-owner: 403.
10. Delete a transfer in `/mine`: its link shows the neutral page.

## Out of scope

Resumable uploads for very large files, virus scanning, zip downloads, email delivery of links without Resend (show a copyable link instead), recipient accounts.
