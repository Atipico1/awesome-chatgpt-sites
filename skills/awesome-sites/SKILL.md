---
name: awesome-sites
description: Entry point for building small SaaS-style apps on ChatGPT Sites (hosting + D1 database + R2 files + Sign in with ChatGPT), including apps that use free-tier AI, search, and email APIs. Use when the user describes something they want to build or need as a web tool, SaaS, internal tool, or MCP server and wants it hosted on Sites, or asks what they could build on Sites. Recommends from a catalog of 31 ready app specs, guides the user through getting any API keys, then builds the chosen one with the official Sites skill.
---

# awesome-sites

Pick the right app spec for the user's need, collect any API keys, and build it on ChatGPT Sites. Reply in the user's language. Specs are in English.

## Flow

1. **Listen.** Read what the user wants. If they only ask what is possible, show the catalog grouped by category and ask which one fits.
2. **Recommend.** Match the need to the catalog below. Offer one best match and at most two alternatives, each with one line on why and what it costs to run (keys needed, free-tier limits). If nothing fits, say so and offer the closest one with the changes needed, or build a custom app using `references/shared/baseline.md`.
3. **Read the spec.** Load `references/apps/<app>.md`, then `references/shared/baseline.md` and `references/shared/access-and-domains.md`. If the app calls an external API, also read `references/shared/usage-guard.md`.
4. **Permission gate (required before any build).** Send one message that lists the decisions below with a recommended default for each, and wait for the user's explicit approval. Do not create, build, or publish anything until they answer. A reply like "go with the defaults" counts as approval. Ask only what applies to the chosen app.
   - **Audience:** private (owner), invited people, workspace, or public internet. Use the recommendation table in `access-and-domains.md`. Say what each choice lets strangers see. You never change the audience yourself; the user does it in Share, or tells you to after you show the URL.
   - **Sign-in:** which actions need Sign in with ChatGPT. Say that visitors can only sign in with a ChatGPT account.
   - **Custom domain:** yes or no. If yes, explain cost (about 25 credits a month plus the domain itself), that they must be able to edit DNS, and the steps in `access-and-domains.md`. The default is the `*.chatgpt.site` address; a domain can be added later.
   - **Keys and who pays:** which providers, which are free, and that the owner's key serves all visitors (see `usage-guard.md`). Whether to offer BYOK where the spec has it.
   - **Data and privacy:** what the app stores about visitors and for how long.
   - **Money:** for payment apps, Stripe test mode first; the user switches to live keys.
   - **Cost note:** hosting is free through 2026-12-31, then credits apply.
5. **Keys.** After approval, for each key in the spec's **Keys** line follow "How to ask the user for a key" in `references/shared/api-keys.md`: give the signup link and steps, tell the user the exact secret names, and have them enter values in the site's settings, never in chat. Ask for one provider at a time. Offer the recommended default (Groq for LLM, Tavily for search) so the user does not have to compare.
6. **Build** with the official `sites` skill, following the spec exactly. Do not wait for keys: build with key-dependent features disabled, then guide the user to set the secrets and run the owner-only health check.
7. **Finish** with the final report required by `references/shared/baseline.md`: URL, audience, secrets still to set, caps chosen, what was left out, and the 2027 hosting-cost note. If a custom domain was approved, give the exact steps and remind the user to set `SITE_URL`.

If the Sites skill or Sites tools are unavailable, tell the user and stop.

## Catalog

Plan requirement: a ChatGPT plan with Sites access (Plus, Pro, or an eligible workspace). Cost column shows what the owner needs beyond Sites.

### Customer-facing tools (no AI key)

| App | What it does | Use when the user says | Needs | Spec |
| --- | --- | --- | --- | --- |
| feedback-board | Customers post and vote on feature requests; public roadmap | "feature requests", "roadmap", "Canny", "user feedback board" | none | `apps/feedback-board.md` |
| waitlist | Collects pre-launch emails; referral links move people up | "waitlist", "launch page", "collect emails" | none | `apps/waitlist.md` |
| changelog | Release-notes page with RSS and an embeddable widget | "changelog", "release notes", "what's new" | none | `apps/changelog.md` |
| form-backend | Form builder and submission inbox; accepts posts from any HTML form | "form backend", "contact form", "Typeform", "collect responses" | none (Resend optional) | `apps/form-backend.md` |
| testimonials | Collect customer testimonials and show a wall of love | "testimonials", "reviews page", "social proof" | none | `apps/testimonials.md` |
| booking | Weekly availability and a page where people pick a time | "scheduling", "Calendly", "book a call" | none (Resend optional) | `apps/booking.md` |
| link-shortener | Short links with click stats and QR codes | "short links", "Bitly", "QR code", "click tracking" | none | `apps/link-shortener.md` |
| link-in-bio | Public page of links with themes and click stats | "link in bio", "Linktree", "profile links page" | none (R2) | `apps/link-in-bio.md` |
| email-signature | Builds copy-paste HTML email signatures, with an optional team mode | "email signature", "signature generator" | none (R2) | `apps/email-signature.md` |

### Files and payments

| App | What it does | Use when the user says | Needs | Spec |
| --- | --- | --- | --- | --- |
| file-transfer | Upload files and share an expiring, optional-password link | "send big files", "WeTransfer", "share files" | none (R2) | `apps/file-transfer.md` |
| invoicing | Invoices with a public pay page and Stripe Checkout | "invoice clients", "get paid", "billing" | Stripe | `apps/invoicing.md` |
| digital-storefront | Sell PDFs, templates, or downloads with Stripe | "sell digital products", "Gumroad", "sell a template" | Stripe (R2) | `apps/digital-storefront.md` |
| doc-sharing | Share a PDF through a trackable link; see who opened it and time per page | "pitch deck tracking", "DocSend", "who opened my PDF" | none (R2) | `apps/doc-sharing.md` |

### AI and web-data tools (free-tier APIs)

| App | What it does | Use when the user says | Needs | Spec |
| --- | --- | --- | --- | --- |
| formula-ai | Turns a plain-language request into an Excel/Sheets formula, SQL, or regex | "formula generator", "write SQL for me", "regex helper" | LLM key | `apps/formula-ai.md` |
| research-briefs | Searches the web and writes a cited report | "research a topic", "market research", "competitor brief" | Tavily + LLM | `apps/research-briefs.md` |
| csv-enricher | Fills new columns in a CSV from web search | "enrich leads", "find company info for a list", "Clay" | Tavily + LLM | `apps/csv-enricher.md` |
| bookmarks-mcp | Bookmark library with AI summaries, searchable from ChatGPT through MCP | "save links", "read later", "Raindrop", "bookmarks for my agent" | none (LLM optional) | `apps/bookmarks-mcp.md` |
| meeting-notes | Audio to transcript, summary, and action items | "meeting notes", "transcribe recordings", "Otter" | Groq + LLM | `apps/meeting-notes.md` |
| resume-tailor | Tailors a resume and cover letter to a job posting | "resume", "cover letter", "job application" | LLM | `apps/resume-tailor.md` |
| docs-chatbot | Support chatbot trained on your docs, embeddable | "chatbot for my docs", "Chatbase", "customer support bot" | LLM (embeddings optional) | `apps/docs-chatbot.md` |
| seo-audit | PageSpeed scores and on-page SEO checklist with a fix list | "SEO audit", "page speed", "check my site" | PageSpeed key (LLM optional) | `apps/seo-audit.md` |
| receipt-tracker | Reads receipt photos into an expense log with CSV export | "expenses", "receipts", "Expensify" | Gemini key | `apps/receipt-tracker.md` |
| feedback-analyzer | Groups reviews or survey answers into themes with sentiment | "analyze reviews", "survey responses", "customer feedback themes" | LLM | `apps/feedback-analyzer.md` |
| snippet-library | Reusable text and prompts with variables, searchable by ChatGPT through MCP | "canned replies", "text snippets", "prompt library", "TextExpander" | none (LLM optional) | `apps/snippet-library.md` |
| review-reply-drafter | Paste a customer review, get three reply drafts in the business's voice | "reply to reviews", "Google review replies", "리뷰 답글" | LLM key | `apps/review-reply-drafter.md` |

### Korean-market tools (UI in Korean)

| App | What it does | Use when the user says | Needs | Spec |
| --- | --- | --- | --- | --- |
| group-order-ledger | Turns pasted KakaoTalk group-order chat into an order table and matches deposits (records only) | "공동구매 정리", "카톡 주문", "입금 확인" | LLM key | `apps/group-order-ledger.md` |
| order-sheet-converter | Merges marketplace order sheets into a courier upload file, in the browser | "스마트스토어 주문 엑셀", "택배 양식", "송장 입력" | none | `apps/order-sheet-converter.md` |
| campaign-tracker | Tracks sponsored-campaign deadlines with a calendar feed (체험단, brand deals) | "체험단 일정", "협찬 관리", "sponsorship tracker" | none (LLM optional) | `apps/campaign-tracker.md` |
| club-ledger | Dues, attendance, fines, and ranking for clubs; records only, never handles money | "회비 관리", "동호회 총무", "모임 장부" | none | `apps/club-ledger.md` |

### Team and agent tools

| App | What it does | Use when the user says | Needs | Spec |
| --- | --- | --- | --- | --- |
| issue-tracker | Linear-style issue board with MCP tools | "issue tracker", "kanban", "Linear" | none | `apps/issue-tracker.md` |
| memory-mcp | Personal memory that ChatGPT and Codex can read and write over MCP | "memory server", "remember across chats" | none | `apps/memory-mcp.md` |

## Rules for recommending

- Prefer the spec that needs the fewest keys when two fit equally.
- When recommending, say what the app replaces and the paid price from `references/shared/pricing.md`, and also what the paid product has that the spec lacks. Never present a spec as a full replacement of a larger product, and say plainly when a free alternative already exists.
- Say plainly when a need depends on something Sites does not offer: scheduled jobs, built-in email, built-in AI, long-running background work, or non-ChatGPT user login. Offer the scaled-down version in the spec.
- Free-tier limits are shared by all visitors. For any public app that spends quota, say who pays when the quota runs out (the owner's key) and mention the BYOK option when the spec has it.
- Do not combine two specs in one build unless the user asks; build them as separate sites.
- Do not claim Sign in with ChatGPT "plan usage" (using the visitor's ChatGPT plan for AI calls) works on Sites. It is not documented for Sites.

## Adding a spec

Create `references/apps/<name>.md` following `references/shared/spec-template.md`. Then add one row to the catalog above and to the README.
