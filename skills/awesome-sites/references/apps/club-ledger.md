# Club Ledger on Sites (소모임/동호회 장부)

Builds a record-only ledger for a club treasurer (총무): dues, attendance, fines, income and expenses, ranking, and a read-only share page for members. Resembles: 총무의가계부, 페이마인드, 클루보, and an Excel sheet kept by a running-crew admin.

Read first: `../shared/baseline.md`, `../shared/access-and-domains.md`, `../shared/usage-guard.md` (privacy section).
Access: public site with owner admin. Audience: Public (anyone on the internet) for the member share page; the owner signs in with Sign in with ChatGPT and is listed in `OWNER_EMAILS`. Each listed owner sees only their own clubs. The owner may instead keep the audience private and invite viewers (Share, Only those invited); then the share link works only for signed-in invited viewers and the password is optional. Use `SITE_URL` for share links.
Keys: none.

Legal note (not legal advice): collecting and forwarding dues for others can fall under Korea's electronic payment regulation. This app only records: it must never collect, hold, or forward money, and shows no payment button, account number field, or payment link. The admin shows the fixed line "기록용 장부입니다. 회비를 받거나 보내지 않아요."

Money is Korean won stored as an integer number of won (`_krw` columns). This is an exception to the minor-unit convention: KRW has no minor unit. Periods are `YYYY-MM` text in Korea time (UTC+9); the current period is computed in code.

## 2. Data

```sql
CREATE TABLE clubs (
  id TEXT PRIMARY KEY, owner_email TEXT NOT NULL,
  name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 60),
  start_period TEXT NOT NULL,
  late_fine_krw INTEGER NOT NULL DEFAULT 0, absent_fine_krw INTEGER NOT NULL DEFAULT 0,
  reminder_template TEXT NOT NULL DEFAULT '' CHECK (length(reminder_template) <= 300),
  share_token TEXT NOT NULL UNIQUE,                  -- 24 random base62 characters
  share_scope TEXT NOT NULL DEFAULT 'summary' CHECK (share_scope IN ('summary','full')),
  share_enabled INTEGER NOT NULL DEFAULT 0, share_pw_hash TEXT, share_pw_salt TEXT,   -- PBKDF2, NULL = no password
  created_at INTEGER NOT NULL
);
CREATE INDEX idx_clubs_owner ON clubs(owner_email);
CREATE TABLE members (
  id TEXT PRIMARY KEY, club_id TEXT NOT NULL REFERENCES clubs(id) ON DELETE CASCADE,
  name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 30), alias TEXT,   -- alias = depositor name if different
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','inactive')),
  joined_period TEXT NOT NULL, left_period TEXT,
  exemptions TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(exemptions))    -- [{"from":"2026-11","to":"2026-11"}]
);
CREATE INDEX idx_members_club ON members(club_id, status);
CREATE TABLE dues_rules (
  id TEXT PRIMARY KEY, club_id TEXT NOT NULL REFERENCES clubs(id) ON DELETE CASCADE,
  from_period TEXT NOT NULL, amount_krw INTEGER NOT NULL CHECK (amount_krw >= 0), UNIQUE (club_id, from_period)
);
CREATE TABLE payments (
  id TEXT PRIMARY KEY, club_id TEXT NOT NULL REFERENCES clubs(id) ON DELETE CASCADE,
  member_id TEXT NOT NULL REFERENCES members(id) ON DELETE CASCADE,
  kind TEXT NOT NULL DEFAULT 'dues' CHECK (kind IN ('dues','fine')),
  period TEXT NOT NULL, amount_krw INTEGER NOT NULL CHECK (amount_krw > 0), paid_on TEXT NOT NULL,
  note TEXT NOT NULL DEFAULT '' CHECK (length(note) <= 100),
  source_hash TEXT, UNIQUE (club_id, source_hash)           -- statement line hash blocks a double apply
);
CREATE INDEX idx_payments_club ON payments(club_id, period, member_id);
CREATE TABLE events (
  id TEXT PRIMARY KEY, club_id TEXT NOT NULL REFERENCES clubs(id) ON DELETE CASCADE,
  title TEXT NOT NULL, event_date TEXT NOT NULL
);
CREATE INDEX idx_events_club ON events(club_id, event_date);
CREATE TABLE attendance (
  event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  member_id TEXT NOT NULL REFERENCES members(id) ON DELETE CASCADE,
  state TEXT NOT NULL CHECK (state IN ('present','late','absent')), PRIMARY KEY (event_id, member_id)
);
CREATE TABLE custom_fines (
  id TEXT PRIMARY KEY, club_id TEXT NOT NULL REFERENCES clubs(id) ON DELETE CASCADE,
  member_id TEXT NOT NULL REFERENCES members(id) ON DELETE CASCADE,
  period TEXT NOT NULL, amount_krw INTEGER NOT NULL CHECK (amount_krw > 0), reason TEXT NOT NULL
);
CREATE TABLE entries (                                       -- club income and expense that are not member payments
  id TEXT PRIMARY KEY, club_id TEXT NOT NULL REFERENCES clubs(id) ON DELETE CASCADE,
  entry_date TEXT NOT NULL, type TEXT NOT NULL CHECK (type IN ('income','expense')),
  category TEXT NOT NULL, amount_krw INTEGER NOT NULL CHECK (amount_krw > 0), memo TEXT NOT NULL DEFAULT ''
);
CREATE INDEX idx_entries_club ON entries(club_id, entry_date);
CREATE TABLE points (
  member_id TEXT NOT NULL REFERENCES members(id) ON DELETE CASCADE,
  period TEXT NOT NULL, points INTEGER NOT NULL, PRIMARY KEY (member_id, period)
);
CREATE TABLE audit_log (
  id TEXT PRIMARY KEY, club_id TEXT NOT NULL, actor_email TEXT NOT NULL, at INTEGER NOT NULL,
  table_name TEXT NOT NULL, row_id TEXT NOT NULL, action TEXT NOT NULL CHECK (action IN ('insert','update','delete')),
  old_value TEXT CHECK (old_value IS NULL OR json_valid(old_value)),
  new_value TEXT CHECK (new_value IS NULL OR json_valid(new_value))
);
CREATE INDEX idx_audit_club ON audit_log(club_id, at DESC);
CREATE TABLE share_attempts (ip_hash TEXT NOT NULL, club_id TEXT NOT NULL, at INTEGER NOT NULL);
```

- Every write except to `audit_log` and `share_attempts` also inserts an `audit_log` row in the same D1 batch. Deleting a club deletes its audit rows.
- Derived, never stored: dues, fines, balance, ranking, unpaid lists.
- Due for a member and period: the amount of the latest `dues_rules` row at or before the period; 0 if exempt; only from `joined_period` to `left_period`. Fines owed: `late_fine_krw` per late, `absent_fine_krw` per absent, plus `custom_fines`. Paid is the sum of `payments` of that kind.
- Balance = all `payments` + income entries - expense entries.
- Share password: PBKDF2 through Web Crypto; a correct password sets a cookie valid 12 hours. 5 wrong tries in 10 minutes per `ip_hash` return 429.

## 3. API contract

| Route | Auth | Request | Success | Errors |
| --- | --- | --- | --- | --- |
| `GET/POST /api/clubs`, `PATCH/DELETE /api/clubs/:id` | owner | name, start_period, fines, reminder_template, share settings | club; DELETE 204 removes all data | `unauthorized`, `forbidden`, `invalid_input`, `conflict` (6th club) |
| `GET/POST/PATCH/DELETE /api/clubs/:id/members` (and `/:mid`) | owner | name, alias, status, joined/left period, exemptions | member | `not_found`, `invalid_input`, `conflict` |
| `GET/PUT /api/clubs/:id/dues-rules` | owner | list of `{from_period, amount_krw}` | rules | `invalid_input` |
| `GET/POST/PATCH/DELETE /api/clubs/:id/payments` | owner | member_id, kind, period, amount_krw, paid_on, note | payment | `not_found`, `invalid_input` |
| `GET/POST/PATCH/DELETE /api/clubs/:id/events`, `PUT /api/events/:id/attendance` | owner | title, date; map member_id to state | event with attendance | `not_found`, `invalid_input` |
| `GET/POST/PATCH/DELETE /api/clubs/:id/entries`, `/custom-fines`, `PUT /points` | owner | fields in section 2 | row | `not_found`, `invalid_input` |
| `GET /api/clubs/:id/summary?period=` | owner | none | balance, per-member due/paid/status, unpaid list with reminder text, fines, ranking | `not_found` |
| `POST /api/clubs/:id/statement/preview` | owner | `text` up to 20,000 chars | 200 `{matched, ambiguous, mismatch, unmatched, unparsed}`; writes nothing | `invalid_input` |
| `POST /api/clubs/:id/statement/apply` | owner | ids of proposed matches | 201 created payments | `invalid_input`, `conflict` |
| `GET /api/clubs/:id/export/:kind.csv` | owner | kind: payments, attendance, entries, members | CSV with UTF-8 BOM | `not_found` |
| `GET /api/clubs/:id/audit` | owner | paginated | rows | `not_found` |
| `POST /api/clubs/:id/share/rotate` | owner | none | new token; old token stops working at once | `not_found` |
| `GET /api/share/:token`, `POST /api/share/:token/unlock` | public | password | scoped summary (see below) | `not_found` (also for disabled or wrong token), `unauthorized`, `rate_limited` |
| `GET /api/health` | owner | none | `{ ok: true }` | `forbidden` |

Share scope `summary` returns club name, income total, expense total, balance, event list, attendance rates and the monthly ranking (member names appear in the ranking). It never returns payment status, amounts per person, or fines per person. Scope `full` adds each member's paid or unpaid status per period. CSV cells starting `=`, `+`, `-`, `@` get a leading single quote. `reminder_template` is rejected when it contains a run of 9 or more digits and hyphens, so no account number is stored.

## 4. LLM contract

None. Reconciliation is code only. Per statement line: amount is `\d{1,3}(,\d{3})+` or `\d{4,9}` with optional 원; date is `\d{4}-\d{2}-\d{2}` or `\d{1,2}[/.]\d{1,2}`; depositor is the remaining 2-20 letter text after removing 입금, 이체, 잔액, 원. A line with no amount or no name is `unparsed`. The depositor is matched to `name` or `alias` after removing spaces and lowercasing: none is `unmatched`, several members is `ambiguous`. For one member, if the amount equals the dues of the oldest unpaid period, or the sum of the oldest k unpaid periods (k up to 12), it is proposed as `matched` for those periods; otherwise `mismatch` (shows expected amount). Nothing is written until the treasurer applies selected proposals; a line already applied (same `source_hash`) is shown as "이미 반영됨".

Ranking per period: attendance rate = (present + late) / events with a recorded state for that member, shown as a whole percent; sorted by rate, then points, then name. Inactive members are excluded. Late counts as attended for the rate and as late for fines.

## 5. Screens and states

- **`/admin`:** club list (up to 5). Empty: "아직 장부가 없어요. 모임을 만들어 보세요." Not an owner: "접근 권한이 없어요."
- **`/admin/c/[id]`** tabs: 요약 (balance, this period's unpaid count), 회비 (period grid of members, status per cell, add payment, "독촉 문구 복사"), 출석 (events, tap present/late/absent per member), 벌금, 장부 (entries and running balance), 랭킹, 입금 붙여넣기 (preview, apply), 내보내기, 기록 (audit trail), 설정 (dues rules, fines, share link with copy button, scope, password, "링크 새로 만들기", "장부 삭제" with typed club name).
- **`/s/[token]`:** read-only page; password form if set; disabled or unknown token shows "공유가 중단되었거나 없는 링크예요." Loading: "불러오는 중..." Error: "불러오지 못했어요. 새로고침해 주세요." No buttons that change data.
- Privacy line on admin and share pages: "이름만 저장하고 전화번호와 계좌번호는 저장하지 않아요. 랭킹에는 회원 이름이 보여요."

Korean strings (default `ko`, English set written literally by the builder, choice kept in `localStorage`):

| Key | Korean |
| --- | --- |
| dues status | 납부완료, 일부납부, 미납, 면제, 초과 |
| attendance | 출석, 지각, 결석, 미기록 |
| member status | 활동, 휴면 |
| statement states | 일치, 금액 불일치, 이름이 여러 명, 일치하는 회원 없음, 해석 못한 줄, 이미 반영됨 |
| empty members | 회원이 없어요. 이름을 추가해 주세요. |
| empty events | 아직 모임 기록이 없어요. |
| empty unpaid | 이번 달 미납자가 없어요. |
| errors | 이름을 입력해 주세요. / 금액은 1원 이상이어야 해요. / 장부는 최대 5개까지 만들 수 있어요. / 비밀번호가 맞지 않아요. 잠시 후 다시 시도해 주세요. / 계좌번호처럼 보이는 숫자는 문구에 넣을 수 없어요. |
| reminder | {이름}님, {모임명} {M월} 회비 {금액}원이 아직 확인되지 않았어요. 이미 보내셨다면 알려 주세요. |

## 6. MCP tools

Omitted.

## 7. Limits and defaults

| Item | Value |
| --- | --- |
| Clubs per owner | 5 |
| Members per club | 100 |
| Events per club | 500 |
| Payments per club | 5,000 |
| Entries per club | 2,000 |
| Statement paste | 20,000 characters |
| Share password attempts | 5 per 10 minutes per `ip_hash` |
| Share cookie lifetime | 12 hours |
| Page size | 50, max 200 |
| Share page reads | choose from what the deployed site accepts, record it in the report |

## 8. Verification

Create club "한강러닝" starting 2026-10, dues 20,000 won from 2026-10, late fine 1,000, absent fine 3,000. Members 가영, 나리, 다온, 라온 (alias of 라온: 이라온), 마루 (exempt for 2026-11).

1. Golden path: record 가영's payment 20,000 for 2026-11. Summary for 2026-11: 가영 납부완료; 나리, 다온, 라온 미납; 마루 면제.
2. Add events 11/2 and 11/9. 11/2: 가영 출석, 나리 지각, 다온 결석, 라온 출석, 마루 출석. 11/9: 가영 출석, 나리 출석, 다온 출석, 라온 결석, 마루 지각. Expected fines: 나리 1,000, 다온 3,000, 라온 3,000, 마루 1,000. Ranking: 가영, 나리, 마루 at 100% (late counts as attended; ties by name), then 다온 and 라온 at 50%. Give 다온 3 points: 다온 ranks above 라온.
3. Statement paste: `11/12 나리 20,000원`, `11/12 이라온 20000`, `다온 15,000`, `김철수 20,000`, `잔액 확인`. Expect 나리 일치 (2026-10 is the oldest unpaid period for 나리, so it applies there), 이라온 일치 for 라온 via alias, 다온 금액 불일치 (expected 20,000), 김철수 일치하는 회원 없음, last line 해석 못한 줄. Apply the two matches; pasting again shows 이미 반영됨.
4. Add an income entry 후원금 50,000 and expense 대관료 30,000. Balance = all payments + 50,000 - 30,000; verify by hand from the payment list.
5. Edge: add two members named 가영; a statement line `가영 20,000` is 이름이 여러 명.
6. Edge: statement line `다온 40,000` with two unpaid periods (2026-10 and 2026-11) is proposed for both periods.
7. Edge: set 마루 inactive with left period 2026-11; 2026-12 dues are not counted and 마루 leaves the ranking.
8. Failure: a club reminder template containing `국민 123-456-789012` is rejected with the account-number message. Creating a 6th club returns 409.
9. Failure: share with a wrong password 6 times returns 429 on the sixth; after Rotate, the old URL shows the stopped-link message.
10. Share scopes: open `/s/[token]` signed out. Scope summary shows balance, attendance, ranking, and no 납부 status; switch to full and reload, statuses appear.
11. Audit: edit 가영's payment from 20,000 to 25,000; 기록 shows actor email, time, old and new values. CSV exports open in Excel with correct Korean.
12. Persistence: reload `/admin/c/[id]`; all data, audit rows and share settings are unchanged. Delete the club: `/s/[token]` returns not found.

## 9. Out of scope

Collecting, holding or forwarding money, payment buttons, bank or Kakao integrations, automatic reminders (no cron, no messaging; the treasurer copies the text), several treasurers or permission levels, receipt uploads, storing phone numbers or account numbers.
