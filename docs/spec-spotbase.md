# SpotBase: spec (the user's own product, 2026-11-01)

SpotBase is the buildable core of Vibe.co's prompt-to-streaming-TV
product, reverse engineered the same day (see
docs/vibe-teardown-2026-11-01.md). Vibe sells two things fused
together: an AI creative step (brief in, finished 15 or 30 second
spot out) and a media step (licensed CTV placement, targeting and
measurement). SpotBase is the creative step as an API. It does NOT
place ads on TV, does not hold any ad network or DSP account, and
never claims to: placement needs the advertiser's own funded
platform account, which is a user tap. What SpotBase removes is
the blank page between a product brief and a production-ready ad
package, which is the work the Claude plus Higgsfield workflow
does by hand today.

Directed by the user in a live voice call on 2026-11-01 ("Reverse
engineer this and build a API"), under the lane's standing full
automation authorization for builds. No incumbent listing is being
competed with here; this is the user's own product, like
SwiftRender and SwiftRead.

## What it does

1. **Ad package from a brief.** POST /ad-package takes brand_name,
   product, audience, offer, call_to_action, tone and
   duration_seconds (15 or 30), plus optional website_url and
   region notes. It returns the complete package described below.
2. **Timed script, budget enforced in code.** Voiceover reads at
   about 150 words per minute, so a 30 second spot carries at most
   75 words and a 15 second spot at most 38; SpotBase enforces
   tighter budgets (72 and 36) so the read leaves air at the tail,
   with the end-card read inside the same budget. The script is built in timed segments
   (30s: hook, problem, product, offer, end card; 15s: hook,
   product and offer, end card), every segment carries its time
   range and word count, and the totals are computed and returned.
   A script that would overrun is trimmed at the offer segment and
   the trim is flagged, never silent.
3. **Shot list with Higgsfield-ready prompts.** One shot per
   script segment: time range, duration, visual description,
   camera move, a ready-to-paste generation prompt (16:9,
   cinematic language, product and setting from the brief, no text
   in frame because text is added in edit), a negative prompt, and
   a model suggestion (Kling or Seedance class). The end-card shot
   is a clean background plate on purpose; the card's text is an
   edit step, and the package says so.
4. **Voiceover, ready for our own lane.** The package carries the
   full voiceover text and a swiftread_payload: the exact JSON
   body for POST /speak on SwiftRead, with a voice suggested from
   SwiftRead's curated list by tone (warm: Aria; bold: Guy;
   friendly: Jenny; premium: Michelle; calm documentary:
   Christopher; urgent: Eric). Music direction is a written brief
   (mood, tempo, licensing note: library or original cleared
   music only).
5. **End-card copy.** Headline, subline, call to action, website,
   logo placement, optional QR code note (scan target equals the
   call to action destination), background plate reference and a
   hold of the final 4-5 seconds inside title-safe margins.
6. **Delivery spec and compliance checklist.** The CTV spec from
   the teardown (Vibe's published upload requirements plus the
   industry common denominator: -24 LKFS plus or minus 2 loudness,
   true peak at or below -2 dBTP, stereo 48 kHz audio at 192 kbps
   or better, no slates or letterbox decoration, captions note)
   returned as data by GET /delivery-spec and embedded in every
   package, with a pass-by-pass checklist for the finished file.
7. **Spec checker.** POST /check-spec scores a finished file's
   measured specs (duration, width, height, format, frame rate,
   constant frame rate, bitrates, channels, sample rate,
   loudness, true peak, file size) against the delivery spec and
   returns per-item pass, fail or not_checked verdicts, an overall
   verdict and a fix list. Items the caller did not supply are
   reported not_checked, never assumed.
8. **Component endpoints.** POST /script returns only the script;
   POST /shots returns only the shot list; GET /tones lists the
   supported tones and their voice suggestions; GET /health is
   open and states the engine state honestly.

## Engines

- **Built-in template engine: LIVE.** Deterministic, zero
  dependency, zero marginal cost. Scripts are assembled from
  tone-keyed segment templates filled from the brief, with word
  budgets enforced in code. This is the engine that runs with no
  key anywhere, and it is genuinely useful: timing, structure,
  prompts, spec and checklist are the product's spine.
- **Gemini engine: CODED, activates with the key.** When
  GEMINI_API_KEY is set (the same key the fleet's SwiftRewrite
  and SwiftTranslate services use), the script and shot visuals
  are drafted by Gemini Flash under a strict JSON contract and
  then passed through the same in-code budget enforcement and
  validation; any failure falls back to the built-in engine and
  the response labels which engine actually produced the package.
  On Render, pasting the key is the same parked user step already
  open for FactBase, DesignBase and ActorBase (decision queue
  item 11). The service is fully functional without it.

## Honesty limits

- SpotBase writes the package; it does not render video, generate
  clips or synthesize the voiceover itself. Generation happens in
  Higgsfield (or the caller's lane) from the package's prompts,
  voiceover in SwiftRead from the package's payload, assembly in
  the caller's editor or SwiftRender. The package is the product.
- It does not place ads, buy media, target households or measure
  campaigns. The delivery spec gets a finished file accepted by a
  platform; the platform account, funding and launch are the
  advertiser's own steps.
- Script quality from the built-in engine is structured and
  competent, not award copy; the response names the engine so no
  one mistakes template output for the Gemini draft.
- No storage: packages are computed per request and not persisted.

## Deployment

Render free web service "spotbase" (see render.yaml): build
`true` (zero dependencies, stdlib only), start
`python spotbase/app.py`. Non-health endpoints sit behind the
standard RapidAPI proxy-secret gate once RAPIDAPI_PROXY_SECRET is
set during the listing step; until then /health reports the gate
state honestly. Keep-warm fleet grows to eighteen services and
the window re-budgets to 09:00-10:10 ET (70 min x 18 x 31 = 651 h
worst month vs the 750 h free cap, about 99 h headroom).

## Pricing (planned, per request, hard limits)

BASIC $0/100mo; PRO $5/1,000mo; ULTRA $20/10,000mo; MEGA
$60/50,000mo, the lane's standard grid for the user's own
products.

## Costs of this build

Research, build, local proof, deploy: $0 spent. No paid API calls
(the Gemini engine was not exercised with a key), no credits
bought, no accounts created. The only costs are the shared Render
free instance hours, re-budgeted above.
