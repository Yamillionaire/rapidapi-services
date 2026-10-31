# XBase reliability record (proof doc for the Spotlight)

What was actually measured, labeled mock or live without blurring
the two. Built 2026-10-31.

## The claim

XBase wraps the official X API v2 recent-search endpoint (no
scraping, which X's Terms prohibit) and returns normalized posts:
id, text, author, timestamp, public metrics, post URL, language.
Three curated /news-scan presets (hiphop, black-news-us,
black-news-international) merge and de-duplicate across their query
sets.

## Mock proof battery (no token existed at build time; this is the
honest state, and the numbers below are fixture numbers)

Local battery (xbase/tests/battery-2026-10-31.json, 13/13 checks):

- Mock mode behind a test proxy secret: /health 200 reporting
  engine "mock"; /search without the secret 401; with a wrong
  secret 401; with the secret and an empty body 422
  missing_parameter (proves the gate passed); /search with a query
  200 with correctly shaped normalized posts (every post carries
  id, text, author username/name, created_at, likes/reposts/
  replies/quotes, an https://x.com/<user>/status/<id> URL, lang),
  meta labeled engine "mock".
- All three /news-scan presets: 200, posts de-duplicated by id,
  same normalized shape.
- Unknown preset: 422 unknown_preset.
- Awaiting mode (no token, no mock): /health reports
  engine "awaiting_token"; /search answers an explicit 503
  engine_not_configured instead of inventing data.

Deployed battery: the same checks run against the Render deployment
in both modes (mock for the shape proof, then mock removed and the
service redeployed into its honest awaiting_token state). Recorded
in the registry entry for queue #13.

## What is NOT claimed yet

- No live X response has passed through this service yet: no X
  Bearer token exists in the owner's approved stores, and creating
  the X developer account, accepting its terms, and funding it are
  the owner's steps. The first live proof is planned at about a
  dozen posts (about $0.06 at $0.005 per post returned) the moment
  the token lands, and this doc will be updated with the live
  numbers before the Spotlight posts.
- Fixture texts are labeled FIXTURE in the text itself and mock
  responses carry "engine": "mock" in their meta; nothing in this
  record presents a fixture as a real post.
