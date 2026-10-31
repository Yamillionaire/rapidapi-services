# DesignBase Reliability Notes

Service: https://designbase.onrender.com (Render
srv-dbj6q967bikc73ej2kq0)
Spec: `docs/spec-designbase.md`. Local battery:
`designbase/tests/battery-2026-10-31.json`. Deployed battery:
`designbase/tests/battery-deployed-2026-10-31.json`.

## What DesignBase is, and what it is not

DesignBase is design intelligence for creators: structured color
palettes for a brief, structured design briefs, production-ready
image-generation prompts, and structured critiques of uploaded
designs.

It is NOT an image generator. No endpoint returns an image, and
nothing in the response pretends otherwise: /image-prompt returns
a prompt (text) that a caller's own generator can execute.

The honesty split is the design:

- Computed in code (facts): every hex value the model returns is
  validated against the hex grammar; invalid values are dropped
  and the drop count is reported in the response, never repaired
  by guessing. WCAG 2.x contrast ratios are computed from
  relative luminance (the battery independently recomputes the
  white-on-black ratio: 21.0, exact). /image-prompt is assembled
  entirely in code from a written prompt-grammar table. Uploaded
  image format and dimensions are read from the file header
  (magic bytes), not the filename. Critique scores are validated
  and clamped to 0-10 in code; an unusable score is reported as
  not scored, never replaced with a guessed number.
- Judged by the model (labeled judgments): which palettes suit
  a brief, the content of a design brief, and the critique's
  scores and fixes. The critique response carries a
  `judgment_source` field saying exactly this.
- Engine failure on a model endpoint returns an explicit 502
  engine_upstream_error. There is no mock mode and no staged
  design advice: while no Gemini key is configured, /palette,
  /design-brief and /critique answer an explicit 503
  engine_not_configured.

## Engines

- Reasoning and vision (palette selection, brief writing,
  critique): the owner's Gemini API. Primary model
  gemini-3.6-flash (the lane's deployed model, same as
  SwiftRewrite/SwiftTranslate/FactBase). Fallback model
  gemini-3.1-flash-lite, chosen by measurement on the owner's
  key during the FactBase build (per-model quota buckets are
  separate; gemini-2.5-flash is retired for new users,
  gemini-3.7/3.8-flash answered in about 77-84 s, 3.1-flash-lite
  in about 3 s with clean JSON).
- One extension over the FactBase client, made during this
  build and recorded here: the first battery run's critique
  call met a persistent 503 from the primary model and failed
  (15/16 on that run). A persistent 500/503 on the primary now
  falls back to the fallback model instead of failing the call,
  the same treatment a 429 already got. The re-run passed
  16/16 with the critique answered (see below). FactBase itself
  was not touched; whether to backport is a separate call.
- Prompt builder and color math: local code, no upstream, live
  in every engine state. /image-prompt therefore answers 200 on
  the deployed service even before the key lands, exactly as
  /health describes.

## Proof battery (local, live engines)

16 of 16 checks passed (`designbase/tests/battery-2026-10-31.json`,
final code). Phase A (no key configured): /health 200 with
reasoning state awaiting_key and both code engines live; gate
401 without the secret and 401 with a wrong value; /palette,
/design-brief and /critique answer the explicit 503
engine_not_configured through the gate; /image-prompt answers
200 through the gate. Phase B (engines live, through the
connector bridge described below):

- /image-prompt, era-locked (a solo b-boy freeze, comic style,
  era "the Bronx in 1983", product "a merch tee"): the prompt
  carries the era lock with the year, the negative prompt
  carries "no text" and "no modern objects", and the product
  framing is present in the components. Missing subject returns
  422 missing_parameter.
- /palette on a merch-tee brief (hip-hop DJ brand, bold,
  nightclub energy, must print on black and white tees), count
  2: two palettes returned; every hex passes the battery's own
  #RRGGBB check; every palette carries a background and a
  primary role and a computed contrast block; zero invalid hex
  values were dropped on this run (the validation count is
  reported either way). Empty body returns 422.
- /design-brief on a concert poster (jazz quartet, record
  collectors 30-55, 1962 Blue Note energy): full structure
  returned, 5 dos and 5 donts, typography and color directions
  populated. Missing vibe returns 422.
- /critique of a real design file from the owner's workspace
  (the DJ Riot hoodie back print, 1254x1254 PNG, context "back
  print of a character merch hoodie"): overall 7.8; composition
  7.0, color harmony 9.0, legibility 8.0, focal point 7.0, each
  with a note grounded in the actual image (background clutter
  competing with the character; the blue/white-on-black palette;
  the DJ RIOT wordmark's clarity); 4 specific fixes with
  priorities; the image block reports format image/png and
  1254x1254, read from the header in code. A non-image upload
  returns 422 unsupported_format.

Transport note: the local battery ran the service's unmodified
pipeline with its Gemini calls routed through the owner's
connected Gemini API via `designbase/tests/connector_bridge.py`
(local test tooling only, never deployed; the credential flow
belongs to the connector and the key was never printed or
logged). The deployed service calls the same Gemini REST
endpoint directly with the owner's key once he adds it to the
Render service.

## Deployed state, and the parked finish

Deployed battery (`designbase/tests/battery-deployed-2026-10-31.json`,
7/7): /health 200 (awaiting_key, engines named); gate 401
without the secret and 401 with a wrong value; through the gate,
/palette, /design-brief and /critique answer the honest 503
engine_not_configured, and /image-prompt answers 200
(code-assembled). No deployed engine calls were run: they
cannot return real palettes, briefs or critiques until the
owner adds GEMINI_API_KEY to the Render service (the lane's
standing key step; the connector credential cannot be extracted
into hosting). On his word that the key is set, the finish runs
unattended: redeploy, the deployed proof battery with real
briefs, Studio listing, proxy-secret wiring, publish, gateway
test, and Spotlight.

Gate state at handoff: a build-time test proxy secret was set
on the origin through the Render API (the env-var route worked
for this build, unlike FactBase's build day), the deployed
battery ran against it, and it was then rotated to an
unrecorded value with a fresh deploy (final live deploy
dep-dbj7097b9u1s73d7bef0). Verified after rotation: the old test
value and a missing header both answer 401, /health stays open.
The origin sits gated under that unrecorded value until the
Studio step sets the real RapidAPI proxy secret.

Publish is PARKED behind the key step by the lane's rule: the
RapidAPI gateway test must pass with real, working responses,
and /palette cannot return one until the engine is configured.
/image-prompt alone would pass a gateway test today, but
publish waits so that no endpoint on the published listing
answers 503. The full listing package is prepared
(`listings/designbase-openapi.json`,
`listings/designbase-listing-notes.md`).

Keep-warm: the fleet is now fifteen services; the window is
re-budgeted to 09:00-10:25 ET (85min x 15 x 31 = 659h worst
month vs the 750h cap, about 91h headroom).

## Limits, stated plainly

- Palette and critique quality is the model's judgment, and it
  varies by brief and image; the computed facts around it (hex
  validity, contrast) are exact, the taste is not guaranteed.
- The critique judges the single uploaded image as presented:
  it cannot judge print quality, physical color accuracy, or
  how a design survives a specific product's print process.
- The prompt grammar's presets cover the styles the owner
  uses; an unmatched style gets generic composition and
  lighting and the response says so. The assembled prompt is a
  strong starting point, not a guarantee about any particular
  generator's output.
- Contrast ratios are computed against the palette's own
  background color(s); a palette used on a different background
  needs its ratios recomputed for that pairing (any two returned
  hex values can be checked with the same WCAG formula).
