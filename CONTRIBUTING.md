# Contributing

Thanks for adding to awesome-chatgpt-sites. This repo holds one skill, `skills/awesome-sites`, and a catalog of app specs under `skills/awesome-sites/references/apps/`. A good contribution is a spec that lets an agent build a working app on ChatGPT Sites in one pass without inventing product decisions.

## What we accept

A new app spec must meet all of these:

1. **Real demand.** Link at least two public sources (Reddit, Hacker News, Product Hunt, X, Indie Hackers, a community post, a revenue page) where people say they use, pay for, or ask for this kind of tool. Quote one line from each. Say plainly if the evidence is thin.
2. **Fits Sites.** It runs on a Cloudflare Worker-compatible runtime with D1, R2, Sign in with ChatGPT, server-side calls to external HTTPS APIs, and optionally MCP. It does not need scheduled jobs, background workers, built-in email, a headless browser, raw TCP, or heavy media processing. Those are not documented for Sites.
3. **Free to run.** Everything beyond Sites hosting uses a free tier or a key the user supplies. Name each provider and link the page that states the free limit. Mark limits you could not verify as `unverified`.
4. **Allowed content.** No PHI, nothing aimed at children under 13, no phishing, malware, or impersonation, no moving money other than card payments through a third-party processor.
5. **Not a duplicate.** It does something no current spec does. A variation of an existing spec belongs in that spec.

## Pull request checklist

Copy this into the PR description.

- [ ] New file `skills/awesome-sites/references/apps/<name>.md`, kebab-case name, no `sites-` prefix
- [ ] Follows `references/shared/spec-template.md`: sections 1–9 in order, header lines `Read first`, `Access`, `Audience`, `Keys`
- [ ] One row added to the catalog table in `skills/awesome-sites/SKILL.md` (what it does, "use when the user says" phrases, keys needed, spec path)
- [ ] One row added to the README table
- [ ] Demand evidence (two links with quotes) and free-tier links in the PR description, plus one row for the app in `docs/demand-evidence.md` with a strength rating (strong, medium, thin)
- [ ] New API keys, if any, added to `references/shared/api-keys.md` with the signup link, numbered steps, secret names, free limits, and a live probe
- [ ] Spec contains no application source code. SQL DDL, route tables, JSON shapes, and prose rules are fine
- [ ] Every absolute link uses `SITE_URL`
- [ ] Audience matches the table in `references/shared/access-and-domains.md`, and the table has a row for the new app
- [ ] `scripts/lint-specs.py` passes (see below)
- [ ] Tested: you built the spec on a real Site and attached the deployed URL, or you state "not built" and the reviewer treats it as unverified

## Spec rules

- **Decide, do not offer options.** Use "must", "default", and numbers. A spec that says "or similar" is not finished.
- **One app per file.** Do not merge apps; link to the other spec instead.
- **State only what is documented.** Facts about Sites and providers come from the shared files. If you add a new fact, cite the page and the date you checked it. If a number depends on an undocumented Sites limit, write "choose from what the deployed site accepts, record it in the report".
- **Keys never go in chat or source.** Specs name secrets; users enter values in the site's settings. The app works with keys missing: the feature shows a disabled state and `/api/health` reports it.
- **Protect free tiers.** Apps that spend quota follow `references/shared/usage-guard.md`: sign-in required, per-user and global caps, caching, graceful 429, and the SSRF rules for fetched URLs. If your spec changes a default, say which and why.
- **Untrusted text is data.** Web pages, uploads, and submissions that reach an LLM prompt are handled as in `usage-guard.md`. Show how model output is checked in code (grounding checks), not only how it is prompted.
- **No scheduled work.** Do work on request or in a client-driven loop that saves progress and resumes after a reload.
- **Verification must be runnable.** Give fixed inputs, expected results, at least three edge cases, at least two failure cases, and a persistence check.
- **Plain language.** No marketing words, no hedging filler. English for specs; other languages may be added only in a separate translation file.

## Changing shared files

`references/shared/` affects every app. Open a separate PR for it, explain which specs it changes, and update those specs in the same PR. When a provider's free tier changes, update `api-keys.md` with the new numbers, the page you checked, and the date.

## Changing an existing spec

Keep every decision that is already there unless the PR is specifically reversing it. Explain the reason in the description. A spec change that alters the data model should say how a site already built from the old spec migrates.

## Reporting a broken spec

Open an issue with the spec name, the step in "Verification" that failed, the deployed URL if public, and what you saw. If a provider's free tier or API changed, link its page.
