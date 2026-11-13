# Digital Storefront on Sites

Builds a small store for digital products (PDFs, templates, zips) with Stripe Checkout and gated downloads.

Resembles: Gumroad, Lemon Squeezy.

Read first: `../shared/baseline.md`, `../shared/access-and-domains.md`, `../shared/api-keys.md` (Stripe).
Access: public site with owner admin (baseline); buyers need no login. Audience: Anyone on the internet.
Keys: `STRIPE_SECRET_KEY` (without it every Buy button is disabled and says "Checkout is not set up yet"). Needs R2 (bind as `FILES`) and D1 (`DB`).

## Data

```sql
CREATE TABLE products (
  id TEXT PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE CHECK (slug GLOB '[a-z0-9-]*' AND length(slug) BETWEEN 3 AND 60),
  name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 120),
  description_md TEXT NOT NULL DEFAULT '' CHECK (length(description_md) <= 5000),
  price INTEGER NOT NULL CHECK (price > 0),          -- minor units, immutable after creation
  currency TEXT NOT NULL CHECK (length(currency) = 3), -- lowercase, immutable
  cover_key TEXT,                                    -- R2, optional
  file_key TEXT, file_name TEXT, file_size INTEGER,  -- R2, set by upload
  active INTEGER NOT NULL DEFAULT 0 CHECK (active IN (0,1)),
  created_at INTEGER NOT NULL
);
CREATE INDEX idx_products_active ON products(active, created_at DESC);
CREATE TABLE orders (
  id TEXT PRIMARY KEY,
  product_id TEXT NOT NULL REFERENCES products(id),
  stripe_session_id TEXT NOT NULL UNIQUE,
  buyer_email TEXT NOT NULL,
  amount INTEGER NOT NULL, currency TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'paid' CHECK (status IN ('paid')),
  download_token TEXT NOT NULL UNIQUE,               -- 32+ random chars
  downloads_used INTEGER NOT NULL DEFAULT 0 CHECK (downloads_used >= 0),
  max_downloads INTEGER NOT NULL DEFAULT 5 CHECK (max_downloads BETWEEN 1 AND 100),
  created_at INTEGER NOT NULL
);
CREATE INDEX idx_orders_product ON orders(product_id, created_at DESC);
CREATE TABLE pages (key TEXT PRIMARY KEY CHECK (key IN ('terms')), body_md TEXT NOT NULL, updated_at INTEGER NOT NULL);
```

- A product can be set `active=1` only when `file_key` is set. Price and currency cannot be changed by the API; to change a price the owner creates a new product. This keeps the amount check below exact.
- The order is created with `INSERT ... ON CONFLICT(stripe_session_id) DO NOTHING`, then selected by session id, so a reloaded or concurrent `/thanks` yields one order.
- Download counting: first head the R2 object (missing means 404, no count), then `UPDATE orders SET downloads_used = downloads_used + 1 WHERE download_token = ? AND downloads_used < max_downloads`; one changed row means stream, zero means refuse.

## API contract

| Route | Auth | Request | Success | Errors |
| --- | --- | --- | --- | --- |
| `GET /api/products` | public | none | `{items}` of active products (no file keys) | none |
| `GET /api/products/:slug` | public | none | product | `not_found` |
| `GET /api/products/:slug/cover` | public | none | image stream | `not_found` |
| `POST /p/:slug/buy` | public | none | 303 to Stripe `url` | `not_found`, `not_configured`, `upstream_error` |
| `GET /thanks` | public | `?session_id=` | renders order and download button | `not_found`, `upstream_error` |
| `GET /d/:token` | token | none | file stream, attachment | `not_found`, `forbidden` (limit reached) |
| `POST /api/admin/products` | owner | `{name, slug, description_md?, price, currency}` | 201 product (inactive) | `invalid_input`, `conflict` (slug) |
| `PATCH /api/admin/products/:id` | owner | `name, description_md, active`, not price | product | `invalid_input` |
| `PUT /api/admin/products/:id/file` | owner | raw body, `?name=` | 200 product | `invalid_input` (over cap) |
| `PUT /api/admin/products/:id/cover` | owner | image, max 2 MB | 200 | `invalid_input` |
| `DELETE /api/admin/products/:id` | owner | none | 200; deactivates if orders exist | `not_found` |
| `GET /api/admin/orders` | owner | pagination | `{items}` with Stripe dashboard link | `forbidden` |
| `POST /api/admin/orders/:id/reset` | owner | none | 200, `downloads_used` = 0 | `not_found` |
| `GET /api/admin/orders.csv` | owner | none | CSV: date, product, email, amount, currency, session id | `forbidden` |
| `PUT /api/admin/pages/terms` | owner | `{body_md}` max 10,000 chars | 200 | `invalid_input` |

## Stripe calls

- **Create (`/p/:slug/buy`):** `POST https://api.stripe.com/v1/checkout/sessions`, form-encoded, `Authorization: Bearer STRIPE_SECRET_KEY`. Fields: `mode=payment`, `line_items[0][price_data][currency]`, `line_items[0][price_data][unit_amount]` and `line_items[0][price_data][product_data][name]` all read from the product row, `line_items[0][quantity]=1`, `client_reference_id` (product id), `metadata[product_id]`, `success_url=SITE_URL/thanks?session_id={CHECKOUT_SESSION_ID}`, `cancel_url=SITE_URL/p/<slug>`. Do not send an email field; Checkout collects the buyer's email.
- **Verify (`/thanks`):** `GET /v1/checkout/sessions/<session_id>`. Accept only if `payment_status` is `paid`, `client_reference_id` names an existing product, `amount_total` equals that product's price, and `currency` equals its currency. Take `buyer_email` from `customer_details.email`, lowercased. Then insert the order once. Any mismatch shows the not-found state and creates nothing.
- Never create or look up a session from browser-sent prices.

## Screens and states

- `/`: grid of active products with cover, name, formatted price. Loading: skeleton cards. Empty: "No products yet." (owner signed in also sees "Add a product in Admin.") Error: "Could not load products. Reload to try again."
- `/p/[slug]`: markdown description, **Buy for <price>**, link to `/terms`. Inactive or unknown slug: "This product is not available."
- `/thanks`: loading "Confirming your payment". Paid: "Thank you. Your file is ready.", **Download** button, "Bookmark this page. You can download up to <max> times." Not paid: "Payment is not confirmed. If you were charged, contact the seller." Not found: "We could not find that order."
- `/d/[token]`: streams the file. Limit reached: "Download limit reached. Contact the seller for a new link."
- `/terms`: owner-edited text plus the fixed line "The seller handles taxes and support. Refunds are issued by the seller."
- `/admin`: tabs Products (create, upload, toggle active), Orders (table, **Reset downloads**, copy download link, Stripe link, **Export CSV**), Terms. Upload over cap: "That file is over the 50 MB limit."

## Limits and defaults

| Item | Value |
| --- | --- |
| Product file | default 50 MB; choose from what the deployed site accepts, record it in the report |
| Cover image | 2 MB, PNG/JPEG/WebP |
| Downloads per order | 5 default, adjustable 1 to 100 per order |
| Products | 200 |
| Description / terms | 5000 / 10,000 chars |
| `/thanks` verify calls | 10 per session id per hour |

## Verification

1. With a test key: create a product "Guide" at 1500 usd, upload a small PDF, activate it.
2. Signed out, open `/p/guide`, Buy, pay with Stripe's test card, land on `/thanks` and download. The bytes match the upload. Admin shows the order.
3. Reload `/thanks`: still one order; counter unchanged by the reload.
4. Edge: download 5 times with `/d/<token>`; the sixth returns the limit message. **Reset downloads** allows another.
5. Edge: open `/d/<random>`: not found. Fetch the product file by any R2 or `file_key` path: not found.
6. Edge: use a `session_id` from an unpaid or cancelled session: "Payment is not confirmed" and no order.
7. Failure: unset `STRIPE_SECRET_KEY`: Buy disabled with the message; `/api/health` reports it false.
8. Failure: `PATCH` a price as owner: ignored with `invalid_input`. Signed out `GET /api/admin/orders`: 401.
9. Reload `/admin`: products, orders, and counters persist.

## Out of scope

Subscriptions, licence keys, affiliate payouts, discount codes, bundles, refunds issued from the app, taxes, email delivery without Resend (show the download link on `/thanks` and in admin).
