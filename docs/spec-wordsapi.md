# Spec G: WordBase Dictionary (wave 3, queue #7)

Approved by the user 2026-10-29 ("Yes" in a voice call). Score 66.

## The comparable listing

WordsAPI by dpventures: 1,561 subscribers, rated 2/5 (53 votes),
pricing Basic $0, Pro $10, Ultra $49, Mega $89. Complaint themes from
its own Discussions and reviews:
1. Valid, paid-up API keys rejected with 403 errors.
2. Discussions abandoned: spam threads sit unmoderated, real questions
   unanswered for years. The provider has effectively walked away.
3. Partial word records: fields silently empty for common words.

## The fix

Same public data the incumbent's product is built on (WordNet), served
on the scaffold behind our other six APIs, with the complaint cases in
the launch test set:
- No spurious 403s: the only auth boundary is the documented RapidAPI
  proxy-secret check, applied exactly as on our six live APIs; every
  rejection is an explicit JSON error object from the shared scaffold,
  never a bare 403 or a silent empty body.
- Complete records: every word WordNet knows returns its full record
  (definitions, part of speech, synonyms, examples, and every relation
  the data supports). A word the data does not know returns a clean,
  documented 404 JSON error, not a partial record.
- Supported product: the launch Spotlight and the weekly watch's
  Discussions sweep cover this API from day one (the incumbent's
  abandonment is the opening we are selling against).

## Scope v1

Endpoints mirror WordsAPI's well-known surface so switching costs a
base-URL change:
- GET /words/{word} - the full record: results[] (definition, part of
  speech, synonyms, antonyms, examples, typeOf, hasTypes, partOf,
  hasParts, memberOf, hasMembers, substanceOf, hasSubstances,
  similarTo, also, derivation, pertainsTo, entails, cause), syllables,
  pronunciation, frequency.
- GET /words/{word}/definitions, /synonyms, /antonyms, /examples,
  /typeOf, /hasTypes, /partOf, /hasParts, /similarTo, /also,
  /derivation, /pertainsTo - one relation per call.
- GET /words/{word}/pronunciation (IPA, converted from CMU ARPAbet),
  /syllables (count from CMU vowel phones; the split list is a
  documented orthographic approximation), /rhymes (derived from CMU
  pronunciations: same stressed-vowel ending), /frequency.
- GET /words - search: letterPattern (regex), lettersMin/lettersMax,
  partOfSpeech, syllablesMin/syllablesMax, frequencyMin/frequencyMax
  (Zipf), hasDetails filter, limit/page pagination.
- GET /health - open, no proxy secret, reports dataset vintage.

Data (all openly licensed, $0, no external API key):
- Princeton WordNet 3.1 database files (WordNet license: free for
  commercial use with notice). Definitions, examples, and every
  relation above are WordNet pointers, parsed from the raw dict
  files at runtime (offset index + on-demand line parse, reverse
  pointer index built at boot).
- CMU Pronouncing Dictionary 0.7b (CMU license, free use):
  pronunciations and syllable counts; rhymes derived from it.
- FrequencyWords en_50k (MIT; OpenSubtitles 2018 counts): frequency
  returned as an honestly labeled Zipf-scale estimate.
- Datasets download at boot when absent (GeoBase pattern): the
  WordNet tarball is 16MB, too large for the repo snapshot route.

Honest limits, stated in the listing: coverage is WordNet's lexicon
(about 147,000 lemmas; slang and proper names are out of scope),
pronunciation is a dictionary transcription (General American),
syllable splits are approximate, frequency is a subtitle-corpus
estimate, not a universal constant.

## Pricing (RapidAPI, hard limits, monthly quotas)

BASIC $0 / 1,000 (taste), PRO $0 / 10,000 (the hook: more free than
the incumbent's $10 Pro), ULTRA $39 / 300,000 (vs $49), MEGA $79 /
1,000,000 (vs $89). If RapidAPI caps requests below a target at a
given price point, save the platform maximum at that price and record
it (the GeoBase lesson). Net after the 25% fee: ULTRA $29.25,
MEGA $59.25. Marginal cost per call is effectively zero (static data,
no upstream), so generous free quotas are safe.

## Costs and risks

Seventh Render service; with the two parallel launches the same night
the fleet lands at nine services and the keep-warm window settles at
09:00-11:00 ET (2h x 9 x 31 = 558h worst month, about 190h headroom
under the 750h workspace cap). Memory is the watch item: the reverse pointer
index is built at boot from the WordNet dict files; measured locally
before deploy, and the synset store is offset-indexed on disk rather
than fully materialized if the footprint needs it. Dataset freshness:
WordNet 3.1 and CMUdict are stable reference works; frequency list
refreshes when upstream republishes.
