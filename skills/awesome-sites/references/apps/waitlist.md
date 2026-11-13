# Waitlist with Referrals on Sites

Builds a pre-launch landing page that collects emails and moves people up the list when they share their link.

Resembles: Prefinery, Waitlister.

**Read first:** `../shared/baseline.md`, `../shared/access-and-domains.md`, Resend section of `../shared/api-keys.md`.
**Access:** public site with owner admin; signup needs no login. **Audience:** Public (anyone on the internet). Private audience breaks signup for every visitor.
**Keys:** none. Optional `RESEND_API_KEY`, `MAIL_FROM` (verified domain) to send a confirmation to the signer; without them the page shows the position and link and sends nothing.

## Data

```sql
CREATE TABLE settings (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  product_name TEXT NOT NULL DEFAULT 'Our product' CHECK (length(product_name) BETWEEN 1 AND 60),
  headline TEXT NOT NULL DEFAULT 'Join the waitlist' CHECK (length(headline) <= 120),
  subheadline TEXT NOT NULL DEFAULT '' CHECK (length(subheadline) <= 300),
  accent TEXT NOT NULL DEFAULT '#2563eb' CHECK (accent GLOB '#[0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F]'),
  launch_note TEXT NOT NULL DEFAULT '' CHECK (length(launch_note) <= 300),
  referral_boost INTEGER NOT NULL DEFAULT 5 CHECK (referral_boost BETWEEN 0 AND 50),
  invite_template TEXT NOT NULL DEFAULT 'Hi, your spot is ready: {{site_url}}',
  contact_email TEXT,                 -- shown in the privacy line
  ip_salt TEXT NOT NULL,              -- random, generated on first request, never returned
  owner_email TEXT                    -- used only when OWNER_EMAILS is empty
);
CREATE TABLE signups (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL UNIQUE CHECK (email = lower(email) AND length(email) <= 254),
  ref_code TEXT NOT NULL UNIQUE CHECK (length(ref_code) = 8),
  referred_by TEXT REFERENCES signups(ref_code),
  ip_hash TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','invited','removed')),
  created_at INTEGER NOT NULL,
  invited_at INTEGER
);
CREATE INDEX signups_status_time ON signups(status, created_at);
CREATE INDEX signups_referred_by ON signups(referred_by);
CREATE INDEX signups_ip_time ON signups(ip_hash, created_at);
```

- Position is never stored. For pending signups: `rank` = ROW_NUMBER() by `created_at`; `score = rank - referral_boost * referrals`; position = order by `score`, ties by `created_at`. `referrals` = count of signups whose `referred_by` is this `ref_code`, status not `removed`, and `ip_hash` different from the referrer's. Invited and removed people have no position.
- `ip_hash` = hex HMAC-SHA-256 of the IP with `ip_salt`. The raw IP is never stored.
- `ref_code`: 8 characters from `abcdefghjkmnpqrstuvwxyz23456789`; retry up to 3 times on a unique conflict.

## API contract

| Route | Auth | Request | Success | Errors |
| --- | --- | --- | --- | --- |
| `POST /api/signups` | public | `email`, `ref?` (8 chars), `website` (honeypot, must be empty) | `{position,total,ref_code,share_url,existing}` 201 new, 200 existing | invalid_input (bad email), rate_limited |
| `POST /api/status` | public | `email` | `{message}` 200, plus `{position,total,share_url}` only when the `wl_me` cookie matches that email | invalid_input |
| `GET /api/admin/signups` | owner | `status?`, `q?`, `sort=position\|created\|referrals`, `limit`, `cursor` | `{items:[{id,email,status,position,referrals,referred_by,created_at}],next_cursor}` | unauthorized, forbidden |
| `PATCH /api/admin/signups/:id` | owner | `status` (`pending`/`invited`/`removed`) | signup 200 | forbidden, not_found, invalid_input |
| `POST /api/admin/invite-next` | owner | `count` 1-100 | `{invited:n}` marks the first n pending by position | forbidden, invalid_input |
| `DELETE /api/admin/signups/:id` | owner | none | 204, permanent | forbidden, not_found |
| `GET /api/admin/export.csv` | owner | `status?` | `text/csv` with every row matching the table | forbidden |
| `PUT /api/admin/settings` | owner | any settings field except `ip_salt` | settings 200 | forbidden, invalid_input |
| `GET /api/health` | owner | none | `{RESEND_API_KEY:bool, MAIL_FROM:bool}` | forbidden |

Rules: a filled `website` returns the normal success shape and stores nothing. Email must match a simple `local@domain.tld` pattern (local max 64, domain has a dot, no spaces); do not use a disposable-domain list. An existing email returns 200 with its current position and link, never an error. Referral codes that are unknown, or belong to the same email, are ignored without error. Rate limit: 5 new signups per hour per `ip_hash`, counted from `signups` rows; the sixth returns 429 "Too many signups from this network. Try again in an hour." CSV cells starting with `=`, `+`, `-`, or `@` are prefixed with a single quote.

## Screens and states

- **`/`:** headline, subheadline, email field, hidden honeypot, submit button "Join the waitlist", privacy line ("We store your email and a hashed network address to run this list. Contact {contact_email} to delete them."). `?ref=CODE` is saved in the `wl_ref` cookie for 30 days and sent with the signup. Success view: "You are #{position} of {total}." and the link `SITE_URL/?ref=CODE` with a Copy button ("Copied" for 2 s). Loading: the button shows "Joining..." and is disabled. Error: the message from the API under the field; network failure: "Could not reach the server. Try again."
- **`/status`:** email field and "Check". Same neutral message for every unknown or unmatched email: "If this email is on the list, the position shows on the browser it signed up from. To see it here, join again with the same email on the home page." The cookie `wl_me` (set at signup, holds the `ref_code`) shows the position for the matching email.
- **`/admin`:** table with search, status filter, sort, "Invite next N" (default 10), per-row Invite, Remove, Delete forever (confirm), Export CSV, a page-text form, and the invite template with a Copy button (`{{site_url}}` is replaced by SITE_URL). Empty: "No signups yet. Share your page: SITE_URL." Loading: "Loading signups..." Error: "Could not load signups. Reload to try again." Non-owners see "You do not have access to this page."

## Limits and defaults

| Item | Value |
| --- | --- |
| Signups per `ip_hash` | 5 per hour |
| Referral boost | 5 places (0-50) |
| Referral cookie | 30 days |
| Email length | 254 |
| Admin page size | 50 (max 200) |
| Invite next | max 100 |
| CSV rows | all rows, streamed |

## Verification

1. Open `/` and sign up `zed@example.com`, then `kim@example.com`, then `ann@example.com`. Ann sees "You are #3 of 3." and a link `SITE_URL/?ref=XXXXXXXX`.
2. Open Ann's link from a different network or browser profile and sign up `bob@example.com`. Ann's referral count is 1. With the default boost of 5 Ann is #1 of 4 (score 3 - 5 = -2). With `referral_boost` set to 2 in `/admin` her score is 1, tied with zed, and zed wins the tie by signing up earlier, so Ann is #2.
3. Edge: sign up `ANN@Example.com` again. Expect 200, same position as step 2, no error, one row in admin.
4. Edge: submit `not-an-email`. Expect 422 `invalid_input`, no row.
5. Edge: use your own link for your own email, or fill the hidden `website` field: no referral counted; the honeypot call looks successful and stores no row.
6. Edge: `/status` with an unknown email shows the neutral message; the same text appears for a known email in a browser without the `wl_me` cookie.
7. Failure: 6 signups within an hour from one network. The sixth returns 429 `rate_limited`.
8. Failure: `GET /api/admin/signups` as a non-owner returns 403 `forbidden`; signed out returns 401.
9. In `/admin`, invite the next 1: that row shows `invited` and leaves the position order. Export CSV: row count and statuses match the table.
10. Reload `/admin` and `/status`: data and positions are unchanged.

Done when a referral moves the referrer up, the CSV matches the table, and a duplicate email returns the existing position.

## Out of scope

Email verification links without Resend, A/B tests, paid tiers, analytics dashboards, per-signup custom fields, automatic invitation emails.
