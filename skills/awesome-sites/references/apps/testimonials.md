# Testimonial Collector on Sites

Builds a link you send to customers to collect written (and photo) testimonials, an approval queue, and an embeddable "Wall of Love".

Resembles: Senja, Testimonial.to.

**Read first:** `../shared/baseline.md`, `../shared/access-and-domains.md`.
**Access:** public site with owner admin; submitting needs no login. **Audience:** Public (anyone on the internet); customers and host sites embedding the wall cannot reach a private site.
**Keys:** none.

## Data

```sql
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);  -- 'owner_email', 'hash_salt'
CREATE TABLE spaces (
  id TEXT PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE CHECK (length(slug) BETWEEN 2 AND 40 AND slug NOT GLOB '*[^a-z0-9-]*'),
  name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 80),
  prompt_text TEXT NOT NULL DEFAULT '' CHECK (length(prompt_text) <= 600),  -- 2-3 questions, one per line
  thank_you TEXT NOT NULL DEFAULT 'Thank you. Your words mean a lot.' CHECK (length(thank_you) <= 300),
  accent TEXT NOT NULL DEFAULT '#2563eb' CHECK (accent GLOB '#[0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F]')
);
CREATE TABLE testimonials (
  id TEXT PRIMARY KEY,
  space_id TEXT NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
  name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 80),
  role_company TEXT NOT NULL DEFAULT '' CHECK (length(role_company) <= 120),
  rating INTEGER CHECK (rating BETWEEN 1 AND 5),
  body TEXT NOT NULL CHECK (length(body) BETWEEN 10 AND 2000),   -- as submitted, never changed
  body_edited TEXT CHECK (body_edited IS NULL OR length(body_edited) BETWEEN 1 AND 2000),  -- shown instead when set
  avatar_key TEXT,
  consent INTEGER NOT NULL CHECK (consent = 1),
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected')),
  featured INTEGER NOT NULL DEFAULT 0 CHECK (featured IN (0,1)),
  ip_hash TEXT NOT NULL,
  created_at INTEGER NOT NULL
);
CREATE INDEX testimonials_wall ON testimonials(space_id, status, featured DESC, created_at DESC);
CREATE INDEX testimonials_rate ON testimonials(ip_hash, created_at);
```

- Display text is `coalesce(body_edited, body)`. The admin shows both when edited, with a "Restore original" button that clears `body_edited`.
- A testimonial is public only when `status='approved'` and `consent=1`. Feature only affects order among approved items.
- Text is stored as plain text and escaped on render; the wall never renders HTML from users. Deleting a testimonial or space deletes its R2 photos.

## API contract

| Route | Auth | Request | Success | Errors |
| --- | --- | --- | --- | --- |
| `GET /api/spaces/:slug` | public | none | `{name,prompt_text,thank_you,accent}` | not_found |
| `POST /api/spaces/:slug/testimonials` | public | multipart: `name`, `role_company?`, `rating?` (1-5), `body`, `consent` (must be true), `photo?`, `website` (honeypot, empty) | `{ok:true}` 201 (honeypot filled: same response, nothing stored) | not_found, invalid_input (message names the field), rate_limited |
| `GET /api/spaces/:slug/wall` | public, CORS `*` | `limit` (default 50, max 100) | `{items:[{name,role_company,rating,text,avatar_url,featured}]}` approved only | not_found |
| `GET /api/avatars/:id` | public for approved, owner otherwise | none | image | not_found |
| `GET /api/admin/testimonials` | owner | `space?`, `status` (default pending), `limit`, `cursor` | `{items,next_cursor,counts:{pending,approved,rejected}}` | unauthorized, forbidden |
| `PATCH /api/admin/testimonials/:id` | owner | any of `status`, `featured`, `body_edited` (null restores) | testimonial 200 | forbidden, not_found, invalid_input |
| `DELETE /api/admin/testimonials/:id` | owner | none | 204 | forbidden, not_found |
| `POST /api/admin/spaces`, `PATCH /api/admin/spaces/:id` | owner | `slug`, `name`, `prompt_text`, `thank_you`, `accent` | space 201/200 | forbidden, invalid_input, conflict |
| `GET /api/admin/spaces/:id/export` | owner | `format=json\|csv` | approved items: `name`, `role_company`, `rating`, `text`, `featured`, `created_at` (ISO), `avatar_url` (SITE_URL based); CSV cells starting `=`, `+`, `-`, `@` get a leading single quote | forbidden, not_found, invalid_input |

Rules: `consent` missing or false returns 422 and nothing is stored. Photo: jpeg, png, or webp, max 2 MB, checked by content type and extension. Rate limit: 5 submissions per hour per `ip_hash` (HMAC of IP with `hash_salt`; the raw IP is never stored); the sixth returns 429 "Too many submissions from this network. Try again in an hour."

## Screens and states

- **`/s/[slug]`:** space name, the prompt questions as a list, one text area, name, role and company, star rating (optional, click again to clear), photo picker (shows a preview and "Remove"), a required checkbox "You may show this on the website", hidden honeypot, submit "Send testimonial". Submitting shows "Sending..." and disables the button; success replaces the form with `thank_you`; error shows the message above the form; network failure: "Could not send. Try again." Unknown slug: "This page does not exist."
- **`/admin`:** owner only; others see "You do not have access to this page." Tabs Pending, Approved, Rejected with counts, a card per testimonial (original and edited text, photo, rating, date) with Approve, Reject, Feature, Edit, Delete (confirm). Space settings and, per space, the share link `SITE_URL/s/[slug]`, the embed snippet, and Export JSON / CSV. Empty Pending: "No testimonials waiting. Share your link: SITE_URL/s/[slug]." Loading: "Loading testimonials..." Error: "Could not load testimonials. Reload to try again." First run: a form to create the first space.
- **`/wall/[slug]`:** masonry (1, 2, 3 columns by width), featured first then newest, each card shows stars, text, avatar, name, role. Empty: "No testimonials yet." Error: "Could not load testimonials."
- **`/embed/[slug].js`:** fetches `/api/spaces/:slug/wall` and renders the same cards inside a shadow root, in a `<div id="wall-of-love">` if the host has one, else right after the script tag. The snippet is a script tag with `src` = `SITE_URL/embed/[slug].js`. It never reads the host page.

## Limits and defaults

| Item | Value |
| --- | --- |
| Name / role / body | 80 / 120 / 10-2,000 characters |
| Photo | jpeg, png, webp; 2 MB |
| Submissions | 5 per hour per `ip_hash` |
| Wall / embed items | 100 / 50 |
| Prompt questions | 3 maximum, 600 characters total |
| Spaces | 10 |
| Video | not supported unless the deployed site accepts uploads of at least 20 MB; otherwise state that in the report |

## Verification

1. As owner create space `acme` with 2 prompt questions. Open `/s/acme` signed out.
2. Submit name "Ann", role "CTO, Acme", rating 5, body "Great product, saved us hours every week.", consent checked, a 100 KB PNG. Expect the thank-you text; `/admin` Pending shows 1 item with the photo.
3. Before approving, `/wall/acme` and the wall API do not list it. Approve: it appears on `/wall/acme` and in the embed on a test page. Reject: it disappears from both.
4. Edge: edit the text to "Great product." Wall shows the edited text; admin still shows the original; Restore original brings it back.
5. Edge: submit without consent: 422, nothing stored. Submit a body of 9 characters: 422.
6. Edge: body `<b>hi</b><script>x</script>` appears as literal text on the wall. A 3 MB photo: 422 naming the 2 MB limit.
7. Failure: the sixth submission within an hour returns 429 `rate_limited`. Filling the hidden `website` field returns 201 but creates no row.
8. Failure: `GET /api/admin/testimonials` signed out returns 401; as a non-owner returns 403. `GET /api/avatars/:id` for a pending item as a visitor returns 404.
9. Feature a second approved item: it sorts first. Export CSV and JSON: only approved items, absolute `avatar_url` starting with SITE_URL.
10. Reload `/admin` and `/wall/acme`: statuses, edits, and photos are unchanged.

Done when a submission appears as pending, approving it shows it on the wall and in the embed, and rejecting hides it.

## Out of scope

Importing from other platforms, AI rewriting, email requests to customers, video testimonials (unless the Limits row allows), star-rating widgets for third-party pages, replies to testimonials.
