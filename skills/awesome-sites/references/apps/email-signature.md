# Email Signature Builder on Sites

Builds a free email-signature generator: pick a layout, fill in fields, and paste the resulting HTML into Gmail, Outlook, or Apple Mail. Signed-in users save signatures; an optional team mode gives members a locked company template.

Resembles: SyncSignature, MySignature.

Read first: `../shared/baseline.md`, `../shared/access-and-domains.md`, `../shared/usage-guard.md` (rate limits, privacy).
Access: public site with owner admin (baseline). The builder works signed out and saves nothing; signing in saves signatures and allows image uploads. Audience: Anyone on the internet.
Keys: none. Needs R2 (bind as `FILES`) and D1 (`DB`).

Hosted images are the weak point. A pasted signature references images by `SITE_URL/img/...`, so the site must stay public and its address stable. If the site is made private, renamed, or moved to a custom domain, images in every installed signature break. Show this warning on the images panel and in the admin settings, and show it again before the owner changes the domain (see `access-and-domains.md`).

## Data

```sql
CREATE TABLE settings (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  team_mode INTEGER NOT NULL DEFAULT 0 CHECK (team_mode IN (0,1))
);
CREATE TABLE images (
  id TEXT PRIMARY KEY,
  owner_email TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('logo','headshot','team_logo')),
  content_type TEXT NOT NULL CHECK (content_type IN ('image/png','image/jpeg')),
  r2_key TEXT NOT NULL UNIQUE,                    -- img/<image id>
  size INTEGER NOT NULL CHECK (size BETWEEN 1 AND 524288),
  width INTEGER NOT NULL CHECK (width BETWEEN 16 AND 1200),   -- declared by the browser after re-encoding
  height INTEGER NOT NULL CHECK (height BETWEEN 16 AND 1200),
  created_at INTEGER NOT NULL
);
CREATE INDEX idx_images_owner ON images(owner_email, created_at DESC);
CREATE TABLE signatures (
  id TEXT PRIMARY KEY,
  owner_email TEXT NOT NULL,
  name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 60),   -- label in the list
  template_id TEXT NOT NULL CHECK (template_id IN ('classic','stacked','compact','sidebar','banner','minimal')),
  fields TEXT NOT NULL CHECK (json_valid(fields)),
  team_id TEXT,                                   -- set for a member's team signature
  created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
);
CREATE INDEX idx_signatures_owner ON signatures(owner_email, updated_at DESC);
CREATE TABLE teams (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 80),
  join_token TEXT NOT NULL UNIQUE,                -- 22+ random URL-safe chars
  template TEXT NOT NULL CHECK (json_valid(template)),   -- locked fields, see below
  logo_image_id TEXT REFERENCES images(id),
  updated_at INTEGER NOT NULL
);
CREATE TABLE team_members (
  team_id TEXT NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
  email TEXT NOT NULL,
  fields TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(fields)),   -- name, title, phone, email, headshot image id
  joined_at INTEGER NOT NULL, updated_at INTEGER NOT NULL,
  PRIMARY KEY (team_id, email)
);
CREATE TABLE rate_hits (
  key TEXT NOT NULL, window_start INTEGER NOT NULL, count INTEGER NOT NULL,
  PRIMARY KEY (key, window_start)
);
```

- `fields` JSON keys: `name`, `title`, `company`, `phone`, `email`, `website`, `address`, `socials` (list of `{network, url}`), `logo_image_id` or `logo_url`, `headshot_image_id`, `disclaimer`, `accent_color`, `font`. Unknown keys are dropped on save.
- The 10-signature cap is checked in the same statement as the insert (`INSERT ... SELECT ... WHERE (SELECT COUNT(*) FROM signatures WHERE owner_email = :e) < 10`). Zero rows inserted returns `conflict`.
- A team has one logo at a stable URL `SITE_URL/img/t/<team id>/logo`. Replacing the logo points `logo_image_id` at a new image row and keeps that URL. All other images use `SITE_URL/img/<image id>` and never change.
- Team mode is one team per site. The locked template holds `template_id`, `accent_color`, `font`, `company`, `website`, `address`, `socials`, `disclaimer`. Members fill only `name`, `title`, `phone`, `email`, and their headshot.

## Templates

| id | Layout |
| --- | --- |
| `classic` | Headshot left, text right, logo under the text |
| `stacked` | Everything in one column: name block, contact lines, logo |
| `compact` | Single text block, no headshot, logo inline after the company |
| `sidebar` | Logo in a left cell, divided by a 2 px accent rule from the text |
| `banner` | Text block, then a full-width row with logo and socials |
| `minimal` | Name, title, and one contact line; no images |

Web-safe fonts: Arial, Helvetica, Georgia, Times New Roman, Verdana, Tahoma, Trebuchet MS, Courier New. Each is emitted with a generic fallback (`sans-serif`, `serif`, `monospace`). Socials: `linkedin`, `x`, `instagram`, `facebook`, `youtube`, `github`, `tiktok`, rendered as text links separated by " | ".

## API contract

| Route | Auth | Request | Success | Errors |
| --- | --- | --- | --- | --- |
| `POST /api/render` | public | `{template_id, fields}` | `{html, text}` | `invalid_input`, `rate_limited` (60 per minute per IP hash) |
| `GET /api/signatures`, `POST /api/signatures` | signed-in | `{name, template_id, fields}` | list, or 201 signature | `invalid_input`, `conflict` (already 10) |
| `PUT` / `DELETE /api/signatures/:id` | signed-in owner | same fields | 200 | `not_found` |
| `POST /api/images?kind=&width=&height=` | signed-in | raw PNG or JPEG body, max 512 KB, magic bytes checked | 201 `{id, url}` | `invalid_input`, `rate_limited` (20 per day) |
| `DELETE /api/images/:id` | signed-in owner | none | 200 | `not_found` |
| `GET /img/:id` | public | none | bytes, `Cache-Control: public, max-age=31536000, immutable`, `X-Content-Type-Options: nosniff` | 404 |
| `GET /img/t/:team_id/logo` | public | none | bytes, `Cache-Control: public, max-age=3600` | 404 |
| `PUT /api/admin/settings` | owner | `{team_mode}` | 200 | `forbidden` |
| `PUT /api/team` | owner | `{name, template, logo_image_id}` | 200 team | `invalid_input`, `forbidden` (team mode off) |
| `POST /api/team/rotate-join` | owner | none | 200 `{join_url}`, `SITE_URL/join/<token>` | `forbidden` |
| `GET /api/team/members`, `DELETE /api/team/members/:email` | owner | none | members with names and dates; removal also deletes that member's team signature | `forbidden`, `not_found` |
| `POST /api/team/join/:token` | signed-in | none | 200 membership (max 200 members) | `not_found`, `conflict` |
| `PUT /api/team/me` | member | name, title, phone, email, headshot id | 200 | `forbidden`, `invalid_input` |
| `DELETE /api/me` | signed-in | none | 200; deletes the user's signatures, images, membership | none |

- Replacing the team logo is refused with `invalid_input` ("The new logo must have the same shape as the current one.") if its width to height ratio differs from the current logo by more than 2 percent, because already-pasted signatures fix the `width` and `height` attributes.
- The browser re-encodes uploads on a canvas to PNG or JPEG, at most 480 by 240 px for logos and 240 by 240 px for headshots, and sends the final width and height. The server stores them as declared, clamped by the `CHECK`.
- Signed-out users can enter an `https:` image URL instead of uploading; it is used as `src` only and never fetched.

## Output rules

`/api/render` is the only place HTML is built, so signed-out and signed-in output are identical. Output must:

1. Use a root `<table>` with `role="presentation"`, `cellpadding="0"`, `cellspacing="0"`, `border="0"`, `width="600"`, `style="max-width:600px"`, and nested tables for layout. No `<div>` layout.
2. Use inline `style` attributes only. No `<style>` block, flex, grid, CSS variables, custom fonts, or background images.
3. Give every `<img>` `src` (absolute `https:`), `width`, `height`, `alt`, `border="0"`, and `style="display:block"`. Alt is the person's name for a headshot and the company name for a logo, or empty with `alt=""` if the field is blank.
4. Escape `& < > " '` in every text field. Newlines in `address` and `disclaimer` become `<br>`.
5. Build links from validated values only: `mailto:` from an email that matches a basic pattern; `tel:` from the phone with only digits and a leading `+` kept; website and image URLs allow only `http:` and `https:` (a bare domain gets `https://`); a social URL must be `https:` on that network's host. Reject `javascript:`, `data:`, and every other scheme with `invalid_input`. No UTM parameters or tracking added.
6. Colors must match `#RRGGBB`; the font must be in the list; otherwise `invalid_input`.

## Screens and states

- `/`: left a form (template picker, fields, images panel), right a live preview with a light and a dark background toggle, updated 400 ms after typing. Under the preview: "If your logo disappears on the dark background, use a logo with a light outline or a solid background." Buttons **Copy signature** (writes `text/html` and `text/plain` to the clipboard; falls back to selecting the preview and copying) and **Copy HTML source**. Success: "Copied." Clipboard blocked: "Your browser blocked copying. Select the preview and copy it by hand." Signed out: "Sign in with ChatGPT to save signatures and upload images." Preview error: "Could not build the preview. Check the highlighted fields."
- Install help (static, on `/help`): Gmail, Outlook (web and desktop), Apple Mail. Each gives the generic steps (copy the signature, open the mail app's signature settings, paste, save) and the line "Menus change. Check your mail app's help." Do not state exact menu paths or button names.
- `/mine`: saved signatures with **Open**, **Duplicate**, **Delete**. Empty: "No saved signatures yet." At 10: "You have 10 signatures. Delete one to add another." Deleting an image shows "Signatures you already installed will lose this image."
- `/join/[token]`: signed out shows the sign-in prompt; signed in joins, then opens the member form with the locked fields read-only. Unknown token: "This join link is not available."
- `/admin`: team mode toggle, template editor, logo replace, join link with **Rotate**, member table. Text: "Changing the template updates the hosted logo and what members see when they open the builder. It does not change signatures already pasted into mail apps."
- Mobile: form above preview.

## Limits and defaults

| Item | Value |
| --- | --- |
| Saved signatures per user | 10 |
| Field lengths | name, title, company 80; phone 30; email 120; website 200; address 200; disclaimer 600 |
| Image upload | PNG or JPEG, 512 KB, 20 per user per day; choose a larger cap only from what the deployed site accepts and record it in the report |
| Rendered width | 600 px |
| Team members | 200 |
| Render rate limit | 60 per minute per IP hash |

## Verification

1. Signed out, open `/`, choose `classic`, enter name "Ada Lovelace", title "Engineer", company "Analytical Co", email `ada@example.com`, website `example.com`. The preview shows; **Copy HTML source** yields a root `<table>` with `width="600"` and an `href` of `https://example.com`. Reload: the form is empty (nothing saved).
2. Paste the copied signature into a mail app's signature box: layout and links keep working. Send it to yourself in a light and a dark mail theme.
3. Sign in, upload a 300 by 100 PNG logo, save as "Work". Reload `/mine` and open it: fields and logo persist. Open `SITE_URL/img/<id>` in a private window: the image loads.
4. Edge: name `<script>alert(1)</script>`: the source shows `&lt;script&gt;`. Website `javascript:alert(1)`: `invalid_input`.
5. Edge: address with two lines renders with `<br>`; a field left blank renders no empty row; an image with no alt text input still has an `alt` attribute.
6. Edge: team mode on, create a team with logo and disclaimer, join from a second account: the locked fields are read-only and member name, title, phone are editable. Replace the team logo with one of a different shape: `invalid_input`. Replace it with the same shape: `SITE_URL/img/t/<team id>/logo` serves the new image.
7. Failure: upload a 600 KB file, and a PNG-named text file: both `invalid_input`; nothing stored.
8. Failure: create an 11th signature: `conflict`; signed out `POST /api/signatures`: 401.
9. Failure: a non-owner `PUT /api/team`: 403; unknown join token: `not_found`.
10. Update the team template text and reopen the member's builder: the new disclaimer shows. The earlier pasted signature still has the old disclaimer.

## Out of scope

Pushing signatures into Gmail or Outlook automatically, click analytics inside signatures, animated banners, paid plans (follow the Stripe pattern in `digital-storefront.md`), bulk deployment through Google Workspace or Microsoft 365 admin APIs, SVG or GIF images, social icons as images.
