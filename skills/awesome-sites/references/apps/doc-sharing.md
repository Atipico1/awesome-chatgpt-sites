# Document Sharing with View Analytics on Sites

Builds a trackable PDF share link: the owner uploads a PDF, creates one link per recipient, and sees who opened it, when, and how long they stayed on each page.

Resembles: Papermark, DocSend.

Read first: `../shared/baseline.md`, `../shared/access-and-domains.md`, `../shared/usage-guard.md` (rate limits, privacy).
Access: public site with owner admin (baseline). Viewers need no login. Audience: Anyone on the internet, because recipients have no ChatGPT account.
Keys: none. Needs R2 (bind as `FILES`) and D1 (`DB`).

## Data

```sql
CREATE TABLE documents (
  id TEXT PRIMARY KEY,
  owner_email TEXT NOT NULL,
  title TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 120),
  r2_key TEXT NOT NULL UNIQUE,                    -- docs/<document id>, never built from a file name
  size INTEGER NOT NULL CHECK (size > 0),
  page_count INTEGER CHECK (page_count IS NULL OR page_count BETWEEN 1 AND 2000),  -- read by the owner's browser after upload
  taken_down_at INTEGER, takedown_reason TEXT,
  created_at INTEGER NOT NULL
);
CREATE INDEX idx_documents_owner ON documents(owner_email, created_at DESC);
CREATE TABLE share_links (
  id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  token TEXT NOT NULL UNIQUE,                     -- 22+ random URL-safe chars
  label TEXT NOT NULL DEFAULT '' CHECK (length(label) <= 80),   -- usually the recipient
  password_hash TEXT, password_salt TEXT,         -- PBKDF2-SHA256, base64; NULL = no password
  failed_attempts INTEGER NOT NULL DEFAULT 0, locked_until INTEGER,
  require_email INTEGER NOT NULL DEFAULT 0 CHECK (require_email IN (0,1)),
  allow_download INTEGER NOT NULL DEFAULT 0 CHECK (allow_download IN (0,1)),
  expires_at INTEGER, revoked_at INTEGER,
  owner_seen_at INTEGER NOT NULL DEFAULT 0,       -- last time the owner opened this link's stats
  created_at INTEGER NOT NULL
);
CREATE INDEX idx_links_document ON share_links(document_id);
CREATE TABLE view_sessions (
  id TEXT PRIMARY KEY,                            -- session cookie value
  link_id TEXT NOT NULL REFERENCES share_links(id) ON DELETE CASCADE,
  viewer_id TEXT NOT NULL,                        -- 180-day cookie, one per browser per link
  email TEXT,                                     -- typed by the viewer, not verified
  started_at INTEGER NOT NULL, last_seen_at INTEGER NOT NULL,
  ip_hash TEXT NOT NULL                           -- first 16 hex of SHA-256(ip | UTC day | link id)
);
CREATE INDEX idx_sessions_link ON view_sessions(link_id, started_at);
CREATE TABLE page_time (
  session_id TEXT NOT NULL REFERENCES view_sessions(id) ON DELETE CASCADE,
  page INTEGER NOT NULL CHECK (page BETWEEN 1 AND 2000),
  seconds INTEGER NOT NULL DEFAULT 0 CHECK (seconds BETWEEN 0 AND 3600),
  PRIMARY KEY (session_id, page)
);
CREATE TABLE reports (
  id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  reason TEXT NOT NULL CHECK (reason IN ('malware','illegal','phishing','other')),
  note TEXT NOT NULL DEFAULT '' CHECK (length(note) <= 500),
  ip_hash TEXT NOT NULL, created_at INTEGER NOT NULL, resolved_at INTEGER
);
CREATE INDEX idx_reports_open ON reports(resolved_at, created_at);
CREATE TABLE rate_hits (
  key TEXT NOT NULL, window_start INTEGER NOT NULL, count INTEGER NOT NULL,
  PRIMARY KEY (key, window_start)
);
```

- A view is one `view_sessions` row. A valid session cookie with `last_seen_at` within 30 minutes reuses the row; otherwise the viewer passes the gate again and a new row is created.
- Beacon writes are one upsert per page: `INSERT ... ON CONFLICT(session_id, page) DO UPDATE SET seconds = MIN(3600, seconds + :delta)`. Rate limits increment `rate_hits` in one statement before the work.
- Upload: check that the first 5 bytes are `%PDF-` before writing to R2, then insert the row. If the insert fails, delete the R2 object.

## API contract

| Route | Auth | Request | Success | Errors |
| --- | --- | --- | --- | --- |
| `POST /api/documents?title=` | owner | raw PDF body within cap | 201 `{id, title, size}` | `invalid_input` (not `%PDF-`, empty, over cap) |
| `GET /api/documents` | owner | pagination | items with `page_count`, `taken_down_at`, `link_count`, `open_reports` | `forbidden` |
| `PATCH /api/documents/:id` | owner | `{title?, page_count?}` | 200 document | `not_found`, `invalid_input` |
| `GET /api/documents/:id/pdf` | owner | none | PDF stream, no view recorded | `not_found` |
| `DELETE /api/documents/:id` | owner | none | 200; R2 object removed | `not_found` |
| `POST /api/documents/:id/takedown`, `/restore` | owner | `{reason?}` | 200 document | `not_found` |
| `POST /api/documents/:id/links` | owner | `{label?, password?, require_email?, allow_download?, expires_at?}` | 201 `{id, token, url}`, `url = SITE_URL/d/<token>` | `invalid_input`, `conflict` (50 links) |
| `PATCH /api/links/:id` | owner | any create field; `password: null` removes; `revoked: true` | 200 link | `not_found`, `invalid_input` |
| `GET /api/links/:id/stats` | owner | none | stats object below; sets `owner_seen_at` | `not_found` |
| `GET /api/reports`, `POST /api/reports/:id/resolve` | owner | pagination | reports with document title | `forbidden` |
| `GET /api/v/:token` | public | none | `{title, requires_password, requires_email, allow_download, has_session}`; taken down returns `{unavailable: true}` | `not_found` (unknown, expired, revoked: one message) |
| `POST /api/v/:token/open` | public | `{password?, email?}` | 200 `{page_count}`, sets cookies | `forbidden` (wrong password), `rate_limited` (locked or over limit), `invalid_input` (bad email), `not_found` |
| `GET /api/v/:token/pdf` | session cookie | optional `Range`; `?download=1` | PDF stream, `Content-Type: application/pdf`, `X-Content-Type-Options: nosniff`, `Cache-Control: private, no-store`; `download=1` adds `attachment` | `unauthorized`, `forbidden` (download off), `not_found` |
| `POST /api/v/:token/beacon` | session cookie | JSON text body `{events: [{page, seconds}]}`, up to 5 events, `seconds` 0 to 15 | 204 | `unauthorized`, `rate_limited`, `invalid_input` |
| `POST /api/v/:token/report` | public | `{reason, note?}` | 201 | `invalid_input`, `rate_limited` |

- Every PDF request re-checks: link exists, not revoked, not expired, document not taken down, session valid for this link. The R2 key is never exposed; there is no public R2 URL.
- Wrong password adds 1 to `failed_attempts`; 5 failures lock the link for 15 minutes; a correct password resets it. The email gate stores the lowercased address if it matches a basic email pattern. It is never verified.
- Beacon `page` must not exceed `page_count` when set. The viewer sends the beacon with `navigator.sendBeacon` every 10 seconds while a page is visible and on `visibilitychange`. Timing is reported by the browser, so it is approximate and can be faked.
- Stats object: `{views, unique_viewers, emails: [{email, first_seen_at}], pages: [{page, avg_seconds, sessions}], drop_off_page, sessions: [{started_at, email, last_page, total_seconds}], new_since_seen}`. `views` counts sessions; `unique_viewers` counts distinct `viewer_id`. `drop_off_page` is the page where most sessions ended (highest page with seconds above 0), ignoring sessions that reached the last page; null when `page_count` is null or there are no sessions. `new_since_seen` counts sessions started after `owner_seen_at`.

## Screens and states

- `/admin`: signed out shows the sign-in prompt; non-owner shows "Only the owner can manage documents." PDF upload; after upload the page opens the file with pdf.js to read `page_count` and saves it. Documents table with link count, open reports, **New link**, **Take down**, **Delete**. Loading: "Loading documents". Empty: "No documents yet. Upload a PDF to get a share link." Over cap: "That file is over the 25 MB limit." Not a PDF: "Only PDF files are accepted." A "New views" count at the top is the only notification; no email is sent.
- `/admin/documents/[id]`: links table with label, views, new-view badge, unique viewers, emails captured, avg time per page, drop-off page, **Copy link**, **Edit**, **Revoke**; per-link detail with a bar of average seconds per page and the session list. Empty: "No one has opened this link yet." Download toggle text: "Download is off. This hides the download button. It does not stop screenshots, and the browser still receives the file."
- `/admin/reports`: open reports with reason, note, time, **Take down document**, **Dismiss**. Empty: "No reports."
- `/d/[token]`: loading "Checking link". Unknown, expired, revoked: "This link is not available." Taken down: "This document is no longer available." The gate form shows only the fields the link needs and is skipped when `has_session` is true. Email label: "Your email. The sender will see it. We do not verify it." Wrong password: "Wrong password." Locked: "Too many tries. Try again in 15 minutes." The viewer uses pdf.js bundled with the site (no third-party host), one canvas per page, rendered lazily. Footer: "No malware or illegal content." and **Report this document**. Idle 30 minutes: "This session ended. Open the link again." Render failure: "Could not display this document."
- Mobile: single column; pages scale to screen width.

## MCP tools

Enabled with `capabilities: ["mcp"]`; owner only; discovery exposes no documents. `list_documents` (read-only): `limit` max 50; returns id, title, page count, link count. `get_document_stats` (read-only): `document_id`; stats per link, without emails unless `include_emails: true`. `create_share_link` (write): `document_id`, `label?`, `expires_in_days?`, `require_email?`; download stays off, no password; returns the URL.

## Limits and defaults

| Item | Value |
| --- | --- |
| File | PDF only; default cap 25 MB; choose from what the deployed site accepts, record it in the report |
| Documents per owner / links per document | 100 / 50 |
| Session | 30 minutes idle; cookie `HttpOnly`, `Secure`, `SameSite=Lax` |
| Viewer cookie | 180 days |
| Rate limits per `ip_hash` | open 20/min; PDF 60/min; report 5/hour; beacon 20/min per session |
| Password | 4 to 64 chars; PBKDF2-SHA256, 100,000 iterations |
| Retention | sessions and page time 365 days, purged 500 rows at a time on admin page load |

## Verification

1. Sign in as owner, upload `sample.pdf` (3 pages, under 1 MB). It lists with `page_count` 3.
2. Create a link "Alice" with email gate on and download off. In a private window enter `alice@example.com`; the PDF shows. Stay 12 seconds on page 1, 5 seconds on page 2, close the tab.
3. Reload `/admin/documents/<id>`: views 1, unique viewers 1, emails 1, page 1 average above 5 seconds, drop-off page 2, new-view badge shown, cleared after opening stats.
4. Edge: reload the viewer within 30 minutes: no gate, views stays 1. After 31 idle minutes the gate returns; passing it gives views 2, unique viewers 1.
5. Edge: password link `hunter22`; five wrong tries lock it and the correct password is refused until the lock ends.
6. Edge: with download off, `GET /api/v/<token>/pdf?download=1` returns 403; with it on, the response has `attachment`.
7. Edge: revoke the link, then separately set `expires_at` in the past: both show "This link is not available."
8. Failure: upload a `.txt` file renamed `.pdf`: `invalid_input`, no R2 object. One byte over the cap: error shown, nothing stored.
9. Failure: signed out `GET /api/documents`: 401; `GET /api/v/<token>/pdf` without a session cookie: 401.
10. Report the document from the viewer, take it down in `/admin/reports`: the link shows "This document is no longer available." and the PDF route sends no bytes. Restore and reload: stats are unchanged.

## Out of scope

E-signature, data rooms with folders or permissions, watermarks, email notifications (Resend could be added later per `api-keys.md`), non-PDF files, verified viewer identity, paid plans. To charge later, follow the Stripe pattern in `digital-storefront.md`.
