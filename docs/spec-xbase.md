# Spec: XBase (X / Twitter news search via the official API; the user's own product, queue #13)

Originated by the user in a live voice call on 2026-10-31:
"Definitely build an API" for X (Twitter) news access, after the
options were laid out in the same call. Direct scraping is off the
table (X's Terms prohibit crawling the platform), so XBase wraps the
OFFICIAL X API v2 recent-search endpoint with the operator's own
Bearer token. Built under his standing full-automation authorization
for this lane (2026-10-29). An original product in the lane's house
style, built first as his own news engine: its /news-scan presets
are the curated query sets the twice-daily feed checks (a cadence he
approved the same day) will call for HipHopolis News and the All
Black Towns Black News feed (America and International tabs).

## The product

- POST /search {query, max_results? (default 25, cap 100),
  hours_back? (default 24, cap 168)} - one X API v2 recent-search
  call; returns normalized posts, newest first: id, text, author
  (username, name), created_at, public metrics (likes, reposts,
  replies, quotes), post URL (https://x.com/<user>/status/<id>),
  lang. The X API's own per-call floor is 10 posts: smaller
  max_results values are honored by slicing the normalized result,
  never by over-claiming.
- POST /news-scan {preset} - runs the preset's curated queries,
  merges, de-duplicates by post id, returns newest first with a
  per-query count. Presets:
  - "hiphop": hip-hop releases, tours and shows, business, culture.
  - "black-news-us": Black news in the United States (policy and
    community, HBCU and Black business, history and heritage).
  - "black-news-international": the African diaspora worldwide
    (Africa, the Caribbean, the UK, Canada, Latin America).
- GET /health - version, engine state, preset inventory, limits.

## Engine states (honest by construction)

The engine reads its token from the X_BEARER_TOKEN env var.

- live: token set; calls go to api.twitter.com.
- mock: XBASE_MOCK=1; the client returns built-in fixture payloads
  that pass through the SAME normalization code as live responses.
  Every mock response carries "engine": "mock" in its meta and the
  fixture post texts say FIXTURE in the text itself, so a fixture
  can never be passed off as a live post downstream.
- awaiting_token: neither set; /search and /news-scan answer an
  explicit 503 engine_not_configured. This is the deployed state
  until the owner completes the token step (see Launch state).

## Cost shape (the reason the token step is the owner's)

X's current pay-per-use pricing is $0.005 per post RETURNED, billed
to the token owner's X account, plus the app rate limit of 450
requests per 15 minutes. The build itself spends nothing. Once the
owner funds his X developer account, the twice-daily preset scans
draw on that balance: three presets x three queries x up to 25 posts
is at most 225 posts per scan round, about $1.13 per round at cap,
less in practice (de-duplication happens after return, and most
queries return fewer than the cap).

## What v1 deliberately does not claim

- No scraping, ever: official API only.
- No user timelines, no follower data, no posting: recent search
  only, the surface the news use case needs.
- No sentiment or summarization layer in v1: normalized posts are
  the product; the feed pipelines do their own editorial pass.

## Plans (to save in Studio, hard limits, per request)

BASIC $0/100mo; PRO $5/1,000mo; ULTRA $20/10,000mo; MEGA $60/50,000mo
(the own-product grid). Note for subscribers, stated in the listing
copy: each request performs real X API searches, and the per-request
price reflects the per-post cost upstream.

## Internal pipeline use (planned, NOT yet wired)

When the listing is live and the token is in place, the twice-daily
X news checks for HipHopolis News and the Black News feed call
/news-scan (one call per preset) through the RapidAPI gateway. The
cron wiring happens only after the API is live and the user
confirms; nothing is scheduled by this build.

## Launch state at build (2026-10-31)

Built and deployed on Render; proven end to end with mocked X API
responses locally AND deployed (health 200, gate 401/422/200,
/search and all three /news-scan presets returning correctly shaped
normalized output from fixtures, labeled mock). PARKED at the token
step: no X credential exists in any approved store, and creating an
X developer account, agreeing to X's developer terms, or buying X
API credits are the owner's steps, not the agent's. Publish is
parked behind the same step: the RapidAPI gateway test would call
/search through the gateway, and with no token the honest answer is
the 503, so the listing stays unpublished until one small live
/search proof (about a dozen posts, about $0.06) can pass. Full
record: docs/xbase-reliability.md; listing package:
listings/xbase-openapi.json + listings/xbase-listing-notes.md.

## Deploy

Render free plan, same repo: build `true` (stdlib only, no
dependencies), start `python xbase/app.py`. Keep-warm fleet becomes
thirteen services; the window is re-budgeted to 09:00-10:40 ET
(671h worst month vs the 750h cap).
