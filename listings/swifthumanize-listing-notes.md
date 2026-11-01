# SwiftHumanize: Studio listing notes (for the listing session)

Prepared 2026-11-01 with the build. The service is deployed on
Render and proven; the Studio steps (create, plans, proxy secret,
publish, Spotlight) run in the browser lane. OpenAPI definition:
listings/swifthumanize-openapi.json.

## Basics

- Name: SwiftHumanize
- Short description: Rewrites AI-sounding text so it reads like a
  person wrote it. Facts, names, and numbers verified in the output;
  AI stock phrases stripped; natural rhythm restored. Plus /score, a
  heuristic reading of how AI-like a text's surface patterns are.
- Long description points:
  - One job, done properly: human voice, not paraphrase. Meaning,
    facts, names, numbers, and quotes are preserved and verified;
    the response reports the verification.
  - Tone control (keep, casual, professional), strength control
    (light, standard, strong), and an optional style_sample so the
    output matches a specific person's writing voice.
  - No em-dash characters in any output, enforced in
    post-processing, not just requested in the prompt.
  - /score returns tell-phrase counts, em-dash count, and
    sentence-length uniformity, labeled heuristic. Honest scope: the
    service improves naturalness and removes common AI tells; it
    does not guarantee passing any AI detector, and detectors are
    themselves unreliable.
  - Honest limits: 10 to 5,000 characters per call, and every
    rejection states the limit and the length received.
  - Live proof: docs/swifthumanize-reliability.md in the repo
    (three samples plus a voice-match case, scores before and
    after, defects caught during proving).

## Plans: bill PER REQUEST (quotas of requests, never per character)

BASIC $0 / 250 requests per month, PRO $3.99 / 3,500,
ULTRA $9.99 / 25,000, MEGA $24.99 / 50,000. One call up to the
5,000-character cap is one request. Confirm the plan unit reads
"requests" before publishing.

## Proxy secret step (after the API exists in Studio)

1. Copy the proxy secret Studio shows for this API.
2. Set RAPIDAPI_PROXY_SECRET to that value on the Render service
   "swifthumanize" and redeploy.
3. Verify the gate: a gateway call without the header returns 401
   from the origin, with it returns 200, /health stays open.
4. The Render service also needs GEMINI_API_KEY in its environment
   (the user's own key, the same parked step as FactBase,
   DesignBase, and ActorBase) before the listing can be presented
   as AI-powered; until then /health honestly reports the built-in
   cleanup engine.

## Spotlight (after publish)

Description must stay UNDER 280 characters. Draft (186 chars):
"SwiftHumanize rewrites AI-sounding text so it reads like a person
wrote it: facts and names verified, stock phrases stripped, rhythm
restored, plus a heuristic /score. Live proof inside."
Post via the URL tab with the GitHub blob URL of
docs/swifthumanize-reliability.md (the File tab rejects markdown):
https://github.com/Yamillionaire/rapidapi-services/blob/main/docs/swifthumanize-reliability.md
