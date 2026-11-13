# Feedback Board on Sites

Builds a public board where customers post feature requests and vote, with a public roadmap the owner controls.

Resembles: Canny, Featurebase.

**Read first:** `../shared/baseline.md`, `../shared/access-and-domains.md`, Resend section of `../shared/api-keys.md`.
**Access:** public site with owner admin. Reading is public; posting, voting, and commenting need SIWC. **Audience:** Public (anyone on the internet). If the account cannot publish publicly, say so and offer an invited-only site.
**Keys:** none required. Optional `RESEND_API_KEY`, `MAIL_FROM`: without them, new-post notifications to the owner are not sent and the outbox row is stored as `skipped`.

## Data

```sql
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);  -- 'owner_email' when OWNER_EMAILS is empty
CREATE TABLE boards (
  id TEXT PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE CHECK (length(slug) BETWEEN 2 AND 40 AND slug NOT GLOB '*[^a-z0-9-]*'),
  name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 60),
  description TEXT NOT NULL DEFAULT '' CHECK (length(description) <= 300),
  created_at INTEGER NOT NULL
);
CREATE TABLE posts (
  id TEXT PRIMARY KEY,
  board_id TEXT NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
  title TEXT NOT NULL CHECK (length(title) BETWEEN 3 AND 120),
  body TEXT NOT NULL DEFAULT '' CHECK (length(body) <= 5000),          -- markdown source, sanitized on render
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','planned','in_progress','shipped','declined')),
  author_email TEXT NOT NULL,
  vote_count INTEGER NOT NULL DEFAULT 0 CHECK (vote_count >= 0),
  pinned INTEGER NOT NULL DEFAULT 0 CHECK (pinned IN (0,1)),
  hidden INTEGER NOT NULL DEFAULT 0 CHECK (hidden IN (0,1)),
  merged_into TEXT REFERENCES posts(id),
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);
CREATE TABLE votes (
  post_id TEXT NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
  voter_email TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  PRIMARY KEY (post_id, voter_email)
);
CREATE TABLE comments (
  id TEXT PRIMARY KEY,
  post_id TEXT NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
  author_email TEXT NOT NULL,
  body TEXT NOT NULL CHECK (length(body) BETWEEN 1 AND 2000),
  is_owner INTEGER NOT NULL DEFAULT 0 CHECK (is_owner IN (0,1)),
  hidden INTEGER NOT NULL DEFAULT 0 CHECK (hidden IN (0,1)),
  created_at INTEGER NOT NULL
);
CREATE TABLE outbox (
  id TEXT PRIMARY KEY, kind TEXT NOT NULL DEFAULT 'email', payload TEXT NOT NULL CHECK (json_valid(payload)),
  status TEXT NOT NULL CHECK (status IN ('pending','sent','failed','skipped')),
  attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT, created_at INTEGER NOT NULL
);
CREATE INDEX posts_board_votes ON posts(board_id, hidden, status, vote_count DESC);
CREATE INDEX posts_board_new ON posts(board_id, hidden, created_at DESC);
CREATE INDEX posts_author_time ON posts(author_email, created_at);
CREATE INDEX comments_post_time ON comments(post_id, created_at);
CREATE INDEX comments_author_time ON comments(author_email, created_at);
CREATE INDEX votes_voter ON votes(voter_email);
```

- Voting toggles one `votes` row and sets `vote_count` to the row count in the same D1 batch. Creating a post also inserts the author's vote (count starts at 1).
- Merge (one batch): `INSERT OR IGNORE` the source's votes into the target; delete the source's votes; move the source's comments to the target; set target `vote_count` to its row count; set source `hidden=1`, `merged_into=target`, `vote_count=0`.
- Other users see authors as the first 3 characters of the local part (1 character if it is shorter than 4), then `•••@`, for example `ann•••@`. The signed-in user sees "You" on their own items. The owner sees full emails in `/admin` only.
- Markdown allows bold, italic, lists, code, and `http`/`https` links (`rel="nofollow noopener"`); raw HTML and images are removed.

## API contract

| Route | Auth | Request | Success | Errors |
| --- | --- | --- | --- | --- |
| `GET /api/boards` | public | none | `{items:[{slug,name,description,post_count}]}` 200 | none |
| `POST /api/boards` | owner | `slug`, `name`, `description?` | board 201 | unauthorized, forbidden, invalid_input, conflict (slug taken) |
| `PATCH /api/boards/:slug` | owner | `name?`, `description?` | board 200 | forbidden, not_found, invalid_input |
| `GET /api/boards/:slug/posts` | public | `sort=votes\|new` (default votes), `status?`, `q?` (max 80), `limit`, `cursor` | `{items:[{id,title,status,vote_count,comment_count,pinned,author_label,created_at,voted}],next_cursor}`; `voted` is false when signed out; pinned items first | not_found, invalid_input |
| `GET /api/boards/:slug/similar` | public | `q` 3-120 chars | `{items:[{id,title,vote_count}]}`, max 5, title contains any word of 3+ characters | invalid_input |
| `POST /api/boards/:slug/posts` | signed-in | `title`, `body?` | post 201 | unauthorized, invalid_input, rate_limited, not_found |
| `GET /api/posts/:id` | public | none | post with `body_html` 200; merged post returns 301 to target | not_found (also for hidden, unless owner) |
| `POST /api/posts/:id/vote` | signed-in | none (toggle) | `{voted, vote_count}` 200 | unauthorized, not_found, rate_limited |
| `GET /api/posts/:id/comments` | public | `limit`, `cursor` (oldest first) | `{items:[{id,author_label,is_owner,body_html,created_at}],next_cursor}` | not_found |
| `POST /api/posts/:id/comments` | signed-in | `body` 1-2000 | comment 201 (`is_owner` set from the session) | unauthorized, invalid_input, rate_limited, not_found |
| `PATCH /api/posts/:id` | owner | any of `status`, `pinned`, `hidden`, `title`, `body` | post 200 | forbidden, invalid_input, not_found |
| `POST /api/posts/:id/merge` | owner | `into_id` | target post 200 | forbidden, not_found, invalid_input (same post or other board) |
| `DELETE /api/posts/:id`, `DELETE /api/comments/:id` | owner | none | 204 | forbidden, not_found |
| `PATCH /api/comments/:id` | owner | `hidden` | comment 200 | forbidden, not_found |
| `GET /api/roadmap` | public | none | `{planned:[],in_progress:[],shipped:[]}` of `{id,title,vote_count,board_slug}` | none |
| `GET /api/health` | owner | none | `{RESEND_API_KEY:bool, MAIL_FROM:bool}` | forbidden |

## Screens and states

- **`/` and `/b/[slug]`:** `/` shows the oldest board. Sort control (Top, New), status filter chips, title search (300 ms debounce), "Add a request" form. While typing a title of 3+ characters the form calls `similar` and lists matches ("Similar requests: vote instead of posting a duplicate"). The vote button reads "Sign in to vote" and links to `/signin-with-chatgpt` when signed out. Loading: 5 skeleton rows. Empty: "No requests yet. Be the first to add one." Empty after filter: "No requests match these filters." Error: "Could not load requests. Reload to try again." with a Retry button. With no board at all, visitors see "This board is not set up yet." and the owner sees a link to `/admin`.
- **`/b/[slug]/[id]`:** post, status badge, vote button, comments (owner comments carry a "Team" badge), comment form. Not found or hidden: "This request does not exist." A merged post redirects to its target with the note "Merged into this request."
- **`/roadmap`:** three columns sorted by votes (shipped by `updated_at`), max 50 each. Empty column: "Nothing here yet." On a phone the columns stack.
- **`/admin`:** owner only; others see "You do not have access to this page." Create boards, change status, pin, hide, delete, merge (pick the target by title search), and a list of recent posts with full emails.
- **`/embed/[slug]`:** the board with no header, search, or admin links; it must be the only route that allows framing.

## MCP tools

Enabled with `capabilities: ["mcp"]`. Every tool acts only for the owner; others get `forbidden`; tool discovery lists names and schemas only.

- `list_posts` (read-only): `board_slug?`, `status?`, `query?`, `limit` max 50; returns `id`, `title`, `status`, `vote_count`, `url` (SITE_URL based).
- `get_post` (read-only): `id`; returns the post and its comments.
- `set_post_status` (write): `id`, `status`.
- `add_owner_comment` (write): `id`, `body`.
- `merge_posts` (write): `id`, `into_id`.

## Limits and defaults

| Item | Value |
| --- | --- |
| Title / body / comment | 3-120 / 5,000 / 2,000 characters |
| Search query | 80 characters |
| Boards | 20 |
| Page size | 50 (max 200) |
| New posts | 5 per hour per email |
| Comments | 20 per hour per email |
| Votes | 60 per hour per email |
| Similar results | 5 |
| Pinned posts per board | 3 |

## Verification

1. Signed out, open `/`: the board is readable and the vote button says "Sign in to vote". `POST /api/boards/product/posts` without a session returns 401 `unauthorized`.
2. As owner, create board slug `product`, name "Product" in `/admin`. Visitors see it at `/b/product`.
3. As user A, type "Dark mode": no similar matches. Submit: the post shows status Open, 1 vote.
4. As user B, type "dark": the similar list shows "Dark mode". Vote on it: 2. Vote again: 1.
5. Reload both: counts and your own vote state are unchanged.
6. Edge: a 2-character title returns 422 `invalid_input` naming the title; a title with `<script>` renders as text; body `**x** <img src=x onerror=alert(1)>` renders bold with no image.
7. Edge: send two simultaneous vote requests as one user; the final `vote_count` equals the number of vote rows.
8. Edge: post X (votes A, B) and post Y (votes B, C). Merge X into Y: Y shows 3 votes, X redirects to Y.
9. Set Y to `planned`: it appears under Planned on `/roadmap`; set `in_progress`: it moves.
10. Failure: as a non-owner, `PATCH /api/posts/:id` returns 403 `forbidden`. The sixth post within an hour returns 429 `rate_limited`.
11. Failure: with Resend unset, posting still succeeds and the outbox row is `skipped`. A hidden post URL returns 404 for visitors.
12. `/embed/product` loads inside an iframe on another page.

Done when steps 1-12 pass on the deployed site.

## Out of scope

Email digests to voters, SSO for customers' own user systems, paid plans, user edits or deletes of their own posts (the owner deletes on request), file attachments, changelog (use the changelog app).
