# SpotBase - RapidAPI listing notes (prepared)

Status: package complete. SpotBase needs NO engine key to be
useful: the built-in template engine, the spec data and the spec
checker all run on code alone, so the listing can proceed as soon
as the Studio steps are run. The optional Gemini drafting engine
activates with the same GEMINI_API_KEY paste already parked for
FactBase, DesignBase and ActorBase (decision queue item 11); the
listing copy below describes it as an engine that activates with
the operator's key, never as live output, and every API response
names the engine that produced it.

PARKED USER STEP: creating the RapidAPI listing itself happens in
RapidAPI Studio in the user's own provider account (basics,
endpoints, pricing, proxy secret), and publishing is the user's
tap, per the lane's standing rule. This package is everything
those steps need; nothing here has been submitted to RapidAPI.

## Basics

- API name: SpotBase
- Base URL: set from the live Render service at listing time
  (see docs/spec-spotbase.md for the deployed URL; if Render
  assigns a suffixed subdomain, use it verbatim, the
  SwiftTranslate pattern)
- Category: Artificial Intelligence/Machine Learning (same as
  SwiftRender, DriftCheck, FactBase, DesignBase, ActorBase)
- Short description (neutral, no overclaim): "Turn a product
  brief into a complete streaming TV ad package: a timed 15 or 30
  second script with word budgets enforced in code, a shot list
  with ready-to-paste Higgsfield generation prompts, voiceover
  text with a ready SwiftRead payload, end-card copy, the CTV
  delivery spec and a compliance checklist, plus a checker that
  scores a finished file against the spec. It does not render
  video or place ads; placement stays with the advertiser's own
  platform account."
- Overview copy rules: the honesty paragraph from
  docs/spec-spotbase.md leads. Never "creates TV ads" without
  "package", never "places ads", never "runs on Hulu" or any
  channel name as a capability. Channel names may appear only
  inside the delivery spec context (what a finished file must
  satisfy to be accepted by platforms).

## Endpoints (from listings/spotbase-openapi.json)

- GET /health (no auth at the origin; engine and gate states)
- POST /ad-package (the full package from a brief)
- POST /script (timed script only)
- POST /shots (shot list with Higgsfield prompts, plus end card)
- POST /check-spec (finished file verdicts against the spec)
- GET /delivery-spec (spec data plus compliance checklist)
- GET /tones (tones, SwiftRead voice suggestions, music direction)

## Plans (monthly, PER REQUEST, hard limit)

- BASIC $0 / 100
- PRO $5 / 1,000
- ULTRA $20 / 10,000
- MEGA $60 / 50,000

## Spotlight draft (under 280 characters, no placement claim)

"SpotBase turns a product brief into a streaming TV ad package:
timed script, Higgsfield-ready shot prompts, voiceover text,
end-card copy, the CTV delivery spec and a finished-file checker.
You bring the platform account; it brings the package."

(243 characters. Post at launch per the lane rule: every new API
gets a Spotlight; keep it under 280 characters and let the
Spotlight URL carry the full spec doc on GitHub.)
