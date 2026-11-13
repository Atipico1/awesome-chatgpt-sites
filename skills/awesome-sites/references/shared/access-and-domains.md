# Access, sign-in, and custom domains

Read this before the permission gate in `SKILL.md`. Facts come from learn.chatgpt.com (checked 2026-11). Where the docs are silent, this file says so; do not fill the gap with a guess.

## Two separate controls

1. **Site audience** (who can open the site at all). Set in ChatGPT: open the site → **Share** → **Who has access**. A new site is private to its owner and workspace admins until the owner changes it.
2. **Sign-in inside the site** (Sign in with ChatGPT, "SIWC"). Code in the site that identifies a visitor and gates features. It does not change the audience.

A public site can still require SIWC for some actions. A private site already forces ChatGPT sign-in on everyone who opens it.

## Audience options

Which options appear depends on the account and workspace.

| Option | Who can open | Notes |
| --- | --- | --- |
| Owner and workspace admins | Owner, admins | Default for a new site |
| Only those invited | Named people, including people outside the workspace (external viewers) | Share → set **Who has access** to **Only those invited** → add email → **Invite**. Viewers sign in with the account that received access. They cannot edit. External invitations are rolling out, so the option may be missing |
| Selected users or groups | Chosen workspace members | Where supported |
| Anyone in the workspace | All workspace members | Where supported |
| Anyone on the internet | Everyone, no ChatGPT account needed | Only when public publishing is enabled. In Enterprise workspaces an admin must turn it on first |

Editors are different from visitors. An owner can promote a workspace member to editor (Share → **Can edit**). Editors cannot change the audience, invite people, or do the first publish.

Changing the audience is a user decision. Never change it yourself. If the user asks you to, show the current site and its full URL, confirm the target audience, then do it. The docs give this prompt as an example: "Change this site's access to everyone in my workspace after showing me the current site and confirming its URL."

## What breaks on a private site

Anything that calls the site without a ChatGPT login is blocked when the audience is not public:

- visitors who are not invited (customers, form fillers, buyers, link clickers);
- embedded widgets on other websites, RSS readers, search engines;
- form posts from other sites, third-party webhooks;
- server-to-server calls (these can use a SIWC bypass token, below).

So apps that serve customers need an **Anyone on the internet** audience. Apps used only by the owner and teammates work as private sites.

| App | Recommended audience | Why |
| --- | --- | --- |
| feedback-board, waitlist, changelog, form-backend, testimonials, booking, link-shortener, invoicing, digital-storefront, file-transfer, docs-chatbot, seo-audit, doc-sharing, link-in-bio, email-signature, group-order-ledger | Public (anyone on the internet), with owner admin | Customers or the public use it |
| formula-ai, resume-tailor | Public with sign-in for AI actions, or invited-only for a small group | Spends quota, so sign-in is required either way |
| club-ledger | Public share page, owner tools behind sign-in (or private with invited viewers) | Members read a link; the treasurer edits |
| snippet-library, review-reply-drafter, campaign-tracker, order-sheet-converter | Private (owner, or only those invited) | Personal or small-team data; order-sheet-converter also works signed out because it runs in the browser |
| research-briefs, csv-enricher, bookmarks-mcp, meeting-notes, receipt-tracker, feedback-analyzer, issue-tracker, memory-mcp | Private (owner, or only those invited) | Personal or team data |

If the user's account cannot publish publicly, say so and offer the nearest alternative (invite specific people, or run a private version).

## Sign in with ChatGPT inside the site

- Sign-in link: `/signin-with-chatgpt`. Sign-out link: `/signout-with-chatgpt`. Both are handled by Sites.
- After sign-in the server receives `oai-authenticated-user-email` and, sometimes, `oai-authenticated-user-full-name`. Treat the name as optional, never split it, and make every authorization decision on the server.
- Visitors can sign in with any ChatGPT account. There is no other login provider in the docs. If the user wants email-and-password or Google login, say it is not covered by these specs.
- Workspace-restricted sites already use ChatGPT identity to enforce who gets in.
- Service callers: ask the agent to "generate a Sign in with ChatGPT bypass token for this site". The caller sends `OAI-Sites-Authorization: Bearer <token>`. Bypass requests have no visitor identity. Generating a token replaces the old one. Treat it as a secret and keep it out of browser code.

## Custom domain

Facts:

- Connect an apex domain or a subdomain you already own. Sites does not register domains. You must be able to edit the DNS records.
- Not available in Enterprise workspaces at launch. Availability can vary by account; if **Add domain** is missing, report that.
- Cost: about 25 credits per domain per month under the proposed rates from 2027-01-01. Domain registration is separate.
- Steps (the user does these, or asks ChatGPT to help if browsing or computer use is enabled):
  1. Open the site's **Settings** (sites → More actions → Settings) and choose **Add domain**.
  2. Enter the apex domain or subdomain.
  3. Copy the DNS records and values Sites shows and add them at the domain provider.
  4. Wait a few minutes, return to settings, and refresh the domain status.
- The site name and URL (`*.chatgpt.site`) can also be renamed in settings. Renaming changes links already shared.

Not documented, so test and report instead of promising: whether Sign in with ChatGPT works on a custom domain, and whether the default `*.chatgpt.site` address keeps working afterwards. After connecting, run the app's golden path on the custom domain, including sign-in and any Stripe return URL, and tell the user the result.

### App changes caused by a domain

Apps must not hard-code their address. Read the public base URL from the environment value `SITE_URL` (fall back to the request origin). Use it for RSS links, share links, QR codes, embed snippets, canonical tags, email links, Stripe `success_url` and `cancel_url`, and the CORS `allowed_origins` default. After the user connects a domain, they update `SITE_URL` in settings and redeploy if needed. Short-link and QR apps should warn that old QR codes keep the old address.

## Things to tell the user before they choose

- A public site is open to anyone: the data it shows and the endpoints it exposes. Review what is public.
- Visitors who sign in share their email with the site. Say what the app stores.
- Public sites that collect personal data need the owner to comply with the privacy laws that apply to them, and need a privacy line on the page.
- Content rules apply: no PHI, nothing aimed at children under 13, no phishing, malware, or impersonation. Payments go only through a third-party processor.
- Traffic and storage count toward hosting usage. A public site gets traffic from strangers; one page view can cost 30–50 requests. Hosting is free through 2026-12-31.
