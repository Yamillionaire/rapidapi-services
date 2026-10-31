# Spec: DesignBase (design intelligence for creators; the user's own product, queue #15)

Originated by the user in a live voice call on 2026-10-31:
"Also, can we create a creative design API?" Built under his
standing full-automation authorization for this lane (2026-10-29).
An original product in the lane's house style, in the Base family
(GeoBase, WordBase, WhoisBase, NewsBase, XBase, DriftCheck,
FactBase).

Scope, set in the directive: v1 is design INTELLIGENCE, not an
image generator. DesignBase helps creators design: palettes,
briefs, generation prompts, and critiques. It never returns a
generated image, and the listing copy never implies it does.

## The product

- POST /palette {brief, count? (default 3, cap 5)} - palettes
  suited to the brief (brand mood, product, audience). Each color
  carries a hex value, a name, and a role (primary, secondary,
  accent, background, text). Every palette also carries a contrast
  block computed in code (see below).
- POST /design-brief {product, audience, vibe} - a structured
  design brief: concept direction, composition, typography
  direction (direction, headline, body), color direction, and a
  do/don't list, each item concrete and checkable.
- POST /image-prompt {subject, style, era?, product?} - a
  production-ready image-generation prompt assembled in code from
  a written prompt-grammar table: subject, medium/style,
  composition, lighting, an era lock when an era is given
  (period-accuracy language plus anachronism negatives), product
  framing when a product is given, and explicit negative
  constraints (no text, no lettering, no watermark, no distorted
  hands, no extra limbs). The grammar is the same discipline the
  owner uses in his merch and character work (one subject per
  generation, era pinned in every prompt, negative constraints
  always present). The response exposes the assembled components
  so a caller can see exactly what the grammar added.
- POST /critique (multipart image upload: png, jpeg, gif, webp;
  8 MB cap; optional "context" text field naming the intended
  use) - a structured critique: summary, four scored dimensions
  (composition, color harmony, legibility, focal point, each
  0-10 with a note), an overall score, strengths, and specific
  fixes (issue, fix, priority).
- GET /health - version, engine states, limits.

## Code vs model (the honesty split, by construction)

- Computed in code, never by the model: hex validation (every
  model-returned hex is checked against the hex grammar;
  invalid values are DROPPED and the drop count is reported,
  never repaired by guessing); WCAG 2.x contrast ratios for each
  palette (computed from relative luminance against the
  palette's background color(s); when no background role comes
  back, ratios are computed against white and black and the
  block says so); the whole /image-prompt assembly; uploaded
  image format and dimensions (read from the file header, magic
  bytes, not the filename); score validation for the critique
  (numeric, clamped to 0-10; an unusable score becomes "not
  scored", never a guessed number).
- Judged by the model (the owner's Gemini API), and labeled as
  model judgment in the response: which palettes suit a brief,
  the brief's content, and the critique's scores and fixes.
- Engine failure returns an explicit structured error (502
  engine_upstream_error), never an invented design judgment.
  There is no mock mode.

## Engine states (honest by construction)

- live: GEMINI_API_KEY set; /palette, /design-brief and
  /critique run.
- awaiting_key: no key yet; those three endpoints answer an
  explicit 503 engine_not_configured. This is the deployed
  resting state until the owner completes the key step (see
  Launch state). /image-prompt is code-assembled, needs no key,
  and keeps working in this state; /health reports all of this.

Engine: the owner's Gemini API. Primary gemini-3.6-flash (the
lane's deployed model), fallback gemini-3.1-flash-lite on the
primary's 429 (per-model quota buckets; fallback chosen by
measurement during the FactBase build). One extension over
FactBase, added after this build's battery met a persistent
primary-model 503 on the critique call: a persistent 500/503 on
the primary also falls back instead of failing the call.

## Cost shape

The build spent $0. At runtime the only upstream is the owner's
own Gemini API key (his existing key, shared with SwiftRewrite,
SwiftTranslate and FactBase; Gemini API free-tier quota covers
this volume, and any paid usage is on his own Google account,
not a new service). /image-prompt and all color math are local
code and cost nothing per call. No new account, no new purchase,
no new terms were agreed for this build.

## What v1 deliberately does not claim

- Not an image generator: no endpoint returns an image.
- Palette names and critique scores are model judgments,
  labeled as such; only hex validity and contrast ratios are
  computed facts.
- The critique sees one image at a time: no side-by-side
  comparison, no brand-consistency scoring across a set (that
  is DriftCheck's territory, against references).
- The prompt grammar covers the styles the owner actually uses
  (sticker, product photo, mockup, photoreal, comic, poster/
  vintage, watercolor, 3D render, vector/emblem); an unmatched
  style gets generic composition and lighting and the response
  says so.

## Plans (to save in Studio, hard limits, per request)

BASIC $0/100mo; PRO $5/1,000mo; ULTRA $20/10,000mo; MEGA
$60/50,000mo (the own-product grid). /image-prompt is
code-assembled, but it is billed per request like every endpoint
for plan simplicity; the listing notes say it needs no engine.

## Launch state at build (2026-10-31)

Built and deployed on Render; proven end to end LOCALLY with the
real engines (the service's unmodified pipeline, its Gemini calls
routed through the user's connected Gemini API via the connector
credential flow - see docs/designbase-reliability.md for the
battery and the exact transport note) and proven on the DEPLOYED
service for gate behavior and the honest awaiting state. PARKED
at the key step, the lane's standing pattern (SwiftTranslate and
FactBase precedents): GEMINI_API_KEY must be added to the
DesignBase Render service env by the owner (the same key he added
for SwiftRewrite/SwiftTranslate/FactBase), because the deployed
service calls Gemini directly and the connector credential cannot
be extracted into hosting. Publish is parked behind the same
step: the RapidAPI gateway test would call /palette through the
gateway, and until the key lands the honest answer is the 503, so
the listing stays unpublished. On his word that the key is set,
the finish runs unattended: redeploy, the deployed proof battery
with real briefs, Studio listing, proxy-secret wiring, publish,
gateway test, Spotlight. Full record:
docs/designbase-reliability.md; listing package:
listings/designbase-openapi.json +
listings/designbase-listing-notes.md.

## Deploy

Render free plan, same repo: build `true` (stdlib only, no
dependencies), start `python designbase/app.py`. Keep-warm fleet
becomes fifteen services; the window is re-budgeted to
09:00-10:25 ET (85min x 15 x 31 = 659h worst month vs the 750h
cap, about 91h headroom).
