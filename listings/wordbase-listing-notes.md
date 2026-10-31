# WordBase Dictionary - RapidAPI listing UPDATE notes (v2 multilingual, 2026-10-31)

Status: the API is already LIVE and published (Studio API ID
api_318c4e4a-2979-49cd-8e9f-91f2d04046f9). This is a copy update
only: description, endpoint list, and a Spotlight refresh, so the
listing states the new multilingual coverage with the real count.
Plans DO NOT change. Prepared for the parent's browser lane to run
in RapidAPI Studio (a subagent cannot operate the Studio UI).

## What changes in Studio

1. Long description / overview: replace the opening with the
   multilingual copy below (the v1 complaint-response body stays;
   docs/wordbase-accuracy.md carries the full v2 section for the
   Spotlight refresh).
2. Endpoints: add GET /languages (list languages with entry counts,
   sources, licenses) and document the optional `lang` query
   parameter on GET /words, GET /words/{word} and
   GET /words/{word}/{relation}. No endpoint is removed; English
   behaviour without `lang` is unchanged.
3. Plans: unchanged - BASIC $0/1,000mo, PRO $0/10,000mo,
   ULTRA $39/300,000mo, MEGA $79/1,000,000mo (hard).

## Short description (use verbatim)

"Dictionary API in 26 languages: definitions, synonyms, translations
to English, examples and word relations for 1.8M+ entries, with IPA
pronunciation, syllables and frequency for English. One call per
word, complete records, honest 404s - never a partial record or a
spurious 403."

## Overview opening (use verbatim)

"WordBase Dictionary now covers 26 languages. Every endpoint accepts
an optional lang parameter (ISO 639-1 or 639-3 code, or the
language's English name); without it, English answers exactly as
before. GET /languages lists all 26 with live entry counts, sources
and licenses.

Coverage: English 147,478 lemmas (WordNet 3.1, with CMU
pronunciation, syllables, rhymes and Zipf frequency); Spanish,
French, Italian, Portuguese, Dutch, Polish, Chinese (Mandarin),
Japanese, Finnish, Thai, Romanian, Malay, Indonesian, Catalan,
Basque, Galician, Croatian, Slovenian and Slovak from Open
Multilingual Wordnet, with English translations for every sense and
own-language definitions where the source wordnet carries them
(Japanese, Italian, Indonesian, Romanian, Slovenian, Greek, Arabic);
German (382,294 headwords), Hungarian, Russian and Esperanto from
FreeDict bilingual dictionaries, with real IPA transcriptions;
Arabic and Greek merge both sources.

Honest limits, stated up front: FreeDict senses are translations
and are labeled as such in every record; pronunciation is offered
only where a real source provides it and returns a documented 404
elsewhere rather than a synthesized guess; syllable and frequency
filters are English-only and return an explicit 400 for other
languages instead of being silently ignored."

## Spotlight refresh

Repost the Spotlight from docs/wordbase-accuracy.md (it now ends
with the v2 section) via its GitHub blob URL, same as the launch
post. Suggested Spotlight description (under the 280-character
limit): "WordBase Dictionary now speaks 26 languages: 1.8M+ entries
with definitions, translations, examples and relations, counted
from the open sources themselves. English is unchanged; every other
language is one lang parameter away." (231 characters)
