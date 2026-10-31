# DriftCheck: proof tests on the owner's own production files

DriftCheck exists because generated art drifts: in the owner's
Elements merch production, an emblem sticker shipped at the wrong
scale (the Break emblem at 50% of frame width where its four peers
sit at 17-19%), and every miss like it is paid for in regeneration
credits. These are the launch proof tests, run against the deployed
code on 2026-10-31 with the owner's real files. Raw responses:
driftcheck/tests/battery-2026-10-31.json.

## Test 1: the oversized emblem (the failure the service was built to catch)

Candidate: the Break emblem sticker (512x512 PNG) from the digital
sticker pack. Reference: Break's model sheet on file.

- Headline drift_score: **68.9, verdict FAIL**
- Similarity drift 56.2 (dhash 0.688, phash 0.734, ssim_global 0.041,
  color_histogram 0.289)
- Proportion: candidate art fills **50.0% of frame width** (62.9%
  height); reference foreground 99.2% / 99.4%; **divergence 49.2
  width points, 36.5 height points - FLAG RAISED** ("subject scale
  diverges from the reference by more than 20 points")
- Proportion penalty 98.4 - the term that separates this reject from
  an approved design (see test 2)
- Peer context, measured by the same code: the other four emblem
  stickers' art fills 17.4% (Mic Check), 17.6% (Tag), 18.6% (Ghost
  Writer) of frame width - Break's 50.0% is the outlier the owner
  caught by eye; DriftCheck catches it by number.

## Test 2: a known-good pair (approved design vs its model sheet)

Candidate: the approved ChatGPT DJ Riot character design. Reference:
DJ Riot's model sheet on file.

- Headline drift_score: **42.2, verdict PASS** - materially better
  than test 1's 68.9 FAIL
- Similarity drift 58.6 (best region: center; dhash 0.562, phash
  0.703, ssim_global 0.021, color_histogram 0.370)
- Proportion: divergence **0.3 width / 1.9 height points, no flag**;
  penalty 3.8
- Sanity pair, same character: two different approved DJ Riot
  renditions against each other grade 42.2 PASS as well.

## Test 3: a real motion clip vs its start still

Video: the Rosewood Chapter 5 "leaving at dawn" motion clip (10.0s,
built-in generation). Reference: its own start still.

- **Verdict PASS**; worst frame drift **39.4 at 5.5s**; mean 29.9
- Per-frame drift rises smoothly as the scene moves (11.2 at 0.5s to
  the 39.4 peak mid-clip, settling to 28.6 at 9.5s) - the signature
  of a healthy clip moving away from and within its start frame
- Frozen spans: none (correct - the clip stays in motion throughout)
- Frozen-detection control: a synthetic clip made by looping the
  still flags its whole span (0.2s-3.8s) and escalates to WARN even
  though its drift is 0.4 - a held frame cannot pass by matching the
  reference perfectly.

## The honest limits (measured, not assumed)

- **Identity vs collage sheets**: the wrong character graded against
  Break's model sheet returned similarity drift 57.2 - about the same
  as the right character's 58.6 against its own sheet. Classical
  metrics (hashes, SSIM, histograms) cannot confirm WHICH character a
  stylized drawing shows when the reference is a multi-panel sheet.
  DriftCheck says this in every /check-image response's notes and
  directs identity-grade gating to same-class references (approved
  comps, start stills), where the metrics separate cleanly: identical
  0.0, approved renditions ~42, real clip frames 11-39.
- **OCR**: no tesseract binary exists on the deployment host, so the
  text component reports status "unavailable" in every response
  rather than pretending to read lettering. The emblem's geometry is
  covered by the proportion report; lettering still wants the
  native-resolution zoom audit before shipping.
- **Anatomy**: v1 has no pose/anatomy check. No lightweight estimator
  deploys on the free tier; the check is omitted, not approximated,
  and /health says so.
- **Video on Render**: /check-video needs ffmpeg/ffprobe on the
  host. /health reports methods.video from the live deployment; if
  the binaries are absent there, /check-video returns an explicit
  503 engine_not_configured (never a fake result) and /check-image
  is unaffected.

## Gate and errors (verified in the same battery)

- POST without the X-RapidAPI-Proxy-Secret header: 401
  {"error": "unauthorized"}; /health stays open.
- Missing reference: 422 {"error": "missing_parameter"} with the
  accepted input forms named. Every failure is a structured JSON
  error object; there are no bare 500s or silent 204s.
