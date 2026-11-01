# SentimentBase: no invented quota errors

The incumbent in this category (1,900 subscribers) has two verified
complaint themes in its own Discussions: callers told they are over
quota when they are not (a bogus "711" error with no path to
resolution), and a free tier that refuses calls the docs never
describe. SentimentBase answers both structurally: there is no code
path in this service that can invent a quota error, and the free
tier answers - 1,000 analyses a month.

## The launch battery (2026-11-01, 19/19 checks)

- Clearly positive text: score 0.9681, label positive, driving
  terms listed with their valences (love 3.2, amazing 2.8,
  excellent 2.7 - quoted from the caller's own text).
- Clearly negative text: score -0.9545, label negative.
- A mixed two-sentence review: NOT averaged into a mushy neutral.
  Sentence 1 scores 0.8439 positive, sentence 2 scores -0.7269
  negative, and the overall label follows the compound with the
  breakdown right there to audit.
- Bulk of 3 texts: 3 results; a bulk call with an empty middle
  item returns that item's error in place, not a failed batch.
- Errors are named and honest: text_too_long states the received
  length and the cap; an unsupported language returns 422
  unsupported_language instead of a confident wrong score.
- Every response reports the label thresholds it used
  (positive >= 0.05, negative <= -0.05) and the lexicon version,
  so scores are comparable across calls and across months.

## The engine, stated plainly

VADER (MIT-licensed lexicon and rules, built for social text:
capitalization, punctuation emphasis, negations, slang). It is a
lexicon, not deep understanding - sarcasm and domain jargon score
approximately, and the per-sentence breakdown exists so you can
see the approximation instead of trusting one number.
