# RapidAPI Services - Build Status

DEPLOYED LIVE 2026-10-28 (free Render plan, from the public repo
github.com/Yamillionaire/rapidapi-services, commit d3e7bf3):
- Currency: https://stablefx-currency-rates.onrender.com (srv-dbh1vrtg1s2s73ci2pa0)
- Email: https://cleanlist-email-verifier.onrender.com (srv-dbh1vtvf3r2c73atjoig)
- Financials: https://edgar-fundamentals.onrender.com (srv-dbh1vv8ae00c73dl7obg)
Live verification the same day: currency convert returned the 2026-10-28 ECB
rate (100 USD = 89.823 EUR) with warm cache latency 0ms server-side; the email
service loaded 224,300 disposable domains at runtime on Render and rejected
idwager.com while accepting a real Gmail address; financials returned AAPL's
19 annual revenue periods and a correct TSLA summary. Render is API-connected
as custom.render (helper in ~/workspace/custom-connectors/custom.render/bin).
Free-plan caveat: services spin down when idle, so a cold first request takes
about 1-2 seconds; warm requests are milliseconds. NEXT STEP: create the three
RapidAPI provider listings pointing at these base URLs, with pricing from the
specs, each shown to the user as a preview before publishing. RAPIDAPI_PROXY_SECRET
env vars get set on each service once the listings exist.

User directed 2026-10-28: build all three services (Currency, Email, Financials).
All three run on one shared zero-dependency Python scaffold (shared/rapidapi_server.py):
stdlib HTTP server, explicit JSON error objects (never a silent 204 or bare 500),
TTL cache with stale-on-error serving, optional RapidAPI proxy-secret check via
RAPIDAPI_PROXY_SECRET env. Zero dependencies means free-tier hosting anywhere
(Render free account is the planned deploy target) and instant cold starts.

## 1. currency/ - StableFX Currency Rates
Endpoints: /latest, /convert, /historical, /currencies, /health.
Data: Frankfurter (ECB daily reference rates), Fawaz API fallback, last-good cache
served flagged stale instead of a 503. Honest label: daily reference, not trading quotes.
TESTED LIVE 2026-10-28:
- /latest USD: EUR 0.89686, GBP 0.7503 (2026-10-27 ECB day). Cold 1,267ms (upstream-bound).
- Same call warm from cache: 2ms. Comparison listing's latency: 23,769ms at 22% service level.
- /convert 100 USD to EUR = 89.686. Correct.
- /historical 2024-01-15 returns that day's rates.
Pricing (from spec): Basic free 1,000/mo; Pro free 10,000/mo (hook); Ultra $10 (net $7.50);
Mega $20 (net $15). Comparable listing: $10 / $20 / $30.
TERMS VERIFIED 2026-10-28: Frankfurter is open source (MIT) and its rates are
free for commercial use (ECB and central-bank reference data). Fawaz is the
fallback only. Deploy package ready (render.yaml at project root).
REMAINING: deploy to Render from the user's account, create RapidAPI provider
listing (user's account, preview first). Noted upgrade path: Frankfurter v2
covers 160+ currencies from 100+ central banks versus v1's ECB-only set.

## 2. emailcheck/ - CleanList Email Verifier
Endpoint: /check?email= with separately labeled checks: syntax, disposable,
MX/DNS via DNS-over-HTTPS, role account. Mailbox probing deliberately NOT faked:
it ships as a separate labeled mode later.
TESTED LIVE 2026-10-28 (5-case set, then re-tested after fixes, all passing):
- Real Gmail address: valid, low risk, MX found.
- mailinator.com address: rejected as disposable.
- Bad syntax: rejected.
- Non-existent domain: rejected, no MX/A records.
- example.com: rejected after fix - it publishes a null MX (RFC 7505, accepts no mail).
  First pass wrongly accepted it; the hard re-check caught it and the code was fixed.
UPDATE 2026-10-28: the full open disposable list is loaded (FFraud-com list, MIT
license, 224,300 domains in data/disposable_domains.txt, rebuilt upstream every
30 minutes; production refetches daily). Verified live: addresses at idwager.com
and bialode.com, the two domains users of a comparable service publicly complained
were missed, are both REJECTED here; Gmail regression still passes.
REMAINING: accuracy test set publication, deploy, listing.
First production run is planned as the dogfood pass on the user's own email database.

## 3. financials/ - EDGAR Fundamentals
Endpoints: /stock/get-fundamentals, /stock/v2/get-timeseries.
Data: SEC EDGAR company-facts (free, public domain, no key), cached 24h.
TESTED LIVE 2026-10-28:
- AAPL annualTotalRevenues: 19 consecutive annual periods, 2007-2025, zero nulls,
  zero gaps after merging EDGAR's alias tags (filers changed revenue tags over the
  years; merging was required - the first pass had gaps in 2018-2020 and the
  re-check caught it). FY2018 = 265,595,000,000 and FY2020 = 274,515,000,000,
  matching Apple's reported figures exactly. All-periods revenue count: 36.
  Comparable service: series capped at 5, revenues null except the last period.
- TSLA annual revenues: 17 periods, 2009-2025.
- pegRatio returns an explicit explanation object plus a real trailing
  earningsGrowth5yrPct computed from filings (AAPL 7.39%), never a silent null.
FREE ENDPOINTS ADDED 2026-10-28 (user approved free-only launch the same day):
/stock/v2/get-summary serves company name, exchange, SIC industry, fiscal year
end and HQ from EDGAR (AAPL and TSLA verified live), filling the missing
name/exchange gap at $0. /stock/v2/get-recommendations serves
related tickers as SEC SIC industry peers (AAPL returns DELL, OMCL, OSS, OURA,
SCKT; method labeled in the response, not passed off as a popularity feed).
REMAINING (the one real cost decision, deferred by the user until revenue):
quotes/charts need a licensed feed whose
terms allow redistribution (Yahoo data is personal-use only, no commercial route
published). Feed pricing researched 2026-10-28 from the providers' own pages:
Tiingo publishes redistribution pricing on its product pages, $250/mo for
startups ($500 enterprise); its $50/mo Commercial plan is INTERNAL use only and
does not cover resale. Massive (formerly Polygon) marks every self-serve plan
individual use; its Business plan with a commercial license runs about
$2,000/mo. Financial Modeling Prep requires a separate Data Display and
Licensing Agreement (no self-serve price). PLAN: launch fundamentals-only at
$0 (that is where the documented complaints and our proven fix are), and add
quotes only when the API's own subscription revenue covers the license
(breakeven roughly 17 Ultra subs at $15 net or 2 Mega at $217.50 net against a
$250/mo Tiingo startup redistribution tier), so the license is never an
out-of-pocket cost. Then build the quote endpoints and related tickers
(EDGAR industry peers), deploy, listing.

## 8. swifttranslate/ - SwiftTranslate

BUILT AND DEPLOYED 2026-10-29 (queue #8, score 66; user authorized the full
automated queue run in a voice call). Render srv-dbhfe08n74is73d8e020,
https://swifttranslate-72rx.onrender.com (GitHub commit 8e8ed8a0). Endpoints
follow the familiar v2 surface with the same response envelope:
GET /language/translate/v2 (q, target, optional source), /detect, /languages
(107 codes), /health. Engine: Gemini 3.6 Flash (2.5-flash retired for new
users; 3.8-flash too slow). Reliability design answers the 84%
service level and unanswered "API unreachable" complaints seen in the market: explicit JSON
errors always, one engine retry, 24h cache serving stale (flagged) on engine
error. No key yet: translate/detect return an explicit 503
engine_not_configured; nothing is faked.
TESTED 2026-10-29: local no-key suite (health, languages, 503s, 422s with
limit-and-length wording, 5,001-char rejection), proxy gate (401 without
header, /health open), bad-key engine errors as explicit 502s; engine verified
with the production payload through the Gemini connector (Spanish to English
correct, proper names intact, ~4.1s; French detection ~2.6s; two transient
Google 503s observed during testing, hence the retry). Deployed /health live
and reporting the engine as awaiting configuration.
Pricing: BASIC $0/1,000mo; PRO $0/10,000mo (the $9 market tier, free);
ULTRA $9/100,000mo; MEGA $29/500,000mo, hard limits.
REMAINING: user adds GEMINI_API_KEY to this service's Render Environment
(same one-time step as SwiftRewrite), then the Studio listing (PRIVATE),
proxy secret + gate verification, publish, Hub gateway test, and the
Spotlight post (docs/swifttranslate-reliability.md) - all via the parent's
browser tasks. Keep-warm now covers nine services, 09:00-11:00 ET.

## 9. newsbase/ - NewsBase Headlines
Endpoints: /headlines, /search, /topic/{topic}, /source/{source}, /topics, /health.
Data: Google News RSS (editions, search, topic sections) plus direct outlet RSS
(BBC, NPR, The Guardian, Al Jazeera, NYT), $0, no key. Complaint fixes are the
product: feeds are parsed into records and serialized by us (valid JSON by
construction, never raw upstream passthrough), and there is no image proxy -
publisher image URLs are returned directly or the field is omitted.
DEPLOYED 2026-10-29: https://newsbase-headlines.onrender.com
(srv-dbhfe5o473hc739rmad0). TESTED LIVE the same day: 11 live checks plus the
16-case local set, every response strict-JSON-valid (27/27); GB and IN editions
return their own headlines; a BBC story's image is the BBC CDN URL itself and
answers HEAD 200 image/jpeg. Pricing (spec): Basic $0/250mo; Pro $15/10,000mo;
Ultra $40/75,000mo; Mega $90/300,000mo hard. Comparable listing: $25/$50/$100.
REMAINING: Studio listing, proxy gate, publish, Spotlight (parent browser route;
package at listings/newsbase-openapi.json, proof doc docs/newsbase-reliability.md).

## 10. whoisbase/ - WhoisBase
Endpoints: /lookup?domain= (fresh/force optional), /domain/{domain}, /tlds, /health.
Data: live RDAP via the IANA bootstrap (data.iana.org/rdap/dns.json) plus a
port-43 fallback to the registry's own whois server for TLDs with no RDAP
(.at, .rs, .eu, .de, .io, .ch) - $0, no key, the registries' own protocols.
Complaint fixes are the product: a 300-second cache whose state and the
record's age ride on every response, a fresh/force flag that genuinely
bypasses it, structured JSON errors only (never a bare 504), and
unregistered domains answered 200 with registered: false instead of blanks.
DEPLOYED 2026-10-29: https://whoisbase.onrender.com
(srv-dbhl8lbbc2fs73epsfp0; GitHub commits cc715442, 929fd827).
TESTED: local port-43 parser battery 15/15 (canned .at/.eu/.rs records plus
a local fake whois server; the first run caught plural-header and date-format
bugs, fixed and re-verified); local live battery over RDAP (.com/.dev/.pl/
.fi/.org full records, cache + fresh + force behavior, named 422s, gate 401
without the test secret, /health open). Nominet .uk rate-limits the shared
build-sandbox egress IP (429 surfaced as a structured error). Deployed
verification: /health live at 1,203 RDAP TLDs; RDAP records live; PORT-43
VERIFIED LIVE FROM RENDER - nic.at, eurid.eu, rnids.rs (6 nameservers after
the DNS-label parser fix), example.de (DENIC restriction labeled); deployed
cache, fresh and negative-result behavior all matching local results.
Pricing (planned, hard limits): BASIC $0/250mo; PRO $0/10,000mo (the
the market's $10 Pro tier, free); ULTRA $20/100,000mo; MEGA $70/500,000mo.
Comparable listing: $10/$30/$80. Keep-warm now covers ten services, 09:00-11:00 ET
(620h worst month vs the 750 cap).
REMAINING: Studio listing, proxy-secret wiring with gate verification,
publish, Hub gateway test, Spotlight (parent browser route; package at
listings/whoisbase-openapi.json, proof doc docs/whoisbase-freshness.md).

## 11. swiftread/ - SwiftRead (the user's own product)
Endpoints: POST /read-url {url, voice?, rate?} -> audio/mpeg, POST /speak
{text, voice?, rate?} -> audio/mpeg, GET /voices, GET /health.
The user's own idea (2026-10-30 voice call): the "listen to this article"
button as an API. No comparable RapidAPI service offers URL-in article extraction
at all; the fix list was built from public complaints about rival TTS services
(swiftread-fixlist-2026-10-30.md). Extraction is the
CleanExtract stack (SSRF-hardened); speech is the free Microsoft Edge
neural set via edge-tts ($0 marginal). FULL CATALOG since 2026-10-31
(owner directive): 322 voices, 142 locales, 75 languages shipped as
data (swiftread/voices.json from the live catalog list), ordered
most-spoken languages first, then the featured African set, then
alphabetical; /voices filters by language/locale/gender; the
original curated 45 are the featured picks; the splitter covers CJK
full stops and the Hindi danda (Yoruba/Igbo/Hausa do not exist in
the Edge catalog). Paragraph-aware parallel chunking
(1,200 chars, pool 4) with a 0.4s inter-paragraph beat, per-request
billing never per character, direct MP3 return (no expiring URLs),
15,000-char cap with an honest 422, and a hard 85s thread-join
synthesis deadline with skip-and-disclose chunks
(X-SwiftRead-Chunks-Skipped) - the design that came out of launch
night's engine stalls (asyncio timeouts cannot bound a stalled
stream) and the NoAudioReceived mixed-script diagnosis.
DEPLOYED 2026-10-30: https://swiftread.onrender.com
(srv-dbild8lg1s2s73dj3hc0; deploys are API-triggered, auto-deploy did
not fire on push). Spec docs/spec-swiftread.md; listing package
listings/swiftread-openapi.json + listings/swiftread-listing-notes.md
(per-request plan check, binary-handling snippets, voice samples).
TESTED: local battery full (gate, 422s, SSRF, extraction, chunk and
paragraph logic incl. CJK/Hindi splitting, silence segment format,
catalog load 322/142/75 with filters and ordering); live GET battery
(health with build tag and catalog counts, 45 voices on the curated
build, full-catalog count on the current build); live POST successes
on the fix build
(English 8.4s first call and 42.0s, Swahili 67.8s, Mandarin 18.9s,
three-paragraph read with beats 14.5s of audio). STILL OWED when a
clean POST test path exists (the build sandbox's egress proxy began
stalling all POSTs on launch night, proven path-side via instant-422
probes and parallel httpbin stalls): the full-cap 14,906-char load
test and a complete /read-url read; the service self-records timings
in /health recent_requests to finish both. Pricing (hard limits,
per request): BASIC $0/100mo; PRO $5/1,000mo; ULTRA $20/10,000mo;
MEGA $60/50,000mo. Keep-warm now covers eleven services, 09:00-11:00
ET (682h worst month vs the 750 cap, about 68h headroom - tightest
the fleet has run).
REMAINING: Studio listing, proxy-secret wiring with gate
verification, publish, Hub gateway test, Spotlight (parent browser
route; proof doc docs/swiftread-reliability.md).

## 12. driftcheck/ - DriftCheck (the user's own product; no incumbent)
Endpoints: POST /check-image {candidate, reference, expected_text?}
-> drift report; POST /check-video {video, reference, frames?} ->
per-frame report; GET /health.
The user's own idea (2026-10-31 voice call, "proceed" the same call):
the drift gate from his generated-media production, productized.
Send a candidate image or video plus the reference it was supposed
to match; get a drift score and a pass/warn/fail verdict BEFORE the
next regeneration credit is spent. Classical metrics only (Pillow +
numpy, no model downloads): subject-crop dhash, phash (DCT), global
SSIM and color histogram, full-frame and against the best-matching
region of the reference; a foreground bounding-box-share proportion
report with a flag past 20 points of divergence (the emblem-scale
check); OCR of the candidate when a tesseract binary exists on the
host, compared with caller-supplied expected_text. Headline drift =
0.7 x similarity drift + 0.3 x proportion penalty (penalty =
min(100, 2 x largest divergence)); verdict pass <= 50, warn <= 65,
fail above, with proportion/text flags escalating to at least warn.
Video: ffmpeg frame sampling across the full duration, per-frame
drift, worst frames with timestamps, frozen-span detection (dhash
similarity >= 0.97 sustained). DELIBERATE OMISSIONS, stated in
/health: no anatomy check (no lightweight pose estimator deploys on
the free tier; omitted, not faked) and OCR reports unavailable on
this deployment (no tesseract on the host) instead of guessing.
MEASURED IDENTITY LIMIT, disclosed in every /check-image response:
against a multi-panel model sheet a wrong character graded
similarity drift 57.2 vs the right one's 58.6 - v1 cannot verify
identity against collage sheets; against same-class references
(approved comps, start stills) the metrics separate cleanly.
DEPLOYED 2026-10-31: https://driftcheck.onrender.com
(srv-dbj39567bikc73ea2kt0; GitHub commit 12d894b4). First build
failed in 18s: PYTHON_VERSION had to be set at service level via
the API; the set plus a redeploy went live. ffmpeg IS present on
Render's image (deployed /health methods.video), so /check-video
runs deployed.
PROOF TESTS (local battery and deployed reproduction with identical
numbers; raw outputs driftcheck/tests/battery-2026-10-31.json,
write-up docs/driftcheck-reliability.md): (1) the oversized Break
emblem sticker vs Break's model sheet: drift 68.9 FAIL, proportion
flag raised - candidate art fills 50.0% of frame width vs the
sheet's 99.2% coverage, divergence 49.2 width / 36.5 height points
(the four peer emblem stickers measure 17.4-18.6% of frame width);
(2) the approved DJ Riot design vs its model sheet: 42.2 PASS,
divergence 0.3 / 1.9 points; identical pair 0.0; (3) the Rosewood
Chapter 5 motion clip (10.0s) vs its start still: PASS, worst frame
39.4 at 5.5s, mean 29.9, no frozen spans; a synthetic still-loop
clip flags its whole span (0.2s-3.8s) and escalates to WARN.
GATE VERIFIED on the deployed service against its own gated deploy
with a build-time test secret: 401 without the header, 422
missing_parameter with it, 401 with a wrong value, /health open.
The test value was not retained and the API rejects empty-value
clears through the helper, so the origin sits gated under that
unrecorded value until the listing step sets the Studio secret
(wiring and re-verification steps in
listings/driftcheck-listing-notes.md).
INTERNAL GATE (user-directed 2026-10-31): DriftCheck is also the
standing production gate for ALL of the user's generated imagery
and video across every lane; the internal request shapes, default
thresholds, and the Break worked example live in
docs/spec-driftcheck.md ("Internal pipeline use").
Pricing (planned, hard limits, per request): BASIC $0/100mo;
PRO $5/1,000mo; ULTRA $20/10,000mo; MEGA $60/50,000mo. Keep-warm
fleet now twelve services, window re-budgeted to 09:00-10:50 ET
(682h worst month vs the 750h cap).
REMAINING: Studio listing (PRIVATE first), proxy-secret wiring with
the Studio value plus gate re-verification, publish, Hub gateway
test, Spotlight (parent browser route; package at
listings/driftcheck-openapi.json + listings/driftcheck-listing-notes.md,
proof doc docs/driftcheck-reliability.md). SwiftRead (#11) remains
separately queued for its own listing; it is not part of this build.

## 13. xbase/ - XBase (the user's own product; no incumbent)
Endpoints: POST /search {query, max_results? (cap 100), hours_back?
(cap 168)} -> normalized posts; POST /news-scan {preset} -> a
curated preset's posts merged and de-duplicated; GET /health.
The user's own direction (2026-10-31 voice call: "Definitely build
an API" for X news access). Direct scraping violates X's Terms, so
XBase wraps the OFFICIAL X API v2 recent-search endpoint with the
operator's own Bearer token (pay-per-use upstream: $0.005 per post
returned). Normalized post shape: id, text, author (username,
name), created_at, public metrics (likes, reposts, replies,
quotes), post URL, lang. Presets, built for his own two news
properties and their twice-daily checks: "hiphop" (releases, tours,
business, culture), "black-news-us", and "black-news-international"
(the African diaspora: Africa, the Caribbean, the UK, Canada,
Latin America). Engine states are honest by construction and
reported in /health and per response: live (token set), mock
(XBASE_MOCK=1; fixture payloads through the same normalization
code, labeled "engine": "mock" with FIXTURE in the post texts), and
awaiting_token (explicit 503 engine_not_configured).
DEPLOYED 2026-10-31: https://xbase.onrender.com
(srv-dbj4pjmtlv9c73c80aqg; GitHub commit 46be9c38). Stdlib only,
build "true". Create-time env vars did not stick (the known lane
race): XBASE_MOCK and RAPIDAPI_PROXY_SECRET were re-set at service
level via the API and redeployed before verification.
PROOF TESTS (local battery xbase/tests/battery-2026-10-31.json,
13/13; deployed reproduction in mock mode with identical behavior):
/health 200 in both modes; gate 401 without the header, 401 with a
wrong value, 422 missing_parameter with it; /search 200 with
correctly shaped normalized posts; all three /news-scan presets
200, de-duplicated by id (9 fixture returns merge to 3 unique);
unknown preset 422. After the proof, mock was switched off and the
service redeployed into its honest awaiting state: /health reports
awaiting_token, /search and /news-scan answer 503
engine_not_configured through the gate. The build-time test secret
was not retained; the origin sits gated under it until the Studio
step sets the real secret.
PARKED at the token step (decision queue item 11, the RapidAPI
needs-you queue): no X credential exists in any approved store, and
creating the X developer account, accepting its terms, and funding
it are the owner's steps. Publish is parked behind the same step:
the Hub gateway test calls /search, which cannot return live data
until the token lands and one small live proof (about a dozen
posts, about $0.06) passes. The twice-daily scan cron is NOT wired;
it is scheduled only after the API is live and the user confirms.
Pricing (planned, hard limits, per request): BASIC $0/100mo;
PRO $5/1,000mo; ULTRA $20/10,000mo; MEGA $60/50,000mo. Keep-warm
fleet now thirteen services, window re-budgeted to 09:00-10:40 ET
(671h worst month vs the 750h cap). Listing package ready:
listings/xbase-openapi.json + listings/xbase-listing-notes.md;
spec docs/spec-xbase.md; proof doc docs/xbase-reliability.md.

## 14. factbase/ - FactBase (the user's own product; no incumbent)
Endpoints: POST /check-text {text, max_claims? (default 5, cap
10)} -> the checkable claims in the text, each verified; POST
/check-claim {claim} -> one claim verified; POST /check-audio
(multipart audio) -> transcript plus the same per-claim results;
GET /health. The user's own direction (2026-10-31 voice call: a
fact checker API for anything somebody says, spoken or written;
this build covers both). Each result carries the claim, a verdict
(supported / refuted / mixed / unverified), a confidence note
computed from the evidence composition, a short explanation, and
the evidence used (source title, URL, snippet). Honest by
construction: no retrievable evidence means "unverified", never
a guess, and a verdict with no source cannot be produced.
Engines: the owner's Gemini API (gemini-3.6-flash primary,
gemini-3.1-flash-lite fallback on the primary's 429, the quota
buckets being per-model), Gemini audio transcription for
speech, keyless evidence retrieval (paced DuckDuckGo with
retries and Lite/Bing fallbacks, plus Wikipedia; published
fact-checks first), and an optional Google Fact Check Tools API
layer when a key is configured for it.
DEPLOYED 2026-10-31: https://factbase.onrender.com
(srv-dbj5slfb9u1s73d4kntg; GitHub commit f0fd127f; live deploy
dep-dbj67putlv9c73cbhprg). Stdlib only, build "true", start
"python factbase/app.py".
PROOF TESTS (local battery factbase/tests/battery-2026-10-31.json,
15/15, run with Gemini calls routed through the owner's connected
Gemini API via a local test bridge; the deployed service calls
the same endpoint directly once the key is set): gate 401
without and with a wrong secret; awaiting mode answers an
explicit 503 engine_not_configured; the Eiffel Tower claim
supported, the Great Wall visibility claim refuted, the Amazon
oxygen claim refuted, an obscure 1974 claim honestly unverified,
a two-statement Obama text split into supported and refuted
claims, opinion-only text returns zero claims, and both audio
proofs (a synthesized claim clip and a real JFK clip) transcribe
and check correctly. Deployed battery
(factbase/tests/battery-deployed-2026-10-31.json): /health 200
in the honest awaiting_key state; the three data endpoints
answer 503 engine_not_configured.
PARKED at the key step (decision queue item 11): the owner adds
GEMINI_API_KEY to the Render service himself (the connector
credential cannot be extracted into hosting). Publish is parked
behind it by the lane's rule: the Hub gateway test must pass
with real responses. One caveat on record: the build-time test
proxy secret could not be set because the Render env-var API
route timed out repeatedly at build time, so the origin passes
the gate until the finish step sets the real secret (harmless
while the endpoints can only answer 503; the dashboard is the
fallback route). On his word the finish runs unattended:
redeploy, deployed real-claims battery, Studio listing,
proxy-secret wiring, publish, gateway test, Spotlight. Pricing
(planned, hard limits, per request): BASIC $0/100mo; PRO
$5/1,000mo; ULTRA $20/10,000mo; MEGA $60/50,000mo. Keep-warm
fleet now fourteen services, window re-budgeted to
09:00-10:30 ET (651h worst month vs the 750h cap). Listing
package ready: listings/factbase-openapi.json +
listings/factbase-listing-notes.md; spec docs/spec-factbase.md;
proof doc docs/factbase-reliability.md.

## 15. designbase/ - DesignBase (the user's own product; no incumbent)
Endpoints: POST /palette {brief, count? (default 3, cap 5)} ->
structured palettes; POST /design-brief {product, audience,
vibe} -> structured design brief; POST /image-prompt {subject,
style, era?, product?} -> a production-ready image-generation
prompt; POST /critique (multipart image) -> a scored critique;
GET /health. The user's own direction (2026-10-31 voice call:
"Also, can we create a creative design API?"). Scope is design
INTELLIGENCE, not image generation: no endpoint returns an
image. The honesty split is the product: hex values are
validated in code (invalid values dropped and the drop count
reported, never repaired), WCAG contrast ratios are computed in
code, /image-prompt is assembled entirely in code from a written
prompt-grammar table (subject, composition, lighting, era lock,
negative constraints - the same discipline as the user's merch
and character prompt work) and needs no engine, and critique
scores are validated/clamped in code and labeled as model
judgments. Engines: the owner's Gemini API (gemini-3.6-flash
primary, gemini-3.1-flash-lite fallback; one extension over
FactBase, made after this build's first battery met a persistent
primary 503 on the critique call: a persistent 500/503 now also
falls back instead of failing the call).
DEPLOYED 2026-10-31: https://designbase.onrender.com
(srv-dbj6q967bikc73ej2kq0; GitHub commit 30519fc0; final live
deploy dep-dbj7097b9u1s73d7bef0). Stdlib only, build "true",
start "python designbase/app.py".
PROOF TESTS (local battery designbase/tests/battery-2026-10-31.json,
16/16 with Gemini calls routed through the owner's connected
Gemini API via a local test bridge): gate 401 without and with a
wrong secret; awaiting mode answers an explicit 503
engine_not_configured on the three engine endpoints while
/image-prompt answers 200 (code-assembled, as /health promises);
the merch-tee palette brief returned 2 valid palettes with
computed contrast blocks (the battery independently recomputed
white-on-black = 21.0); the poster design brief returned the
full structure (5 dos, 5 donts); the era-locked image prompt
carried the era lock, product framing and anachronism negatives;
the critique of the real DJ Riot hoodie-back design (1254x1254
PNG) scored 7.8 overall with four grounded dimension notes and
4 specific fixes, image format/dimensions read from the header
in code; invalid inputs return named 422s. Deployed battery
(designbase/tests/battery-deployed-2026-10-31.json, 7/7):
/health 200 awaiting_key; gate 401 without and with a wrong
value; through the gate the three engine endpoints answer 503
engine_not_configured and /image-prompt answers 200. The
build-time test secret was then rotated to an unrecorded value
and re-verified (old value 401, no header 401, /health open), so
the origin sits gated under that value until the Studio step
sets the real secret (the env-var API route worked for this
build, unlike FactBase's build day).
PARKED at the key step (decision queue item 11): the owner adds
GEMINI_API_KEY to the Render service himself (the connector
credential cannot be extracted into hosting). Publish is parked
behind it by the lane's rule: the Hub gateway test must pass
with real responses on the engine endpoints. On his word the
finish runs unattended: redeploy, deployed proof battery with
real briefs, Studio listing, proxy-secret wiring, publish,
gateway test, Spotlight. Pricing (planned, hard limits, per
request): BASIC $0/100mo; PRO $5/1,000mo; ULTRA $20/10,000mo;
MEGA $60/50,000mo. Keep-warm fleet now fifteen services, window
re-budgeted to 09:00-10:25 ET (659h worst month vs the 750h
cap). Listing package ready: listings/designbase-openapi.json +
listings/designbase-listing-notes.md; spec
docs/spec-designbase.md; proof doc docs/designbase-reliability.md.

## 16. actorbase/ - ActorBase (the user's own product; no incumbent)
Endpoints: POST /perform {text, emotion?, intensity? (1-5),
voice?, persona?} -> the line performed as acted speech (MP3
base64) with the delivery used, the segment-by-segment plan
and an SSML-style score; POST /table-read {lines[], cast{}} ->
a whole scene performed with one distinct voice per speaker,
stitched into one MP3 with a measured per-line timing map;
POST /character {description, name?, play_context?} -> the
actor's build (objective, super-objective, obstacles, tactics
as action verbs, backstory beats, given circumstances, voice
and physicality notes); POST /three-reads {line, context?} ->
three genuinely different performed reads (different tactic
and subtext each); POST /scene-notes {scene_text} -> beats,
turns, subtext, power shifts, per character; GET /health.
The user's own direction (2026-10-31 voice call: an actor API,
good for drama writing and able to do all forms of acting).
Delivery is computed in code from a fixed emotion x intensity
table (ten emotions, per-point steps, shipped in the spec);
segmentation and emphasis (*marked* spans) are planned in
code; durations are measured by an in-code MP3 frame parser,
never estimated. Personas are generic craft archetypes
(ingenue, villain, matriarch, trickster...) mapped to stock
voices - no real actor is imitated. Engines: performance on
the SwiftRead synthesis path (Edge neural voices via edge-tts,
322-voice catalog, zero marginal cost, NO key - /perform and
/table-read work in the awaiting state); reasoning on the
owner's Gemini API (gemini-3.6-flash primary,
gemini-3.1-flash-lite fallback) for character builds, scene
analysis, three-reads tactics and direction interpretation,
every response shape-validated in code.
DEPLOYED 2026-10-31: https://actorbase.onrender.com
(srv-dbj7440ae00c73dd3es0; GitHub commits d389ebbb +
7d7a2623; live deploy dep-dbj7atou01pc73elkulg). Build
"pip install -r actorbase/requirements.txt", start
"python actorbase/app.py".
PROOF TESTS: local battery (actorbase/tests/
battery-2026-10-31.json, 13/18 - every non-synthesis check
passed, including the reasoning endpoints against the real
Gemini engine through the test bridge: a full Rosa Delgado
character build with verb tactics, scene notes with 4 beats
and 3 power shifts; the 5 failures are the synthesis checks,
all 502 synthesis_failed because the build sandbox's egress
stalls the speech websocket, the SwiftRead/DriftCheck split);
deployed battery (battery-deployed-2026-10-31.json, 10/10):
gate 401s, the honest 503s, and REAL performed audio - the
grief line at 8.18s with its table row and emphasis realized,
a 3-line table read in 2 persona voices at 10.70s with an
ordered timing map, durations cross-checked with ffprobe and
non-silence with volumedetect; reasoning supplement
(proof-reasoning-halves-2026-10-31.json, 2/2): three reads of
"I never loved you." with distinct tactics (to repel /
to protect / to convince) and a directed line interpreted to
anger. One bug found by the first deployed run and fixed:
a word-less beat (lone sentence punctuation after an
emphasis span) is unspeakable and failed the performance;
the planner now merges word-less beats into the adjacent
beat (commit 7d7a2623).
PARKED at the key step (decision queue item 11): the owner
adds GEMINI_API_KEY to the Render service himself (the
connector credential cannot be extracted into hosting).
Publish is parked behind it by the lane's rule: the gateway
test must pass with real responses on the reasoning
endpoints. GATE STATE: the build-time test secret was set
for the deployed battery, then rotated to an unrecorded
value and re-verified (401 without, 401 with the old value,
/health open), so the origin sits gated until the Studio
step sets the real secret. On his word the finish runs
unattended: redeploy, deployed proof battery with real
scenes, Studio listing, proxy-secret wiring, publish,
gateway test, Spotlight. Pricing (planned, hard limits, per
request): BASIC $0/100mo; PRO $5/1,000mo; ULTRA $20/10,000mo;
MEGA $60/50,000mo. Keep-warm fleet now sixteen services,
window re-budgeted to 09:00-10:20 ET (661h worst month vs
the 750h cap). Listing package ready:
listings/actorbase-openapi.json +
listings/actorbase-listing-notes.md; spec
docs/spec-actorbase.md; proof doc
docs/actorbase-reliability.md.

## Sequence
Currency deploy-ready first (done at prototype level), Email second, Financials
third once the quote feed is chosen. Nothing is published until the user approves
each listing preview. PayPal payout linking on RapidAPI is the user's own tap.

## wordbase/ - WordBase Dictionary
Built 2026-10-29 (Spec G, docs/spec-wordsapi.md). Endpoints follow the
established dictionary surface: /words/{word} full record, per-relation endpoints (definitions,
synonyms, antonyms, examples, typeOf, hasTypes, partOf, hasParts, memberOf,
hasMembers, substanceOf, hasSubstances, similarTo, also, derivation,
pertainsTo, entails, cause), /pronunciation, /syllables, /frequency,
/rhymes, /words search, /health. Data: WordNet 3.1 + CMUdict + FrequencyWords
en_50k, all openly licensed, all downloaded at boot (WordNet tarball 16MB,
too large for the snapshot route). Synsets parse on demand from an offset
index (boot RSS about 151MB measured locally).
TESTED LOCALLY 2026-10-29 (all passing): health reports 147,478 lemmas,
126,052 pronunciations, 50,000 frequency words. serendipity returns the full
record (definition, typeOf, derivation, 5 syllables, IPA, zipf 2.54); run
returns 57 senses across noun and verb; dog typeOf, wheel partOf, car
hasParts all correct; cat rhymes derived from CMU; geese resolves to goose
and running to its base forms via the exception lists; unknown words return
a clean documented 404 JSON error; bank (18 senses) answers in about 9ms.
Pricing (planned, hard limits): BASIC $0/1,000mo, PRO $0/10,000mo (hook vs
the $10 market tier free), ULTRA $39/300,000mo (market $49), MEGA $79/1,000,000mo (market $89),
or the platform maximum at each price where RapidAPI caps lower.
Keep-warm final fleet state: nine services, window 09:00-11:00 ET
(2h x 9 x 31 = 558h worst month vs the 750 cap).
DEPLOYED 2026-10-29: GitHub commit a18d1c7f; Render service
wordbase-dictionary (srv-dbhfdb6c6qcc73f9geh0),
https://wordbase-dictionary.onrender.com, deploy live. Live test battery
matches the local results (health 147,478 lemmas; serendipity full
record; run 57 senses; clean 404s; search; morphology). The user
authorized the full launch run for this build on 2026-10-29 (publish
gate lifted): the Studio listing (PRIVATE first), proxy-secret wiring
with gate verification, publish, Hub gateway test, and Spotlight post
from docs/wordbase-accuracy.md remain, run via the parent's browser
tasks. Mark PUBLISHED LIVE in the registry once the gateway test
returns 200.
MULTILINGUAL v2 (2026-10-31): WordBase now serves 26 languages - the
v1 English engine plus 25 languages selected with ?lang=<code> on the
same endpoints (ISO 639-1/639-3 and English names accepted; unknown
codes return 400 with the supported list), and a /languages endpoint.
Sources: Open Multilingual Wordnet 1.4 (19 languages over the 20,000
entry quality bar, English glosses and translations via an auxiliary
WordNet 3.0 load, own-language definitions/examples where the wordnet
carries them) and FreeDict dictd dictionaries (German, Russian,
Hungarian, Esperanto as new languages; Arabic and Greek lifted over
the bar merged with OMW; real IPA for those six languages). 1,695,718
non-English entries in a SQLite index built at first boot (cold boot
about 100 seconds locally, build peak RSS 335MB, steady state
191MB); English responses without a lang parameter are byte-for-byte
v1 (golden-tested). Local battery 54/54 (wordbase/tests/
battery-local-2026-10-31.json). Honest ceiling from the surveyed
sources: 33 languages (Kaikki.org counts verified for Korean,
Turkish, Vietnamese, Hindi, Czech, Ukrainian, Swedish; the raw
Kaikki files need an offline compaction before they fit the boot
pattern). Full survey in docs/spec-wordsapi.md.
