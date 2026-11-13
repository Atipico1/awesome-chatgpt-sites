# Order Sheet Converter on Sites (주문 엑셀 → 택배 양식 변환 + 송장 매칭)

Builds a browser-side tool for online sellers: merge the daily order files from several sales channels into one table, check them, export a courier upload file, then import the courier's result file and produce a dispatch sheet per channel. Resembles: 주문합치기 (Windows program), EXCLOAD, and paid monthly order-management tools.

Read first: `../shared/baseline.md`, `../shared/access-and-domains.md`, `../shared/usage-guard.md` (privacy section), `../shared/api-keys.md` (not needed, listed to confirm no key).
Access: private tool. Audience: Private (owner, or only those invited), recommended because saved mappings belong to a person. The converter itself works without signing in: the page does no sign-in redirect of its own, and a signed-out visitor can do every step except save mappings to the server (they download and re-import a mapping file instead). Signing in with Sign in with ChatGPT only turns on server-saved mappings. Use `SITE_URL` for any absolute link.
Keys: none. There is no LLM and no external API. Order rows are never sent to any server or API.

## 2. Data

The server holds only mapping definitions. It never receives order rows, names, phones, addresses, or tracking numbers.

```sql
CREATE TABLE mappings (
  id TEXT PRIMARY KEY,
  user_email TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('channel','courier_out','courier_in','dispatch')),
  name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 40),       -- "스마트스토어", "우체국"
  definition TEXT NOT NULL CHECK (json_valid(definition) AND length(definition) <= 20000),
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  UNIQUE (user_email, kind, name)
);
CREATE INDEX idx_mappings_user ON mappings(user_email, kind);
```

`definition` JSON by kind. All kinds hold `sheet_name?`, `header_row` (default 1), and `sample_headers` (the header texts of the sample file, no data rows).
- `channel`: `{fields: {order_no, recipient, phone, phone2?, postal, address, product, option, qty, memo: "<source header>"}}`.
- `courier_out`: `{max_name_len, columns: [{header, source: "field"|"constant"|"blank", field?, value?}]}` in the order of the sample's columns. `max_name_len` default 20; the user sets it from the courier's template.
- `courier_in`: `{order_no_header, tracking_header, courier_header?}`.
- `dispatch` (one per channel): `{columns: [{header, source: "field"|"constant"|"blank", field?, value?}]}` where field is `order_no`, `tracking_no`, or `courier`.

Constants are short user-typed texts such as a courier name; they must not contain order data.

## 3. API contract

| Route | Auth | Request | Success | Errors |
| --- | --- | --- | --- | --- |
| `GET /api/mappings?kind=` | signed-in | none | 200 `{items}` | `unauthorized` |
| `PUT /api/mappings` | signed-in | `kind`, `name`, `definition` (upsert by user, kind, name) | 200 mapping | `unauthorized`, `invalid_input` (names the field) |
| `DELETE /api/mappings/:id` | signed-in | none | 204 | `unauthorized`, `not_found` |
| `DELETE /api/me/data` | signed-in | none | 204, deletes the user's mappings | `unauthorized` |
| `GET /api/health` | owner | none | `{ ok: true }` (no keys exist) | `forbidden` |

Limits: 50 mappings per user. Signed-out visitors call no API; mapping export and import use a local `.json` file with the same `definition` shape. The server must reject any `definition` whose JSON contains an array named `rows`.

## 4. LLM contract

None. All parsing, matching and validation are deterministic code in the browser. The page must make no network request that carries order data; the browser Network tab shows only static assets and `/api/mappings` calls.

Built-in behavior the builder implements in the browser:

**Reading files.** `.xlsx`, `.xls`, `.csv`. Use a bundled SheetJS-style reader (include it in the build; do not load it from a CDN at run time). Read every cell as its displayed text so long numbers and leading zeros survive; warn when a cell looks like `1.23E+15`. For `.csv`, decode with `TextDecoder('utf-8', {fatal: true})`; if that throws, decode with `euc-kr` (CP949). A UTF-8 BOM is removed. Parse in a Web Worker and show a progress bar by stage and by 500-row steps.

**Password-protected files.** If an `.xlsx` file does not start with the zip signature `PK`, or the reader throws an encryption error, show: "암호가 걸린 파일은 열 수 없어요. Excel에서 암호를 해제하고 다시 저장한 뒤 올려 주세요."

**Synonym dictionary** (header match is exact first, then by this list after trimming and removing spaces):

| Field | Accepted headers |
| --- | --- |
| order_no | 주문번호, 상품주문번호, 주문 번호, 주문코드, 오더번호 |
| recipient | 수취인명, 수령인, 수취인, 받는분, 받는사람, 수신자, 받는이 |
| phone | 연락처, 수취인연락처1, 수취인연락처, 휴대폰, 휴대전화, 핸드폰, 전화번호, 받는분연락처 |
| phone2 | 연락처2, 수취인연락처2, 보조연락처, 안심번호 |
| postal | 우편번호, 배송지우편번호, 우편 번호, zip |
| address | 주소, 배송지, 배송지주소, 통합배송지, 수취인주소, 받는분주소 |
| product | 상품명, 품명, 제품명, 주문상품, 노출상품명 |
| option | 옵션, 옵션명, 옵션정보, 상품옵션 |
| qty | 수량, 주문수량, 구매수량, 개수 |
| memo | 배송메모, 배송메세지, 배송요청사항, 요청사항, 배송 메시지 |

Unmapped required fields (order_no, recipient, phone, address, product, qty) turn the file red until the user picks a header from a list. The chosen mapping is saved under the channel name.

**Validation per row** (flag codes):
- `missing_phone`, `missing_address`, `missing_recipient` are errors (row excluded from export by default).
- Phone: strip non-digits, turn a leading `82` into `0`, add the leading `0` that Excel dropped when the result is 10 digits starting `10`. 11 digits starting `010` become `010-0000-0000`; `02` numbers become `02-000-0000` or `02-0000-0000`; other 10-digit area codes become `0XX-000-0000`. Anything else is `bad_phone` (warning, original kept).
- Postal: 5 digits is valid; 4 digits are padded with a leading `0` and noted; 6 digits or empty is `bad_postal` (warning).
- `name_too_long` (warning) when the recipient exceeds `max_name_len` of the selected courier mapping.
- `duplicate_order_no` (warning on every row sharing an order number, within and across channels).
- Quantity must be an integer 1-9999, else `bad_qty` (error).

**Merging (합포장).** A toggle, default off. Rows with the same normalized recipient (spaces removed) and normalized address (spaces collapsed, lowercase) become one parcel: quantity summed, product text `상품 옵션 x수량` joined with ` / `, `order_no` joined with `,`, memo joined with ` / `.

**Courier match.** Courier result rows match by exact `order_no` after trimming and removing a trailing `.0`; for a merged parcel the courier's echoed value is split on commas and spaces and every part receives the tracking number. Unmatched result rows and orders without tracking are listed separately.

## 5. Screens and states

One page `/` with four steps, plus `/mappings` (list, rename, delete, export or import a mapping file).

- **Banner (always visible):** "주문 데이터는 이 브라우저 안에서만 처리되고 서버로 전송되지 않아요." Closing the tab loses the loaded orders; the browser asks for confirmation before leaving with data loaded.
- **Step 1 가져오기:** drop zone for several files; each file gets a channel name and mapping panel with the matched and missing fields. Empty: "주문 파일을 끌어다 놓으세요 (.xlsx, .xls, .csv)." Loading: progress bar "읽는 중... 1,500 / 3,200행". Errors: "지원하지 않는 파일이에요." / "한 번에 5,000행까지 처리할 수 있어요 (현재 N행)." / "파일이 너무 커요 (최대 10MB)." / "글자가 깨져 보여요. 인코딩을 다시 확인해 주세요."
- **Step 2 확인:** unified table with channel, flags, filter by flag, inline edit of any cell, toggle 합포장. Counts bar: "N행 · 확인 필요 N행 · 합포장 N건 → 택배 N건". Empty: "아직 불러온 주문이 없어요."
- **Step 3 택배 파일:** upload one sample of the courier template once, map each column (field, constant, blank), set max name length, save as courier mapping. Choose xlsx or CSV (UTF-8 with BOM). Before download the counts show rows exported, rows excluded as errors, rows with warnings, merged parcels. Notice: "택배사 양식은 바뀔 수 있어요. 내려받기 전에 택배사의 현재 양식과 맞는지 확인해 주세요." Checkbox "경고가 있는 행도 포함" is on by default; error rows are always excluded.
- **Step 4 송장:** upload the courier result file, map order number and tracking columns once, see matched and unmatched counts, then for each channel upload a sample of its dispatch template, map columns once, and download one file per channel. Not signed in: "로그인하면 열 매핑을 저장할 수 있어요. 지금은 매핑 파일로 저장할 수 있어요."

Mobile: steps stack; the table scrolls horizontally with the first two columns pinned.

## 6. MCP tools

Omitted.

## 7. Limits and defaults

| Item | Value |
| --- | --- |
| Rows across all loaded files | 5,000 |
| File size | 10 MB per file (browser-side, no upload) |
| Files at once | 10 |
| Mappings per user | 50; definition size 20,000 characters |
| Sample template columns | 60 |
| Default `max_name_len` | 20, user-editable |
| Progress step | 500 rows |
| Export format | xlsx or CSV with UTF-8 BOM, sheet name copied from the sample |
| Output styling | values only; cell styles of the sample are not kept |
| Request body size to the server | choose from what the deployed site accepts, record it in the report (definitions stay far below it) |

## 8. Verification

Create these fixtures as text files. Channel A (`a.csv`, UTF-8):

```text
주문번호,수취인명,휴대폰,우편번호,주소,상품명,옵션,수량,배송메모
A1001,김민지,1012345678,4524,서울 중구 세종대로 110,사과 5kg,,2,문 앞
A1002,박준호,010-2222-3333,06236,서울 강남구 테헤란로 1,배 5kg,,1,
A1003,김민지,010-1234-5678,04524,서울 중구  세종대로 110,감귤 3kg,대과,1,
A1001,이서연,02-312-4567,12345,경기 성남시 분당구 1,사과 5kg,,1,
```

Channel B (`b.csv`, saved as EUC-KR): header `주문 번호,받는분,핸드폰,배송지,품명,구매수량`, one row `B2001,최하늘,010-5555-6666,부산 해운대구 1,배 5kg,1`. Courier sample (`t.csv`): header `받는분,전화번호,우편번호,주소,상품명,수량,배송메모,주문번호`. Courier result (`r.csv`): header `주문번호,운송장번호`, rows `"A1001,A1003",600000000001`, `A1002,600000000002`, `B2001,600000000003`, `Z9999,600000000004`.

1. Golden path: load both files. Channel A maps fully by exact headers; channel B maps by synonyms (주문 번호, 받는분, 핸드폰, 배송지, 품명, 구매수량) with 우편번호 missing. Table shows 5 rows. Counts: flagged rows are the two `A1001` rows (duplicate) and `B2001` (bad postal). Row 1 phone shows `010-1234-5678` and postal `04524`.
2. Turn on 합포장: rows A1001 (김민지) and A1003 merge despite the double space; counts read 5 rows, 3 flagged, 1 merged group, 4 parcels; merged quantity 3, order number `A1001,A1003`.
3. Step 3: map `t.csv` (주문번호 <- order_no, others by field), choose CSV. The download opens in Excel with correct Korean and 4 data rows. Switch to xlsx; same content.
4. Step 4: import `r.csv`, map columns. A1001, A1003, A1002, B2001 are matched (the merged parcel gives the same number to both orders); `Z9999` is listed as unmatched. Upload a sample dispatch template per channel and download two files, each with only its channel's orders.
5. Edge: a row with an empty phone is marked `missing_phone`, appears in the "excluded" count, and is not in the courier file.
6. Edge: set `max_name_len` to 2; every 3-character name gets `name_too_long`.
7. Edge: a CSV saved as EUC-KR displays correct Korean; the same file saved as UTF-8 with BOM also displays correctly.
8. Edge: a cell `1.23E+15` in the order number column shows the warning.
9. Failure: an xlsx saved with an Excel open-password shows the password message and loads nothing.
10. Failure: a file with 5,001 rows shows the row-cap message and loads none of it; a `.pdf` shows "지원하지 않는 파일이에요."
11. Failure: signed out, "매핑 저장" shows the sign-in notice and offers the `.json` download; import of that file restores the mapping.
12. Privacy: with the browser Network tab open during steps 1-4, no request body contains any name, phone, or address.
13. Persistence: sign in, save the channel A and courier mappings, reload; they are listed and apply automatically on the next load. Loaded orders are gone after reload by design.

## 9. Out of scope

Marketplace APIs or logins, scraping, label printing, inventory, settlement, storing order rows on the server, EUC-KR output files, hard-coded courier formats.
