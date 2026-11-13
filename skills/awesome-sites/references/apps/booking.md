# Booking Page on Sites

Builds a scheduling page: set weekly availability, share a link, and let people pick a time. No calendar sync.

Resembles: Calendly, Cal.com.

Read first: `../shared/baseline.md`, `../shared/access-and-domains.md`, `../shared/api-keys.md` (Resend, optional).
Access: public site with owner admin (baseline); bookers need no login. Audience: Anyone on the internet.
Keys: none. Optional: `RESEND_API_KEY` and `MAIL_FROM` for confirmation emails; without them the confirmation page, the ICS file, and the admin list are the only notifications.

## Data

```sql
CREATE TABLE settings (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  owner_name TEXT NOT NULL DEFAULT '',
  timezone TEXT NOT NULL DEFAULT 'UTC',           -- IANA
  min_notice_hours INTEGER NOT NULL DEFAULT 4 CHECK (min_notice_hours BETWEEN 0 AND 720),
  max_days_ahead INTEGER NOT NULL DEFAULT 60 CHECK (max_days_ahead BETWEEN 1 AND 365),
  feed_token TEXT NOT NULL                        -- 32+ random chars for the ICS feed
);
CREATE TABLE event_types (
  id TEXT PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE CHECK (slug GLOB '[a-z0-9-]*' AND length(slug) BETWEEN 3 AND 40),
  title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
  duration_min INTEGER NOT NULL CHECK (duration_min BETWEEN 5 AND 480),
  buffer_min INTEGER NOT NULL DEFAULT 0 CHECK (buffer_min BETWEEN 0 AND 120),  -- blocked after the event
  slot_step_min INTEGER NOT NULL DEFAULT 30 CHECK (slot_step_min IN (5,10,15,20,30,60)),
  location_text TEXT NOT NULL DEFAULT '',
  questions TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(questions)),   -- [{id,label,required}], max 5
  is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1))
);
CREATE TABLE availability_rules (
  id TEXT PRIMARY KEY,
  weekday INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6),   -- 0 = Sunday, owner timezone
  start_minute INTEGER NOT NULL CHECK (start_minute BETWEEN 0 AND 1439),
  end_minute INTEGER NOT NULL CHECK (end_minute BETWEEN 1 AND 1440 AND end_minute > start_minute)
);
CREATE INDEX idx_rules_weekday ON availability_rules(weekday);
CREATE TABLE date_overrides (
  id TEXT PRIMARY KEY,
  date TEXT NOT NULL,                              -- YYYY-MM-DD, owner timezone
  is_unavailable INTEGER NOT NULL DEFAULT 0 CHECK (is_unavailable IN (0,1)),
  start_minute INTEGER, end_minute INTEGER         -- null when is_unavailable = 1
);
CREATE INDEX idx_overrides_date ON date_overrides(date);
CREATE TABLE bookings (
  id TEXT PRIMARY KEY,
  event_type_id TEXT NOT NULL REFERENCES event_types(id),
  start_utc INTEGER NOT NULL, end_utc INTEGER NOT NULL CHECK (end_utc > start_utc),
  name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 100),
  email TEXT NOT NULL,
  booker_timezone TEXT NOT NULL DEFAULT 'UTC',
  answers TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(answers)),
  cancel_token TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL DEFAULT 'confirmed' CHECK (status IN ('confirmed','canceled')),
  created_at INTEGER NOT NULL, canceled_at INTEGER
);
CREATE UNIQUE INDEX uq_bookings_confirmed_start ON bookings(start_utc) WHERE status = 'confirmed';
CREATE INDEX idx_bookings_start ON bookings(start_utc, status);
```

- `start_utc` and `end_utc` are epoch milliseconds. The owner has one calendar, so the partial unique index covers all event types. A date override with times replaces that date's weekly rules; with `is_unavailable = 1` it removes them.
- Booking insert is one statement: `INSERT ... SELECT ... WHERE NOT EXISTS (SELECT 1 FROM bookings WHERE status='confirmed' AND start_utc < :new_end + buffer AND end_utc + buffer > :new_start)`, where buffer comes from each booking's own event type. Zero rows inserted or a unique-index violation both return `conflict` "That time was just taken."
- Slot generation: for each date in the owner's timezone, convert rule minutes to UTC per date. Local times that do not exist (spring forward) are skipped; ambiguous times (fall back) use the first occurrence. Never add 24 hours to step days. Slots start on `slot_step_min` boundaries, must end by the rule end, and exclude anything before now + `min_notice_hours`, after now + `max_days_ahead`, or overlapping a confirmed booking plus buffers.

## API contract

| Route | Auth | Request | Success | Errors |
| --- | --- | --- | --- | --- |
| `GET /api/event-types` | public | none | `{items: [{slug, title, description, duration_min}]}` active only | none |
| `GET /api/event-types/:slug/slots` | public | `?month=YYYY-MM&tz=<IANA>` | `{event, owner_timezone, days: {"2026-12-01": [<UTC ISO>, ...]}}` | `not_found`, `invalid_input` (month outside horizon, bad tz) |
| `POST /api/event-types/:slug/bookings` | public | `{start_utc, name, email, tz, answers?, website?}`; `website` must be empty | 201 `{cancel_url, ics_url, start_utc, end_utc}` | `invalid_input`, `conflict`, `rate_limited` (more than 3 future confirmed bookings per email) |
| `GET /api/bookings/:cancel_token` | token | none | booking summary | `not_found` |
| `POST /api/bookings/:cancel_token/cancel` | token | none | 200 `{status: "canceled"}` | `not_found`, `conflict` (already started) |
| `GET /ics/booking/:cancel_token` | token | none | `text/calendar` file for one booking | `not_found` |
| `GET /ics/feed/:feed_token` | token | none | `text/calendar` with confirmed bookings from 30 days ago to the horizon | `not_found` |
| `GET/PUT /api/admin/settings`, `/rules`, `/overrides`, `/event-types` | owner | the table fields above | saved objects | `invalid_input`, `forbidden` |
| `GET /api/admin/bookings` | owner | `?when=upcoming\|past`, pagination | `{items, next_cursor}` | `forbidden` |
| `POST /api/admin/bookings/:id/cancel` | owner | none | 200 | `not_found` |
| `POST /api/admin/feed-token/rotate` | owner | none | 200 `{feed_url}` | `forbidden` |

- ICS content: CRLF line endings, `UID` = booking id plus the `SITE_URL` host, `DTSTART`/`DTEND` in UTC, `SUMMARY` = event title with the booker's name, `LOCATION` = `location_text`, `URL` = `SITE_URL/c/<cancel_token>`. All links use `SITE_URL`.
- Server rejects `start_utc` that is not one of the generated slots for that event type.

## Screens and states

- `/`: list of active event types. Empty: "No times are open for booking yet."
- `/e/[slug]`: month calendar with days that have slots marked; timezone select defaulting to the browser zone; slot list for the chosen day. Loading: "Loading times". Day with none: "No times left on this day." Month with none: "No times available this month. Try next month." Form: name, email, owner questions; on submit **Confirm booking**. Conflict: "That time was just taken. Pick another." and the slots reload. Error: "Could not load times. Reload to try again."
- Confirmation: summary in the booker's timezone, **Add to calendar**, cancel link, and without Resend "Save the calendar file. No email is sent."
- `/c/[cancel_token]`: summary and **Cancel booking**. After: "Your booking is canceled." Unknown: "This booking was not found."
- `/admin`: weekly hours editor, date overrides, event types, upcoming and past bookings with cancel, copyable feed URL (`SITE_URL/ics/feed/<feed_token>`) and **Rotate link**. Empty bookings: "No bookings yet. Share your link: <SITE_URL>."

## MCP tools

Enabled with `capabilities: ["mcp"]`; owner only. `list_upcoming_bookings` (read-only): `limit` default 20, max 50; returns `start_utc`, event title, name, email, status, `cancel_url`. Discovery exposes no bookings.

## Limits and defaults

| Item | Value |
| --- | --- |
| Min notice / horizon | 4 hours / 60 days |
| Slot step | 30 minutes |
| Duration / buffer | 5 to 480 / 0 to 120 minutes |
| Event types | 20 |
| Questions per event | 5; answer max 500 chars |
| Future bookings per email | 3 |
| Feed token | 32+ random chars |

## Verification

1. Sign in as owner, set timezone `America/New_York`, Monday 09:00 to 12:00, event "Intro" 30 minutes.
2. In a private window open `/e/intro`, pick the next Monday's 10:00 slot, submit name and email. Confirmation appears; the ICS opens in a calendar app with the right time.
3. Reload `/admin`: the booking is listed. Cancel it from the `/c/` link: the 10:00 slot is available again.
4. Edge: send two simultaneous `POST` requests for the same slot: one 201, one 409 "That time was just taken."
5. Edge: book across a DST change date (March or November, owner zone `America/New_York`): slots remain 09:00 to 12:00 local on both sides.
6. Edge: set the booker timezone to `Asia/Tokyo`: displayed times shift correctly; stored `start_utc` is identical.
7. Edge: a date override marking next Monday unavailable removes all its slots.
8. Failure: POST a `start_utc` not on a slot (10:07): `invalid_input`. A fourth future booking for one email: `rate_limited`.
9. Failure: signed out `GET /api/admin/bookings`: 401; wrong `feed_token`: 404.
10. Without Resend, the confirmation page shows the "Save the calendar file" note.

## Out of scope

Google or Outlook calendar sync, payments, group events, round-robin teams, reminders without Resend, rescheduling (cancel and rebook instead), per-event availability.
