# Form Backend on Sites

Builds a form builder and submission inbox, plus an endpoint that accepts posts from any HTML form.

Resembles: Tally, Typeform basics, Web3Forms.

**Read first:** `../shared/baseline.md`, `../shared/access-and-domains.md`, `../shared/usage-guard.md` (SSRF and untrusted text sections), Resend section of `../shared/api-keys.md`.
**Access:** public site with owner admin. **Audience:** Public (anyone on the internet); on a private audience every outside form post is blocked.
**Keys:** none. Optional `RESEND_API_KEY`, `MAIL_FROM` for notification emails (a verified domain is required for recipients other than the account owner); without them email outbox rows are stored as `failed` with `last_error` "RESEND_API_KEY not set" and show in the admin.

## Data

```sql
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);  -- 'owner_email', 'hash_salt'
CREATE TABLE forms (
  id TEXT PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE CHECK (length(slug) BETWEEN 2 AND 40 AND slug NOT GLOB '*[^a-z0-9-]*'),
  name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 80),
  fields TEXT NOT NULL CHECK (json_valid(fields)),   -- array of {id,label,type,required,options}
  success_message TEXT NOT NULL DEFAULT 'Thanks, we received your response.' CHECK (length(success_message) <= 300),
  redirect_url TEXT,
  notify_email TEXT,
  webhook_url TEXT,
  allowed_origins TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(allowed_origins)),
  is_open INTEGER NOT NULL DEFAULT 1 CHECK (is_open IN (0,1)),
  created_at INTEGER NOT NULL
);
CREATE TABLE submissions (
  id TEXT PRIMARY KEY,
  form_id TEXT NOT NULL REFERENCES forms(id) ON DELETE CASCADE,
  data TEXT NOT NULL CHECK (json_valid(data)),       -- {field_id: value}
  files TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(files)),  -- [{field_id,name,type,size,r2_key}]
  ip_hash TEXT NOT NULL,
  user_agent TEXT NOT NULL DEFAULT '' CHECK (length(user_agent) <= 300),
  status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new','read','spam')),
  created_at INTEGER NOT NULL
);
CREATE TABLE outbox (
  id TEXT PRIMARY KEY,
  submission_id TEXT NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
  kind TEXT NOT NULL CHECK (kind IN ('email','webhook')),
  payload TEXT NOT NULL CHECK (json_valid(payload)),
  status TEXT NOT NULL CHECK (status IN ('pending','sent','failed')),
  attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT, created_at INTEGER NOT NULL
);
CREATE INDEX submissions_form_time ON submissions(form_id, created_at DESC);
CREATE INDEX submissions_form_status ON submissions(form_id, status);
CREATE INDEX submissions_rate ON submissions(form_id, ip_hash, created_at);
CREATE INDEX outbox_status ON outbox(status, created_at);
```

- Field `id`: `^[a-z][a-z0-9_]{0,31}$`, unique in the form, max 30 fields. Types `text` (500 chars), `email`, `textarea` (5,000), `select` (value must be in `options`, max 50 options), `checkbox` (stored 0/1), `file`. Posted keys that are not field ids, and keys starting `_`, are dropped.
- Store the submission, then create outbox rows and attempt each send in the same request with a 10 s timeout; the response never waits for retries. Webhook URLs follow the SSRF rules in `usage-guard.md` when saved and when sent. Webhook body: `{form,submission_id,created_at,data,files:[names]}`.
- Deleting a submission or form deletes its R2 objects.

## API contract

| Route | Auth | Request | Success | Errors |
| --- | --- | --- | --- | --- |
| `POST /f/:slug` | public | urlencoded, multipart, or JSON; field values; optional `_gotcha` (honeypot, empty), `_t` (fill-time token) | JSON clients (`Accept` or body is JSON): `{ok:true,id,message}` 201. Others: 303 to `redirect_url`, else a thank-you page showing `success_message` | not_found, forbidden (form closed), invalid_input (message names the field), rate_limited |
| `OPTIONS /f/:slug` | public | preflight | 204 with CORS headers only when `Origin` is in `allowed_origins` | none |
| `GET /api/admin/forms`, `POST /api/admin/forms` | owner | create: `slug`, `name`, `fields` | form 200/201 | unauthorized, forbidden, invalid_input, conflict |
| `PATCH /api/admin/forms/:id`, `DELETE /api/admin/forms/:id` | owner | any form field | form 200 / 204 | forbidden, not_found, invalid_input |
| `GET /api/admin/forms/:id/submissions` | owner | `status?`, `q?` (max 80), `limit`, `cursor` | `{items:[submission],next_cursor}` | forbidden, not_found |
| `PATCH /api/admin/submissions/:id` | owner | `status` | submission 200 | forbidden, not_found, invalid_input |
| `DELETE /api/admin/submissions/:id` | owner | none | 204 | forbidden, not_found |
| `GET /api/admin/submissions/:id/files/:index` | owner | none | the R2 object as an attachment | forbidden, not_found |
| `GET /api/admin/forms/:id/export.csv` | owner | `status?` | CSV: `id`, `created_at` (ISO), `status`, one column per field label, extra columns for removed field ids | forbidden |
| `POST /api/admin/outbox/:id/retry` | owner | none | outbox row 200 (max 5 attempts) | forbidden, not_found, conflict |
| `GET /api/health` | owner | none | `{RESEND_API_KEY:bool, MAIL_FROM:bool}` | forbidden |

Spam rules: a non-empty `_gotcha`, or a `_t` token (hosted forms; signed with `hash_salt`) younger than 3 seconds, stores the submission with status `spam` and returns the normal success response. Plain external forms carry no `_t` and rely on the honeypot and the rate limit. More than 10 submissions in the last hour from one `ip_hash` for one form returns 429. CORS only controls browser `fetch` calls; ordinary form navigations are not blocked by origin. CSV cells starting `=`, `+`, `-`, or `@` get a leading single quote. Email notification: subject "New response: {form name}", body lists each label and value plus the admin link `SITE_URL/admin`; files are not attached.

## Screens and states

- **`/f/[slug]`:** hosted form rendered from `fields`, submit button "Submit", errors under each field. Closed form: "This form is not accepting responses." Unknown slug: "This form does not exist." Submitting shows "Sending..." and disables the button; on success the `success_message`. Network failure: "Could not send. Try again."
- **`/admin`:** owner only; others see "You do not have access to this page." Form list with response counts; first run: "No forms yet. Create your first form." Builder: add, edit, delete, and drag-to-reorder fields (move up/down buttons on a phone), settings for message, redirect, notification email, webhook, allowed origins, open/closed. Inbox: table with search, status filter, row detail, mark read/spam, delete, download file, CSV export. Empty inbox: "No responses yet. Send the form link or paste the snippet below." Loading: "Loading responses..." Error: "Could not load responses. Reload to try again." Snippet panel: an HTML form whose action is `SITE_URL/f/[slug]` and a curl example posting JSON to the same URL, each with Copy. Outbox panel lists failed rows with error text and a Retry button.

## MCP tools

Enabled with `capabilities: ["mcp"]`; owner only, others get `forbidden`; discovery lists names and schemas only.

- `list_forms` (read-only): returns `slug`, `name`, `new_count`, `url`.
- `list_submissions` (read-only): `form_slug`, `status?`, `limit` max 50; returns `id`, `created_at`, `status`, `data`. File contents are never returned.
- `get_submission` (read-only): `id`.
- `set_submission_status` (write): `id`, `status`.

## Limits and defaults

| Item | Value |
| --- | --- |
| Fields per form / options per select | 30 / 50 |
| Text / textarea value | 500 / 5,000 characters |
| Files | 5 MB each, 3 per submission; pdf, png, jpeg, webp, plain text, csv (type and extension must both match) |
| Total request size | choose from what the deployed site accepts, record it in the report |
| Rate limit | 10 per hour per `ip_hash` per form |
| Fill-time token | min age 3 s, max 24 h |
| Send timeout / attempts | 10 s / 5 |
| Page size | 50 (max 200) |

## Verification

1. As owner create form `contact` with fields `name` (text, required), `email` (email, required), `message` (textarea), `topic` (select: sales, support).
2. From a plain HTML page with `action="SITE_URL/f/contact"` post name "Ann", email "ann@example.com", message "Hi". Expect the thank-you page or redirect; the inbox shows 1 `new` submission.
3. `curl -H 'Content-Type: application/json' -d '{"name":"Bo","email":"bo@example.com"}' SITE_URL/f/contact` returns 201 `{ok:true,id,...}`.
4. Edge: post `email=nope`: 422 naming the email field; no row. Post `topic=other`: 422.
5. Edge: post with `_gotcha=x`: success response, row appears with status `spam`. Extra key `evil=1` is not stored.
6. Edge: upload a 6 MB file: 422 naming the 5 MB limit. Upload a 100 KB PNG: it downloads from the admin and `GET /api/admin/submissions/:id/files/0` as a visitor returns 401.
7. Set `webhook_url` to a test receiver and submit: the outbox shows `sent`. Set it to `http://127.0.0.1/x`: saving returns 422. Set it to an unreachable public URL: outbox `failed`, and Retry works after fixing it.
8. Failure: the 11th submission within an hour returns 429 `rate_limited`. A closed form returns 403 `forbidden`.
9. Failure: with Resend unset, set `notify_email` and submit: the submission is saved and the email outbox row is `failed` with the missing-key text.
10. Reload `/admin`: forms, submissions, field order, and outbox rows are unchanged. CSV rows match the inbox.

Done when steps 2, 6, and 7 pass.

## Out of scope

Conditional logic, payments inside forms, multi-page forms, team roles, signed webhooks, autoresponder emails to submitters, CAPTCHA services.
