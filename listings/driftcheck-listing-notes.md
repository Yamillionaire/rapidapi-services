# DriftCheck: Studio listing notes (for the browser-lane listing session)

Prepared 2026-10-31 at build time. The listing itself (Studio
create/PRIVATE, plans, proxy-secret wiring, publish, gateway test,
Spotlight) runs in the parent's browser lane, in SMALL CHUNKED TASKS
(basics, then endpoints, then pricing plus proxy secret) - monolithic
Studio sessions die silently (PIPELINE.md stage 7). Service is live
on Render first; see README section 12 for the service id and URL.

## Basics

- Name: DriftCheck
- Base URL: https://driftcheck.onrender.com (confirm the exact
  subdomain from the Render service record before saving; Render
  suffixes the name when the bare one is taken globally)
- Short description: Drift and quality checks for AI-generated images
  and video: grade a candidate against its reference before you spend
  another regeneration credit.
- Category: Artificial Intelligence / Media (provider's pick in
  Studio; the service is a media QA utility)

## Endpoints (3)

- POST /check-image - multipart or JSON. Inputs: candidate and
  reference, each as an upload (multipart fields candidate /
  reference), a URL (candidate_url / reference_url), or base64
  (candidate_base64 / reference_base64); optional expected_text.
  Returns drift_score, verdict (pass/warn/fail), score_composition,
  similarity (per-method parts, full-frame and best reference
  region), proportion (bbox shares, divergence, flag), text_check
  (OCR status and expected-text result), notes.
- POST /check-video - video (upload / video_url / video_base64) plus
  reference as above; optional frames (3-24, default 10). Returns
  per-frame drift scores, worst frames with timestamps, frozen_spans
  and the frozen flag, mean and worst drift, verdict.
- GET /health - status, limits, method inventory (open, no gate).

Full machine-readable spec: listings/driftcheck-openapi.json.

## Plans: bill PER REQUEST (one check of any allowed size = 1 request)

BASIC $0 / 100 requests per month; PRO $5 / 1,000; ULTRA $20 /
10,000; MEGA $60 / 50,000, all hard limits (the SwiftRead own-product
grid). Do not enable any per-file or per-megabyte metering if Studio
offers it.

## Proxy secret wiring (before publish)

1. In Studio, connect the API / open the security or proxy settings
   and copy the API's proxy secret.
2. Set it on the Render service as RAPIDAPI_PROXY_SECRET
   (render_api.py set-env, or the dashboard), then trigger a deploy.
3. VERIFY THE GATE AT THE SERVICE, not from the env write: POST
   /check-image without the header must return 401
   {"error": "unauthorized"}; with the header it must answer (a 422
   missing_parameter on an empty JSON body proves the gate passed);
   GET /health stays open. If the gate is not active after the first
   deploy, deploy once more and re-verify (the env write and the
   deploy can race; learned 2026-10-28 on GeoBase/SwiftRewrite).
   NOTE: the service was gate-tested at build time with a temporary
   secret and the secret was then REMOVED, so pre-listing it answers
   without a header like the lane's other unlisted services; the
   Studio secret is the one that must end up set.
4. Publish, then run the Hub gateway test end to end (subscribe the
   owner's test account to BASIC first): POST /check-image through
   driftcheck.p.rapidapi.com with the Break emblem sticker vs the
   Break model sheet (files in the workspace) - expect 200 with
   drift_score 68.9, verdict fail, proportion flag raised. A
   cold-start timeout on the first call is the known free-tier
   behavior; retry once before treating it as a failure.

## Spotlight (after publish, same session)

Description must stay UNDER 280 characters. Draft (223 chars):
"DriftCheck grades AI-generated images and video against their
reference before you spend another credit: drift score, emblem-scale
proportion flags, text check, per-frame video grading, frozen-frame
detection. Proof inside."
Post via the URL tab with the GitHub blob URL of
docs/driftcheck-reliability.md (the File tab rejects markdown; use
the blob URL of the pushed file on
github.com/Yamillionaire/rapidapi-competitors).

## Honesty notes for the overview copy (do not oversell)

- v1 similarity uses classical metrics (hashes, SSIM, histograms),
  not a learned embedding; the listing copy must not claim
  face/identity recognition. Against multi-panel model sheets the
  service grades scale, palette/structure drift, text, and motion
  integrity; identity-grade gating uses same-class references. The
  proof doc prints the measured wrong-character number (57.2) next
  to the right one (58.6) - keep that transparency; it is the lane's
  brand.
- OCR reports unavailable on this deployment (no tesseract on the
  host); do not list "OCR text verification" as a live feature -
  "text check (reports its own availability)" is the honest wording.
- No anatomy check in v1; do not imply one.
