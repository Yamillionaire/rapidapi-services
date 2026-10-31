# Spec: ActorBase (an acting engine for drama writing and performance; the user's own product, queue #16)

Originated by the user in a live voice call on 2026-10-31:
"Can we create an actor API that we can develop and make good
for drama writing?" - refined in the same call: "Or just actor
API. It's actor, so it should be able to do all forms of acting."
Built under his standing full-automation authorization for this
lane (2026-10-29). An original product in the lane's house style,
in the Base family (GeoBase, WordBase, WhoisBase, NewsBase,
XBase, DriftCheck, FactBase, DesignBase).

The name is the scope: not a drama-writing plug-in, but an actor.
Stage, screen and voice acting share one craft underneath -
objectives, tactics, beats, subtext - and ActorBase makes that
craft callable, with performance (acted speech) as the output,
not just notes about performance.

## The product

- POST /perform {text, emotion?, intensity? (1-5, default 3),
  voice?, persona?} - performs the text as acted speech.
  Returns the MP3 (base64), the measured duration, the delivery
  actually used (the delivery-table row as applied), the full
  segment-by-segment delivery plan, and the plan rendered as an
  SSML-style score. Emphasis is marked in the text with
  asterisks (*ours*) and realized in code (see below). Works
  with NO Gemini key: the performance engine is self-contained.
- POST /table-read {lines: [{speaker, line, direction?,
  emotion?, intensity?, pause_after_ms?}], cast: {speaker:
  voice id | persona name | {voice?, persona?, emotion?,
  intensity?}}} - performs a scene read with one distinct voice
  per speaker, stitched into one MP3, with a measured per-line
  timing map (start, end, duration per line) so a writer can
  hear and see the scene's rhythm. Free-text directions are
  interpreted into the fixed delivery vocabulary by the
  reasoning engine when it is live (one batched call); when it
  is not, they are carried through uninterpreted and the
  response says so in `warnings`.
- POST /character {description, name?, play_context?} - the
  actor's character build: name, objective and super-objective
  (action sentences), obstacles, tactics (action verbs with a
  phrase each), backstory beats, given circumstances, voice
  notes, physicality notes. Working acting craft vocabulary
  throughout: actions and verbs, not adjectives.
- POST /three-reads {line, context?, voice?, persona?} - three
  genuinely different deliveries of the same line: a different
  tactic and subtext per read, each performed as its own MP3
  with its delivery notes and plan, so a drama writer can hear
  which read lands.
- POST /scene-notes {scene_text} - acting analysis: beats
  (what changes, where it turns, the subtext), power shifts
  (where, from whom, to whom), and per character their wants,
  what they hide, and the tactics they use, plus a summary of
  what the scene is really about.
- GET /health - version, both engine states, the delivery
  table summary, the persona roster, limits.

Responses are JSON with the MP3 base64-encoded: a performance
is audio PLUS its delivery notes and timing map, and the notes
are half the product. (SwiftRead returns bare audio because it
is a reading pipe; ActorBase is an instrument.)

## The delivery table (fixed, in code, verbatim)

Emotion x intensity becomes engine prosody in exactly one
place (`delivery_params`). Signature values hold at intensity
3; each intensity point moves by the step, and every step
deepens its signature (same sign), so higher intensity always
means more of the emotion. Rate and volume are percents, pitch
is Hz. Clamps: rate -50..+100, pitch -30..+30, volume -50..+50.

| Emotion | Rate | Pitch | Vol | Rate step | Pitch step | Vol step | Beat pause |
|---|---|---|---|---|---|---|---|
| neutral | 0 | 0 | 0 | 0 | 0 | 0 | 250 ms |
| joy | +6 | +6 | +4 | +2 | +2 | +1 | 200 ms |
| anger | +8 | +2 | +10 | +3 | +1 | +3 | 150 ms |
| grief | -12 | -6 | -4 | -3 | -2 | -1 | 450 ms |
| fear | +10 | +8 | -2 | +3 | +2 | -1 | 180 ms |
| tenderness | -6 | -2 | -4 | -2 | -1 | -1 | 350 ms |
| contempt | -4 | -4 | +2 | -1 | -1 | +1 | 300 ms |
| resolve | -2 | -2 | +6 | -1 | -1 | +2 | 300 ms |
| awe | -8 | +2 | -2 | -2 | +1 | -1 | 500 ms |
| guilt | -8 | -5 | -6 | -2 | -2 | -2 | 400 ms |

Performance planning, all in code: the text is segmented into
beats at sentence boundaries; an emphasis span becomes its own
segment with a fixed lift (pitch +4 Hz, volume +6%, rate -4%)
and a setting-off beat before it (the emotion's beat pause
halved, at least 120 ms); segments are synthesized individually
with their own prosody and stitched with measured silence built
from the engine's own silent frames. The plan is returned with
every performance (segments, prosody, pauses, measured
durations) and rendered as an SSML-style score string.
edge-tts's plain-text path does not accept raw SSML, so the
score is the documentation of the performance and the stitching
is its realization - stated here so nobody mistakes the score
for the mechanism.

Durations are MEASURED, never estimated: an in-code MPEG frame
parser walks the actual MP3 frames of every segment and of the
stitched whole, so the timing map is the audio's own timing.

## Personas (generic archetypes only)

ingenue (Aria, leans tenderness), leading-lady (Sonia, resolve),
leading-man (Guy, resolve), young-hero (Eric, joy), matriarch
(Michelle, resolve), patriarch (Thomas, contempt), villain
(Christopher, contempt), trickster (Jenny, joy), confidante
(Libby, tenderness), narrator (Ryan, neutral). A persona
supplies a stock Edge voice and a default emotional lean;
explicit voice / emotion / intensity fields override it. No
real actor's voice or likeness is imitated, and no persona is
named for a person.

## Engines (the honesty split)

- Performance: the SwiftRead synthesis path, reused - Microsoft
  Edge neural voices via edge-tts (322 voices, 142 locales, 75
  languages; actorbase/voices.json is the same catalog data),
  zero marginal cost, no key. Segment synthesis runs with
  per-segment retries, bounded concurrency, and SwiftRead's
  hard 85-second thread-join budget. A segment that fails after
  retries fails the performance with a structured 502: a
  performance with a missing beat is not shipped silently
  (unlike an article read, where SwiftRead skips and discloses).
- Reasoning: the owner's Gemini API. Primary gemini-3.6-flash,
  fallback gemini-3.1-flash-lite on the primary's 429 and on a
  persistent 500/503 (per-model quota buckets; fallback chosen
  by measurement during the FactBase build). Used for character
  builds, scene analysis, the three reads' tactics/subtext, and
  direction interpretation. Every reasoning response is
  shape-validated in code; a malformed or incomplete result is
  a structured 502, never padded out with invented craft.
- Code, never the model: the delivery table and all prosody
  math, segmentation and emphasis realization, casting
  resolution, MP3 measurement, the timing map, all validation.

## Engine states (honest by construction)

- Reasoning live / performance installed: everything runs.
- awaiting_key (no GEMINI_API_KEY): /character, /scene-notes
  and /three-reads answer an explicit 503 engine_not_configured;
  /perform and /table-read keep working on the performance
  engine alone (precedent: DesignBase's code-only /image-prompt
  works in its awaiting state). This is the deployed resting
  state until the owner completes the key step (see Launch
  state). There is no mock mode.

## Cost shape

The build spent $0. At runtime: performances cost nothing
(Edge voices, zero marginal cost, the SwiftRead economics);
reasoning rides the owner's own Gemini API key (his existing
key, shared with SwiftRewrite, SwiftTranslate, FactBase and
DesignBase; Gemini API free-tier quota covers this volume, and
any paid usage is on his own Google account, not a new
service). No new account, no new purchase, no new terms were
agreed for this build.

## What v1 deliberately does not claim

- Not a human actor: the voice is synthesis under a generic
  archetype. The delivery notes describe exactly what the
  delivery table did, and emotional range is bounded by that
  table - ten emotions, five intensities, fixed prosody steps.
  Nuance beyond the table is not claimed.
- No imitation: personas are craft archetypes mapped to stock
  voices. No endpoint takes a real person's name as a voice or
  style target, and none will be added.
- The reasoning engine's craft (tactics, subtext, beats) is
  model judgment, labeled by its presence in a reasoning
  response; the performed prosody that realizes it is computed
  in code and reported exactly.
- Table reads cap at 40 lines / 12 cast / 8,000 characters;
  scenes at 12,000 characters; a single performance at 2,000
  characters. Longer work splits into calls.

## Plans (to save in Studio, hard limits, per request)

BASIC $0/100mo; PRO $5/1,000mo; ULTRA $20/10,000mo; MEGA
$60/50,000mo (the own-product grid). Each request runs real
synthesis and, on the reasoning endpoints, real model work;
the per-request price reflects that.

## Launch state at build (2026-10-31)

Built and deployed on Render; proven end to end LOCALLY with
the real engines (Gemini calls routed through the user's
connected Gemini API via the connector credential flow;
performances synthesized on the local edge-tts install where
the sandbox egress allows, and on the deployed service where
it does not - see docs/actorbase-reliability.md for the exact
split and the transport note) and proven on the DEPLOYED
service for gate behavior and the honest awaiting state.
PARKED at the key step, the lane's standing pattern
(SwiftTranslate, FactBase and DesignBase precedents):
GEMINI_API_KEY must be added to the ActorBase Render service
env by the owner (the same key he added for
SwiftRewrite/SwiftTranslate), because the deployed service
calls Gemini directly and the connector credential cannot be
extracted into hosting. Publish is parked behind the same
step: the RapidAPI gateway test would call a reasoning
endpoint through the gateway, and until the key lands the
honest answer there is the 503, so the listing stays
unpublished. On his word that the key is set, the finish runs
unattended: redeploy, the deployed proof battery with real
scenes, Studio listing, proxy-secret wiring, publish, gateway
test, Spotlight. Full record: docs/actorbase-reliability.md;
listing package: listings/actorbase-openapi.json +
listings/actorbase-listing-notes.md.

## Deploy

Render free plan, same repo: build `pip install -r
actorbase/requirements.txt` (edge-tts, the service's only
dependency, exactly as SwiftRead), start `python
actorbase/app.py`. Keep-warm fleet becomes sixteen services
(DesignBase #15 lands in the same window); the window is
re-budgeted to 09:00-10:20 ET (80min x 16 x 31 = 661h worst
month vs the 750h cap, about 89h headroom).
