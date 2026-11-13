# SEO Audit on Sites

Builds a tool where the user enters a URL and gets Google PageSpeed Insights scores, an on-page SEO checklist computed in code, and a prioritized fix list. Resembles the free audit tools from Ahrefs and Semrush.

Read first: `../shared/baseline.md`, `../shared/usage-guard.md`, `../shared/access-and-domains.md`, `../shared/api-keys.md`.
Access: public tool with sign-in for audits (pages and shared reports open signed out; running an audit needs SIWC). Audience: public (anyone on the internet), with owner admin for `/api/health`.
Keys: `PAGESPEED_API_KEY` (required in practice; without it audits return `not_configured` and the form says "Set PAGESPEED_API_KEY in the site settings"). Optional: `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` for the explained fix list; without them the deterministic fix list is shown.

## 2. Data

```sql
CREATE TABLE audits (
  id TEXT PRIMARY KEY,
  user_email TEXT NOT NULL,
  url TEXT NOT NULL,                         -- normalized: https default, no fragment, lowercase host
  final_url TEXT,
  strategy TEXT NOT NULL CHECK (strategy IN ('mobile','desktop')),
  status TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running','done','failed')),
  error_code TEXT,
  scores TEXT CHECK (scores IS NULL OR json_valid(scores)),         -- performance, accessibility, best_practices, seo (0-100)
  metrics TEXT CHECK (metrics IS NULL OR json_valid(metrics)),      -- LCP, CLS, INP or TBT, FCP, TTFB: value, unit, label
  opportunities TEXT CHECK (opportunities IS NULL OR json_valid(opportunities)),
  onpage TEXT CHECK (onpage IS NULL OR json_valid(onpage)),         -- checklist results
  fix_list TEXT CHECK (fix_list IS NULL OR json_valid(fix_list)),
  ai_summary_md TEXT,
  cached INTEGER NOT NULL DEFAULT 0,
  share_token TEXT UNIQUE,
  created_at INTEGER NOT NULL
);
CREATE INDEX idx_audits_user_url ON audits(user_email, url, created_at DESC);
CREATE INDEX idx_audits_user ON audits(user_email, created_at DESC);
```

`usage_daily` and `api_cache` come from `usage-guard.md`. Cache keys: `psi:{strategy}:{url}` (a compact subset of the response, not the full payload) and `page:{url}` (computed checklist), both 6 hours. A `running` row older than 120 seconds is shown and stored as `failed` with `error_code` `timeout` when read.

## 3. API contract

| Route | Auth | Request | Success | Errors |
| --- | --- | --- | --- | --- |
| `POST /api/audits` | signed-in | `url` (max 2,048 chars; scheme optional), `strategy` default `mobile` | 201 audit (waits up to 60 s) with `remaining_calls` | `invalid_input`, `rate_limited`, `quota_exhausted`, `not_configured`, `upstream_error` |
| `GET /api/audits/:id` | signed-in, own | none | 200 audit | `not_found` |
| `GET /api/audits` | signed-in | `?url=`, pagination | 200 `{items, next_cursor}` (score summary only) | `unauthorized` |
| `DELETE /api/audits/:id` | signed-in, own | none | 204 | `not_found` |
| `POST /api/audits/:id/share` | signed-in, own | none | 200 `{share_url: SITE_URL/s/{token}}` (22-char random token) | `not_found` |
| `DELETE /api/audits/:id/share` | signed-in, own | none | 204, link stops working | `not_found` |
| `GET /api/shared/:token` | public | none | 200 audit without `user_email` | `not_found` |
| `GET /api/usage` | signed-in | none | 200 `{used, cap, remaining}` | `unauthorized` |
| `DELETE /api/me` | signed-in | none | 204, deletes the user's audits | `unauthorized` |
| `GET /api/health` | owner | none | `{PAGESPEED_API_KEY, LLM_API_KEY, ok}` | `forbidden` |

A cache hit returns 201 with a new audit row copied from cache, `cached: 1`, no cap cost.

## 4. LLM contract and external calls

**PageSpeed Insights.** From the server: `GET https://www.googleapis.com/pagespeedonline/v5/runPagespeed` with `url`, `strategy`, `category=performance`, `category=seo`, `category=accessibility`, `category=best-practices`, and `key`; timeout 60 s. Read `lighthouseResult.categories.{performance,accessibility,best-practices,seo}.score` (0 to 1, store as 0 to 100 rounded); `lighthouseResult.audits` entries `largest-contentful-paint`, `cumulative-layout-shift`, `total-blocking-time`, `first-contentful-paint`, `server-response-time` (shown as TTFB), each using `numericValue` and `displayValue`; `lighthouseResult.finalUrl`; and every audit whose `details.type` is `opportunity` with `details.overallSavingsMs` above 0 (id, title, savings). INP appears only from field data when present (`loadingExperience.metrics`, verify the key in provider docs); otherwise show TBT and label it. Provider 429 maps to `quota_exhausted` "Google's free quota is used up for today"; other non-200 maps to `upstream_error`.

**Metric labels** (computed in code): LCP good at most 2,500 ms, poor over 4,000; CLS good at most 0.1, poor over 0.25; TBT good at most 200 ms, poor over 600; FCP good at most 1,800 ms, poor over 3,000; TTFB good at most 800 ms, poor over 1,800; INP good at most 200 ms, poor over 500; between is "needs work".

**On-page checklist (all code).** Fetch the HTML once (2 MB cap, 10 s, URL rules from `usage-guard.md`, content type must be HTML else `invalid_input` "That URL did not return an HTML page.") and parse with an HTML parser. Each check has `id`, `status` pass/warn/fail, `observed`, `weight` 1 to 3:
- `title`: pass 30-60 chars; warn 1-29 or 61-80; fail missing or longer.
- `meta_description`: pass 70-160; warn 1-69 or 161-250; fail missing.
- `h1`: pass exactly one; warn more than one; fail none.
- `heading_order`: pass no skipped level; else warn.
- `canonical`: pass present; else warn.
- `robots_meta`: fail if it contains `noindex`; else pass.
- `open_graph`: pass with og:title, og:description, og:image; else warn.
- `twitter_card`: pass with twitter:card; else warn.
- `lang`: pass present on `html`; else warn.
- `image_alt`: share of images with an `alt` attribute (empty counts); pass at least 90%, warn 50-89%, fail below; pass when no images.
- `viewport`: pass present; else fail.
- `structured_data`: pass with a parseable `application/ld+json`; else warn.
- `https`: pass when the final URL is https; else fail.
- `robots_txt` and `sitemap`: pass when `/robots.txt` and `/sitemap.xml` (or a `Sitemap:` line) return 200; else warn.

**Fix list.** Code builds the candidate list: every warn/fail check and the top 8 opportunities by savings, ordered fail before warn by weight, then opportunities by savings; this is the default and the only list when no LLM is configured. With an LLM, send only a JSON object of those candidates (`id`, `status`, `observed` or `savings_ms`) and the five metric labels, 20,000 chars max, temperature 0.2, `max_tokens` 1,200, timeout 20 s, cached with the audit.

System rules:
1. You only order and explain the candidates provided. Do not add findings.
2. Return at most 5 items, ranked by likely impact for a typical site owner.
3. Do not predict rankings, traffic, or score changes, and do not invent numbers; use only numbers in the input.
4. Write for a non-expert in plain sentences.
5. Return only the JSON object.

Output: `{ "fixes": [ { "candidate_id": string, "rank": 1-5, "why": string max 200, "how": string max 300, "effort": "low"|"medium"|"high" } ] }`. Code checks that each `candidate_id` exists once, ranks are unique, and every number in the text occurs in the input. One retry on failure; if it still fails, show the deterministic list without explanations and no error. `ai_summary_md` is assembled by code from the validated items.

## 5. Screens and states

- **`/`:** URL input, strategy toggle (mobile default), **Audit** button, remaining calls. Signed out: "Sign in to run an audit." Loading: progress bar and "Running Google PageSpeed. This takes about 30 seconds." Errors show the API message.
- **`/a/[id]`:** four score rings (green 90-100, amber 50-89, red below 50), caption "Lighthouse lab data, one run", metric cards with good/needs work/poor, checklist with pass/warn/fail, fix list, **Run again** (bypasses cache and counts against the cap), **Share**, **Delete**. Failed audit: the error message and a retry button.
- **`/s/[token]`:** read-only copy of the report, no user email, noindex. Unknown token: "This report link is not valid."
- **`/history`:** audits for the signed-in user, filter by URL, a score trend line with at least 2 points. Empty: "No audits yet. Run your first one on the home page."

## 6. MCP tools (owner only)

`run_audit(url, strategy)` writes and spends quota; `get_audit(id)` is read-only. Both act only for the owner; discovery exposes no data. Enabled with `capabilities: ["mcp"]`.

## 7. Limits and defaults

| Item | Value |
| --- | --- |
| Audits per user | 10 per day; global `GLOBAL_DAILY_CAP` default 300 |
| PSI timeout | 60 s |
| HTML fetch | 2 MB, 10 s, 3 redirects |
| Cache | 6 hours |
| Share links per audit | 1 |
| History | 100 audits per user, oldest deleted past that |
| Fix list | 5 items |

## 8. Verification

Fixed input: `https://example.com`, which has a title, one `h1`, and a viewport tag but no meta description and no canonical.
1. Sign in, audit `example.com` (no scheme). The URL is stored as `https://example.com/`; four scores appear within about 60 s; `meta_description` is fail and `canonical` is not pass; the caption "Lighthouse lab data, one run" shows.
2. Run it again: it returns at once with `cached: 1` and the remaining count is unchanged.
3. Reload `/history`: the audit is listed. Open its share link signed out; it renders without an email.
4. Edge: `HTTPS://Example.com/#top` hits the same cache entry.
5. Edge: a URL that returns a PDF or image gives `invalid_input` "That URL did not return an HTML page."
6. Edge: with `LLM_API_KEY` unset the fix list is deterministic and fail items precede warn items.
7. Failure: `http://169.254.169.254/` and `http://localhost` return `invalid_input` with no outbound call.
8. Failure: unset `PAGESPEED_API_KEY`; the audit returns `not_configured`.
9. Failure: run 11 non-cached audits; the 11th returns `rate_limited`.
10. Failure: signed out, `POST /api/audits` returns 401.

## 9. Out of scope

Site-wide crawling, backlink data, keyword rankings, scheduled re-audits (offer a Run again button), ranking or traffic predictions, PDF export.
