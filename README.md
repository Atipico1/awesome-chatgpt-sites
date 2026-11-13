# awesome-chatgpt-sites

App-building skills for [ChatGPT Sites](https://learn.chatgpt.com/docs/sites), OpenAI's hosting for sites built in ChatGPT and Codex. (This is not a list of ChatGPT mirror sites.)

Each skill builds one specific app (a personal web app or an MCP server) and publishes it to Sites in one pass. The skills fix the product decisions: scope, data model, screens, MCP tools, and done criteria. The official Sites skill handles setup, build, and publishing.

## Skill

One skill, [awesome-sites](skills/awesome-sites/SKILL.md), is the entry point. Describe what you need ("a feedback board for my SaaS", "something that turns meeting recordings into notes"). It recommends a matching app spec from the catalog, walks you through getting any API keys, and builds the app on Sites.

The 31 app specs live in [`skills/awesome-sites/references/apps/`](skills/awesome-sites/references/apps/). Shared rules are in [`references/shared/`](skills/awesome-sites/references/shared/): platform baseline, API key guides, and the usage guard for free-tier APIs.

| Group | Apps |
| --- | --- |
| Customer-facing tools | feedback-board, waitlist, changelog, form-backend, testimonials, booking, link-shortener, link-in-bio, email-signature |
| Files and payments | file-transfer, doc-sharing, invoicing, digital-storefront |
| AI and web-data tools | formula-ai, research-briefs, csv-enricher, bookmarks-mcp, meeting-notes, resume-tailor, docs-chatbot, seo-audit, receipt-tracker, feedback-analyzer, snippet-library, review-reply-drafter |
| Korean-market tools (Korean UI) | group-order-ledger, order-sheet-converter, campaign-tracker, club-ledger |
| Team and agent tools | issue-tracker, memory-mcp |

Sites is the free host, database, and file store. AI, search, and email come from outside APIs with free tiers (Groq, Gemini, Cloudflare Workers AI, Tavily, Jina Reader, PageSpeed Insights, Resend). Sites does not document a built-in AI binding, scheduled jobs, or built-in email, so the specs avoid depending on them.

## Requirements

- Codex with the official **Sites** plugin installed and enabled
- A ChatGPT plan with Sites access (Plus, Pro, or an eligible workspace; not Free or Go)

## Install

Copy the one skill folder into your skills directory:

```bash
git clone https://github.com/Atipico1/awesome-chatgpt-sites.git
cp -R awesome-chatgpt-sites/skills/awesome-sites ~/.codex/skills/
```

Then ask Codex, for example: "I want a feedback board for my product on Sites."

API keys go into the site's settings in ChatGPT (environment variables and secrets), never into the chat.

## Adding an app spec

Read [CONTRIBUTING.md](CONTRIBUTING.md) first: it lists what a new spec must prove (real demand, fits Sites, free to run) and the PR checklist. Run `python3 scripts/lint-specs.py` before opening a PR.


- One app per file: `skills/awesome-sites/references/apps/<name>.md`, plus one row in the catalog in `SKILL.md`.
- Put only instructions in the spec. Do not include app source code.
- Leave setup, build, and publishing to the official Sites skill. The spec covers product decisions and done criteria.
- If the app cannot run within Sites limits (Cloudflare Workers runtime, ChatGPT sign-in, D1/R2 storage, no documented cron or email), drop or scope down that feature.
