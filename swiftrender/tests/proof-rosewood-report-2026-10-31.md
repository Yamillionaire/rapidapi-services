# SwiftRender proof: Rosewood music video, lines 1-16 (2026-10-31)

**This is a PIPELINE PROOF SEGMENT, not the Gate 5 master.** It
covers lines 1-16 of 46 only, and the wordless beats (intro,
interlude A, the line 11/12 gap) are black fill where the finished
video will carry generated period imagery. Its job is to prove the
service end to end on the owner's real material: the Rosewood
studio master (MD5 verified f8a26ca20f409265ae3f3585f978090f, the
version of record), the real cut-sheet timing, and the 16 clips
already installed by the manual workflow.

Run by `proof_rosewood.py` against a locally booted instance of
the real service (the same code that deploys to Render). Machine
report: `proof-rosewood-2026-10-31.json`. Assembled segment:
`proof-rosewood-lines1-16.mp4` (32.9 MB, local only; it is binary
and is not part of the GitHub snapshot).

## Headline figure: the duration math

Computed in code from the real timing map (rule: ceil(span + 1.0 s
handle), min 3 s, max 10 s, per line):

- Needed spans, lines 1-16: 41.90 s in total.
- Right-sized generation requests: **66 s in total**.
- What the manual workflow actually generated: **160 s** (16 clips
  at the flat 10 s default).
- **Generation time never spent: 94 s, 58.8%**, with every line
  still holding its full needed span plus a 1.0 s handle.

## Auto-gate vs the manual gate: 16 of 16 verdicts identical

Each installed clip was imported through the service and gated
automatically (DriftCheck worst frame vs the clip's own first
frame, 10 sampled frames, plus freezedetect). Manual verdicts and
worst-frame scores are from qa-log-batch1/2/3.md (final installed
takes).

| Line | Manual | Manual worst | Auto | Auto worst | Agree |
|---|---|---|---|---|---|
| 1 | pass | 49.6 | pass | 49.4 | yes |
| 2 | warn | 60.6 | warn | 60.5 | yes |
| 3 | warn | 54.4 | warn | 54.4 | yes |
| 4 | warn | 57.8 | warn | 57.8 | yes |
| 5 | warn | 64.3 | warn | 64.0 | yes |
| 6 | pass | 46.4 | pass | 46.7 | yes |
| 7 | warn | 57.2 | warn | 57.1 | yes |
| 8 | pass | 38.0 | pass | 37.7 | yes |
| 9 | warn | 59.4 | warn | 58.7 | yes |
| 10 | warn | 59.0 | warn | 59.1 | yes |
| 11 | warn | 53.3 | warn | 53.3 | yes |
| 12 | warn | 26.0 | warn | 26.3 | yes |
| 13 | pass | 49.8 | pass | 49.7 | yes |
| 14 | warn | 54.8 | warn | 55.6 | yes |
| 15 | warn | 59.2 | warn | 59.4 | yes |
| 16 | warn | 56.9 | warn | 57.2 | yes |

Agreement: **16/16 verdicts identical**, worst-frame scores within
0.8 of the manual run on every line (small differences are frame
sampling at slightly different offsets; the manual logs sampled
the same 10-frame plan). No disagreements to report. Line 12 was
imported with its manual assembly note (approved in-point 5.0 s,
the latch-drop span) and the assembly used exactly that span.

## Assembly verification

- Timeline total (line 16 end): 63.50 s. Assembled output probed
  at 63.566 s: **delta +0.066 s**, inside the stated +/-1.0 s
  tolerance.
- Full decode: clean (ffmpeg decode with zero errors).
- Frozen spans: **none inside any clip-covered region**. The only
  frozen spans freezedetect reports are the two intentional black
  gap fills (0.00-10.57 intro, 32.33-42.63 interlude A), which are
  placeholder by design in a proof segment.
- Audio is the master: the assembled track and the studio master
  (trimmed to 63.50 s) were both decoded to 22050 Hz mono and
  compared sample by sample over 1,400,175 samples: correlation
  **0.9991**, RMS 3950.8 vs 3971.4 (the small level difference is
  the AAC encode at 192k). Verdict: is_master_audio = true.
- Loudness of the assembled segment: -15.94 LUFS integrated
  (loudnorm measurement of the master audio as muxed; the service
  measures and reports loudness, it does not normalize).
- Warn lines carried into the assembly report, as designed: 2, 3,
  4, 5, 7, 9, 10, 11, 12, 14, 15, 16 (the same 12 warns the manual
  workflow installed with reasons recorded).

## What this proves and what it does not

Proves: job creation with real timing math, the import adapter,
the automatic gate reproducing the manual gate exactly on real
material, timeline assembly with per-line approved spans against
the real master, and the verification chain (duration, decode,
frozen split, audio fingerprint). Does not prove: the Replicate
adapter's live generation path (parked on the owner's token), or
anything about lines 17-46, which the production run will book,
gate and assemble through this same service.
