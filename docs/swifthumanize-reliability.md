# SwiftHumanize: proof results (2026-11-01)

Live proof of the service described in spec-swifthumanize.md, run
against the real Gemini engine through the fleet's connector route.
Full before-and-after texts are in swifthumanize/proofs/proof-results.md
in this repository; this page is the summary the listing links to.

## The three samples plus the voice-match case

| Case | Score before | Score after | Preserved |
| --- | --- | --- | --- |
| Generic AI paragraph | 37 | 85 to 96 across runs | names, numbers, quotes |
| Stiff AI business email | 88 | 100 | all (dates, time, room, project, sender) |
| Assistant-style summary | 80 | 100 | all (12 percent, 94 percent, 8 minutes) |
| style_sample voice match | 76 | 80 | all (Patterson, November 9, November 4) |

Scores are the service's own heuristic pattern reading (tell phrases,
sentence-length variation, formatting), not an AI detector verdict,
and the service says so in every response.

## What the edits actually look like

- The generic paragraph lost all 17 tell phrases ("in today's
  fast-paced world", "moreover", "furthermore", "leverage",
  "cutting-edge", "serves as a testament") and came back in plain,
  uneven sentences a person would write.
- The business email reads like a real manager wrote it: "Our
  quarterly meeting is moving to March 14 at 2:30 PM in Conference
  Room B. We also pushed the Harrison project report deadline to
  March 21. Attendance is mandatory." Every fact intact.
- The voice-match case took a stiff company note and returned it in
  the sample's blunt voice: "We pushed back the delivery date for
  the Patterson order. The shipment arrives November 9 instead of
  November 4. We will let the client know today."

## Defects the proof process caught and fixed

- The model's thinking tokens were silently consuming the output
  budget and truncating long results mid-sentence. Fixed with a zero
  thinking budget for the edit call, a larger output budget, and a
  retry at maximum budget when a response reports MAX_TOKENS. The
  preservation checker caught the truncated numbers first.
- A rhythm rule was strengthened after one run merged an
  even-length summary into even lengths again; the rerun lands a
  short sentence in the run, as a person would.

## Guarantees verified on every proof call

- No em-dash character in any output (post-processing enforces it
  even when the model produces one).
- Names, numbers, and quoted spans verified in the output; one
  corrective retry fires automatically when verification fails.
- The engine label is honest on every response.

## Home lane

The same code runs on the owner's machine as a systemd user unit
(127.0.0.1 only, secret-gated except /health), engine reached
through a local connector bridge so no key is stored on the
machine. Kill-and-recover measured: 4.24 seconds from SIGKILL to
/health answering again.
