# Spec: SwiftHumanize

Directed by the user 2026-11-01 ("I need to create an API where when
you're writing it doesn't sound like an AI writing. Whatever we're
writing."), with the home-base addition the same day ("we'll put that
on our own base as well"). This is a user-directed fleet product, not a
competitor clone: it enters the pipeline at the Build stage.

## How this differs from SwiftRewrite

SwiftRewrite is a general paraphraser: it puts text into different
words (modes standard, fluency, creative), and changing the wording is
the point. SwiftHumanize does one job only: keep the writer's meaning,
facts, and as much of the wording as possible, while removing the
patterns that make text read as AI-generated and restoring natural
human rhythm. It also adds a /score analysis endpoint that SwiftRewrite
does not have, tone control aimed at voice rather than variety, and an
optional style_sample so the output can match a specific person's
writing voice. Different job, different prompt, different buyer.

## The product

- POST /humanize: {text, tone (keep, casual, professional), strength
  (light, standard, strong), style_sample optional}. Returns the text
  sounding like a person wrote it.
- POST /score: {text}. Analysis only, no rewrite: AI-tell phrase counts
  with examples, em-dash count, sentence-length uniformity statistics,
  and an overall human-likeness score labeled heuristic.
- GET /health: open, no gate.

## Hard requirements

- Meaning, facts, names, numbers, and quoted material preserved
  exactly. Names, numbers, and quoted spans are extracted before the
  model call and verified in the output; the response reports what was
  verified, and a failed verification triggers one corrective retry.
- AI tells removed: stock transitions and filler ("delve", "moreover",
  "furthermore", "it's important to note", "in today's fast-paced
  world"), padded triplets, uniform sentence length, over-formatting.
- Rhythm varied on purpose: mixed sentence lengths, natural
  contractions where the tone allows.
- No em-dash characters anywhere in the output. The character is
  replaced during post-processing if the model produces one, so the
  guarantee holds even when the model slips.
- Honest engine labeling on every response ("gemini" vs a labeled
  built-in cleanup when no key is configured). Nothing is faked.

## Honest scope

This service improves naturalness and removes common AI tells. It does
not guarantee passing any AI detector, and AI detectors are themselves
unreliable; /score is a heuristic reading of surface patterns, not a
detector verdict. The spec, README, and listing copy all say this
plainly.

## Limits

Text 10 to 5,000 characters; style_sample up to 3,000 characters.
Every rejection states the limit and the length received (the fleet's
standing fix from the SwiftRewrite spec).

## Engine

Gemini Flash (gemini-3.6-flash default) through the fleet's existing
Gemini route, the same REST shape SwiftRewrite and SwiftTranslate use.
Temperature ladder by strength: light 0.5, standard 0.7, strong 0.85.

## Deployment, two lanes

1. Fleet lane: Render free tier from the fleet repo, then a RapidAPI
   listing prepared to one-tap state. The new Render service needs the
   user's own GEMINI_API_KEY in its environment (the same key step
   already parked for FactBase, DesignBase, and ActorBase; the
   connector-held key cannot be read out), and the RapidAPI proxy
   secret comes from Studio when the API is connected there.
2. Home lane: the same code on this machine as a systemd user unit
   (swifthumanize-home.service, port 8115, bound to 127.0.0.1,
   secret-gated except /health), with the engine reached through the
   local connector bridge pattern proven on FactBase and DesignBase
   home testing, so no key value is stored on this machine either.

Keep-warm: adding an eighteenth Render service re-budgets the window
to 09:00-10:10 ET (70 minutes x 18 services x 31 days = 651 hours,
under the 750-hour workspace cap).

## Pricing (RapidAPI, hard limits, monthly quotas of requests)

BASIC $0 / 250, PRO $3.99 / 3,500, ULTRA $9.99 / 25,000,
MEGA $24.99 / 50,000. Net after the 25% fee: $2.99 / $7.49 / $18.74.
One request is one call up to the 5,000-character cap, never metered
per character.

## Costs

Zero marginal cost beyond the existing Gemini API usage on the user's
own key (a humanize call is a fraction of a cent of model usage).
Nothing new is purchased.
