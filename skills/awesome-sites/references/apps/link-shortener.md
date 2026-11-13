# Link Shortener with QR and Stats on Sites

Builds short links with click statistics and QR codes.

Resembles: Bitly, Dub.

Read first: `../shared/baseline.md`, `../shared/access-and-domains.md`, `../shared/usage-guard.md` (URL checks).
Access: public site with owner admin (baseline): redirects are public; creating links requires SIWC and (default) the owner's email. Audience: Anyone on the internet.
Keys: none.

## Data

```sql
CREATE TABLE links (
  id TEXT PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE CHECK (slug = lower(slug) AND length(slug) BETWEEN 3 AND 32),
  target_url TEXT NOT NULL CHECK (length(target_url) <= 2048),
  title TEXT NOT NULL DEFAULT '' CHECK (length(title) <= 120),
  owner_email TEXT NOT NULL,
  expires_at INTEGER,
  password_hash TEXT, password_salt TEXT,
  is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
  click_count INTEGER NOT NULL DEFAULT 0,       -- human clicks only
  created_at INTEGER NOT NULL
);
CREATE INDEX idx_links_owner ON links(owner_email, created_at DESC);
CREATE TABLE clicks (
  id TEXT PRIMARY KEY,
  link_id TEXT NOT NULL REFERENCES links(id) ON DELETE CASCADE,
  ts INTEGER NOT NULL,
  referrer_host TEXT, country TEXT,
  device TEXT NOT NULL CHECK (device IN ('mobile','desktop','bot')),
  ip_hash TEXT                                  -- first 16 hex of SHA-256(ip | UTC day | link id)
);
CREATE INDEX idx_clicks_link_ts ON clicks(link_id, ts);
CREATE TABLE unlock_attempts (
  link_id TEXT NOT NULL, ip_hash TEXT NOT NULL, window_start INTEGER NOT NULL, count INTEGER NOT NULL,
  PRIMARY KEY (link_id, ip_hash)
);
```

- Reserved slugs (rejected with `invalid_input`): `admin`, `api`, `signin-with-chatgpt`, `signout-with-chatgpt`, `_next`, `assets`, `favicon.ico`, `terms`, `health`, and every other app route. Slugs are lowercased before the check.
- A recorded click is one batch: insert into `clicks`, and `UPDATE links SET click_count = click_count + 1` only when device is not `bot`. A failure in this batch must be caught and must not stop the redirect.
- Raw IP addresses are never stored. Clicks older than 365 days are deleted by the admin stats page load, 500 rows at a time.

## API contract

| Route | Auth | Request | Success | Errors |
| --- | --- | --- | --- | --- |
| `GET /:slug` | public | none | 302 to target after recording | neutral 404 page (unknown, inactive, expired); password link shows a form |
| `POST /:slug/unlock` | public | form `password` | 302 to target after recording | `forbidden` (wrong), `rate_limited` |
| `GET /api/links` | owner | `?q=`, pagination | `{items: [{id, slug, short_url, target_url, title, click_count, is_active, expires_at}], next_cursor}` | `forbidden` |
| `POST /api/links` | owner | `{target_url, slug?, title?, expires_at?, password?}` | 201 link with `short_url` | `invalid_input`, `conflict` (slug taken) |
| `PATCH /api/links/:id` | owner | any of title, target_url, expires_at, is_active, password (null removes) | 200 link | `not_found`, `invalid_input` |
| `DELETE /api/links/:id` | owner | none | 200 `{deleted: true}` | `not_found` |
| `GET /api/links/:id/stats` | owner | `?days=30` | `{total, daily: [{day, count}], referrers: [{host, count}], devices, countries}` | `not_found` |
| `POST /api/links/bulk` | owner | `{urls: string[]}` max 100 | `text/csv` with columns `url,short_url,error` | `invalid_input` (empty or over 100) |

- `short_url` is always `SITE_URL/<slug>`. QR codes encode the same value.
- Auto slug: 7 characters from `a-z0-9` without `0o1li`; on collision retry up to 5 times, then `conflict`.
- Target rules: only `http:` and `https:`; length at most 2048; reject any URL whose host equals the host of `SITE_URL` or the request origin. Do not fetch the target. Expiry must be in the future.
- Bot detection: user agent contains `bot`, `crawler`, `spider`, `preview`, `facebookexternalhit`, or `curl`; mobile if it contains `Mobi`. Country comes from the request metadata when present, otherwise null.
- A password link records a click only after a correct password, not when the form is shown.
- Wrong password: 5 failures per (link, ip_hash) in 10 minutes returns `rate_limited`.

## Screens and states

- `/[slug]`: neutral 404 reads "This link is not available." and shows no owner or target data. Password form: "This link is protected. Enter the password." and wrong password reads "Wrong password."
- `/admin`: signed out shows the sign-in prompt; non-owner shows "Only the owner can manage links." Loading: "Loading links". Empty: "No links yet. Paste a URL above to create one." Error: "Could not load links. Reload to try again." Create form: URL, optional slug, optional title, optional expiry date, optional password. Slug taken: "That short name is taken." Table: slug, target, clicks, status, **Copy**, **Edit**, **Deactivate**, **Delete** (confirm: "Delete this link? Its short URL will stop working.").
- Bulk panel: textarea, one URL per line, **Create and download CSV**.
- `/admin/[id]`: total clicks, 30 daily bars (days with zero shown), top 10 referrers, devices, top 10 countries, QR code with **Download PNG** (1024 px) and **Download SVG**. Empty stats: "No clicks yet." Under the QR: "This QR code points to <short_url>. If you change SITE_URL or the domain, printed codes keep the old address."
- Mobile: table becomes a list of cards.

## MCP tools

Enabled with `capabilities: ["mcp"]`; every tool requires the owner, and discovery exposes no links. `create_link` (write): `target_url`, `slug?`, `title?`, `expires_at?`; returns `short_url`. `list_links` (read-only): `q?`, `limit` max 50; returns slug, `short_url`, target, `click_count`. `link_stats` (read-only): `slug`, `days?`; returns the stats object above.

## Limits and defaults

| Item | Value |
| --- | --- |
| Slug length | 3 to 32, `[a-z0-9-_]` |
| Target URL | 2048 chars |
| Bulk | 100 URLs per request |
| Links per owner | 10,000 |
| Stats window | default 30 days, max 365 |
| Password | 4 to 64 chars, PBKDF2-SHA256 |
| Click retention | 365 days |

## Verification

1. Sign in as owner, create a link to `https://example.com` with slug `demo`. `short_url` is `SITE_URL/demo`.
2. Open `/demo` signed out: 302 to `https://example.com`. Reload `/admin/<id>`: 1 click, today's bar is 1.
3. Scan or decode the QR: the text equals `SITE_URL/demo`.
4. Edge: `curl -A "Googlebot/2.1" SITE_URL/demo`: still redirects; `click_count` unchanged.
5. Edge: create `Demo` again: `conflict` (lowercased). Create slug `admin`: `invalid_input`.
6. Edge: bulk with 3 valid URLs and `ftp://x`: CSV has 4 rows, the last with an error.
7. Edge: `PATCH` with a past `expires_at` is refused with `invalid_input`; set it 1 minute ahead, wait, open: neutral 404.
8. Failure: create a link whose target is `SITE_URL/demo`: `invalid_input`. Signed out `POST /api/links`: 401.
9. Failure: password link with 5 wrong tries: `rate_limited`.
10. Reload `/admin`: links and click counts persist.

## Out of scope

Deep links, A/B routing, retargeting pixels, team workspaces, link previews, per-visitor identity, automatic domain changes (the owner sets a custom domain in Sites settings; it costs credits per month).
