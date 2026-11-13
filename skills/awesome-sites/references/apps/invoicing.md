# Invoicing on Sites

Builds an invoice maker: clients, line items, a public pay page, and Stripe Checkout payment.

Resembles: Wave, Bonsai, Invoice Ninja.

Read first: `../shared/baseline.md`, `../shared/access-and-domains.md`, `../shared/api-keys.md` (Stripe, Resend).
Access: public site with owner admin (baseline); the client opens a token link and needs no login. Audience: Anyone on the internet.
Keys: `STRIPE_SECRET_KEY` (without it the Pay button is hidden). Optional: `RESEND_API_KEY` and `MAIL_FROM` (without them "Email to client" is hidden). R2 only if a logo is uploaded.

## Data

```sql
CREATE TABLE settings (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  business_name TEXT NOT NULL DEFAULT '', address TEXT NOT NULL DEFAULT '', tax_id TEXT,
  default_currency TEXT NOT NULL DEFAULT 'usd',
  default_tax_rate_bp INTEGER NOT NULL DEFAULT 0 CHECK (default_tax_rate_bp BETWEEN 0 AND 10000),
  payment_terms_days INTEGER NOT NULL DEFAULT 14,
  logo_key TEXT, next_number INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE clients (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL,
  address TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '', created_at INTEGER NOT NULL
);
CREATE TABLE invoices (
  id TEXT PRIMARY KEY,
  number TEXT NOT NULL UNIQUE,                       -- INV-0001
  client_id TEXT NOT NULL REFERENCES clients(id),
  token TEXT NOT NULL UNIQUE,                        -- 22+ random chars
  status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','sent','paid','void')),
  currency TEXT NOT NULL CHECK (length(currency) = 3),  -- lowercase
  issue_date TEXT NOT NULL, due_date TEXT NOT NULL,
  tax_rate_bp INTEGER NOT NULL DEFAULT 0 CHECK (tax_rate_bp BETWEEN 0 AND 10000),
  notes TEXT NOT NULL DEFAULT '',
  stripe_session_id TEXT, paid_at INTEGER, created_at INTEGER NOT NULL
);
CREATE INDEX idx_invoices_status ON invoices(status, due_date);
CREATE INDEX idx_invoices_client ON invoices(client_id);
CREATE TABLE invoice_items (
  id TEXT PRIMARY KEY,
  invoice_id TEXT NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
  description TEXT NOT NULL CHECK (length(description) BETWEEN 1 AND 300),
  quantity INTEGER NOT NULL CHECK (quantity > 0),     -- thousandths: 1500 = 1.5
  unit_amount INTEGER NOT NULL CHECK (unit_amount >= 0),
  sort_order INTEGER NOT NULL
);
CREATE INDEX idx_items_invoice ON invoice_items(invoice_id, sort_order);
CREATE TABLE outbox (
  id TEXT PRIMARY KEY, invoice_id TEXT, to_email TEXT, subject TEXT, body TEXT,
  status TEXT NOT NULL CHECK (status IN ('sent','failed')), error TEXT, created_at INTEGER NOT NULL
);
```

- Invoice creation is one D1 batch: insert the invoice with `number = 'INV-' || printf('%04d', next_number)` selected from `settings`, insert its items, then `UPDATE settings SET next_number = next_number + 1`. The unique index on `number` is the backstop.
- Server totals: line = round half up of `quantity * unit_amount / 1000`; subtotal = sum of lines; tax = round half up of `subtotal * tax_rate_bp / 10000`; total = subtotal + tax. A total must be above 0 to be marked sent.
- Items and amounts are editable only in `draft`. `overdue` is derived at read time: status `sent` and `due_date` before today (UTC).
- Marking paid is `UPDATE invoices SET status='paid', paid_at=? WHERE id=? AND status='sent'`.

## API contract

| Route | Auth | Request | Success | Errors |
| --- | --- | --- | --- | --- |
| `GET /api/admin/invoices` | owner | `?status=`, pagination | `{items, next_cursor, outstanding_total_by_currency}` | `forbidden` |
| `POST /api/admin/invoices` | owner | `{client_id, currency?, issue_date?, due_date?, tax_rate_bp?, notes?, items[1..50]}` | 201 invoice with totals | `invalid_input` |
| `PATCH /api/admin/invoices/:id` | owner | same fields, draft only | 200 invoice | `conflict` (not draft), `not_found` |
| `POST /api/admin/invoices/:id/send` | owner | none | 200, status `sent`, `{url}` = `SITE_URL/i/<token>` | `invalid_input` (total 0), `conflict` |
| `POST /api/admin/invoices/:id/void` | owner | none | 200 | `conflict` (paid) |
| `POST /api/admin/invoices/:id/email` | owner | `{message?}` | 200, outbox row | `not_configured`, `upstream_error` |
| `GET/POST/PATCH /api/admin/clients` | owner | `{name, email, address?, notes?}` | client | `invalid_input` |
| `GET/PUT /api/admin/settings` | owner | settings fields | settings | `invalid_input` |
| `GET /api/i/:token` | public | none | invoice view model, no internal ids | `not_found` |
| `POST /i/:token/pay` | public | none | 303 redirect to Stripe `url` | `conflict` (not `sent`), `not_configured`, `upstream_error` |
| `GET /i/:token/paid` | public | `?session_id=` | renders paid page | `not_found` (mismatch) |

## Stripe calls

- **Create:** `POST https://api.stripe.com/v1/checkout/sessions`, form-encoded, `Authorization: Bearer STRIPE_SECRET_KEY`. Fields: `mode=payment`, `line_items[0][price_data][currency]` (invoice currency), `line_items[0][price_data][unit_amount]` (server total), `line_items[0][price_data][product_data][name]` ("Invoice INV-0001"), `line_items[0][quantity]=1`, `client_reference_id` (invoice id), `metadata[invoice_id]`, `customer_email` (client email), `success_url=SITE_URL/i/<token>/paid?session_id={CHECKOUT_SESSION_ID}`, `cancel_url=SITE_URL/i/<token>`.
- **Reuse:** if the invoice already has `stripe_session_id`, retrieve it first; if `status` is `open`, redirect to its `url`. Otherwise create a new session and save its id.
- **Verify:** `GET /v1/checkout/sessions/<session_id>`. Accept only if the id equals the invoice's `stripe_session_id`, `payment_status` is `paid`, `amount_total` equals the server total, `currency` equals the invoice currency, and `client_reference_id` equals the invoice id. Then run the conditional paid update. If the invoice is already `paid`, show the paid page without writing. Any mismatch returns `not_found`.

## Screens and states

- `/admin`: invoice table (number, client, total, status, due) with status filter tabs and "Outstanding: <amount>". Loading: "Loading invoices". Empty: "No invoices yet. Create your first invoice." Error: "Could not load invoices. Reload to try again." First run (no settings): a business-details form before anything else.
- New invoice form: client select or inline new client, item rows (description, quantity, unit price), live subtotal, tax, total.
- `/i/[token]`: invoice with business details, items, totals, due date; print stylesheet. `sent`: **Pay now**. `paid`: "Paid on <date>". `void`: "This invoice was voided." Without Stripe key: no button and "Pay by the method on the invoice". Unknown token: "This invoice is not available."
- Paid page: "Payment received. Thank you." Pending payment: "Payment is not confirmed yet. Reload in a minute."
- Send panel: **Mark as sent**, then the copyable link and a copyable message. **Email to client** appears only with Resend.

## MCP tools

Enabled with `capabilities: ["mcp"]`; every call requires the owner. `list_invoices` (read-only): `status?`, `limit` max 50; returns `number`, `client`, `status`, `total`, `currency`, `due_date`, `url`. `create_draft_invoice` (write): `client_email`, `client_name`, `items[]`, `currency?`; creates a `draft` only and never sends or pays.

## Limits and defaults

| Item | Value |
| --- | --- |
| Items per invoice | 50 |
| Default currency / terms / tax | `usd` / 14 days / 0 bp |
| Notes length | 2000 chars |
| Logo | PNG or JPEG, 1 MB; choose from what the deployed site accepts, record it in the report |
| Email send | 20 per day |

## Verification

1. With a Stripe test key: create a client, then an invoice with item "Design" quantity 1.5 at 10000 and tax 1000 bp. Total must be 16500.
2. Mark sent; open the URL signed out; click **Pay now**; pay with Stripe's test card; land on the paid page and see `paid` in `/admin`.
3. Reload the paid page: still paid, one `paid_at`.
4. Edge: create two invoices in quick succession: numbers `INV-0001` and `INV-0002` with no gap or duplicate.
5. Edge: open the paid URL with a `session_id` from another invoice: refused.
6. Edge: edit a `sent` invoice: 409.
7. Edge: Pay on a `void` invoice: refused.
8. Failure: unset the key; the invoice page shows "Pay by the method on the invoice" and `/api/health` reports `STRIPE_SECRET_KEY: false`.
9. Failure: signed out `GET /api/admin/invoices`: 401.
10. Reload `/admin`: all invoices and statuses persist.

## Out of scope

Recurring invoices, multi-currency conversion, tax calculation by region, accounting exports, partial payments, refunds, handling card details of any kind.
