# SwiftRender: reliability and proof record (2026-10-31)

Spec: docs/spec-swiftrender.md. The service accelerates the
production pipeline around video generation; it does not and
cannot speed up a model's own rendering, and nothing in this
record claims otherwise.

## Proof on the owner's real material (the centerpiece)

A complete job ran locally against the real service code with the
real Rosewood inputs (studio master MD5 verified, cut-sheet
timing, the 16 installed line 1-16 clips). Full report:
swiftrender/tests/proof-rosewood-report-2026-10-31.md; machine
report swiftrender/tests/proof-rosewood-2026-10-31.json; the
assembled proof segment (proof-rosewood-lines1-16.mp4, 32.9 MB)
is kept in the tests folder locally only (binary, outside the
GitHub snapshot). It is a pipeline proof segment, NOT the Gate 5
master: lines 17-46 and the wordless beats are not in it and the
gaps are black fill.

- Duration math: needed spans 41.90 s; right-sized requests
  **66 s** vs the **160 s** the manual flat-10 s workflow
  generated; **94 s (58.8%) of generation time never spent**.
- Auto-gate vs manual gate (qa-log-batch1/2/3.md): **16/16
  verdicts identical**, worst-frame drift scores within 0.8 on
  every line. No disagreements.
- Assembly: output 63.566 s vs the timing map's 63.50 s (delta
  +0.066 s, tolerance +/-1.0 s); full decode clean; frozen spans
  only inside the two intentional black gap fills and none inside
  any clip region; audio verified as the master by decoded
  waveform comparison (correlation 0.9991 over 1.4M samples);
  loudness measured -15.94 LUFS integrated.

## Local battery (swiftrender/tests/battery-2026-10-31.json)

20/20 against a locally booted instance with a test proxy secret:
health open with honest adapter states; gate 401 without and with
a wrong secret; job creation (multipart audio upload) with the
duration math verified per line and in totals; the parked
Replicate adapter answering a clean 503 provider_not_configured;
a moving synthetic clip gating pass and installing; a fully
frozen clip gating FAIL, installing nothing, and returning the
frozen-class corrected prompt; the visual_failure text_artifact
attestation returning the no-text-bearing-surfaces corrected
prompt; assembly refusing with the missing line listed; assembly
succeeding after the line passed (duration delta 0.0, decode
clean, loudness measured); the output downloading through the
gate; final job status with an empty retry queue.

## Bugs found by the first battery run, fixed before the pass

1. DriftCheck's extract_frame raises on failure instead of
   returning a status tuple, and check_video's errors arrive as
   (status, payload) tuples: the first import crashed the handler
   connection. run_gate now normalizes both.
2. A fully frozen clip (solid frame, zero drift against its own
   first frame) gated only "warn" under the raw DriftCheck
   escalation, and would have installed. The gate now escalates
   on frozen COVERAGE: 50% or more of runtime frozen fails the
   clip (the owner's motion-integrity rule), with the escalation
   recorded in the gate report. This is a deliberate, documented
   extension of the DriftCheck bands, in the gate layer only;
   DriftCheck itself is untouched.

## Deployed state

DEPLOYED 2026-10-31: https://swiftrender.onrender.com
(Render service id and commit recorded in the registry entry and
README section 17 after the deploy lands.) The deployed battery
(swiftrender/tests/run_tests_deployed.py) runs a real small job
end to end through the gate because this service needs no engine
key; its results are recorded in
swiftrender/tests/battery-deployed-2026-10-31.json once run. The
build-time test proxy secret is then rotated to an unrecorded
value and re-verified (old value 401, no header 401, /health
open), per the DesignBase precedent, so the origin sits gated
under that value until the Studio step sets the real secret.

## Parked, honestly

- The Replicate (Seedance) adapter is coded and parked on
  REPLICATE_API_TOKEN (decision queue item 11). Its live path is
  UNVERIFIED: no token was available at build time, no account was
  created, no credit bought, no paid generation run. Until the
  token lands it answers 503 provider_not_configured with the
  prompt and right-sized duration that would be submitted.
- The RapidAPI Studio listing itself (create listing, wire the
  real proxy secret, publish, Spotlight) is prepared in
  listings/swiftrender-listing-notes.md + the OpenAPI file. This
  service needs no key gate, so nothing blocks it but the Studio
  steps themselves.

## Limits (stated, not hidden)

- The gate's metrics cannot read text (no OCR on this host) and
  cannot verify character identity; the visual_failure attestation
  at import is the bridge for human-caught classes.
- Storage is a filesystem job store; on Render's free tier the
  disk is ephemeral. Jobs are production working state, not an
  archive.
- Assembly normalizes to 1280x720/30 fps and fills timing gaps
  with black; a finished production books its wordless beats as
  lines in the timing map (the Rosewood plan does exactly that).
- Loudness is measured and reported, never normalized silently.
