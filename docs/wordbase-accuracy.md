# Your API key was never broken

WordsAPI (1,561 subscribers, 2/5 on 53 votes) built a paying audience
and then walked away from it: subscribers with valid keys report 403
errors, and its Discussions are an unmoderated spam archive where real
questions have sat unanswered for years. WordBase Dictionary was built
against those exact complaints:

| Complaint | WordBase's answer |
| --- | --- |
| Valid keys rejected with 403s | No home-grown auth to break: the only boundary is the standard RapidAPI gateway check, and every rejection is an explicit JSON error that says what happened, never a bare 403 |
| Discussions abandoned, spam unmoderated | Supported from day one: the weekly watch reads this API's Discussions and Reviews and verifies every claimed bug against the live service |
| Partial records, silently empty fields | Every word returns its complete WordNet record (147,478 lemmas) in one call: definitions, synonyms, antonyms, examples, and 15 relation types |
| A second service needed for pronunciation, syllables, rhymes | All in the same response, from the CMU Pronouncing Dictionary: IPA pronunciation, syllable count, derived rhymes |
| No frequency data | Zipf-scale frequency in the same call, labeled an estimate from the OpenSubtitles corpus |

Measured on the launch build (local test set, warm):
- "serendipity": complete record with definition, typeOf, derivation,
  5 syllables, IPA pronunciation, frequency, in under a millisecond of
  server time.
- "run": 57 senses across noun and verb (the incumbent's own data
  source holds them; our records do not truncate).
- "geese" resolves to "goose"; "running" resolves to its base forms.
- A word outside the lexicon returns a clean, documented 404 JSON
  error explaining the coverage, not an empty 200 or a mystery 403.
- "bank" (18 senses) answers in single-digit milliseconds.

Pricing answers too: Pro is free against their $10, Ultra $39 against
$49, Mega $79 against $89, and the free Pro tier carries 10,000
requests a month.

## v2: 26 languages (2026-10-31)

WordBase is now a multilingual dictionary. Add ?lang=<code> to any
endpoint (ISO 639-1, ISO 639-3, or the English language name) or call
GET /languages for the full list with entry counts, sources and
licenses. Without a lang parameter, English behaves exactly as v1.

What was verified for v2, and how:
- Every language shipped clears a stated bar: at least 20,000
  structured entries with definitions, or definitions plus English
  translations, counted from the downloaded source files (Open
  Multilingual Wordnet 1.4; FreeDict dictd dictionaries), never from
  project pages. The full survey table lives in docs/spec-wordsapi.md.
- Local battery 54/54 (wordbase/tests/run_tests.py): the English
  golden set is byte-for-byte identical to the pre-upgrade build
  (serendipity record, run's 57 senses, geese -> goose, search,
  documented 404s); the proxy gate still returns 401 without and
  with a wrong header; an unknown language returns 400 with the
  supported list; one source-verified lookup per shipped language
  (Spanish "entidad" -> translations ["entity"]; Japanese "cat"
  served with a Japanese definition plus its English gloss; German
  "Haus" -> "house" with IPA hˈaʊs; Russian "dog"; Greek
  "cosmodrome"; Arabic with IPA kitˈaab).
- Pronunciation exists only where a real source provides it
  (German, Russian, Hungarian, Esperanto, Arabic, Greek, via
  FreeDict IPA). For every other language the field is omitted and
  the pronunciation relation returns a documented 404 instead of a
  synthesized guess.
- FreeDict senses are translations and are labeled as such in every
  record (definitionSource). English-only filters (syllables,
  frequency) return an explicit 400 for other languages rather than
  being silently ignored.
- The honest ceiling: the surveyed sources support 33 languages at
  the same bar. Korean, Turkish, Vietnamese, Hindi, Czech, Ukrainian
  and Swedish are verified in Kaikki.org's Wiktionary extracts by
  full-file counts and wait on an offline compaction step, because
  the raw extracts run to gigabytes against the free tier's
  first-boot download pattern. 26 live today; 33 is the ceiling,
  stated as a ceiling.

Deployed verification (2026-10-31): GitHub commits 1396efcb +
3d0d3bc6, Render deploys dep-dbj7gcvlk1mc738fbtog +
dep-dbj7l9ss728c7391vqfg on srv-dbhfdb6c6qcc73f9geh0.
The first v2 deploy used a synchronous build at boot and took over
15 minutes to bind on Render; the shipped shape builds the index
in a background thread (English binds immediately, /health shows
multilingual_status "building", language endpoints answer an
honest 503 until it lands; the Render-side build took about 10
minutes against 45-100 seconds locally). Deployed battery
(wordbase/tests/battery-deployed-2026-10-31.json): 6/6 open checks
- health reports all 26 languages with per-language entry counts
identical to the local build, English legacy counts unchanged
(147,478 / 126,052 / 50,000), proxy gate 401 without and with a
wrong header. The authenticated half of the battery (54 checks,
passed locally) runs against the deployed service through the
RapidAPI gateway in the Studio pass that also updates the listing
copy; the production proxy secret is not readable from this lane.
