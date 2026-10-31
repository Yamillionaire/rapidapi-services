# ActorBase Reliability Notes

Service: https://actorbase.onrender.com (Render srv-dbj7440ae00c73dd3es0)
Spec: `docs/spec-actorbase.md`. Local battery:
`actorbase/tests/battery-2026-10-31.json`. Deployed battery:
`actorbase/tests/battery-deployed-2026-10-31.json`. Reasoning
supplement: `actorbase/tests/proof-reasoning-halves-2026-10-31.json`.
Live deploy at handoff: dep-dbj7atou01pc73elkulg (GitHub commit
7d7a2623).

## What ActorBase is, and what it is not

ActorBase is an acting engine for drama writing and performance:
it performs lines as acted speech, reads scenes aloud with a
cast of distinct voices, builds characters from objectives and
tactics, performs the same line three genuinely different ways,
and analyzes scenes for beats, subtext and power shifts.

It is NOT a human actor, and it does not claim to be:

- The voice is Microsoft Edge neural synthesis (the SwiftRead
  engine) steered by a FIXED delivery table: ten emotions, five
  intensities, prosody steps computed in code. Emotional range
  is exactly the table's range; nuance beyond it is not claimed,
  and every performance returns the table row and the full
  segment plan so a caller can see precisely what was done.
- Personas are generic craft archetypes (ingenue, villain,
  matriarch, trickster) mapped to stock voices. No real actor's
  voice or likeness is imitated, and no endpoint accepts a real
  person's name as a voice or style target.
- The reasoning content (tactics, subtext, beats, character
  builds) is Gemini model judgment. The performed prosody that
  realizes it, all timing, and all validation are computed in
  code. Every reasoning response is shape-checked in code; a
  malformed result is a structured 502, never padded with
  invented craft.
- Durations are measured, not estimated: an in-code MPEG frame
  parser walks the actual MP3 frames. Cross-checked in both
  batteries against ffprobe (agreement within 0.05 s on every
  proof) and non-silence proven with ffmpeg volumedetect.

## Engines, and how each was proven

- Performance (edge-tts, the SwiftRead synthesis path reused):
  per-segment synthesis with the segment's own prosody,
  bounded concurrency, per-segment retries, SwiftRead's hard
  85-second thread-join budget, stitched with measured silence
  built from the engine's own silent frames. A segment failing
  after retries fails the performance with a structured 502 -
  no partial performance ships.
- Reasoning (the owner's Gemini API): primary gemini-3.6-flash,
  fallback gemini-3.1-flash-lite on the primary's 429 and on a
  persistent 500/503 (per-model quota buckets; fallback chosen
  by measurement during the FactBase build). Proven locally
  through the connector bridge (below).
- Casting, the delivery table, segmentation, emphasis
  realization, MP3 measurement and the timing map are code.

## Proof, and the transport split (stated plainly)

The build sandbox's egress proxy stalls the Edge speech
websocket (two failure shapes observed: read timeouts, and a
101 "Invalid connection header" from the handshake) and
intermittently stalls HTTPS POSTs to onrender.com. The same
code path is proven working from the deployed host, whose
egress is direct (SwiftRead and DriftCheck hit the identical
split at their builds). The proof is therefore split, and each
half is labeled:

- LOCAL battery (`run_tests.py`, 13/18): everything except
  live synthesis passed, including the reasoning endpoints
  against the REAL Gemini engine through
  `actorbase/tests/connector_bridge.py` (the connector
  credential flow; no key read or printed): a full character
  build for Rosa Delgado (objective "I want to force my son to
  reverse the plant closure decision by using the exact
  leverage strategies I taught him", tactics as verbs - to
  corner, to shame, to interrogate...), scene notes on a
  two-person scene (4 beats, 3 power shifts, both characters
  with wants/hides/tactics), gate 401s, the awaiting 503s, and
  all five input-validation 422s. The 5 failures are exactly
  the synthesis-dependent checks, all 502 synthesis_failed on
  the sandbox transport - the endpoint behaved as designed
  (structured error, no partial performance).
- DEPLOYED battery (`run_tests_deployed.py`, 10/10) against
  the live service in its awaiting state, through the
  build-time test secret: /health honest; gate 401 without and
  with a wrong secret; the three reasoning endpoints answer
  the explicit 503; /perform of the grief battery line returns
  real audio (8.18 s measured, ffprobe 8.20 s, mean volume
  -23.0 dB) with the grief/intensity-4 table row (rate -15)
  and the emphasis segment realized; /table-read performs 3
  lines in 2 distinct persona voices (10.70 s, ffprobe 10.73 s,
  mean volume -20.5 dB) with a timing map that is ordered and
  spans the audio; the villain persona resolves to the
  Christopher voice with its contempt lean.
- REASONING SUPPLEMENT (`proof_reasoning_halves.py`, 2/2):
  the two local checks whose reasoning half the local battery
  could not surface (the endpoint discards the reads when
  synthesis fails, by design). Run against the real Gemini
  engine with ONLY the synthesis function replaced in the test
  process by measured silence (production code untouched): the
  three reads of "I never loved you." came back with genuinely
  different tactics - to repel (contempt, intensity 4), to
  protect (grief, 5), to convince (resolve, 3) - each with its
  own subtext and delivery note; and the directed table read
  interpreted "barely contained fury, each word weighed like a
  stone" to anger with direction_interpreted true, leaving the
  undirected line on its cast defaults. The audio half of both
  endpoints is the deployed battery's proof above.

One real bug was found and fixed by the deployed battery's
first run (8/10): an emphasis span ending exactly at a sentence
end left a lone "." segment, which is unspeakable (the engine
returns no audio) and failed the whole performance. The
planner now merges word-less beats into the adjacent beat -
spoken text unchanged - and word-less performance text is a
422. Fix commit 7d7a2623; the re-run passed 10/10 on deploy
dep-dbj798g473hc73bbjbu0.

## Deployed state, gate state, and the parked finish

The service rests in the honest awaiting_key state: /perform
and /table-read WORK deployed (keyless performance engine);
the reasoning endpoints answer 503 engine_not_configured. No
deployed reasoning checks were run: they cannot return real
builds until the owner adds GEMINI_API_KEY to the Render
service (the lane's standing key step; the connector
credential cannot be extracted into hosting).

GATE STATE at handoff: the build-time test proxy secret was
set through the Render API for the deployed battery, then
rotated to an unrecorded value with a fresh deploy
(dep-dbj7atou01pc73elkulg) and re-verified (no header 401, old
test value 401, /health open), so the origin sits gated under
that unrecorded value until the Studio step sets the real
secret. Auto-deploy did not fire on the fix push (the
SwiftRead behavior), so the fix deploy was API-triggered.

Publish is PARKED behind the key step by the lane's rule: the
RapidAPI gateway test must pass with real, working responses
on the reasoning endpoints, and it cannot until the engine is
configured. The full listing package is prepared
(`listings/actorbase-openapi.json`,
`listings/actorbase-listing-notes.md`). On the owner's word
that the key is set, the finish runs unattended: redeploy, the
deployed proof battery with real scenes (the listing notes
specify /character as the gateway test target so the test
proves the whole service), Studio listing, proxy-secret
wiring, publish, gateway test, Spotlight.

## Limits, stated plainly

- Emotional range is the delivery table's range: ten emotions
  x five intensities of rate/pitch/volume/pause shaping on a
  synthesis voice. It reads as directed delivery, not as a
  human performance, and the copy says so.
- Segment prosody is uniform within a beat: the engine's
  plain-text path takes per-call prosody, so within-sentence
  inflection rides on segmentation and emphasis spans, not on
  continuous pitch contouring.
- The three reads are as different as the reasoning engine
  makes them; the endpoint validates that three reads exist
  with tactics and subtexts, and the battery verified
  distinctness on the proof line, but a caller should read the
  returned tactics - the difference is in the response, not
  asserted by the marketing.
- Table reads cap at 40 lines / 12 cast members / 8,000
  characters; synthesis runs under an 85-second budget, so a
  maximum-size read in slow voices can hit the budget and
  fail with a structured 502 rather than truncating.
