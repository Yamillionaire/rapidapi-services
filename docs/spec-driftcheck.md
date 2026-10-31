# Spec: DriftCheck (generated-media drift / quality check; the user's own product, queue #12)

Originated by the user in a voice call on 2026-10-31: "Is there an API
we can create that does a quality check so that when there's drift on
imagery or videos you're able to locate that and fix the error before
actually spending too many credits? ... build a RapidAPI that does
that." He confirmed "proceed" the same call. Built under his standing
full-automation authorization for this lane (2026-10-29). Not a
competitor clone: a new product in the lane's house style, born from
his own production pipeline (the All Black Towns chapters and the
Elements merch runs), where generated art drifts from its reference
and every miss costs regeneration credits (a Seedance shot is 80
Higgsfield credits; a design pass is a ChatGPT quota slot).

## The product

POST a candidate image (or video) plus the reference it was supposed
to match; get a drift report back BEFORE the next credit is spent.
The report says WHERE the failure is (which component, which frames),
so the regeneration prompt gets fixed instead of blindly re-rolled.

- POST /check-image {candidate, reference, expected_text?} - each
  image as a multipart upload, a URL, or base64.
  - Similarity: subject art (foreground bounding-box crop) graded with
    classical metrics only - difference hash, perceptual hash (DCT),
    global SSIM, color-histogram intersection - per method and as a
    composite, full-frame and against the best-matching region of the
    reference (a model sheet is a collage; region search stops the
    sheet's layout from grading the candidate).
  - Proportion: foreground bounding-box share of frame (width %,
    height %, area %) for candidate and reference, divergence in
    points, and a flag past 20 points. This is the check that catches
    an emblem rendered at the wrong scale.
  - Text/emblem: OCR of the candidate when a tesseract binary exists
    on the host, compared with the caller-supplied expected_text. On
    the current deployment there is no tesseract, so the component
    reports itself unavailable in every response instead of guessing.
  - Headline drift_score = 0.7 x similarity drift + 0.3 x proportion
    penalty (penalty = min(100, 2 x largest divergence)); verdict
    pass <= 50, warn <= 65, fail above; a proportion flag or a missing
    expected text escalates the verdict to at least warn.
- POST /check-video {video, reference, frames?} - frames sampled
  across the full duration with ffmpeg, each graded against the
  reference; per-frame scores, the three worst frames with
  timestamps, and frozen-span detection (consecutive sampled frames
  with dhash similarity >= 0.97, sustained) with a flag, answering the
  user's standing motion-integrity rule (a motion clip stays in
  motion for its full duration).
- GET /health - version, limits, and an honest method inventory.

## What v1 deliberately does not claim

- No anatomy/pose check: no lightweight pose estimator deploys
  cleanly on the free tier, so the component is omitted, not faked,
  and /health says so.
- No identity verification against multi-panel model sheets:
  calibration measured a WRONG character grading 57.2 similarity
  drift against a sheet vs 58.6 for the right one - classical metrics
  cannot tell characters apart at that remove. The notes field of
  every /check-image response says so and directs callers to pass the
  approved same-class comp as the reference for identity-grade
  gating (against a same-class reference the metrics do separate:
  identical 0.0, two approved renditions of one character 42.2,
  frames of a real clip 11-39 against their start still).
- OCR unavailable on this deployment (no tesseract binary); the gap
  is reported per response, never silently skipped.

## Calibration anchors (measured 2026-10-31, full record in docs/driftcheck-reliability.md)

- Oversized-emblem reject (Break emblem sticker vs Break model
  sheet): drift 68.9 FAIL, proportion flag, divergence 49.2 width /
  36.5 height points (art fills 50.0% of frame width; the other four
  characters' emblem stickers measure 17.4-18.6%).
- Approved DJ Riot design vs its model sheet: drift 42.2 PASS,
  divergence 0.3 / 1.9 points.
- Identical pair: 0.0 PASS.
- Real 10s motion clip vs its start still: PASS, worst frame 39.4 at
  5.5s, mean 29.9, no frozen spans; a synthetic still-loop clip flags
  its full span and escalates to WARN at drift 0.4.

## Plans (to save in Studio, hard limits, per request)

BASIC $0/100mo; PRO $5/1,000mo; ULTRA $20/10,000mo; MEGA $60/50,000mo
(the SwiftRead own-product grid: one check, any size up to the caps,
is one request).

## Deploy

Render free plan, same repo: build `pip install -r
driftcheck/requirements.txt` (Pillow + numpy only), start `python
driftcheck/app.py`. ffmpeg/ffprobe ship in the local environment;
on Render's native Python image their presence must be verified on
the deployed /health (methods.video) - if absent there, /check-video
answers an explicit 503 engine_not_configured and /check-image is
unaffected. Keep-warm fleet becomes twelve services; the window is
re-budgeted to 09:00-10:50 ET (682h worst month vs the 750h cap).
