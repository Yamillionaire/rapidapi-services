# Spec F: SwiftRewrite

Approved by the user 2026-10-28 ("Go"). Score 68.

## The comparable listing

Paraphrasing and Rewriter API by NeuralWriter: 5,632 subscribers,
rated 3/5 (21 votes), service level 99% but latency 9,978ms against an
overview that claims "Very Fast" and "NO limits"; paid tiers are in fact
capped at 1 request per second. Pricing: Basic $0 / 5 per day (Light
mode only), Pro $3.99 / 3,500, Ultra $19.99 / 25,000, Mega $34.99 /
50,000. Complaints: 500 server-down errors, unexplained "text is too
long or too short" rejections, free-limit complaints, unanswered
400/403 threads, and rewrites that change character names.

## The fix

- Speed: Gemini Flash answers in about 1-3 seconds, not 10.
- Honest limits: text 10 to 2,000 characters; every rejection states the
  limit AND the length received (the incumbent's most confusing error).
- Name preservation: capitalized names are extracted before the rewrite
  and verified in the output; the response reports names_preserved.
- Modes: standard, fluency, creative (temperature ladder).
- No silent failure: if the model is unreachable, a built-in rules
  engine answers instead and the response labels engine honestly
  ("gemini" vs "builtin-fallback").

## The one input needed

The connected Gemini connector's key is surrogate-held and cannot be
read out, so the hosted service needs the user's own Gemini API key as
an environment variable. He supplies it through the secure entry flow
before publish; nothing is listed as AI-powered until the key is in and
a live AI-engine test passes.

## Pricing (RapidAPI, hard limits, monthly quotas)

BASIC $0 / 250 (vs 5 per day, light mode only), PRO $3.99 / 3,500
(price match, won on speed and honesty), ULTRA $9.99 / 25,000,
MEGA $24.99 / 50,000. Net after the 25% fee: $2.99 / $7.49 / $18.74.
Unit economics: a typical rewrite costs well under a tenth of a cent of
model usage; the 2,000-character cap bounds the worst case.

## Costs and risks

Sixth Render service: keep-warm window shrinks to 09:00-12:00 ET
(3h x 6 x 31 = 558h, about 190h headroom). Model quality is the product;
the built-in fallback is a safety net, never the headline.
