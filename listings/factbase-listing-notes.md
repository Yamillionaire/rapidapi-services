# FactBase - RapidAPI listing notes (prepared; publish PARKED)

Status: package complete, publish parked behind the owner's key
step (see "Key gate" below). Prepared for the parent's browser
lane to run in RapidAPI Studio once the key clears, exactly as
XBase's package was prepared.

## Basics

- API name: FactBase
- Base URL: https://factbase.onrender.com
- Category: Artificial Intelligence/Machine Learning (same as
  DriftCheck).
- Short description (neutral, no overclaim): "Evidence-based
  claim checking for text and speech. Send text, a single claim,
  or an audio clip; FactBase extracts the checkable claims,
  verifies each against published fact-checks and retrievable
  sources, and returns a verdict with its sources for every
  claim. Claims with no retrievable evidence return unverified,
  never a guess."
- Overview copy rules: describe it as evidence-based claim
  checking with sources. Never "checks anything", never
  "settles truth". The honest limits from
  docs/factbase-reliability.md belong in the overview: coverage
  depends on what sources have published, and fresh or niche
  claims will often be unverified.

## Endpoints (from listings/factbase-openapi.json)

- GET /health (no auth at the origin; engine states + limits)
- POST /check-text {text, max_claims? (default 5, cap 10)}
- POST /check-claim {claim}
- POST /check-audio (multipart, field "audio"; mp3, wav, ogg,
  flac, aac, aiff; 12 MB cap)

## Plans (monthly, PER REQUEST, hard limit)

- BASIC $0 / 100
- PRO $5 / 1,000
- ULTRA $20 / 10,000
- MEGA $60 / 50,000

## Key gate (must clear before proxy-secret wiring and publish)

1. The owner adds GEMINI_API_KEY to the FactBase Render service
   (Render srv-dbj5slfb9u1s73d4kntg) - the same key he added for
   SwiftRewrite/SwiftTranslate; or provides it through the
   Secure Vault. The Gemini connector credential cannot be
   extracted into hosting, so this is his step alone (decision
   queue item 11).
2. On his word: redeploy, run the deployed proof battery with
   real claims (factbase/tests/run_tests.py Phase B shapes
   against the deployed URL), and confirm verdicts with sources.
3. Only then: create the Studio listing from
   listings/factbase-openapi.json, wire the RapidAPI proxy
   secret (set RAPIDAPI_PROXY_SECRET on the Render service to
   the value Studio shows; note the build-time caveat in
   docs/factbase-reliability.md: the Render env-var API route
   timed out repeatedly at build time, so the dashboard is the
   fallback route if it still stalls), point the gateway at
   https://factbase.onrender.com, run the gateway test, and
   publish only when the test passes with real responses.
4. Optional enrichment, not a blocker: if the Fact Check Tools
   API layer returns 403 with the key set, the owner enables
   "Fact Check Tools API" on the key's Google Cloud project;
   web and Wikipedia evidence carry the service without it.

## Spotlight draft (post after publish; under 280 characters)

Title: "FactBase reliability proof"
Description (228 chars): "FactBase checks claims in text or
speech against published fact-checks and retrievable sources,
verdict plus sources per claim, unverified when no evidence
exists. Local battery 15/15 and deployed proof: see the
reliability doc."
URL tab: the GitHub blob URL for docs/factbase-reliability.md
in Yamillionaire/rapidapi-services (main branch).
