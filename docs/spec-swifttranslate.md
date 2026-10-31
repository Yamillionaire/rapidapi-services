# Spec H: SwiftTranslate

Approved by the user 2026-10-29 (full-queue automation authorization,
voice call). Score 66.

## The comparable listing

Google Translate by Hark Translate: 5,975 subscribers, rated 4/5
(41 votes), service level 84% (roughly one request in six fails at the
platform level), pricing Basic $0, Pro $9, Ultra $19, Mega $39.
Discussions carry a fresh, unanswered "API unreachable" complaint: the
endpoint simply stops answering and subscribers get silence. Endpoint
surface mirrors Google's Translate API v2: translate, detect,
languages.

## The fix

- Reachability: the service runs on the shared scaffold (explicit JSON
  error objects always, never a silent drop or a bare 500), plus a
  24-hour translation cache with stale-on-error serving: if the engine
  hiccups, a previously translated string is served flagged stale
  instead of failing. One automatic engine retry before any error is
  returned.
- Honest engine: Gemini 3.6 Flash does the translating; every response
  names the engine. Nothing is passed off as Google's own engine.
- The incumbent's $9 Pro tier is free here (the hook).
- Drop-in surface: same v2 paths and the same response envelope
  (data.translations / data.detections / data.languages) so incumbent
  code migrates by changing the host and key only.
- Documented limits: 5,000 characters per request; every rejection
  states the limit AND the length received.

## The one input needed

Same gate as SwiftRewrite: the hosted service needs the user's own
Gemini API key as a Render environment variable (the connector's key is
surrogate-held and cannot be read out, and the swiftrewrite service's
env cannot be read back). Until the key is in, /health reports the
engine as awaiting configuration and translate/detect return an
explicit 503 JSON error naming the problem. Nothing is published as
AI-powered until a live gateway translation verifies with
engine "gemini". (Pre-launch engine check through the connector,
2026-10-29: gemini-3.6-flash translated the Spanish test sentence
correctly with proper names intact in about 4.1s and detected French
in about 2.6s; two transient Google 503s were observed during testing,
which is why the service retries once and serves stale cache.)

## Pricing (RapidAPI, hard limits, monthly quotas)

BASIC $0 / 1,000, PRO $0 / 10,000 (incumbent charges $9 for this tier),
ULTRA $9 / 100,000, MEGA $29 / 500,000. Net after the 25% fee:
$6.75 / $21.75 on the paid tiers. Unit economics: a typical translation
is a few hundred model tokens, well under a tenth of a cent; the
5,000-character cap bounds the worst case.

## Costs and risks

Eighth Render service: keep-warm re-budgeted for the nine-service
final state (see keepwarm/): window 09:00-11:00 ET, 2h x 9 x 31 =
558h against the 750h workspace cap. Model quality is the product;
the cache and retry design is the reliability story against the
incumbent's 84% service level.
