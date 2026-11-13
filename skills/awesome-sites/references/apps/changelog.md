# Changelog Page on Sites

Builds a public release-notes page with categories, an RSS feed, and an embeddable "What's new" widget.

Resembles: Headway, Beamer.

**Read first:** `../shared/baseline.md`, `../shared/access-and-domains.md`.
**Access:** public site with owner admin. **Audience:** Public (anyone on the internet); RSS readers and the widget on other sites fail on a private audience.
**Keys:** none.

## Data

```sql
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);  -- 'owner_email' when OWNER_EMAILS is empty; 'hash_salt'
CREATE TABLE products (
  id TEXT PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE CHECK (length(slug) BETWEEN 2 AND 40 AND slug NOT GLOB '*[^a-z0-9-]*'),
  name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 60),
  accent TEXT NOT NULL DEFAULT '#2563eb' CHECK (accent GLOB '#[0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F]')
);
CREATE TABLE entries (
  id TEXT PRIMARY KEY,
  product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  title TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 120),
  body_md TEXT NOT NULL CHECK (length(body_md) <= 20000),
  category TEXT NOT NULL CHECK (category IN ('new','improved','fixed','removed')),
  published_at INTEGER,              -- NULL = draft; future = scheduled; past = live
  slug TEXT NOT NULL UNIQUE,         -- from title, lowercase, max 80, plus -xxxx suffix on conflict
  pinned INTEGER NOT NULL DEFAULT 0 CHECK (pinned IN (0,1)),
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);
CREATE TABLE reactions (
  entry_id TEXT NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
  reactor_hash TEXT NOT NULL,        -- HMAC of the cookie id with hash_salt
  kind TEXT NOT NULL CHECK (kind IN ('👍','🎉','❤️')),
  created_at INTEGER NOT NULL,
  PRIMARY KEY (entry_id, reactor_hash, kind)
);
CREATE INDEX entries_live ON entries(published_at DESC) WHERE published_at IS NOT NULL;
CREATE INDEX entries_product_live ON entries(product_id, published_at DESC);
CREATE INDEX reactions_entry ON reactions(entry_id, kind);
```

- An entry is visible only when `published_at IS NOT NULL AND published_at <= now`, checked on every request in the page, feed, widget API, and entry page. Never cache these responses for more than 60 seconds, so a scheduled entry appears without a job.
- Body is rendered to HTML on the server. Allowed: headings, bold, italic, lists, code, blockquote, links (`http`, `https`, `mailto`), and images whose source starts with `SITE_URL/img/`. Everything else is stripped.
- `reactor_hash`: a random cookie `cl_rid` (1 year) hashed with `hash_salt`. Reacting twice with the same kind removes it.

## API contract

| Route | Auth | Request | Success | Errors |
| --- | --- | --- | --- | --- |
| `GET /api/entries` | public | `product?` (slug), `category?`, `limit` (default 20), `cursor` | `{items:[{slug,title,category,product,body_html,published_at,pinned,reactions:{"👍":n,"🎉":n,"❤️":n}}],next_cursor}` live entries, pinned first, then newest | not_found (unknown product) |
| `GET /api/entries/:slug` | public | none | entry 200 | not_found (draft, scheduled, or unknown) |
| `POST /api/entries/:slug/reactions` | public | `kind` | `{kind,active,count}` toggles for this cookie | invalid_input, not_found, rate_limited |
| `GET /api/embed/entries` | public, CORS `*` | none | `{items:[last 5 live: slug,title,category,published_at,url]}` | none |
| `GET /feed.xml` | public | `product?` | RSS 2.0, see below | not_found |
| `GET /img/:key` | public | none | the R2 object with its content type | not_found |
| `GET /api/admin/entries` | owner | `status=draft\|scheduled\|live`, `limit`, `cursor` | entries with `body_md` | unauthorized, forbidden |
| `POST /api/admin/entries` | owner | `product_id`, `title`, `body_md`, `category`, `published_at?`, `pinned?` | entry 201 | forbidden, invalid_input (also more than 3 pinned) |
| `PATCH /api/admin/entries/:id` | owner | any entry field except `id`, `slug` | entry 200 | forbidden, not_found, invalid_input |
| `DELETE /api/admin/entries/:id` | owner | none | 204 | forbidden, not_found |
| `POST /api/admin/images` | owner | multipart `file` jpeg/png/webp, max 2 MB | `{url}` 201 (`SITE_URL/img/<uuid>.<ext>`) | forbidden, invalid_input (type or size) |
| `POST /api/admin/products`, `PATCH /api/admin/products/:id` | owner | `slug`, `name`, `accent?` | product 201/200 | forbidden, invalid_input, conflict |

Feed: RSS 2.0, latest 30 live entries (all products, or one with `?product=`), `<link>` = SITE_URL, each item has `title`, `link` and `guid` = `SITE_URL/e/<slug>`, `pubDate` in RFC 822, `category`, and the full HTML in `content:encoded`. Drafts and scheduled entries never appear.

## Screens and states

- **`/` and `/p/[slug]`:** entries newest first, grouped under month headings ("November 2026", UTC), pinned entries in a "Pinned" group first, a category filter (All, New, Improved, Fixed, Removed), a coloured category label per entry, and an anchor link per entry (`#slug`). Product tabs show only when there are 2 or more products. 20 per page with a "Load more" button. Loading: 3 skeleton entries. Empty: "No updates yet." Filter with no match: "No updates in this category." Error: "Could not load updates. Reload to try again."
- **`/e/[slug]`:** one entry, a Copy link button, three reaction buttons with counts (active when the visitor reacted). Missing or unpublished: "This update does not exist."
- **`/embed.js`:** injects a bell button fixed at the bottom right of the host page and, on click, a panel listing the last five entries as links to `/e/[slug]` ("What's new"). Everything lives in a shadow root; the script never reads the host page's DOM, cookies, or storage. Panel empty: "No updates yet." Panel error: "Could not load updates." Snippet shown in `/admin`: a single script tag with `src` = `SITE_URL/embed.js`.
- **`/admin`:** owner only; others see "You do not have access to this page." First run with no product: only a form to create the first product. Entry list with tabs Drafts, Scheduled, Live. Editor: product, title, category, markdown textarea with a live preview beside it (stacked on a phone), image button (inserts the returned markdown), pin toggle, a date-time field read in the browser's time zone and stored as UTC milliseconds, and buttons Save draft, Publish now, Schedule. A scheduled entry is listed with its date and shown publicly only after that time.

## Limits and defaults

| Item | Value |
| --- | --- |
| Title / body | 120 / 20,000 characters |
| Image | jpeg, png, webp; 2 MB |
| Feed items | 30 |
| Widget items | 5 |
| Page size | 20 (admin 50, max 200) |
| Pinned entries | 3 |
| Products | 10 |
| Reactions | 60 per hour per cookie |
| Response caching | max 60 s |

## Verification

1. As owner, create product "App" (slug `app`) and a draft "First release" in category `new`. Open `/`, `/feed.xml`, and `/api/embed/entries` signed out: the draft appears in none.
2. Click Publish now. Reload `/`: the entry is listed under the current month; `/feed.xml` has one item with full HTML; the widget panel lists it.
3. Feed check: it parses with a standard RSS parser or validator with no errors, and the item `link` starts with SITE_URL.
4. Edge: create an entry scheduled 2 minutes ahead. It is absent now and present after the time passes, with no admin action.
5. Edge: upload a 3 MB PNG: 422 `invalid_input` naming the 2 MB limit. Upload a 100 KB PNG: the markdown image renders on the entry page.
6. Edge: body `<script>alert(1)</script> [x](javascript:alert(1))` renders as plain text and no clickable `javascript:` link.
7. Edge: react 🎉 twice on `/e/<slug>`: count goes to 1, then back to 0.
8. Failure: signed out, `POST /api/admin/entries` returns 401; signed in as non-owner returns 403.
9. Failure: `GET /e/does-not-exist` shows "This update does not exist." with status 404.
10. Pin a fourth entry: 422 `invalid_input`. Reload `/`: all data and reaction counts are unchanged.

Done when a published entry appears on the page, the feed, and the widget, a draft appears in none, and the feed parses.

## Out of scope

Email subscribers, per-user "unread" tracking and badges, multi-language entries, comments, video embeds, image editing.
