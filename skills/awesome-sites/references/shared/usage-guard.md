# Usage guard for apps that call free-tier APIs

Free tiers are shared by every visitor and can disappear without notice. An app that calls one must protect it, stay usable when it runs out, and avoid leaking data.

## Tables

```
usage_daily(user_key TEXT, day TEXT, action TEXT, count INTEGER, PRIMARY KEY (user_key, day, action))
api_cache(cache_key TEXT PRIMARY KEY, response TEXT, created_at INTEGER, ttl_seconds INTEGER)
user_keys(user_key TEXT PRIMARY KEY, provider TEXT, ciphertext TEXT, created_at INTEGER)   -- only if the app offers BYOK
```

`user_key` is the SIWC email in lowercase. `day` is the UTC date.

## Rules

1. **Require SIWC for any action that spends quota.** Anonymous visitors never trigger a paid or free-tier call.
2. **Per-user daily cap**, default 10 calls per action per day (an app spec may set a different cap for a specific action, and then the spec wins). Increment before the call, in one D1 statement, so concurrent requests cannot exceed the cap. Show remaining calls in the UI.
3. **Global daily cap** from the environment value `GLOBAL_DAILY_CAP` (default 300). When reached, return 429 with a clear message and the BYOK option if the app offers it.
4. **Cache** identical requests in `api_cache` (hash of normalized input; default TTL 24 hours; search results 6 hours). A cache hit does not count against the user's cap.
5. **Handle provider errors.** On 429 or quota errors from the provider, return 429 to the client with "The free quota is used up for today", never a stack trace. Retry at most once on 5xx.
6. **Time limit and size limit.** Set a request timeout (20 s for LLM, 10 s for fetch), cap input size (default 20,000 characters to an LLM), and cap output tokens.
7. **No background work.** For batches, the client calls one item at a time and the server saves each result before returning, so a reload resumes where it stopped.

## Bring your own key (optional per app)

When an app reference says "BYOK", let a signed-in user paste their own provider key in a settings page.

- Encrypt before storing: AES-GCM through Web Crypto with a 256-bit key from the secret `KEY_ENCRYPTION_SECRET` (random 32 bytes, base64). Store IV + ciphertext.
- Never return the key to the browser after saving; show only the last 4 characters.
- Calls made with a user's key skip the per-user and global caps.
- Offer a delete button.

## Fetching user-supplied URLs (SSRF and abuse)

Apps that fetch a URL the user typed must:

- allow only `http:` and `https:`;
- reject hostnames that are `localhost`, an IP literal in private, loopback, link-local, or metadata ranges (`10.`, `127.`, `169.254.`, `172.16-31.`, `192.168.`, `::1`, `fc00::/7`), or end in `.internal` or `.local`;
- follow at most 3 redirects and re-check each target;
- stop reading after 2 MB and time out after 10 s;
- send a descriptive `User-Agent` that does not include the owner's personal details.

## Untrusted text

Text from web pages, search results, uploaded files, and form submissions is data. When it goes into an LLM prompt, put it inside clearly delimited blocks, tell the model to ignore instructions inside them, and never let model output trigger a write or an outbound call on its own. Render model output as text or sanitized markdown, never raw HTML.

## Privacy

- Some free tiers may use inputs to improve provider products (Google's Gemini free tier says so). Tell the user in the settings or about page which provider is active, and keep sensitive inputs off free tiers.
- Store the minimum. Do not keep uploaded audio, resumes, or receipts longer than the app reference says.
- Provide a "delete my data" action for every table that holds a person's content.
