# Spec: FactBase (evidence-based fact-checking for text and speech; the user's own product, queue #14)

Originated by the user in a live voice call on 2026-10-31:
"Could I create a fact checker API? That fact checks anything
somebody says?" - clarified the same call: it must handle BOTH
spoken words (audio in) and written words (text in). Built under
his standing full-automation authorization for this lane
(2026-10-29). An original product in the lane's house style, in the
Base family (GeoBase, WordBase, WhoisBase, NewsBase, XBase).

The product name in the listing copy is deliberately narrower than
the call's phrasing: FactBase checks claims against published
fact-checks and retrievable evidence, with sources on every
verdict. It does not "check anything" and the copy never says so;
a claim with no retrievable evidence is reported "unverified",
never guessed.

## The product

- POST /check-text {text, max_claims? (default 5, cap 10)} -
  extracts the checkable factual claims from the text (opinions,
  predictions, questions and quotations of belief are left out),
  verifies each, and returns per claim: the claim, a verdict from
  exactly (supported / refuted / mixed / unverified), a confidence
  note, a one or two sentence explanation, and the evidence used
  (source title, URL, snippet per source).
- POST /check-claim {claim} - a single claim through the same
  pipeline.
- POST /check-audio (multipart audio file: mp3, wav, ogg, flac,
  aac, aiff; 12 MB cap) - transcribes the speech with Gemini audio,
  then runs the identical claim pipeline; the response carries the
  transcript plus the same per-claim results.
- GET /health - version, engine states, evidence layer states,
  limits.

## Pipeline (per claim)

1. Claim extraction: Gemini (gemini-3.6-flash, the lane's deployed
   model) returns the checkable claims as JSON.
2. Evidence retrieval, three layers, all zero marginal cost:
   - Google Fact Check Tools API (the ClaimReview database of
     published fact-checks) when a key is configured
     (FACTCHECK_API_KEY, falling back to GEMINI_API_KEY; it works
     when the API is enabled on that key's Google Cloud project);
   - DuckDuckGo HTML web search (keyless): the claim itself plus
     one fact-check-targeted query ("<claim> fact check");
   - Wikipedia search API (keyless) for entity grounding.
   Evidence is de-duplicated by URL and capped at 7 per claim,
   published fact-checks first.
3. Verdict synthesis: Gemini sees ONLY the claim and the retrieved
   evidence and must return one of the four verdicts plus an
   explanation grounded in that evidence. If NO evidence was
   retrieved, the verdict is "unverified" by construction and the
   model is never asked - a verdict with no source is treated as a
   bug, not a result. The confidence note is computed in code from
   the evidence composition (a published fact-check in evidence =
   high; 3+ domains = moderate; thin evidence or none = low), not
   by the model.

## Engine states (honest by construction)

- live: GEMINI_API_KEY set; the full pipeline runs.
- awaiting_key: no key yet; the three data endpoints answer an
  explicit 503 engine_not_configured. This is the deployed resting
  state until the owner completes the key step (see Launch state).
  There is deliberately NO mock mode for this service: a fact
  checker must never serve staged verdicts.

Speech-to-text choice: Gemini audio (gemini-3.6-flash) through the
user's key, proven at build time through the connected Gemini API
(a synthesized claim clip transcribed word-perfectly in substance
and the real JFK speech clip transcribed exactly).
faster-whisper was evaluated as the fallback: open source and
license-clean, but on the Render free tier (512 MB) only the tiny
or base model is realistic, with a runtime model download and slow
CPU transcription; it is held as the documented fallback if the
Gemini key is ever unavailable, and /health says so.

## Cost shape

The build spent $0. At runtime the only upstream is the owner's
own Gemini API key (his existing key, shared with SwiftRewrite and
SwiftTranslate; Gemini API free-tier quota covers this volume, and
any paid usage is on his own Google account, not a new service).
Evidence layers are keyless or ride the same Google key. No new
account, no new purchase, no new terms were agreed for this build.

## What v1 deliberately does not claim

- Not an oracle: verdicts summarize retrieved evidence; they do
  not settle truth. Coverage depends on what fact-checkers and
  sources have published; fresh, local or niche claims will often
  be unverified, and that answer is a feature, not a failure.
- No live/broadcast audio in v1: uploaded clips only.
- No claim extraction from images or video in v1.
- Verdicts are English-language-evidence based in v1
  (languageCode en on the ClaimReview layer; web evidence follows
  the claim's own wording).

## Plans (to save in Studio, hard limits, per request)

BASIC $0/100mo; PRO $5/1,000mo; ULTRA $20/10,000mo; MEGA
$60/50,000mo (the own-product grid). Each request runs real
extraction, retrieval and synthesis; the per-request price
reflects that.

## Launch state at build (2026-10-31)

Built and deployed on Render; proven end to end LOCALLY with the
real engines (the service's unmodified pipeline, its Gemini calls
routed through the user's connected Gemini API via the connector
credential flow - see docs/factbase-reliability.md for the battery
and the exact transport note) and proven on the DEPLOYED service
for gate behavior and the honest awaiting state. PARKED at the key
step, the lane's standing pattern (SwiftTranslate precedent):
GEMINI_API_KEY must be added to the FactBase Render service env by
the owner (the same key he added for SwiftRewrite/SwiftTranslate),
because the deployed service calls Gemini directly and the
connector credential cannot be extracted into hosting. Publish is
parked behind the same step: the RapidAPI gateway test would call
/check-claim through the gateway, and until the key lands the
honest answer is the 503, so the listing stays unpublished. On his
word that the key is set, the finish runs unattended: redeploy,
the deployed proof battery with real claims, Studio listing,
proxy-secret wiring, publish, gateway test, Spotlight. The Fact
Check Tools API layer activates automatically when the key's
project has that API enabled; if claims search returns 403 after
the key is set, enabling "Fact Check Tools API" on the project is
a second, optional owner step (web and Wikipedia evidence carry
the service without it). Full record: docs/factbase-reliability.md;
listing package: listings/factbase-openapi.json +
listings/factbase-listing-notes.md.

## Deploy

Render free plan, same repo: build `true` (stdlib only, no
dependencies), start `python factbase/app.py`. Keep-warm fleet
becomes fourteen services; the window is re-budgeted to
09:00-10:30 ET (90min x 14 x 31 = 651h worst month vs the 750h
cap).
