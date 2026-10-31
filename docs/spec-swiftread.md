# Spec: SwiftRead (article-to-speech; the user's own product, queue #11)

Originated by the user in a voice call on 2026-10-30: "an API that
reads articles aloud - give it an article and it reads it, like the
play button on a news article." Built and launched under his standing
full-automation authorization for this lane (2026-10-29). An original
product, not a clone: new, in the lane's house style.

## The product

POST a URL, get spoken audio back. The service fetches the page,
extracts the article's main text, and synthesizes it with a natural
neural voice, returning audio/mpeg directly - the "listen to this
article" button as an API, for read-it-later apps, accessibility
tools, newsletters, and content platforms.

- Extraction: the lane's proven stack, shared with CleanExtract -
  stdlib density-scored main-content extraction, SSRF-hardened fetch
  (public addresses only, checked on every redirect hop), size and
  time caps, boilerplate and navigation stripped by construction.
- Speech: the free Microsoft Edge read-aloud neural voices via the
  edge-tts package. Zero marginal cost, no key, no paid TTS. Text is
  chunked at sentence boundaries within paragraphs (1,200 characters
  per chunk); chunks synthesize in parallel under a bounded pool
  (concurrency 4) with one retry per chunk and a 60-second
  per-attempt ceiling, under an 85-second whole-request budget sized
  to the platform's response cutoff: chunks that stall, error, miss
  the budget, or are unspeakable for the chosen voice (foreign-script
  example text) are skipped and disclosed in the
  X-SwiftRead-Chunks-Skipped response header instead of failing the
  article, and the MP3 segments are
  concatenated in reading order with a 0.4-second silence beat
  between paragraphs, so playback keeps the article's rhythm.
- POST /read-url {url, voice?, rate?} -> audio/mpeg. POST /speak
  {text, voice?, rate?} -> audio/mpeg for caller-supplied text.
  GET /voices lists the FULL Edge catalog: 322 voices, 142 locales,
  75 languages, shipped as data (swiftread/voices.json, generated
  from the live catalog list) and ordered most-spoken languages
  first (English, Chinese, Hindi, Spanish, French, Arabic, Bangla,
  Portuguese, Russian, Japanese, German, Indonesian, Urdu), then
  the featured African set (Swahili, Amharic, Somali, Zulu,
  Afrikaans, with the African English variants grouped under
  English), then the rest alphabetically. Filters: ?language=
  (name or code), ?locale=, ?gender=. The earlier curated 45 are
  flagged featured and stay the highlighted picks in docs and
  listing copy. Sentence splitting covers Latin punctuation plus
  the CJK full stops and the Hindi danda; the 1,200-character hard
  split remains the backstop (and the only mechanism for Thai).
  GET /health is lane-standard.
- Caps and errors, stated not hidden: 15,000 characters of extracted
  or supplied text per request; beyond the cap a 422 names the cap
  and the length received. A page with no extractable article text
  returns a clear 422 no_article_text. Unknown voice or malformed
  rate returns a 422 naming the valid values. Rate accepts a
  multiplier (0.5-2.0) or a percent string, clamped to -50%..+100%.
- Server: the scaffold's conventions (RapidAPI proxy-secret gate,
  401 JSON without the header, /health open, structured JSON errors)
  extended with POST JSON bodies and binary audio responses, since
  the shared GET/JSON scaffold cannot carry either.
- Audio responses carry X-SwiftRead-Voice, X-SwiftRead-Characters,
  X-SwiftRead-Chunks, X-SwiftRead-Paragraphs, and (for /read-url)
  X-SwiftRead-Title headers, so callers can log what was read
  without parsing the audio.

Fix pass (2026-10-30, from
swiftread-fixlist-2026-10-30.md - rival listings' public
complaints mined and fixed before listing): (a) chunk synthesis
parallelized, the checklist's one real engineering gap (item 6);
(b) the voice roster widened from English-only to 45 voices in 13
languages, including the owner's two additions, Mandarin Chinese
and the African set: Swahili, Amharic, Somali, Zulu, Afrikaans plus
African English variants (item 8); (c) paragraph-aware chunking
with an audible pause between paragraphs (item 7); (d) listing
actions: plans bill PER REQUEST, never per character (item 9),
documentation ships copy-paste snippets for handling the binary MP3
response in JavaScript and Python (item 10), and playable voice
samples are prepared for the listing (item 5). A full-cap
(15,000-character) end-to-end load test is specified for the
deployed service; its result, and the rest of the live record, live
in docs/swiftread-reliability.md.

Full-catalog pass (2026-10-31, owner directive superseding the
curated roster): "take it all the way to the 75 language limit."
The roster is now the entire Edge catalog as shipped data
(322 voices, 142 locales, 75 languages), validation accepts any
catalog id, /voices filters by language, locale, and gender, the
presentation order puts the most-spoken languages first with the
featured African set right behind them, and the splitter handles
CJK and Hindi sentence punctuation. The curated 45 became the
featured set. (Yoruba, Igbo, and Hausa remain impossible on this
engine - they are not in the catalog at all.)

Copyright posture: a read-aloud tool the caller points at content
they supply. Listing copy stays generic ("turn articles and web
pages into natural spoken audio") and never markets the service as
a way to obtain any specific publisher's content.

## Pricing (RapidAPI, hard limits, monthly quotas)

BASIC $0 / 100 per month, PRO $5 / 1,000, ULTRA $20 / 10,000,
MEGA $60 / 50,000. Net after RapidAPI's 25% fee: $3.75 / $15 / $45.
Quotas bill PER REQUEST, never per character (the structural
complaint against the biggest article-listening rival is that one
15,000-character article costs 15 quotas there; here it costs 1).
Audio generation is the heaviest workload in the fleet, so the free
tier is deliberately modest; the engine itself costs $0 per call.

## Costs and risks

$0 end to end: extraction is on-server stdlib; the voices are the
free Edge read-aloud set; hosting is the eleventh Render free
service. Keep-warm math must be re-budgeted: 2h window x 11 services
x 31 days = 682h worst month against the 750h workspace cap, about
68h of headroom for organic traffic - the tightest the fleet has
run; if a twelfth service lands, the window narrows.

Two honest environment notes. (1) The build sandbox's egress cannot
complete the speech engine's websocket connection (direct egress is
intercepted at the network level; the sandbox proxy mangles the
websocket upgrade), so synthesis is verified live on Render - the
same pattern WhoisBase used for port-43, which the sandbox blocks
and Render passes. Extraction, the gate, and every error path are
verified locally. (2) Launch night produced the full failure museum
of a free speech engine: streams that stall while ignoring asyncio
cancellation (fixed with a hard thread-join deadline and
skip-and-disclose chunks), chunks a voice cannot speak
(NoAudioReceived on mixed-script text, same fix), and finally the
sandbox's own egress proxy stalling ALL POST traffic - proven
path-side when instant-422 POSTs stopped reaching the service while
GETs answered in under a second and POSTs to unrelated hosts
stalled identically. A 15,000-character article is roughly 15
minutes of speech; with parallel chunk synthesis the deployed
wall-clock is recorded per request in GET /health (recent_requests,
service-side seconds) and summarized in
docs/swiftread-reliability.md; the full-cap load test and a complete
/read-url read are the two rows that wait on a clean POST test path.
Callers should treat /read-url as a slow endpoint, and the listing
says so.

## Local test log (2026-10-30, build sandbox, test proxy secret set)

/health open without the secret, reporting the edge-tts engine and
the 15,000-character cap. GET /voices: 401 without the header, 200
with it, 10 voices. POST /speak: 401 without the header. Named 422s
verified: unknown voice (lists the valid ids), malformed rate,
over-cap text at 15,999 characters (states the cap and the length),
missing text, missing URL. SSRF guard verified: a 127.0.0.1 URL is
refused with fetch_refused. Extraction verified live locally:
example.com's body text passed extraction and reached the synthesis
stage (which then returned the structured 502 the sandbox's blocked
websocket causes), and a page whose paragraphs are all short
returned the clean 422 no_article_text. Synthesis itself is
verified on the deployed service (see docs/swiftread-reliability.md).

## Fix-pass test log (2026-10-30, after the fixes)

Offline unit checks of the new logic: 45 voices across 13 languages
in the roster (zh-CN pair present; 20 voices in the African set);
the paragraph-pause segment decodes to 2,928 bytes of valid MP3
frames at the engine's format; paragraph splitting and per-paragraph
chunking verified on multi-paragraph text; a 200-sentence paragraph
chunks into 6 parts, none over 1,600 characters; rate normalization
unchanged. Local server smoke with the test secret: /health open;
GET /voices 401 without the header and 200 with it, returning all
45 voices with language tags; the unknown-voice 422 now lists all
45 valid ids; the over-cap 422 unchanged. (A stale pre-fix server
was found still holding local port 8112 during this pass and was
killed; the smoke above ran against the new build.)
