# OCRBase: Studio listing notes (for the browser-lane listing session)

Prepared 2026-11-01 at build time. The listing itself (Studio
create/PRIVATE, plans, proxy-secret wiring, publish, gateway test,
Spotlight) runs in the parent's browser lane, in SMALL CHUNKED
TASKS (basics, then endpoints, then pricing plus proxy secret).
Service is live on Render first; see the registry's sweep-derived
originals section for the service id and URL.

## Basics

- Name: OCRBase
- Base URL: confirm the exact subdomain from the Render service
  record before saving (Render suffixes the name when the bare one
  is taken globally)
- Short description: Print OCR with every word scored: text,
  bounding boxes, and per-word confidence from Tesseract 5, honest
  named errors, handwriting labeled not supported.
- Category: Artificial Intelligence / Text Analysis (provider's
  pick in Studio)

## Endpoints (3)

- POST /extract - multipart file upload (field "file"), or JSON
  {"url": "..."} or {"image_base64": "..."}; optional "lang"
  (default eng; installed: eng, spa, fra, deu, por) and "pdf_page"
  (PDF first page at launch). Returns text in reading order, words
  with confidence and bounding boxes, mean_confidence computed in
  code, low_confidence_warning under 60, engine and version,
  processing_ms.
- GET /languages - the tessdata packs actually installed.
- GET /health - status, engine, limits (open, no gate).

Full machine-readable spec: listings/ocrbase-openapi.json.

## Plans (hard limits, monthly quotas, billed per request)

BASIC $0 / 100 pages; PRO $5 / 2,000; ULTRA $14.94 / 10,000;
MEGA $46.94 / 50,000. (Incumbent IRROR grid: $10.94 / $24.94 /
$56.94 - undercut by $10 where a tier exists; PRO is the wedge.)

## Proxy secret wiring (before publish)

1. In Studio, copy the API's proxy secret.
2. Set it on the Render service as RAPIDAPI_PROXY_SECRET
   (render_api.py set-env), then trigger a deploy.
3. VERIFY THE GATE AT THE SERVICE: POST /extract without the
   header must return 401 {"error": "unauthorized"}; with the
   header it must answer (a structured error on an empty body
   proves the gate passed); GET /health stays open. If the gate
   is not active after the first deploy, deploy once more and
   re-verify (env write and deploy can race; learned 2026-10-28).
   NOTE: the service was gate-tested at build time with a
   temporary secret that was NOT retained, so the origin currently
   sits GATED under that unrecorded value. Setting the Studio
   secret overwrites it; re-verify right after, before publishing.
4. Publish, then run the Hub gateway test: POST /extract through
   the gateway with any clear printed-text PNG - expect 200 with
   text, words, and mean_confidence. A cold-start timeout on the
   first call is known free-tier behavior; retry once.

## Spotlight (after publish, same session)

Description must stay UNDER 280 characters. Draft (about 250):
"OCRBase publishes its own test page: 202 words extracted at 96.5
mean word confidence, every word scored with a bounding box. Print
OCR on Tesseract 5, honest named errors, handwriting labeled not
supported. Proof inside."
Post via the URL tab with the GitHub blob URL of
docs/ocrbase-reliability.md on github.com/Yamillionaire/rapidapi-services.

## Honesty notes for the overview copy (do not oversell)

- Do NOT claim a speed record. Measured: about 5 seconds of engine
  time for a dense 300-DPI page on an unloaded host; processing_ms
  is reported per response. The incumbent's 4.7s average latency
  is comparable; our wedge is confidence data, errors, and price.
- Handwriting is NOT supported and must be labeled as such, never
  implied. Print and typed documents only.
- Languages are exactly the five installed packs; /languages is
  the source of truth.
