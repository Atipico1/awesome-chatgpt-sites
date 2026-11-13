# Demand evidence

Why each app is in the catalog, how strong the evidence is, and what was rejected. Checked 2026-11-13. Revenue and user numbers are claims by founders, vendors, or TrustMRR pages (which show Stripe, Paddle, RevenueCat, or Polar-verified figures) unless noted. New specs add a section here (see CONTRIBUTING.md).

**Coverage gaps.** Reddit and X/Twitter could not be read with the tools used (search returned nothing for those domains), and Hacker News gave no usable "what would you pay for" threads. Most evidence comes from Indie Hackers, TrustMRR, Product Hunt pages, vendor blogs, and Korean and Japanese communities. Treat the strength ratings below as a guide, not proof. Indonesian, Brazilian, and Chinese sources were only skimmed.

Strength: **strong** = a verified or widely reported paying market; **medium** = paying competitors exist and users describe the pain; **thin** = pain described, little payment evidence.

## First batch (from market knowledge, not re-verified)

feedback-board (Canny, Featurebase), waitlist (Prefinery, Waitlister), changelog (Headway, Beamer), form-backend (Tally, Web3Forms), testimonials (Senja, Testimonial.to), booking (Calendly, Cal.com), link-shortener (Bitly, Dub), file-transfer (WeTransfer), invoicing (Wave, Bonsai), digital-storefront (Gumroad, Lemon Squeezy), formula-ai (Excel Formula Bot, reported around $23K a month in a video), research-briefs, csv-enricher (Clay), bookmarks-mcp (Raindrop), meeting-notes (Otter, Fireflies), resume-tailor (Teal), docs-chatbot (Chatbase), seo-audit (free audit tools), receipt-tracker (Expensify), feedback-analyzer (Thematic). These were chosen from the named paid products, not from per-app research. Strength: medium for all; no per-app source review was done.

## Second batch

| App | Strength | Evidence |
| --- | --- | --- |
| doc-sharing | strong | Papermark reported at about $900K ARR and about 1,000 paying customers (founderspec.com/breakdowns/papermark). A Product Hunt "free DocSend alternative" (producthunt.com/products/roundos-data-room) quotes "tired of paying $45 a month to see who opened our own pitch deck". |
| link-in-bio | medium | TrustMRR: Linkie $392 MRR, 55 subscriptions, $14.9K all-time (trustmrr.com/startup/linkie); Linkos $7.8K all-time, 500+ users (trustmrr.com/startup/linkos). Linktree is the incumbent. Phishing risk is real; the spec adds `SIGNUP_MODE`, reports, and takedown. |
| email-signature | medium | SyncSignature on TrustMRR: $2,622 MRR, 138 subscriptions, $40.6K all-time, about 40,000 users, Paddle-verified (trustmrr.com/startup/syncsignature). Growth is SEO-driven, so revenue is modest. |
| snippet-library | thin to medium | Indie Hackers: Slashit reported at $1K MRR (indiehackers.com/post/from-a-personal-problem-to-a-1k-mrr-saas-tool-b39793a0fd, 2025-11-23); a reply helper with a free daily limit (indiehackers.com/post/i-built-a-small-tool-to-reply-faster-to-emails-and-dms-29e1f56bd6, 2026-01-29). The MCP access from ChatGPT is the reason to host it. |
| review-reply-drafter | medium | Indie Hackers: a small agency spends 5+ hours a week on review replies and existing tools cost "$200-500/month" (indiehackers.com/post/i-built-a-chrome-extension-that-responds-to-google-reviews-in-10-seconds-just-launched-3ce1122f5c, 2026-02-07). Paid per-store services exist in Korea; their value is auto-posting, which this spec excludes. |
| group-order-ledger | medium | 다골라 devlog: forms collect requests but non-responders, deposit matching, ordering, and distribution stay manual in Excel (2nd-korea.com/blog/dagolla-group-order, 2026-10-23). Competing products: 주문하마 (hipporder.com), 장부AI (jangbuai.com), EXCLOAD. A test of 40 synthetic orders found a plain prompt dropped ambiguous customers 3 of 3 times and a "needs review" instruction kept them (gwfuture.co.kr/news/gw-467, 2026-11-12). |
| order-sheet-converter | medium | Seller community posts about merging 스마트스토어, 쿠팡, and 지마켓 orders by hand and finding monthly-fee tools too expensive (sellermoim.com/post/2226, 2026-06-20; sellermoim.com/post/4490, 2026-10-08). A Windows tool "주문합치기" (postype.com/@arche-studio/post/23317819) and EXCLOAD sell the same output. No revenue figures found. |
| campaign-tracker | thin to medium | 콜라보매니저 reported at 20,000 users with no ads, a press release (benews.co.kr/news/469138, 2026-02-20). A maker's Threads post says users like the 체험단 schedule app they built for themselves. The main competitor is free. |
| club-ledger | thin to medium | Existing apps: 총무의가계부 (free for one group and 30 entries; no bank sync or auto reminders; jjchongmoo.com/guide/dues-management-app, 2026-10-07), 페이마인드 (free; Pro 3,300 KRW a month; atelierlaunch.kr/ideas/club-dues, 2026-11-06). A running-crew admin tallies mileage and fines in Excel (brunch.co.kr/@eggholder/4). Collecting dues for others may fall under Korean electronic payment rules (not legal advice), so the spec only records. |

## Considered and not added

| Idea | Why not |
| --- | --- |
| Uptime monitor and status page with auto checks | Needs scheduled jobs and email; a manual-update status page had weak willingness to pay (a post reports 3 customers out of 132 users). |
| Dynamic QR codes | Near-duplicate of link-shortener; one report shows 4 customers and $60; another $274 MRR. |
| Stripe dunning and failed-payment recovery | Needs webhooks, scheduled retries, and email; moving money is prohibited. |
| Auto-posting review replies, marketplace profit sync, web-novel calendars | Need platform logins, scraping, or cron. |
| Browser-only dev and PDF tools | A hosted backend adds nothing; one maker reports thousands of users and $0 revenue. |
| Stripe CSV to MRR dashboard | Narrow audience; thin evidence. A candidate for later. |
| Business-plan generator | About 5 paying users at $29 and ad-dependent traffic; heavy token use on free tiers. |
| Quote and proposal generator | Overlaps invoicing; acceptance notifications need email. Better as an extension of invoicing. |
| Job-search tracker | Overlaps resume-tailor; the scraping part cannot run on Sites. |
| Teacher worksheet generator | Thinnest evidence; under-13 risk if students log in. |
| AI interview practice (case interviews) | One product at about $4.3K MRR (trustmrr.com/startup/road-to-offer). The value is authored case content, not software; generic mock-interview apps earn little. A candidate if someone supplies content. |
| Voice-to-social-post | One strong iOS app ($19.8K MRR, trustmrr.com/startup/draft-ai-1); no evidence a web recorder converts the same way; Groq free file-size cap unverified. A candidate later. |
| Paid launch directory | Revenue depends on domain authority and audience a new site lacks. |
| Verified-revenue pages | Requires storing customers' Stripe keys; security burden; crowded. |
| Baby and gift registry | Anonymous gift-givers need public access; URL fetching raises SSRF exposure; one strong app is a localized mobile product. |
| Niche job board | About $543 MRR in one case; needs supply seeding and email alerts. |
| Niche calculator with saved reports | One Indie Hackers story of about $500 MRR after SEO growth; the moat is domain expertise, so a generic spec adds little. A candidate for a specific vertical. |
| 정산 대조 + 순이익, 핸드메이드 원가, 수강료 장부, 모바일 청첩장, 월세 장부, 유튜브 리포트 | Free or cheap incumbents, thin evidence, or collecting gift money online (prohibited). |
| AI humanizer, scraping and lead tools, mobile consumer apps | Commoditized or ethically poor; need scraping, cron, or app-store distribution. |
