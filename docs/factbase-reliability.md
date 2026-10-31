# FactBase Reliability Notes

Service: https://factbase.onrender.com (Render srv-dbj5slfb9u1s73d4kntg)
Spec: `docs/spec-factbase.md`. Local battery:
`factbase/tests/battery-2026-10-31.json`. Deployed battery:
`factbase/tests/battery-deployed-2026-10-31.json`.

## What FactBase is, and what it is not

FactBase checks claims in text or speech against retrievable
evidence: published fact-checks where they exist, plus ordinary
web and reference sources. It returns a verdict per claim
(supported / refuted / mixed / unverified), an explanation, and
the sources used, with titles, URLs, and snippets.

It is NOT an oracle. It can only judge a claim against what
sources have actually published and what its retrieval can find:

- Coverage depends on what fact-checkers and sources have
  published. Famous claims are usually well covered; fresh,
  local, or niche claims will often return "unverified", because
  no retrievable evidence exists either way.
- A claim with no retrievable evidence returns "unverified" by
  construction, never a guessed verdict. Zero evidence means the
  verdict step is not even called.
- Every verdict carries its sources. A verdict with no source is
  a bug, and the pipeline is built so it cannot happen: verdicts
  are only synthesized from the evidence list the response
  returns.
- If the verdict step itself fails (engine error), the claim is
  reported "unverified" with an explicit `error` field rather
  than a guessed verdict.
- Verdicts summarize evidence; they do not settle truth. The
  confidence note is computed in code from the evidence
  composition (a published fact-check in the evidence = high;
  three or more source domains = moderate; otherwise low), not
  invented by the model.

## Engines, and how each was proven

- Reasoning (claim extraction + verdict synthesis): the owner's
  Gemini API. Primary model gemini-3.6-flash (the lane's deployed
  model, same as SwiftRewrite/SwiftTranslate). Proven through the
  connector before the build: a models call returned 50 models,
  and an extraction test on an Eiffel Tower sample returned
  exactly the three checkable claims, dropping the opinion in the
  same text ("I think it is beautiful").
- Fallback model: gemini-3.1-flash-lite, chosen by measurement on
  the owner's key after build-day testing exhausted the primary
  model's quota (HTTP 429). Per-model quotas are separate
  buckets, so a 429 on the primary retries against the fallback
  instead of failing the check. Measured at build time:
  gemini-2.5-flash is retired for new users on this key (404),
  gemini-3.7-flash and gemini-3.8-flash answered a trivial prompt
  in about 77-84 s (too slow for a checking call), and
  gemini-3.1-flash-lite answered in about 3 s with clean JSON.
  A 429 on the primary costs one 8-second pause and a retry,
  then the fallback answers.
- Transcription (/check-audio): Gemini audio transcription
  through the same key (engine name "gemini-audio", reported in
  /health). Proven at build time with two clips: (1) a claim clip
  synthesized for the test ("The Eiffel Tower was completed in
  1889. It stands 330 metres tall and is located in Paris,
  France.") transcribed with substance exact ("metres" rendered
  "meters"), all three extracted claims then checked and
  supported; (2) a real 11-second JFK recording ("ask not what
  your country can do for you") transcribed exactly.
  faster-whisper (open source) was evaluated as the fallback:
  viable only at tiny/base size on the Render free tier (512 MB)
  with a runtime model download and slow CPU transcription. It
  is held as the documented fallback in /health and is not
  needed while the Gemini key is configured.
- Evidence: keyless retrieval, in order per claim: DuckDuckGo
  HTML (one general query and one fact-check-targeted query),
  DuckDuckGo Lite, Bing HTML as the last fallback, plus the
  Wikipedia search API. Results are de-duplicated by URL, capped
  at 7 per claim, with published fact-checks sorted first.
- Google Fact Check Tools API (ClaimReview database): the
  endpoint is live, but it requires an API key, and whether the
  owner's Google key works for it depends on that key and on the
  API being enabled on the key's Google Cloud project. That
  cannot be tested from the build machine (the host is not
  registered for the Gemini connector's credential flow), so
  this layer ships as an optional enrichment: the service uses
  FACTCHECK_API_KEY when configured (falling back to
  GEMINI_API_KEY) and carries the service without it. If claim
  search returns 403 after the key is set, the owner enables
  "Fact Check Tools API" on the key's project (decision queue
  item 11). Not a launch blocker.

## Retrieval lesson recorded during the build

The first full battery failed one check: a false claim ("Barack
Obama was born in Kenya") came back "unverified" because both
DuckDuckGo queries returned zero results under burst load (up
to 8 simultaneous requests; DuckDuckGo throttles bursts). The
verdict logic was correct on the thin evidence it had; the
retrieval was not robust. Fix, now in the code: DuckDuckGo
calls are paced globally (minimum 0.6 s apart), an empty page
earns one spaced retry, then the Lite endpoint, then Bing HTML.
The same claim now returns "refuted" with 6 evidence items,
including PolitiFact and AP fact-checks. The battery paces its
own engine-heavy calls for the same reason the service paces
retrieval: quotas and throttles are real, and the proof should
measure the pipeline, not the throttle.

## Proof battery (local, live engines)

15 of 15 checks passed (`factbase/tests/battery-2026-10-31.json`,
final code). Phase A (no key configured): /health 200 with
reasoning state awaiting_key; gate 401 without the secret and
401 with a wrong value; /check-text and /check-audio answer an
explicit 503 engine_not_configured through the gate. Phase B
(engines live, through the connector bridge described below):

- TRUE: "The Eiffel Tower was completed in 1889." -> supported,
  4 evidence items.
- FALSE: "The Great Wall of China is visible from the Moon with
  the naked eye." -> refuted, 5 evidence items.
- MISLEADING: "The Amazon rainforest produces 20 percent of the
  world's oxygen." -> refuted (the mixed/refuted family; the
  figure is a well-documented myth), 5 evidence items.
- OBSCURE: "The Millersville town council approved exactly
  fourteen parking permits in March 1974." -> unverified,
  honestly: no retrievable evidence settles it.
- /check-text with one true and one false statement about Barack
  Obama's birth: extraction split the text into its claims;
  Hawaii supported, Kenya refuted.
- /check-text opinion-only text ("I think pizza is the best
  food...") -> claims_found 0 with an explanatory note; opinions
  are not checked.
- /check-audio claim clip -> transcript plus 3 supported claims.
- /check-audio JFK clip -> accurate transcript.

Transport note: the local battery ran the service's unmodified
pipeline with its Gemini calls routed through the owner's
connected Gemini API via `factbase/tests/connector_bridge.py`
(local test tooling only, never deployed; the credential flow
belongs to the connector and the key was never printed or
logged). The deployed service calls the same Gemini REST
endpoint directly with the owner's key once he adds it to the
Render service.

## Deployed state, and the parked finish

Deployed battery (`factbase/tests/battery-deployed-2026-10-31.json`):
/health 200 (awaiting_key, engines named); /check-text,
/check-claim, and /check-audio all answer the honest 503
engine_not_configured. No deployed real-claim checks were run:
they cannot return real verdicts until the owner adds
GEMINI_API_KEY to the Render service (the lane's standing key
step; the connector credential cannot be extracted into
hosting). On his word that the key is set, the finish runs
unattended: redeploy, the deployed proof battery with real
claims, Studio listing, proxy-secret wiring, publish, gateway
test, and Spotlight.

One deployment caveat, recorded plainly: the lane normally sets
a build-time test proxy secret on the origin. For FactBase the
Render env-var API call timed out on three attempts at build
time (120 s, 280 s, and one unbounded attempt) through the
build egress route, while service creation, deploy triggers,
and reads all worked. Behavior proves the writes never landed:
with no origin secret configured, the gate passes and the data
endpoints answer the honest 503 to any caller. Nothing is
exposed by this (the endpoints cannot check anything until the
key lands), and the finish step sets the real
RAPIDAPI_PROXY_SECRET together with the key; if the API route
is still stalling then, the Render dashboard is the fallback
route for both values.

Publish is PARKED behind the key step by the lane's rule: the
RapidAPI gateway test must pass with real, working responses,
and it cannot until the engine is configured. The full listing
package is prepared (`listings/factbase-openapi.json`,
`listings/factbase-listing-notes.md`).

## Limits, stated plainly

- Fresh or niche claims will often be unverified; that is the
  honest answer, and the API gives it rather than guessing.
- Evidence quality is the ceiling: if the retrievable sources
  are wrong or one-sided, the verdict summarizes them as found,
  with the sources attached so a caller can judge.
- Audio checks inherit transcription accuracy; a mis-heard word
  can change a claim. The transcript is always returned so the
  caller can see exactly what was checked.
- Latency is evidence-bound: each claim costs retrieval plus one
  model call, so a 10-claim text takes longer than a 1-claim
  check. Claims in a text are checked in parallel (bounded).
