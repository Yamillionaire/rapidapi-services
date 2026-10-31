# DesignBase - RapidAPI listing notes (prepared; publish PARKED)

Status: package complete, publish parked behind the owner's key
step (see "Key gate" below). Prepared for the parent's browser
lane to run in RapidAPI Studio once the key clears, exactly as
FactBase's package was prepared.

## Basics

- API name: DesignBase
- Base URL: https://designbase.onrender.com
- Category: Artificial Intelligence/Machine Learning (same as
  DriftCheck and FactBase).
- Short description (neutral, no overclaim): "Design intelligence
  for creators, not an image generator. Send a brief and get
  structured color palettes with code-validated hex values and
  computed WCAG contrast ratios; send a product, audience and
  vibe and get a structured design brief; send a subject and
  style and get a production-ready image-generation prompt built
  from a prompt-grammar table; upload a design and get a scored
  critique with specific fixes."
- Overview copy rules: describe it as design intelligence.
  Never imply it generates images. The honesty split belongs in
  the overview: hex validity and contrast ratios are computed in
  code; palette choices, brief content and critique scores are
  labeled model judgments. /image-prompt is assembled in code
  and works without the reasoning engine.

## Endpoints (from listings/designbase-openapi.json)

- GET /health (no auth at the origin; engine states + limits)
- POST /palette {brief, count? (default 3, cap 5)}
- POST /design-brief {product, audience, vibe}
- POST /image-prompt {subject, style, era?, product?}
  (code-assembled; no engine needed)
- POST /critique (multipart, field "image" or any file part;
  png, jpeg, gif, webp; 8 MB cap; optional "context" field)

## Plans (monthly, PER REQUEST, hard limit)

- BASIC $0 / 100
- PRO $5 / 1,000
- ULTRA $20 / 10,000
- MEGA $60 / 50,000

## Key gate (must clear before proxy-secret wiring and publish)

1. The owner adds GEMINI_API_KEY to the DesignBase Render
   service - the same key he added for SwiftRewrite/
   SwiftTranslate (and the one FactBase is parked on); or
   provides it through the Secure Vault. The Gemini connector
   credential cannot be extracted into hosting, so this is his
   step alone (decision queue item 11).
2. On his word: redeploy, run the deployed proof battery with
   real briefs (designbase/tests/run_tests_deployed.py shapes
   against the deployed URL), and confirm palettes, a brief and
   a critique come back real.
3. Only then: create the Studio listing from
   listings/designbase-openapi.json, wire the RapidAPI proxy
   secret (set RAPIDAPI_PROXY_SECRET on the Render service to
   the value Studio shows; the Render dashboard is the fallback
   route if the env-var API route stalls, per the FactBase
   build-time caveat), point the gateway at
   https://designbase.onrender.com, run the gateway test, and
   publish only when the test passes with real responses.
   Note: /image-prompt would pass a gateway test even before
   the key lands because it is code-assembled; publish still
   waits for the key, per the lane precedent, so no endpoint on
   the published listing answers 503.

## Spotlight draft (post after publish; under 280 characters)

Title: "DesignBase reliability proof"
Description (215 chars): "DesignBase returns palettes with
code-validated hex and computed contrast, structured briefs,
grammar-built image prompts, and scored critiques with fixes.
Local battery 16/16, deployed proof in the reliability doc."
URL tab: the GitHub blob URL for docs/designbase-reliability.md
in Yamillionaire/rapidapi-services (main branch).
