# SwiftRender: spec (queue #17, the user's own product, 2026-10-31)

SwiftRender accelerates the production pipeline AROUND video
generation. It cannot speed up any generation model's own rendering
or inference, and it never claims to: no API can make a frontier
model render faster. What it removes is the waiting, the waste and
the rework around generation, which is where the manual workflow
actually lost its time: clips generated at a flat 10 seconds when
the song only needed about 3, gates run by hand after the fact,
failed clips discovered late, and assembly done manually against a
timing sheet.

Directed by the user in a live voice call on 2026-10-31 ("Is there
a way to create an API that helps to make a video generate
faster?" -> the honest split -> "Proceed" / "Also create that
API" / "cloud based"). Built under the lane's standing full
automation authorization. No incumbent: this is the user's own
product, built from his own Rosewood production workflow.

## What it does

1. **Jobs with a timing map.** POST /jobs takes a title, the audio
   track (multipart upload or audio_url) and a timing map
   [{line_id, start, end}], plus per-line prompts. The service
   computes each line's needed span from the map and books a
   RIGHT-SIZED generation request in code: ceil(span + 1.0 s
   handle), minimum 3 s, maximum 10 s. The computation is shown in
   the job record. On the owner's real Rosewood lines 1-16 this
   books 66 s of generation against the 160 s the manual flat-10 s
   workflow generated: 94 s (58.8%) of generation time never spent.
2. **Import adapter (live).** POST /jobs/{id}/clips/{line_id}/import
   takes a clip generated anywhere (Muse's built-in generator,
   Seedance, any lane) as a multipart video part. Every clip flows
   through the same gate and assembly, so the service is genuinely
   useful today with no provider credential at all.
3. **Auto-gate on arrival.** Every imported or generated clip runs
   the DriftCheck engine in-process (worst sampled frame vs the
   clip's own first frame, 10 frames, the lane's verdict bands)
   plus ffmpeg freezedetect (n=0.003:d=2), automatically.
   Escalation coded on top: frozen coverage of 50% or more of the
   runtime fails the clip (the owner's motion-integrity rule: a
   motion clip stays in motion), any frozen span escalates a pass
   to a warn. Verdicts: pass, warn (installed, reason recorded),
   fail (never installed).
4. **Auto-retry queue.** A failed clip returns a corrected-prompt
   draft built in code from its failure class, using the same
   corrections that worked manually on Rosewood lines 9, 12 and 13:
   composition-replacement -> hold ONE stable composition, motion
   inside the frame only; text-artifact -> no text-bearing surfaces
   in frame; frozen -> continuous visible motion, no held frames;
   general drift -> hold subject, framing, palette and era. The
   line re-queues as awaiting generation with the corrected prompt
   and its right-sized duration. An import may also carry a
   caller-attested visual_failure (for example text_artifact: the
   drift metrics cannot read lettering and OCR is unavailable on
   this host, exactly as DriftCheck reports; the manual workflow's
   lettering catches on lines 12/13 were visual). That attestation
   is recorded as a gate failure of the named class, never hidden.
5. **Assembly.** POST /jobs/{id}/assemble refuses, listing the
   missing lines, until every line has a passing (pass or warn)
   clip and the job has its audio. It then cuts each clip's
   approved span (per-import approved_in_s; Rosewood line 12's
   latch-drop span at 5.0 s is the working example), lays the
   pieces on the job timeline at each line's start (gaps are black
   fill; a finished production fills them with their own beats),
   muxes the job's audio trimmed to the timeline, and returns an
   assembly report: per-line spans used, timeline total vs probed
   output duration, integrated loudness measured with loudnorm,
   frozen spans, decode check. The MP4 downloads from
   GET /jobs/{id}/output.
6. **Status.** GET /jobs/{id} returns the full job: timing math
   per line, every import with its gate report, the retry queue,
   missing lines, and the assembly report. GET /health is open and
   states engine and adapter states honestly.

## Provider adapters

- **import: LIVE.** The manual-lane adapter described above.
- **replicate: CODED, PARKED.** Seedance through Replicate (the
  owner's specced route: account yamillionaire, about $1.16 per
  5 s 720p shot at the rate on record). POST
  /jobs/{id}/clips/{line_id}/generate submits the line's prompt at
  its right-sized duration, polls, downloads the result and runs
  it through the same gate. Without REPLICATE_API_TOKEN it answers
  a clean 503 provider_not_configured with the prompt and duration
  that would be submitted. The owner provides the token through
  the Secure Vault (decision queue item 11). No account was
  created, no credit bought, and no paid generation was run for
  this build; the adapter's live path is unverified until the
  token lands, and the docs say so.

## Engines and honesty limits

- Gate metrics are the DriftCheck classical metrics (dHash
  similarity and frame-change measurement). They catch drift,
  composition replacement and frozen spans; they cannot read text
  (no OCR on this host) and cannot verify character identity. The
  visual_failure attestation exists precisely for the classes a
  human QA pass catches and the metrics cannot.
- Storage is a filesystem job store (SWIFTRENDER_DATA_DIR). On
  Render's free tier the disk is ephemeral: job records survive a
  process restart, not necessarily a full disk wipe. The service
  does not claim durable storage.
- Assembly output is 1280x720 at 30 fps, libx264 where the host's
  ffmpeg has it, mpeg4 fallback otherwise; the encoder used is
  named in every assembly report.
- This service needs no Gemini key. Its only parked step is the
  Replicate token.

## Deployment

Render free web service "swiftrender" (live at
https://swiftrender-yqqd.onrender.com, srv-dbj7kocs728c7391u68g;
see render.yaml): build
`pip install -r swiftrender/requirements.txt` (Pillow + numpy, the
DriftCheck engine's dependencies), start `python
swiftrender/app.py`. All non-health endpoints sit behind the
standard RapidAPI proxy-secret gate. Keep-warm fleet: seventeen
services, window re-budgeted to 09:00-10:15 ET (75 min x 17 x 31 =
658.75 h worst month vs the 750 h free cap, about 91 h headroom).

## Pricing (planned, per request, hard limits)

BASIC $0/100mo; PRO $5/1,000mo; ULTRA $20/10,000mo; MEGA
$60/50,000mo, the lane's standard grid for the user's own
products.
