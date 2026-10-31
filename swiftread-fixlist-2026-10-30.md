# SwiftRead: Complaint Research and Fix Checklist

Researched 2026-10-30, per the user's direction: find the APIs like SwiftRead, read their
comment sections for where they fall short, and make sure SwiftRead fixes what people
are reporting.

## Method and readability note (read this first)

RapidAPI's main listing pages and discussion index pages are JavaScript-rendered; the
plain text fetcher gets only the page title back from them. Discussion and detail
content below was therefore read from RapidAPI's own indexed pages (the rapidapi.com
and v2.rapidapi.com discussion/detail pages, which search engines index with full
text), from provider sites (voicerss.org), and from public forums and GitHub issues
that name the API. Where a comparable listing's discussion section could not be enumerated at
all, that is stated plainly per API instead of guessed.

## The competitive field on RapidAPI

| API (provider) | Popularity | Model | Hard limits found | Voices / languages |
|---|---|---|---|---|
| Text-to-Speech (VoiceRSS) | 9.7/10, ~1,050-1,190 ms latency | Sync, returns audio stream only, no download URL | 100 KB per request; direct plans: 350 req/day free up to 20,000/day at $40/mo (voicerss.org) | 49 languages, 100 voices |
| Large Text to Speech (k_1) | 9.7/10 | Async job + poll; download URL valid 24 h | "Unlimited" text (72,000 chars tested); billed 1 quota per 1,000 chars | English only |
| Text-to-Speech API (the one with the official PyPI SDK, rapidapi-tts) | n/a | Sync; word timestamps on paid tier | Free $0: 50 req/day, max 1,000 chars. Basic $3/mo: 5,000 chars. Pro $9/mo: 10,000 chars | 400+ voices, 100+ languages claimed |
| Text To Speach API (elisbushaj2) | 9.2/10 | Sync | Not stated on the detail page read | Plans $0 / $0.99 / $4.99 / $8.93 per mo |
| Text To Speech for 28+ languages (rahilkhan224) | n/a | Sync | Stated ~3,000-char limit (see complaint 2: users report it is not honored) | 28+ languages (sibling listing claims 65+) |
| Text To Speech (HiVoicy) | n/a | Sync | **250 characters per request** | English, French, Persian only |
| Text to Speech AI (riyanshgupta750) | n/a | Sync | **500 characters per request** | Multiple, unspecified |
| Text To Speech (Emiledaou) | n/a | Sync | **1,000 characters per request** | Many locales |
| AI Voice Text to Speach (sknuraktar1999) | n/a | Sync | Not stated | 8 voices total (f1-f3, m1-m5); plans $0 / $5 / $10 / $20 |
| Realistic Text to Speech (ptwebsolution) | 0.1/10 | Sync | Not stated | "Hyper-realistic" claims, near-zero traction |

Key structural fact: **no meaningful comparable RapidAPI listing offers URL-in / article
extraction at all.** Even Large Text to Speech, whose provider markets article
listening, makes the caller extract and paste the article text themselves (their
Medium how-to passes raw article text to the API). SwiftRead's /read-url with
built-in extraction is open field. The complaints below are therefore mostly about
the TTS half, which is where users are hurting.

## Ranked fix checklist

### 1. Long text fails: tiny character caps, and errors/timeouts when text gets long

- Reported against: HiVoicy (250-char cap, listing detail page); Text to Speech AI
  (500-char cap, listing documentation); Emiledaou Text To Speech (1,000-char cap,
  listing detail via Toolify mirror); the PyPI-SDK Text-to-Speech API (1,000-char cap
  even shapes its free tier; 10,000 only at Pro); VoiceRSS (openHAB community:
  "the 'say' command times out often (though not always) when no cached mp3 is
  available," i.e. fresh/longer syntheses time out).
- Sources: RapidAPI listing detail/documentation pages for HiVoicy, Text to Speech AI,
  Emiledaou; PyPI rapidapi-tts package page (pricing table); openHAB community forum,
  "Could not find or load main class org.openhab.voice.voicerss" thread.
- Fix for SwiftRead: a per-request cap in the tens of thousands of characters with
  sentence-boundary chunking and concatenated audio, plus an honest, explicit error
  (actual count vs. max) when the cap is exceeded, never a timeout or a bare 5xx.
- SwiftRead coverage: **COVERED.** 15,000-char cap (15x to 60x the caps above),
  1,600-char sentence-boundary chunks concatenated in order, and the over-cap error
  states the submitted length and the maximum and tells the caller to split.

### 2. Stated limits are not honored: calls fail below the documented cap

- Reported against: Text To Speech for 28+ languages (rahilkhan224). Discussion
  thread titled "Long Inputs Not Working": a user reports ~2,000-character texts,
  under the stated 3,000 limit, failing with "Usage Limit Exceeded... Please fix
  ASAP!"
- Source: RapidAPI discussion page for that API (v2.rapidapi.com mirror of
  discussions/100015).
- Fix: the enforced limit must equal the documented limit, limits must be published
  in the listing, and every response should report the character count consumed so
  users can verify accounting themselves.
- SwiftRead coverage: **COVERED.** The cap is a hard length check in code, /health
  publishes the limit, and successful responses carry X-SwiftRead-Characters and
  X-SwiftRead-Chunks headers.

### 3. Reliability: outages, silent breakage, and a provider who stopped responding

- Reported against: VoiceRSS, heavily, in 2025: multiple openHAB threads titled
  "VoiceRSS does not work anymore" and "Could not read from VoiceRSS service" (the
  service's TLS/certificate path failed for users for weeks; some never resolved it);
  a GitHub issue in Mason10198/SkywarnPlus: "voicerss.org is no longer sending
  activation emails making the service useless for new users"; AllStarLink community
  (Aug 2025): "VoiceRSS no longer allows you to create an account, paid or
  otherwise... My guess is that VoiceRSS is going to fold as they don't respond to
  anyone. Eight of us tried to create paid accounts as well as free accounts with
  absolutely zero response from them." Also Large Text to Speech: its own discussion
  page carries the provider's apology for "degraded service" and an FAQ entry "api
  not working."
- Sources: openHAB community forum (three threads, Jun-Oct 2025); AllStarLink
  community forum; GitHub issue #136 in Mason10198/SkywarnPlus; RapidAPI discussion
  page for Large Text to Speech (v2.rapidapi.com mirror of discussions/142869).
- Fix: boring reliability engineering plus visible life: health endpoint, structured
  errors instead of silent failure, uptime kept by the lane's keep-warm pattern, and
  a provider who actually answers discussion threads.
- SwiftRead coverage: **PARTIALLY COVERED.** /health exists, every failure is a
  structured JSON error (never a bare 503), and RapidAPI itself handles accounts and
  billing, so the dead-signup failure mode cannot occur. The conduct half (monitor,
  answer users) is an operating commitment, not code: keep it on the lane checklist.

### 4. Audio delivery pain: download URLs that expire instantly, or no URL at all

- Reported against: Large Text to Speech, discussion thread "GET audio url NOT
  working": the user receives the download URL and it is already expired
  (S3 "AccessDenied / Request has expired"), despite the documented 24-hour
  validity; the provider's remedy is "download it and store it on your end."
  VoiceRSS, from the other side: RapidAPI discussion thread where users ask how to
  get a generated audio URL to download via mobile apps, and the provider answers
  "Our API does not provide a URL to download an audio file" (stream only).
- Sources: RapidAPI discussion page for Large Text to Speech (discussions/33076);
  RapidAPI discussion page for VoiceRSS Text-to-Speech (discussions/31491).
- Fix: return the audio itself in the response, so nothing can expire; optionally
  also offer a hosted URL with long validity for mobile clients that cannot handle
  binary responses.
- SwiftRead coverage: **COVERED on the main pain, PARTIAL on the secondary want.**
  Audio returns directly as audio/mpeg, so expiry is impossible. There is no
  hosted-URL option for binary-averse clients; add one only if subscribers ask
  (and if added, validity should be days, not Large TTS's broken 24 hours).

### 5. Dated, low-quality voices

- Reported against: VoiceRSS. Domoticz forum user: quality "is not as good as with
  Google, it sounds like someone speaking in a closet, and low bps." AllStarLink
  forum: "VoiceRSS just uses renamed versions of the Microsoft OneCore voices,
  which have been around since Windows 8." 5app.ai review: voices "sometimes lack
  emotion or variety in tone." (Inference, labeled: this is the predictable result
  of selling pre-neural voices in a neural-voice market; the 0.1-popularity
  "Realistic Text to Speech" listing also shows that claiming realism is not the
  same as earning users.)
- Sources: Domoticz community forum; AllStarLink community forum; 5app.ai Voice
  RSS review page.
- Fix: use current-generation neural voices, and put sample audio in the listing so
  buyers can hear the quality instead of trusting adjectives.
- SwiftRead coverage: **COVERED in the engine** (modern Microsoft Edge neural
  voices: Aria, Jenny, Guy, Christopher, Sonia, Ryan, etc.). **Action for the
  listing:** include playable samples per voice; the code cannot fix this part.
  UPDATE 2026-10-30 (fix pass): samples are prepared in
  listings/swiftread-listing-notes.md - one short sample per language group,
  generated from the deployed service, to attach in Studio or link from the
  Spotlight proof doc if Studio cannot host audio.

### 6. Slow synthesis, and long jobs that take forever with no guarantee

- Reported against: Large Text to Speech's own documentation: 72,000 characters
  produced 78 minutes of audio "completed in 16 min," and "ETA is estimated time
  of completion of the current job, this is not garanteed." VoiceRSS: MyRobotLab's
  integration notes say "It has slow responses," and RapidAPI shows ~1.05-1.19 s
  latency for a short-text service.
- Sources: Large Text to Speech RapidAPI detail page; MyRobotLab VoiceRss service
  page; RapidAPI thread roundups quoting VoiceRSS latency.
- Fix: synthesize chunks in parallel (bounded concurrency) and concatenate in
  order, so wall-clock time tracks the slowest chunk, not the sum; for very long
  texts, prefer this over an async job queue, which is the pattern users are
  fleeing.
- SwiftRead coverage: **COVERED (fix pass 2026-10-30).** Chunk synthesis is
  now parallel under a bounded pool (concurrency 4) with one retry per
  chunk, concatenated in reading order. A full-cap 15,000-character
  end-to-end load test on the deployed service is recorded in
  docs/swiftread-reliability.md. Before the fix, the sequential build
  needed over 130 seconds for a 6,666-character article and the call
  died at the gateway - the complaint above, reproduced and then fixed.

### 7. No control over pauses; paragraph structure is flattened

- Reported against: Large Text to Speech, RapidAPI discussion: a user working with
  paragraph text asks about pauses between paragraphs; the provider confirms:
  "currently we do not support special character/token to force a pause."
- Source: RapidAPI discussion page for Large Text to Speech (discussions/43462).
- Fix: paragraph-aware reading: preserve paragraph breaks as audible pauses, and
  accept an explicit pause token or SSML <break> in /speak input.
- SwiftRead coverage: **COVERED (fix pass 2026-10-30) on the pause half.**
  Chunking is paragraph-aware: paragraphs are preserved through extraction
  (/read-url content already carries paragraph breaks) and /speak input,
  and a 0.4-second silence segment in the engine's exact MP3 format is
  inserted between paragraphs, so the breaks are audible. Responses report
  X-SwiftRead-Paragraphs. An explicit SSML/pause token is still not
  accepted (see item 11); the paragraph beat was the cheap fix and it
  shipped.

### 8. Language coverage is thin where users need breadth

- Reported against: Large Text to Speech ("It supports only English language texts
  at the moment," its own documentation); HiVoicy (English, French, Persian only,
  its listing). The market signal runs the other way: the listings competing on
  breadth advertise 28+, 49, 65+, and 100+ languages.
- Sources: the two listings' own detail/documentation pages; comparable listings' detail
  pages for the breadth claims.
- Fix: ship more than English at launch or fast-follow. The Edge neural set has
  quality voices in Spanish, French, German, Portuguese, Italian, Japanese, and
  more at the same zero marginal cost, so this is roster work, not engine work.
- SwiftRead coverage: **COVERED (fix pass 2026-10-30; FULL CATALOG
  2026-10-31).** The roster began at 45 voices across 13 languages,
  each tagged with its language in GET /voices: English (US, UK, plus
  Kenyan, Nigerian, Tanzanian, and South African variants), Spanish,
  French, German, Portuguese, Italian, Japanese, Mandarin Chinese
  (zh-CN, added at the owner's direction), and the African set the
  owner directed: Swahili (sw-KE, sw-TZ), Amharic, Somali, Zulu, and
  Afrikaans. Yoruba, Igbo, and Hausa have no voices in the Edge
  catalog (verified against the live 322-voice list), so they cannot
  be offered on this engine and are not listed. SUPERSEDED the next
  day by the owner's full-catalog directive: the entire Edge catalog
  now ships as data (322 voices, 142 locales, 75 languages), any
  catalog id validates, /voices filters by language, locale, and
  gender, and the default order runs most-spoken languages first
  with the African set right behind them; the 45 remain the featured
  picks.

### 9. Pricing that punishes exactly the long content the product is for

- Reported against (structural, from published pricing rather than a complaint
  thread): Large Text to Speech bills 1 quota per 1,000 characters, so one
  15,000-character article costs 15 quotas; the PyPI-SDK API gates even 5,000
  characters behind paid tiers. Nobody writes a comment saying "your per-character
  billing is why I left," but the arithmetic is on their pricing pages, and it is
  the mirror image of the cap complaints in item 1. Labeled as pricing analysis,
  not a quoted complaint.
- Sources: Large Text to Speech detail page (Billing & Limitations); PyPI
  rapidapi-tts pricing table.
- Fix: bill per request, not per character, with request quotas sized for article
  reading; a subscriber should never do quota math before pressing listen.
- SwiftRead coverage: **NOT A CODE ITEM; ACTION AT LISTING SETUP.** Confirm the
  RapidAPI plan configuration is per-request before publishing the Spotlight.
  UPDATE 2026-10-30: the four plans are specified as request quotas in the
  spec, and listings/swiftread-listing-notes.md carries the explicit
  Studio instruction (bill per request, never per character; confirm the
  plan unit reads "requests" before publishing).

### 10. Documentation gaps around the binary response

- Reported against: VoiceRSS, RapidAPI discussion thread 31491: alongside the URL
  question, users ask "Can you provide some JS code snippets for handling your
  binary data like converting to audio file data?" and ask for an in-app usage
  example.
- Source: RapidAPI discussion page for VoiceRSS Text-to-Speech (discussions/31491).
- Fix: listing documentation with copy-paste snippets (JavaScript fetch to Blob,
  Python requests) for saving and playing the returned MP3, including a mobile
  note.
- SwiftRead coverage: **ACTION FOR THE LISTING.** The API returns standard
  audio/mpeg; the docs page must show the three-line save/play patterns.
  UPDATE 2026-10-30: copy-paste snippets (JavaScript fetch to Blob and
  play; Python requests save-to-file, with a mobile note) are written in
  listings/swiftread-listing-notes.md, ready to paste into the listing
  documentation at Studio setup.

### 11. Prosody controls gated or missing (SSML, emotion)

- Reported against: VoiceRSS (its own plans page marks SSML input "NO" on the
  listed tiers; the 5app.ai review flags the lack of SSML and tonal variety as the
  ceiling on the product). Weaker and less frequent than items 1-8; a want, not
  an outage.
- Sources: voicerss.org plans page; 5app.ai review.
- Fix: accept optional SSML (or at least break/emphasis markup) in /speak once the
  core is proven; do not gate basic rate control behind paid tiers.
- SwiftRead coverage: **PARTIALLY COVERED.** Rate control (0.5x-2.0x, plus percent
  strings) ships free in the base API; SSML is not accepted. Fine for launch;
  revisit if subscribers ask.

## What could not be read (stated plainly)

- RapidAPI's discussion index pages and ratings render client-side and returned
  titles only to the fetcher; individual discussion threads were recovered through
  RapidAPI's indexed copies where they exist. VoiceRSS (1 thread), Large Text to
  Speech (3 threads), and Text To Speech for 28+ languages (1 thread) yielded real
  discussion text.
- The discussion sections of HiVoicy, Text to Speech AI, Emiledaou, elisbushaj2,
  sknuraktar1999, and ptwebsolution could not be enumerated; for those APIs only
  their listing-stated limits and pricing are reported, and no complaints are
  attributed to them beyond those facts.
- No dedicated URL-to-audio/article-reader API of any consequence exists on
  RapidAPI to mine for extraction complaints specifically; the extraction-junk
  failure mode (nav/ads read aloud) is a known risk of the category rather than a
  sourced complaint here, and SwiftRead's density-scored extractor (nav, header,
  footer, aside, form, and figure blocks skipped; paragraphs under 40 characters
  dropped) already aims at it. It should be proven with tests on cluttered real
  pages, not assumed.

## Bottom line for the build

Already fixed by the current spec: character caps (1), honest limits (2), expiry
(4), voice quality (5), signup/platform risk (part of 3). One engineering fix to
make: parallel chunk synthesis (6). Two cheap roster/doc fixes: add non-English
voices (8) and paragraph pauses (7). Two listing-time actions: per-request pricing
(9) and binary-handling snippets with voice samples (10, 5).

## Fix pass outcome (2026-10-30, before listing)

Items 6, 7, and 8 are now COVERED in the shipped code (parallel chunk
synthesis with per-chunk retry; paragraph-aware chunking with a 0.4 s
inter-paragraph beat; 45 voices in 13 languages including the owner's
Mandarin and African additions). Items 9 and 10 and the samples half of
item 5 are prepared as explicit listing actions in
listings/swiftread-listing-notes.md for the Studio session. A full-cap
load test on the deployed service is recorded in
docs/swiftread-reliability.md.
