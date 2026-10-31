# XBase: Studio listing notes (for the browser-lane listing session)

Prepared 2026-10-31 at build time. The listing itself (Studio
create/PRIVATE, plans, proxy-secret wiring, publish, gateway test,
Spotlight) runs in the parent's browser lane, in SMALL CHUNKED TASKS
(basics, then endpoints, then pricing plus proxy secret) - monolithic
Studio sessions die silently (PIPELINE.md stage 7). Service is live
on Render first; see README section 13 for the service id and URL.

PUBLISH IS PARKED until the X token step completes (see "Proxy
secret wiring" and "Token gate" below): the Hub gateway test calls
/search through the gateway, and until the owner adds his X Bearer
token the service honestly answers 503 engine_not_configured, so a
gateway test cannot pass. Do not publish an unproven service.

## Basics

- Name: XBase
- Base URL: https://xbase.onrender.com (confirm the exact subdomain
  from the Render service record before saving; Render suffixes the
  name when the bare one is taken globally)
- Short description: Search X (Twitter) through the official API:
  normalized posts for any query, plus curated news-scan presets
  for hip-hop and Black news, US and international.
- Category: Social / News (provider's pick in Studio)

## Endpoints (3)

- POST /search - JSON {query, max_results? (default 25, cap 100),
  hours_back? (default 24, cap 168)}. Returns query, count, and
  posts[] {id, text, author {username, name}, created_at, metrics
  {likes, reposts, replies, quotes}, url, lang}, newest first.
- POST /news-scan - JSON {preset}: hiphop | black-news-us |
  black-news-international. Returns preset, label, queries,
  posts_per_query, count, and the merged de-duplicated posts[].
- GET /health - status, engine state, presets, limits (open, no
  gate).

Full machine-readable spec: listings/xbase-openapi.json.

## Plans: bill PER REQUEST (one search or scan = 1 request)

BASIC $0 / 100 requests per month; PRO $5 / 1,000; ULTRA $20 /
10,000; MEGA $60 / 50,000, all hard limits (the own-product grid).

## Token gate (BEFORE proxy-secret wiring and publish)

1. The owner creates an app at developer.x.com under his own X
   account, accepts the developer terms himself, and funds the
   pay-per-use balance himself ($0.005 per post returned).
2. He provides the app's Bearer token through the Secure Vault
   (never in chat).
3. Set X_BEARER_TOKEN on the Render service (render_api.py set-env),
   redeploy, and run ONE small live proof: POST /search for a
   dozen-post query (about $0.06) through the proxy gate; expect 200
   with real normalized posts and _meta.engine "live". Record the
   live numbers in docs/xbase-reliability.md.

## Proxy secret wiring (after the token gate)

1. In Studio, connect the API / open the security or proxy settings
   and copy the API's proxy secret.
2. Set it on the Render service as RAPIDAPI_PROXY_SECRET
   (render_api.py set-env, or the dashboard), then trigger a deploy.
3. VERIFY THE GATE AT THE SERVICE, not from the env write: POST
   /search without the header must return 401
   {"error": "unauthorized"}; with the header it must answer (a 422
   missing_parameter on an empty JSON body proves the gate passed);
   GET /health stays open. If the gate is not active after the first
   deploy, deploy once more and re-verify (the env write and the
   deploy can race; learned 2026-10-28 on GeoBase/SwiftRewrite).
   NOTE: the service was gate-tested at build time with a temporary
   secret in mock mode, then redeployed into its awaiting-token
   state still gated under that test value (not retained). Setting
   the Studio secret here overwrites it; re-verify the gate right
   after, as above, before publishing.
4. Publish, then run the Hub gateway test end to end (subscribe the
   owner's test account to BASIC first): POST /search through
   xbase.p.rapidapi.com with a small query - expect 200 with real
   normalized posts, engine "live". A cold-start timeout on the
   first call is the known free-tier behavior; retry once before
   treating it as a failure.

## Spotlight (after publish, same session)

Description must stay UNDER 280 characters. Draft (236 chars):
"XBase searches X through the official API, no scraping: normalized
posts for any query, plus curated news scans for hip-hop and Black
news, US and the diaspora worldwide. Per-post cost and engine state
stated honestly in every response."
Post via the URL tab with the GitHub blob URL of
docs/xbase-reliability.md (the File tab rejects markdown; use the
blob URL of the pushed file on
github.com/Yamillionaire/rapidapi-services).

## Honesty notes for the overview copy (do not oversell)

- Official API only; never claim scraping, timelines, follower
  data, or posting. v1 is recent search plus the three presets.
- The upstream charges per post returned; the listing copy should
  say the per-request price reflects real upstream cost.
- Until the token gate clears, the deployed service answers 503
  engine_not_configured on its data endpoints. That state must be
  resolved before publish, never papered over in copy.
