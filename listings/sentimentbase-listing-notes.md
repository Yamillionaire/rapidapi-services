# SentimentBase: Studio listing notes (for the browser-lane listing session)

Prepared 2026-11-01 at build time. The listing itself (Studio
create/PRIVATE, plans, proxy-secret wiring, publish, gateway test,
Spotlight) runs in the parent's browser lane, in SMALL CHUNKED
TASKS (basics, then endpoints, then pricing plus proxy secret).
Service is live on Render first; see the registry's sweep-derived
originals section for the service id and URL.

## Basics

- Name: SentimentBase
- Base URL: confirm the exact subdomain from the Render service
  record before saving (Render suffixes the name when the bare one
  is taken globally)
- Short description: Sentiment analysis that answers on the free
  tier: per-sentence breakdowns, the exact words that drove the
  score, and no invented quota errors.
- Category: Artificial Intelligence / Text Analysis (provider's
  pick in Studio)

## Endpoints (4)

- GET /analyze?text= - one text.
- POST /analyze {text} - same, POST form.
- POST /analyze/bulk {texts: [...]} - cap 100, per-item errors in
  place, one request counted per text (stated in the response).
- GET /health - status, engine, honest limits (open, no gate).

Every analysis returns: score (-1..1 compound), magnitude with
its basis stated, label with the thresholds used (positive
>= 0.05, negative <= -0.05), pos/neu/neg proportions, per-sentence
breakdown, top positive and negative terms with lexicon valences,
and the lexicon version.

Full machine-readable spec: listings/sentimentbase-openapi.json.

## Plans (hard limits, monthly quotas)

BASIC $0 / 1,000 (a free tier that actually answers - the
incumbent's blocking free tier is complaint #1); PRO $9 / 25,000;
ULTRA $19 / 150,000; MEGA $49 / 750,000.
NOTE: the incumbent (Twinword) grid was verified on the provider's
own site during wave 3 but not yet read on RapidAPI itself; if the
live RapidAPI grid differs, true these prices to a $10-undercut
shape against it before saving.

## Proxy secret wiring (before publish)

1. In Studio, copy the API's proxy secret.
2. Set it on the Render service as RAPIDAPI_PROXY_SECRET
   (render_api.py set-env), then trigger a deploy.
3. VERIFY THE GATE AT THE SERVICE: GET /analyze?text=great
   without the header must return 401 {"error": "unauthorized"};
   with the header, 200 with a positive score; GET /health stays
   open. If the gate is not active after the first deploy, deploy
   once more and re-verify (env race, learned 2026-10-28).
   NOTE: the service was gate-tested at build time with a
   temporary secret that was NOT retained, so the origin currently
   sits GATED under that unrecorded value. Setting the Studio
   secret overwrites it; re-verify right after, before publishing.
4. Publish, then run the Hub gateway test (subscribe the owner's
   test account to BASIC first): GET /analyze with a mixed
   two-sentence review - expect 200 with both sentences scored in
   opposite directions. Retry once on a cold-start timeout.

## Spotlight (after publish, same session)

Description must stay UNDER 280 characters. Draft (about 245):
"No invented quota errors: SentimentBase answers on the free tier,
breaks mixed reviews down per sentence, and names the exact words
that drove the score. VADER lexicon engine, versions reported,
zero per-call cost. Proof inside."
Post via the URL tab with the GitHub blob URL of
docs/sentimentbase-reliability.md on
github.com/Yamillionaire/rapidapi-services.

## Honesty notes for the overview copy (do not oversell)

- Lexicon sentiment (VADER), not deep understanding: sarcasm and
  domain jargon score approximately; the per-sentence breakdown
  is the audit trail, say so.
- English-first: a non-English lang parameter returns a named
  422, never a confident wrong score. Do not list other languages
  as supported.
