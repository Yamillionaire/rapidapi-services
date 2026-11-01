# SwiftHumanize

Writing in, writing out that sounds like a person wrote it.

SwiftHumanize does one job: it takes text that reads as AI-generated
and returns the same content in a natural human voice. It is not a
paraphraser (that is SwiftRewrite, the fleet's general rewriter, which
changes wording on purpose). SwiftHumanize keeps the writer's meaning,
facts, and as much wording as possible, and removes the patterns that
give machine writing away: stock transitions and filler ("delve",
"moreover", "furthermore", "it's important to note", "in today's
fast-paced world"), padded triplets, uniform sentence length, passive
constructions that hide who is acting, and over-formatting. Rhythm is
varied on purpose, and names, numbers, and quoted material are
extracted before the edit and verified in the output.

## Endpoints

- `GET /health` (open): status, engine state, limits, honesty note.
- `POST /humanize`: body {text, tone, strength, style_sample}.
  - tone: keep (default), casual, professional.
  - strength: light, standard (default), strong.
  - style_sample: optional writing sample; the output matches its
    voice (rhythm, vocabulary, formality) without reusing its content.
  - Returns the rewritten text, the engine label, preservation
    verification (names, numbers, quotes), and heuristic scores
    before and after.
- `POST /score`: body {text}. Analysis only, no rewrite: AI-tell
  phrase counts with categories, em-dash count, triplet and
  formatting counts, sentence-length statistics with a uniformity
  reading, and an overall human-likeness score.

Limits: text 10 to 5,000 characters; style_sample up to 3,000.
Every rejection states the limit and the length received.

## Honest scope

This service improves naturalness and removes common AI tells. It
does not guarantee passing any AI detector, and AI detectors are
themselves unreliable. /score is a heuristic reading of surface
patterns, labeled as such in every response, never a detector
verdict. No em-dash character ever appears in the output: if the
model produces one, post-processing replaces it, so the guarantee
holds even when the model slips.

## Engine

Gemini Flash (gemini-3.6-flash by default) through the fleet's
existing Gemini REST route. Two design points worth knowing:

- Thinking is disabled for the edit call (thinkingConfig budget 0).
  Proof testing caught the model's thinking tokens silently eating
  the output budget and truncating long results mid-sentence; the
  service also retries once at a larger budget if a response reports
  MAX_TOKENS, and the preservation check catches dropped numbers.
- Without a configured key the endpoint still answers, with a
  built-in cleanup engine that removes stock phrases, and the
  response labels the engine honestly ("builtin-cleanup").

## Running it

Fleet lane (Render): `python swifthumanize/app.py` with PORT set by
the platform, GEMINI_API_KEY in the service environment, and
RAPIDAPI_PROXY_SECRET once the API is connected in RapidAPI Studio
(requests except /health then require X-RapidAPI-Proxy-Secret).

Home lane (this machine): systemd user units
swifthumanize-home.service (127.0.0.1:8115, secret-gated except
/health via X-SwiftHumanize-Secret) and swifthumanize-bridge.service
(the connector bridge that reaches the Gemini engine with no key
stored on the machine; see home_bridge.py). Unit files and the env
template live in this folder; the env file itself
(swifthumanize-home.env, mode 600) is never committed. Proof of the
home lane, including the kill-and-recover timing, is in
proofs/home-lane-proof.md.

Proofs for the writing quality itself are in proofs/proof-results.md:
three samples plus a style_sample case, each with /score before,
/humanize output, /score after, preservation checks, and an operator
honest read.
