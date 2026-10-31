# ActorBase - RapidAPI listing notes (prepared; publish PARKED)

Status: package complete, publish parked behind the owner's key
step (see "Key gate" below). Prepared for the parent's browser
lane to run in RapidAPI Studio once the key clears, exactly as
FactBase's and DesignBase's packages were prepared.

## Basics

- API name: ActorBase
- Base URL: https://actorbase.onrender.com
- Category: Artificial Intelligence/Machine Learning (same as
  DriftCheck, FactBase, DesignBase).
- Short description (neutral, no overclaim): "An acting engine
  for drama writing and performance. Perform a line as acted
  speech, hear a whole scene read by a cast of distinct voices
  with a measured timing map, build a character from objectives
  and tactics, get three genuinely different reads of the same
  line, and analyze a scene for beats, subtext and power
  shifts. Delivery is computed from a fixed table; voices are
  stock synthesis under generic archetypes, never imitations
  of real actors."
- Overview copy rules: describe it as an acting engine whose
  delivery is computed and reported exactly. Never "a real
  actor", never "indistinguishable from human performance",
  never emotion claims beyond the fixed delivery table. The
  honest limits from docs/actorbase-reliability.md belong in
  the overview: synthesis voices under generic archetypes,
  emotional range bounded by the table, reasoning content is
  model judgment while prosody and timings are computed.

## Endpoints (from listings/actorbase-openapi.json)

- GET /health (no auth at the origin; engine states + limits)
- POST /perform {text, emotion?, intensity?, voice?, persona?}
- POST /table-read {lines[], cast{}}
- POST /character {description, name?, play_context?}
- POST /three-reads {line, context?, voice?, persona?}
- POST /scene-notes {scene_text}

## Plans (monthly, PER REQUEST, hard limit)

- BASIC $0 / 100
- PRO $5 / 1,000
- ULTRA $20 / 10,000
- MEGA $60 / 50,000

## Key gate (must clear before proxy-secret wiring and publish)

1. The owner adds GEMINI_API_KEY to the ActorBase Render
   service (Render srv-dbj7440ae00c73dd3es0) - the same key
   he added for SwiftRewrite/SwiftTranslate; or provides it
   through the Secure Vault. The Gemini connector credential
   cannot be extracted into hosting, so this is his step alone
   (decision queue item 11).
2. On his word: redeploy, run the deployed proof battery with
   real scenes (actorbase/tests/run_tests.py shapes against
   the deployed URL), and confirm the reasoning endpoints
   return real builds, notes and reads.
3. Only then: create the Studio listing from
   listings/actorbase-openapi.json, wire the RapidAPI proxy
   secret (set RAPIDAPI_PROXY_SECRET on the Render service to
   the value Studio shows), point the gateway at
   https://actorbase.onrender.com, run the gateway test, and
   publish only when the test passes with real responses.
   Note: /perform and /table-read already work without the
   key; the gateway test target for the finish should be a
   reasoning endpoint (/character) so the test proves the
   whole service, not only its keyless half.

## Spotlight draft (post after publish; under 280 characters)

Title: "ActorBase reliability proof"
Description (192 chars): "ActorBase performs lines and
scenes for drama writers: a fixed delivery table, measured
timing maps, three reads that audibly differ. Local battery
and deployed proof: see the reliability doc."
URL tab: the GitHub blob URL for docs/actorbase-reliability.md
in Yamillionaire/rapidapi-services (main branch).
