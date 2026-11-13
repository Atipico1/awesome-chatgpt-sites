# Baseline for every app

Every app reference inherits these rules. An app reference only states what differs.

Use the official `sites` skill for project setup, registration, dependencies, build, packaging, and publishing. If the Sites skill or Sites tools are unavailable, tell the user and stop. Build in one pass without stopping to ask about product details; ask only for API keys (see `api-keys.md`).

## Platform facts (checked against learn.chatgpt.com, 2026-11)

- Runtime is a Cloudflare Worker-compatible module. HTTP, HTTPS, and WebSockets work. Raw TCP does not.
- D1 (relational, 10 GB per site) and R2 (files) are the only storage. Bind D1 as `DB`. Add R2 only when the app stores files.
- Identity: Sign in with ChatGPT (SIWC). Server code reads `oai-authenticated-user-email` and optionally `oai-authenticated-user-full-name`. Sign-in path `/signin-with-chatgpt`, sign-out path `/signout-with-chatgpt`. Make every authorization decision on the server.
- Secrets and environment values are set in the site's settings, never in prompts, source, or `.openai/hosting.json`.
- Payments only through a third-party processor. The site must never see card data. Other financial transactions are prohibited.
- Prohibited content: PHI, services aimed at children under 13, malware, phishing, impersonation.
- Hosting is free through 2026-12-31. From 2027-01-01 a site with a database costs about 25 credits a month before traffic (Plus allowance: 125). Mention this once in the final report.

## Not documented by Sites: design around it

- **No scheduled jobs.** Do not depend on cron or background workers. Do work on request, on page load, or in a client-driven loop that saves progress to D1 and can resume.
- **No built-in email.** Send mail only through Resend (see `api-keys.md`). The app must work fully without it by showing the message in an in-app inbox or giving a copyable link.
- **Upload and request size limits are unknown.** Cap uploads in the app, show a clear error above the cap, and record the cap you chose in the final report.

## Access patterns

Pick the pattern the app reference names.

- **Private tool** (default): audience is owner only. Add people through Sites access settings. Every user shares one dataset unless the app says otherwise.
- **Public site with owner admin**: the public pages work signed out. Admin pages and write APIs require SIWC and `oai-authenticated-user-email` listed in the `OWNER_EMAILS` environment value (comma-separated). If `OWNER_EMAILS` is empty, the first signed-in user to open `/admin` is stored as owner in a `settings` table and no one else can claim it afterwards.
- **Public tool with sign-in for AI actions**: anyone can browse; any action that spends an API quota requires SIWC and passes the usage guard in `usage-guard.md`.

## Site address

Never hard-code the site address. Read `SITE_URL` from the environment (fall back to the request origin) for every absolute link; see `access-and-domains.md`.

## Environment values shared by specs

| Name | Used for | Default |
| --- | --- | --- |
| `OWNER_EMAILS` | Comma-separated emails allowed to use admin pages | empty (first signed-in user to open `/admin` becomes owner) |
| `SITE_URL` | Public base URL for absolute links | request origin |
| `GLOBAL_DAILY_CAP` | Daily limit on quota-spending calls across all users | 300 |
| `SIGNUP_MODE` | `owner_only` or `open`; whether any signed-in user may create their own public pages (link-in-bio) | `owner_only` |

A spec may add its own values; list them in its Keys or Limits section.

## Keys and health check

- Read each key from the environment on the server only. Never send a key, or a response containing one, to the browser.
- If a required key is missing, the feature stays visible but disabled, with a message that names the missing setting. Never crash.
- Add an owner-only `GET /api/health` that returns `{ "<KEY_NAME>": true|false }` for each key, and `ok:true` for a live probe call where the app reference lists one. It never returns values.

## Style

Unless the app reference says otherwise: neutral palette, one accent color, readable on a phone, dark mode supported, empty states that tell the user what to do next, and no marketing copy inside tools.

## Done criteria pattern

Each app reference lists "Done when". In addition, every app is done only when:

1. The build passes and a deployment URL is returned.
2. The golden path works in the deployed site, and the data survives a reload.
3. Each required key is either configured and its live probe passes, or the dependent feature shows its disabled state. Report which.
4. The final report lists: URL, audience, secrets still to set, caps chosen, and anything intentionally left out.
