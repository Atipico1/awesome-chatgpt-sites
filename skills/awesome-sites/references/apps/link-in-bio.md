# Link-in-Bio Pages on Sites

Builds public one-page profiles of links with themes and click analytics.

Resembles: Linktree, Linkie, Linkos.

Read first: `../shared/baseline.md`, `../shared/access-and-domains.md`, `../shared/usage-guard.md` (rate limits, privacy), `link-shortener.md` (adjacent; this app does not duplicate it).
Access: public site with owner admin (baseline). Pages are public; creating one requires SIWC and the `SIGNUP_MODE` rule below. Audience: Anyone on the internet.
Keys: none. Needs R2 (bind as `FILES`) and D1 (`DB`).

Environment value `SIGNUP_MODE`: `owner_only` (default; also used when the value is missing or invalid) or `open`. In `owner_only` only emails in `OWNER_EMAILS` create pages, up to 20 each; everyone else sees only "Link pages on this site are created by the site owner." at `/`. In `open` any signed-in ChatGPT user creates up to 3 pages. Public multi-tenant link pages are a phishing vector, which Sites prohibits, so `open` requires everything marked "open mode" below: reports, suspension, URL filtering, rate limits. Both modes use them; `open` adds stricter URL rules.

Both this app and `link-shortener.md` serve slugs at the site root. Do not combine them in one site.

## Data

```sql
CREATE TABLE pages (
  id TEXT PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE CHECK (slug = lower(slug) AND length(slug) BETWEEN 3 AND 32),
  owner_email TEXT NOT NULL,
  title TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 60),
  bio TEXT NOT NULL DEFAULT '' CHECK (length(bio) <= 300),
  avatar_key TEXT, avatar_version INTEGER NOT NULL DEFAULT 0,   -- R2 key avatars/<page id>
  theme_id TEXT NOT NULL DEFAULT 'paper',
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','suspended')),
  suspended_reason TEXT,
  rules_accepted_at INTEGER NOT NULL,
  created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
);
CREATE INDEX idx_pages_owner ON pages(owner_email, created_at DESC);
CREATE TABLE blocks (
  id TEXT PRIMARY KEY,
  page_id TEXT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
  type TEXT NOT NULL CHECK (type IN ('link','header','text','social')),
  position INTEGER NOT NULL,
  label TEXT NOT NULL DEFAULT '' CHECK (length(label) <= 80),   -- link text or header text
  url TEXT CHECK (url IS NULL OR length(url) <= 2048),          -- link blocks
  body TEXT NOT NULL DEFAULT '' CHECK (length(body) <= 500),    -- text blocks
  socials TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(socials)), -- [{network,url}], max 8
  is_visible INTEGER NOT NULL DEFAULT 1 CHECK (is_visible IN (0,1)),
  created_at INTEGER NOT NULL
);
CREATE INDEX idx_blocks_page ON blocks(page_id, position);
CREATE TABLE page_views (
  id TEXT PRIMARY KEY,
  page_id TEXT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
  session_id TEXT NOT NULL, ts INTEGER NOT NULL,
  referrer_host TEXT, device TEXT NOT NULL CHECK (device IN ('mobile','desktop'))
);
CREATE INDEX idx_views_page_ts ON page_views(page_id, ts);
CREATE INDEX idx_views_session ON page_views(page_id, session_id, ts);
CREATE TABLE block_clicks (
  id TEXT PRIMARY KEY,
  block_id TEXT NOT NULL REFERENCES blocks(id) ON DELETE CASCADE,
  page_id TEXT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
  network TEXT, ts INTEGER NOT NULL
);
CREATE INDEX idx_clicks_page_ts ON block_clicks(page_id, ts);
CREATE TABLE blocked_hosts (host TEXT PRIMARY KEY, note TEXT NOT NULL DEFAULT '', created_at INTEGER NOT NULL);
CREATE TABLE reports (
  id TEXT PRIMARY KEY,
  page_id TEXT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
  reason TEXT NOT NULL CHECK (reason IN ('phishing','impersonation','illegal','other')),
  note TEXT NOT NULL DEFAULT '' CHECK (length(note) <= 500),
  ip_hash TEXT NOT NULL, created_at INTEGER NOT NULL, resolved_at INTEGER
);
CREATE TABLE rate_hits (
  key TEXT NOT NULL, window_start INTEGER NOT NULL, count INTEGER NOT NULL,
  PRIMARY KEY (key, window_start)
);
```

- Reordering is one batch: the client sends the full ordered id list and the server rewrites `position` as 0, 1, 2 and so on. Drag in the UI sets the order; the server never trusts a position sent by a block edit.
- A page view is inserted only if no row exists for the same `page_id` and `session_id` with `ts` in the last 30 minutes. The `lb_s` cookie holds a random session id, `HttpOnly`, `Secure`, `SameSite=Lax`. Bots (user agent containing `bot`, `crawler`, `spider`, `preview`, `facebookexternalhit`, `curl`) are neither counted nor stored. Raw IPs are never stored.
- Themes are constants (below), not user data. `theme_id` must be one of their ids.

## Slugs and themes

Slugs use `a-z0-9-_`, no leading or trailing hyphen, lowercased before checks. Reserved (`invalid_input`): `admin`, `api`, `signin-with-chatgpt`, `signout-with-chatgpt`, `_next`, `assets`, `favicon.ico`, `terms`, `health`, `report`, `settings`, `out`, and every other app route.

| id | Page bg | Text | Button bg | Button text | Style | Radius px | Font stack |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `paper` | #FFFFFF | #111111 | #111111 | #FFFFFF | solid | 8 | system sans-serif |
| `night` | #0F172A | #F8FAFC | #38BDF8 | #0F172A | solid | 12 | system sans-serif |
| `sand` | #F5EFE6 | #2B2118 | #2B2118 | #2B2118 | outline | 4 | Georgia, serif |
| `forest` | #14301F | #EAF5EC | #A7F3D0 | #14301F | solid | 999 | system sans-serif |
| `sunset` | #FFF1E6 | #4A1D0B | #C2410C | #FFFFFF | solid | 999 | system sans-serif |
| `mono` | #E5E5E5 | #000000 | #000000 | #000000 | outline | 0 | ui-monospace, Menlo, Consolas, monospace |

Outline buttons draw a 2 px border in the button color over a transparent fill. Social networks and their allowed hosts: `instagram` (instagram.com), `x` (x.com, twitter.com), `youtube` (youtube.com, youtu.be), `tiktok` (tiktok.com), `github` (github.com), `linkedin` (linkedin.com), `facebook` (facebook.com). A social URL must be https and its host must equal or be a subdomain of an allowed host.

## API contract

| Route | Auth | Request | Success | Errors |
| --- | --- | --- | --- | --- |
| `POST /api/pages` | signed-in, allowed by mode | `{slug, title, bio?, theme_id?, rules_accepted: true}` | 201 page with `url = SITE_URL/<slug>` | `forbidden` (mode or limit), `invalid_input`, `conflict` (slug), `rate_limited` (5 per user per day) |
| `GET /api/pages` | signed-in | pagination | own pages with status | none |
| `PATCH /api/pages/:id` | page owner | title, bio, theme_id, slug | 200 page | `not_found`, `invalid_input`, `conflict` |
| `DELETE /api/pages/:id` | page owner | none | 200 `{deleted: true}`; avatar removed | `not_found` |
| `PUT /api/pages/:id/avatar` | page owner | raw body, `image/jpeg`, `image/png` or `image/webp`, max 1 MB, magic bytes checked | 200 page | `invalid_input`, `rate_limited` (10 per day) |
| `POST /api/pages/:id/blocks` | page owner | `{type, label?, url?, body?, socials?}` | 201 block | `invalid_input` (30 blocks max, bad URL) |
| `PATCH` / `DELETE /api/blocks/:id` | page owner | any block field except position | 200 | `not_found`, `invalid_input` |
| `PUT /api/pages/:id/order` | page owner | `{block_ids: [...]}` all blocks of the page | 200 | `invalid_input` (set differs) |
| `GET /api/pages/:id/stats` | page owner | `?days=30` | `{views, unique_sessions, clicks, daily: [{day, views, clicks}], blocks: [{block_id, label, clicks}], referrers: [{host, count}], devices}` | `not_found` |
| `GET /:slug` | public | none | rendered page | neutral 404 |
| `GET /out/:block_id` | public | `?n=<network>` for social blocks | 302 to the stored URL after recording | neutral 404 |
| `GET /a/:page_id` | public | none | avatar bytes, `nosniff` | 404 |
| `POST /api/report/:slug` | public | `{reason, note?}` | 201 | `invalid_input`, `rate_limited` (5 per hour per `ip_hash`, 1 per page per day) |
| `GET/POST/DELETE /api/admin/blocked-hosts` | owner | `{host}` | list or saved | `forbidden`, `invalid_input` |
| `GET /api/admin/pages`, `POST /api/admin/pages/:id/suspend`, `/restore` | owner | `{reason?}` | pages sorted by open reports; 200 | `forbidden`, `not_found` |
| `GET /api/admin/reports`, `POST /api/admin/reports/:id/resolve` | owner | pagination | reports | `forbidden` |

- URL rules at save and again at redirect: scheme `http:` or `https:` only; no `javascript:`, `data:`, or any other scheme; length at most 2048; host must not equal the host of `SITE_URL` or the request origin; host must not equal or be a subdomain of a `blocked_hosts` row. In `open` mode also require `https:`, reject IP-literal hosts, URLs containing `user:pass@`, and hosts with a label starting `xn--`. A target that fails at redirect time shows the neutral 404 and is not recorded.
- `/out/:block_id` records one `block_clicks` row, then returns 302. A recording failure must not stop the redirect. Suspended pages and hidden blocks return the neutral 404.
- Each link button shows its target host in small text under the label.
- Stats keep 30 days in the UI; rows older than 90 days are deleted on stats load, 500 at a time.

## Screens and states

- `/`: signed out shows the sign-in prompt. Not allowed by mode: the sentence above. Allowed: own pages with **New page**. Empty: "You have no pages yet."
- Create dialog: slug, title, theme, and the rules text "No phishing, impersonation, malware, or illegal content. Nothing aimed at children under 13. The site owner can remove any page." with a required checkbox. Slug taken: "That name is taken."
- `/admin/pages/[id]` editor: block list with drag handles, add block menu, per-block edit and hide, theme picker, avatar upload, live preview, QR code generated in the browser from `SITE_URL/<slug>` with **Download PNG**, and the note "Printed QR codes keep the address they had when created." Stats tab: totals, 30 daily bars, clicks per block, top 10 referrers, devices. Empty stats: "No views yet."
- `/[slug]`: avatar, title, bio, blocks, footer **Report this page**. Open Graph and Twitter tags: title, description (bio, 160 chars), image (`SITE_URL/a/<id>?v=<version>`), URL (`SITE_URL/<slug>`). Suspended or unknown: "This page is unavailable." and nothing else, no OG tags, `noindex`.
- `/admin`: for `OWNER_EMAILS`: all pages with open-report counts, **Suspend**, **Restore**, the blocked-hosts editor, open reports.
- Mobile: single column, 100% width buttons.

## MCP tools

Enabled with `capabilities: ["mcp"]`; owner only; discovery exposes no pages. `list_pages` (read-only): returns slug, title, status, view and click totals. `add_link` (write): `slug`, `label`, `url`; same URL rules; appends at the end. `get_stats` (read-only): `slug`, `days?` max 30.

## Limits and defaults

| Item | Value |
| --- | --- |
| Pages per user | 20 owners, 3 in `open` mode |
| Blocks per page | 30; socials per block 8 |
| Avatar | 1 MB; jpeg, png, webp |
| Session window | 30 minutes |
| Rate limits | `/out` 120/min per `ip_hash`; page create 5/day; report 5/hour |
| Retention | views and clicks 90 days |

## Verification

1. Set `SIGNUP_MODE=owner_only`, sign in as owner, create slug `demo-bio`, theme `night`, accept the rules. Add a header "Links", a link "Example" to `https://example.com`, and a social row with `github` `https://github.com/example`.
2. Open `/demo-bio` signed out: blocks in order, target host shown. Click "Example": lands on example.com. Reload the editor stats: views 1, clicks 1 for that block.
3. Reload `/demo-bio` within 30 minutes: views stays 1. Drag "Example" above the header, reload: order persists.
4. Edge: slugs `Demo-Bio` (taken after lowercasing), `admin`, `ab` (too short), `-abc`: `conflict` or `invalid_input`.
5. Edge: link URLs `javascript:alert(1)`, `data:text/html,x`, and `SITE_URL/demo-bio`: `invalid_input`.
6. Edge: add `example.com` to blocked hosts; click "Example": neutral 404, no click recorded. Remove it: redirect works.
7. Edge: with `SIGNUP_MODE=open`, a second account creates 3 pages; the fourth returns `forbidden`; `http://example.com` and `https://192.168.0.1/x` return `invalid_input`.
8. Failure: upload a 1.1 MB or non-image avatar: `invalid_input`. A non-owner in `owner_only` mode `POST /api/pages`: 403.
9. Failure: send 6 reports from one address in an hour: `rate_limited`.
10. Report the page, suspend it in `/admin`: `/demo-bio` shows "This page is unavailable." and `/out/<id>` shows the neutral 404. Restore, reload: data persists.

## Out of scope

Custom domains per user (the owner can set one for the whole site; see `access-and-domains.md`), paid tiers (follow the Stripe pattern in `digital-storefront.md`), embedded video players, email collection, per-link scheduling, branding-removal toggles.
