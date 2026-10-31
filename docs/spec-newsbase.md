# Spec: NewsBase Headlines (wave 3, queue #9)

Approved by the user 2026-10-29 (full-run authorization in a voice call:
automate the whole queue, publish with Spotlights). Score 64.

## The comparable listing

Google News by BFD: 7,316 subscribers, rated 3/5, pricing Basic free,
Pro $25, Ultra $50, Mega $100. Complaint themes from its own Discussions:
1. Responses that are not valid JSON, breaking client parsers.
2. A broken image proxy: article images routed through the provider's
   proxy arrive broken or not at all.
3. The usual silent-failure pattern behind both: upstream content passed
   through raw instead of normalized on the provider's server.

## The fix

An RSS aggregation service on the shared scaffold. Sources are Google
News RSS (top headlines, search, topic sections, per-country/language
editions) plus direct RSS from major outlets (BBC, NPR, The Guardian,
Al Jazeera, New York Times). All $0, no API key, no scraping: RSS is the
publishers' own syndication route.

- Always valid JSON: feeds are parsed into typed records on our server
  and serialized by us. Upstream content is never passed through raw, so
  there is no upstream formatting bug left to inherit. Malformed feed
  XML returns a structured error or the last good cached edition,
  flagged stale, never a malformed body.
- No image proxy: when a feed carries a publisher image URL
  (media:content / media:thumbnail), we return that URL directly,
  exactly as the publisher hosts it. When a feed carries no image, the
  field is omitted. Nothing is ever routed through a proxy of ours.
- Explicit errors only: unknown topic, missing query, unsupported
  source, and upstream failures all return the scaffold's structured
  JSON error objects.

Endpoints: GET /headlines (country, language, limit),
GET /search?q= (country, language, limit),
GET /topic/{topic} (WORLD, NATION, BUSINESS, TECHNOLOGY,
ENTERTAINMENT, SPORTS, SCIENCE, HEALTH),
GET /source/{source} (bbc, npr, guardian, aljazeera, nytimes),
GET /topics (everything supported, listed), GET /health.

Feeds are cached with a short TTL; on upstream failure the last good
edition is served flagged stale instead of an error.

## Pricing (RapidAPI, hard limits, monthly quotas)

BASIC $0 / 250 per month, PRO $15 / 10,000 (the incumbent charges $25),
ULTRA $40 / 75,000 (vs $50), MEGA $90 / 300,000 (vs $100). Net after
the 25% fee: $11.25 / $30 / $67.50.

## Costs and risks

$0 end to end. Ninth Render service: the keep-warm fleet window settles
at 09:00-11:00 ET (2h x 9 services x 31 days = 558h inside the 750h
workspace cap). Google News RSS is an undocumented but long-stable
public feed; the outlet feeds diversify the source mix so no single
feed disappearing empties the product. Article summaries are the
feeds' own descriptions, cleaned of HTML and labeled as such.
