# Candidate Registry

Every candidate the pipeline has scored, with status. Scores follow the
rubric in `PIPELINE.md`. Full evidence for waves 1-2 lives in the report at
`~/workspace/goals/monetize-my-instagrams-and-facebook/files/rapidapi-competitor-targets-2026-10-28.md`.

## LIVE (built, deployed, published 2026-10-28)

| Candidate | Product | Subs | Rating | Score at pick |
|---|---|---|---|---|
| Yahu Financials (58,328) | EDGAR Fundamentals | 58,328 | 2/5 | 88 |
| Currency Exchange (22,987) | StableFX Currency Rates | 22,987 | 3/5 | 90 |
| E-mail Check (5,540) | CleanList Email Verifier | 5,540 | 4/5 | 74 |

## QUEUED (scored, awaiting the user's build tap)

| # | Candidate | Subs | Rating | Pricing | Undercut plan | Score | Notes |
|---|---|---|---|---|---|---|---|
| 4 | GeoDB Cities (wirefreethought) | 50,222 | 3/5 (60) | $20/$40/$80 | Basic free x2 quota; $10/$30/$70 | 86 | WAVE 3, live-verified 2026-10-28. PUBLISHED LIVE 2026-10-28 as GeoBase Cities: https://rapidapi.com/YamilLittle/api/geobase-cities (API ID api_9af674f9-3086-4269-b6b8-347582f52296, Render srv-dbh7o66c6qcc73b6k3fg). Plans: BASIC $0 2,000/day, PRO $10 27,777/day, ULTRA $30 49,999/day, MEGA $70 94,443/day, all hard (RapidAPI caps quotas per price; prices kept, quotas at platform max). Gateway-verified (Rome search 200 through the Hub), Spotlight "The cities other APIs lose are here" live on the Overview. |
| 5 | Article Extractor and Summarizer (restyler) | 11,784 | 3/5 | $15/$95/$195 | $5/$85/$185 | 82 | PUBLISHED LIVE 2026-10-28 as CleanExtract: https://rapidapi.com/YamilLittle/api/cleanextract (API ID api_47083d92-7a84-4272-bb6a-712449631a9b, Render srv-dbh8kp6c6qcc73em76sg). Stdlib extraction + extractive summarizer on-server (no Gemini dependency; summaries honestly labeled extractive), SSRF-hardened. Plans: BASIC $0/250mo, PRO $5/5,000mo, ULTRA $85/50,000mo, MEGA $185/250,000mo hard. Gateway-verified through the Hub (Wikipedia extraction 200, 9,347 words); Spotlight "Extraction that answers, with the error, instead of a bare 503" live on the Overview. |
| 6 | Paraphrasing / Rewriter (NeuralWriter) | 5,632 | 3/5 | Ultra $19.99, Mega $34.99 | $9.99/$24.99 | 68 | BUILT AND LISTED 2026-10-28 as SwiftRewrite (API ID api_01c1558f-60b3-465c-b6b5-e164a1fe6e7f, Render srv-dbh99i67bikc73dv5lm0), PRIVATE. Plans: BASIC $0/250mo, PRO $3.99/3,500mo, ULTRA $9.99/25,000mo, MEGA $24.99/50,000mo hard. Proxy gate verified. KEY GATE CLEARED 2026-10-29: user added GEMINI_API_KEY in the Render dashboard; model set to gemini-3.6-flash (2.5-flash retired for new users, 3.8-flash too slow) in env and code (commit 002e4d20); AI engine verified end to end through the proxy gate (engine "gemini", names preserved). PUBLISHED LIVE 2026-10-29 on his tap ("Publish it" in the voice call). Hub https://rapidapi.com/YamilLittle/api/swiftrewrite. Gateway test through RapidAPI: 200, engine gemini, names preserved (cold start 12.3s at 3 AM ET). Spotlight posting at launch from docs/swiftrewrite-speed.md. Launch baseline in the watch state file. |
| 7 | WordsAPI (dpventures) | 1,561 | 2/5 (53) | $10/$49/$89 | Pro FREE; $39/$79 | 66 | WAVE 3, live-verified. Valid keys get 403s; Discussions abandoned (spam sitting unmoderated). BUILT 2026-10-29 as WordBase Dictionary (wordbase/app.py, spec docs/spec-wordsapi.md, Spotlight doc docs/wordbase-accuracy.md ready, not posted). WordNet 3.1 + CMUdict + FrequencyWords, all downloaded at boot (tarball too large for the snapshot route); 147,478 lemmas. Local test set all passing (serendipity full record, run 57 senses, geese -> goose, clean documented 404s, search filters). Plans: BASIC $0/1,000mo, PRO $0/10,000mo, ULTRA $39/300,000mo, MEGA $79/1,000,000mo hard (or platform max at price). Keep-warm final fleet state: nine services, window 09:00-11:00 ET (558h worst month). DEPLOYED 2026-10-29: GitHub commit a18d1c7f, Render srv-dbhfdb6c6qcc73f9geh0, https://wordbase-dictionary.onrender.com, deploy live; live test battery all passing (health 147,478 lemmas; serendipity full record; run 57 senses; documented 404s; search; geese -> goose). PUBLISH AUTHORIZED by the user 2026-10-29 (full-run voice authorization; the earlier per-build tap gate is lifted for this build). Remaining launch steps, run via the parent's browser tasks: Studio listing (PRIVATE first), proxy-secret wiring with gate verification (401/200), publish public, Hub gateway test, Spotlight post from docs/wordbase-accuracy.md via its GitHub blob URL. PUBLISHED LIVE 2026-10-29: https://rapidapi.com/YamilLittle/api/wordbase-dictionary (Studio API ID api_318c4e4a-2979-49cd-8e9f-91f2d04046f9). Listing saved exactly (19 endpoints; plans BASIC $0/1,000mo, PRO $0/10,000mo, ULTRA $39/300,000mo, MEGA $79/1,000,000mo hard, no platform caps hit). Proxy gate verified at the service (401 without header, 200 with, /health open). Gateway test through the Hub: 200 (1,446 ms), serendipity full record (results array, syllables 5, IPA pronunciation, zipf 2.54). Spotlight "Your API key was never broken" live on the Overview. Launch baseline in the watch state file amended with the gateway result. Note: the Hub plans carousel also shows a leftover "$0.00 BASIC Deprecated" card from project creation (same artifact as NewsBase); left unchanged at launch. |
| 8 | Google Translate (Hark Translate) | 5,975 | 4/5 (41 votes) | $9/$19/$39 | Ultra $9, Mega $29 | 66 | Fresh "API unreachable" complaint, unanswered. Service level 84%. BUILT AND DEPLOYED 2026-10-29 as SwiftTranslate (swifttranslate/app.py, spec docs/spec-swifttranslate.md, Spotlight doc docs/swifttranslate-reliability.md ready, not posted). Render srv-dbhfe08n74is73d8e020, https://swifttranslate-72rx.onrender.com (Render suffixed the subdomain; the bare name was taken globally). Gemini 3.6 Flash wrapper on the incumbent's v2 surface (/language/translate/v2, /detect, /languages; same response envelope), 107 languages, 24h cache with stale-on-error, one engine retry, explicit JSON errors. Engine verified pre-launch through the connector with the production payload (es to en correct with proper names intact ~4.1s, fr detect ~2.6s; two transient Google 503s observed, hence the retry). Plans: BASIC $0/1,000mo, PRO $0/10,000mo (their $9 Pro free), ULTRA $9/100,000mo, MEGA $29/500,000mo hard. PARKED 2026-10-29 at the key step per the user's rule update (SKIPPED AT THE KEY STEP; explicitly not a blocker, the queue moves on): (1) GEMINI_API_KEY must be added to the swifttranslate Render env by the user, a one-minute step (same as SwiftRewrite; deployed /health re-verified reporting "awaiting key", translate/detect return an explicit 503 until then); (2) the Studio listing (PRIVATE first; full listing content ready in listings/swifttranslate-openapi.json), proxy-secret wiring with gate verification, publish, Hub gateway test (engine "gemini"), and Spotlight post from docs/swifttranslate-reliability.md (description condensed to 228 chars per the 280-char platform limit) remain, run via the parent's browser tasks. PUBLISHED LIVE 2026-10-29: https://rapidapi.com/YamilLittle/api/swifttranslate1 (Studio API ID api_6871988a-cfd2-4848-91bb-b9f1e6a629f3; the plain "swifttranslate" slug was taken, hence the 1). Listing saved exactly (3 endpoints on the v2 paths plus health; plans BASIC $0/1,000mo, PRO $0/10,000mo, ULTRA $9/100,000mo, MEGA $29/500,000mo hard). Proxy gate verified at the service (unauthorized JSON without header, /health open reporting engine "gemini"). Gateway test through the Hub: first attempt 502 at 34.3s (cold start), retry 200 in 28.8s, es to en correct, engine "gemini", model gemini-3.6-flash. Spotlight ""API unreachable" is not a status: the translation reliability fix" live on the Overview. Hub plans carousel shows the same leftover "$0.00 BASIC Deprecated" card as WordBase and NewsBase; left unchanged. |
| 9 | Google News (BFD) | 7,316 | 3/5 | $25/$50/$100 | $15/$40/$90 | 64 | BUILT AND DEPLOYED 2026-10-29 as NewsBase Headlines (Render srv-dbhfe5o473hc739rmad0, https://newsbase-headlines.onrender.com). RSS build (Google News RSS editions/search/topics + BBC, NPR, Guardian, Al Jazeera, NYT feeds): responses serialized from parsed records (valid JSON by construction; 27/27 strict-parse checks across local and live suites), NO image proxy (publisher image URLs returned directly; live BBC CDN image verified 200 image/jpeg). Endpoints: /headlines, /search, /topic/{topic}, /source/{source}, /topics, /health. Plans to save in Studio: BASIC $0/250mo, PRO $15/10,000mo, ULTRA $40/75,000mo, MEGA $90/300,000mo hard. Listing package ready: listings/newsbase-openapi.json; Spotlight proof doc docs/newsbase-reliability.md ("The news API whose JSON actually parses"). PUBLISHED LIVE 2026-10-29: https://rapidapi.com/YamilLittle/api/newsbase-headlines (Studio API ID api_c7c0fe01-cd4b-4e9b-9efe-17d9f91c52e3). Listing saved exactly (6 endpoints; plans BASIC $0/250mo, PRO $15/10,000mo, ULTRA $40/75,000mo, MEGA $90/300,000mo hard, no platform caps hit). Proxy gate verified at the service (401 without header, 200 with, /health open). Gateway test through the Hub: 200 (1,310 ms), strict-valid JSON, 20 articles. Spotlight "The news API whose JSON actually parses" live on the Overview. Launch baseline appended to the watch state file. Note: the Hub plans carousel also shows a leftover "$0.00 BASIC Deprecated" card from project creation; left unchanged at launch. |

| 10 | Whois Lookup (Zozor54) | 3,811 | 3/5 (16) | $10/$30/$80 | Pro FREE; $20/$70 | 63 | WAVE 4, live-verified 2026-10-29. Service level 99%, latency 1,371ms. 29 Discussion threads, every one listed Unanswered. Themes: stale cached results (users report records wrong for hours despite the force flag), timeouts and 504s, missing/blank/null data for many TLDs (.dev, .at, .rs, .pl, .eu, .fi and more), double-subscription billing. BUILT AND DEPLOYED 2026-10-29 as WhoisBase (whoisbase/app.py, spec docs/spec-whoisbase.md, Spotlight doc docs/whoisbase-freshness.md ready, not posted; listing package listings/whoisbase-openapi.json). Render srv-dbhl8lbbc2fs73epsfp0, https://whoisbase.onrender.com (the bare product name was available on both Render and the subdomain). Build state at handoff: BUILT AND DEPLOYED, awaiting the parent's Studio lane for listing, proxy-secret wiring, publish, gateway test, and Spotlight. Design answers the complaints in order: RDAP via the IANA bootstrap (1,203 TLDs live at deploy), port-43 fallback for the no-RDAP TLDs (whois.nic.at, whois.eu, whois.rnids.rs, whois.denic.de, whois.identity.digital, whois.nic.ch), 300s cache with a cache block on every response (cached flag, age_seconds, TTL) and fresh/force that genuinely bypasses, structured JSON errors only, unregistered domains return 200 registered:false. Local battery: port-43 parser 15/15 against canned .at/.eu/.rs records plus a local fake server; live RDAP records for .com/.dev/.pl/.fi/.org; Nominet .uk rate-limits the shared build-sandbox egress (429 surfaced as a structured error; succeeds when spaced). DEPLOYED VERIFICATION 2026-10-29: /health live (1,203 RDAP TLDs); RDAP records for google.com, web.dev, allegro.pl, finnair.fi; PORT-43 VERIFIED LIVE FROM RENDER (the sandbox blocks it, Render does not): nic.at (created 2000-08-25, 5 nameservers), eurid.eu (registrar EURid vzw, 6 nameservers), rnids.rs (registrar RNIDS, 6 nameservers after a parser fix for RNIDS's DNS-label format, commit 929fd827), example.de (status connect, DENIC restriction labeled in the response); deployed cache behavior verified (repeat call cached:true, fresh=true refetches, unregistered .com registered:false at the 60s negative TTL). Plans to save in Studio: BASIC $0/250mo, PRO $0/10,000mo (the incumbent's $10 Pro made free), ULTRA $20/100,000mo, MEGA $70/500,000mo hard (or platform maximum quotas at those prices). Keep-warm fleet is now ten services, window held at 09:00-11:00 ET (2h x 10 x 31 = 620h worst month vs the 750h cap). Known polish items, not launch blockers: .at registrant/registrar come back as registry handles (nic.at publishes handle blocks); .eu records carry no dates because EURid's port-43 record has none to give. |
PUBLISHED LIVE 2026-10-29: https://rapidapi.com/YamilLittle/api/whoisbase (Studio API ID api_d929ebc1-41a9-4113-8fab-59602753880f, Render srv-dbhl8lbbc2fs73epsfp0). Listing saved exactly (4 endpoints; plans BASIC $0/250mo, PRO $0/10,000mo, ULTRA $20/100,000mo, MEGA $70/500,000mo hard). Proxy gate verified at the service (401 without header, /health open). Gateway test through the Hub: 200 (33.1s playground round trip, service latency 213 ms), google.com full RDAP record with cache block (cached false, age 0, ttl 300). Spotlight "Fresh records, and a force flag that actually forces" live on the Overview.
| 11 | (none - the user's own product) | n/a | n/a | n/a | $0/$5/$20/$60 per request | n/a | USER-ORIGINATED 2026-10-30 (voice call): SwiftRead, the "listen to this article" button as an API. No incumbent offers URL-in article extraction on RapidAPI; the fix list (swiftread-fixlist-2026-10-30.md) was mined from the TTS rivals' complaints (VoiceRSS, Large Text to Speech) and applied BEFORE listing: parallel chunk synthesis, paragraph pauses, per-request billing, binary-response doc snippets, voice samples prepared. FULL CATALOG 2026-10-31 (owner directive, superseding the curated roster): the entire Edge catalog shipped as data (swiftread/voices.json from the live list: 322 voices, 142 locales, 75 languages), any catalog id validates, /voices filters by language/locale/gender, presentation ordered most-spoken languages first (English, Chinese, Hindi, Spanish, French, Arabic, Bangla, Portuguese, Russian, Japanese, German, Indonesian, Urdu) then the featured African set (Swahili, Amharic, Somali, Zulu, Afrikaans + African English variants) then alphabetical; the curated 45 are the featured picks; sentence splitting extended to CJK full stops and the Hindi danda (Yoruba/Igbo/Hausa absent from the Edge catalog). BUILT AND DEPLOYED 2026-10-30 as SwiftRead (swiftread/app.py, spec docs/spec-swiftread.md, Spotlight proof doc docs/swiftread-reliability.md, listing package listings/swiftread-openapi.json + listings/swiftread-listing-notes.md). Render srv-dbild8lg1s2s73dj3hc0, https://swiftread.onrender.com (deploys API-triggered; auto-deploy did not fire on push). Design: CleanExtract extraction stack + free Edge neural voices via edge-tts ($0 marginal), 15,000-char cap with honest 422s, paragraph-aware parallel chunks (1,200 chars, pool 4, 0.4s inter-paragraph beat), hard 85s thread-join synthesis deadline with skip-and-disclose (X-SwiftRead-Chunks-Skipped) - forged on launch night against engine stream stalls that ignore asyncio cancellation, plus the NoAudioReceived mixed-script diagnosis. VERIFIED: full local battery; live GET battery (health build tag, 45 voices); live POST 200s (English, Swahili sw-KE, Mandarin zh-CN, three-paragraph read with beats). STILL OWED via a clean POST path (build-sandbox egress proxy stalls POSTs since launch night, proven path-side): full-cap 14,906-char load test and a complete /read-url read; service self-records timings in /health recent_requests. Plans to save in Studio (PER REQUEST, hard): BASIC $0/100mo, PRO $5/1,000mo, ULTRA $20/10,000mo, MEGA $60/50,000mo. Keep-warm fleet now eleven services, window 09:00-11:00 ET (682h worst month vs the 750h cap). Remaining: Studio listing, proxy-secret wiring with gate verification, publish, Hub gateway test, Spotlight (parent browser route). |

## WATCHLIST

| Candidate | Subs | Why held |
|---|---|---|
| Alpha Vantage | 33,812 | Complaints are two 7-year-old forex threads; provider is the brand owner; overlaps EDGAR Fundamentals. |
| Weather (Api Dojo weather338) | 2,725 | Complaints are documentation/support only; 4/5 on 4 votes. |
| Twinword Sentiment Analysis | 1,900 | WAVE 3, live-verified: 5/5 rating rests on a single vote, so pain evidence is the two verified complaint themes only (bogus 711 quota errors, free-tier blocking). Pricing grid known from the provider's site, not yet read on RapidAPI itself. Score ~52. |
| Domains API (layered) | 1,327 | WAVE 4, live-verified 2026-10-29 (Overview only): 4/5 (8 votes), 91% service level, 821ms latency; pricing from the Overview: $0/$5/$10/$30 (full grid not read). Discussions NOT read, so pain is unverified; also overlaps the Whois Lookup queue pick (#10) in the same whois/domain space. Read Discussions before any scoring. |

## EXCLUDED (with reason)

| Candidate | Reason |
|---|---|
| WeatherAPI.com (52,194) | $0 pricing on RapidAPI: nothing to undercut. |
| CoinGecko (11,580) | Free tier only on RapidAPI. |
| Yahoo Finance by enclout (1,163) | Free tier only; Yahoo resale terms risk. |
| NFL API Data (3,450) | Sports data licensing. |
| Binance (Glavier), Telize, Jobs Scanner, Real Time Email Verification, ViewStats, real-estate scrapers | Below subscriber floor, no complaint pattern, or no free legal data route. |
| Flight data, entire category (wave 3) | OpenSky requires a paid license for commercial use; AeroDataBox terms ban resale on every plan; ADSBexchange is non-commercial only. No $0 terms-clean route exists. |
| Phone validation, entire category (wave 3) | The HLR trap: the paid value is live carrier status; free libphonenumber covers format/region/allocation only. A clone would be a partial match by construction. |
| TMDB-based movie APIs (wave 3) | TMDB commercial use needs its $149/mo key. IMDb datasets are non-commercial; OMDb data is CC BY-NC. |
| PDF Generator (domware.apps) | Live-verified at 2 subscribers. Below floor. |
| URL To Screenshot (APILight) | Live-verified at 103 subscribers despite a real 11.9s latency wedge. Below floor. |
| Custom QR Code with Logo (qrcode-monkey) | Live-verified at 294 subscribers; verified 500-error complaints. Below floor. |
| Dad Jokes (API-Ninjas), Numbers API, barcode.monster, Screenshotlayer, Free IP Geolocation | Free tier only on RapidAPI. |
| Calendarific (ryancli) | Live-verified 2026-10-29 (wave 4): 550 subscribers, below the 1,000 floor. Not rated (2 votes). Pricing has paid tiers (Basic $0 / 500,000 per month; Pro $10 unlimited; Ultra $30 unlimited), but Discussions hold exactly 1 thread ("API support", 7 years old, unanswered, body not read), so the 2-complaint-theme criterion also fails. |
| Abstract IP geolocation (karmadele) | Live-verified 2026-10-29 (wave 4): 131 subscribers, below floor; free-only on the Overview ($0 BASIC shown), not rated (0 votes), 100% service level, 251ms latency. |
| public-holidays7 (hefesto-technologies) | Lead not found 2026-10-29 (wave 4): direct listing URL returns API not found; hub searches for the name and provider returned no such listing. The community-post reference that suggested it appears to point at a removed or renamed listing. |
| Open Weather Map (cedricnoguera) | Live-verified 2026-10-29 (wave 4): 7,536 subscribers, 2/5 (16 votes), 100% service level, 335ms - but only a free Basic tier on RapidAPI ($0 / 500,000 per month), so nothing to undercut (same exclusion as WeatherAPI.com). Discussions hold a single complaint theme (invalid API key, 7 threads, all unanswered). |
| Whois by API-Ninjas (apininjas) | Live-verified 2026-10-29 (wave 4): 516 subscribers, below floor. 4/5 on 2 votes, 100% service level; only a $0 BASIC tier shown on the Overview. |

## WAVE 3 CALIBRATION NOTE (2026-10-28)

Utility APIs (PDF, screenshot, QR) concentrate at tiny subscriber counts
even when complaints are real (verified: 2, 103, 294). Demand concentrates
in data and content APIs. Future sweeps should weight categories
accordingly. Method note: listing pages are JavaScript-rendered, so
subscriber counts and ratings must be read in the live signed-in browser;
text fetching returns titles only. Complaint dossiers and pricing grids
are fetchable and were verified that way in wave 3.

## WAVE 4 SWEEP NOTE (2026-10-29, extra run ahead of the 2026-11-01 monthly run)

Outcome: ONE new candidate qualified and was scored - Whois Lookup
(Zozor54), QUEUED at #10 with score 63 (see the queue table). Both
browser reports arrived after the run's first summary and were folded
in the same morning; the final state below supersedes every interim
note. Calendarific (550 subs) and Abstract IP geolocation (131 subs,
free-only) were fully read live and FAIL the floor - recorded in
EXCLUDED with their verified figures. Whois by API-Ninjas (516 subs)
is Excluded below the floor; Open Weather Map by cedricnoguera
(7,536 subs, 2/5) is Excluded because its RapidAPI listing is
free-tier-only; Domains API (1,327 subs) sits in WATCHLIST with its
Discussions unread. Still VERIFICATION PENDING for the 2026-11-01
run: the largest IP geolocation listing, the largest holidays
listing, and the largest OCR listing (search cards seen, figures
never read). Hub searches run: holidays, Public Holidays,
Calendarific, hefesto, public-holidays7, IP geolocation, abstractapi,
whois, Open Weather Map. Holidays search cards (figures NOT verified,
largest holidays API not determined): Public holidays by Data And
Apis, Public Holidays by StandingAPI, Working days by JoursOuvres.
IP geolocation search cards (figures NOT verified, largest not
determined): IP GEO Location by FutureAPI, Telize by Frederic Cambus,
IP Geolocation by IPWHOIS.io, IP Info by NeutrinoAPI, ipstack by
Idera Dev Tools. OCR, Spoonacular/recipe, translator alternatives,
news alternatives, metals, air quality, and trivia were in the sweep
brief but no listing in those categories was reached for verification
this run.

Build routes pre-verified this run (sources checked 2026-10-29), ready
to apply the moment an incumbent verifies:
- Holidays: python-holidays and holidata are MIT-licensed (100+
  countries, subdivisions) = clean $0 route. Nager.Date's hosted API is
  NOT the route (commercial use asks sponsorship; its offline package
  needs a license key).
- Whois: RDAP via the IANA bootstrap (data.iana.org/rdap/dns.json) is a
  free public protocol with structured JSON = clean $0 route.
- IP geolocation: MaxMind GeoLite2's standard EULA bars serving
  geolocation to third parties without a paid Commercial Redistribution
  License (a resale trap). Partial clean routes exist with attribution:
  DB-IP Lite (CC BY), IP2Location LITE (free for commercial use, about
  98% country / 60% city accuracy), IPLocate country+ASN (CC BY-SA).
  Partial-match risk, same shape as the phone-validation exclusion.
- Weather: Open-Meteo's hosted API is non-commercial on its free tier;
  its data is CC BY 4.0 and its code AGPLv3 (self-host), and NOAA data
  is public domain (US only) = contested/partial route.
- OCR: Tesseract is Apache 2.0 = clean, but heavy to host on the
  Render free tier.
- Air quality (no incumbent reached): OpenAQ data is CC BY 4.0,
  commercial use allowed with attribution = clean route.
- Trivia (no incumbent reached): OpenTDB is CC BY-SA 4.0,
  commercial-clean.
- Metals (no incumbent reached): the LBMA benchmark requires a
  redistribution license = contested.
