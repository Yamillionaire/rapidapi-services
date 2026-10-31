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

## v2: Multilingual upgrade (2026-10-31)

User directive, live voice call 2026-10-31: "On the Word dictionary,
can you make that dictionary be for multiple languages? And figure out
how many languages can you put in WordBase."

### Answer to "how many"

**26 languages ship in v2** (English + 25), carrying 1,695,718
non-English entries. **The honest ceiling from the sources surveyed is
33 languages**: 7 more (Korean, Turkish, Vietnamese, Hindi, Czech,
Ukrainian, Swedish) clear the same quality bar in Kaikki.org's
Wiktionary extracts, verified by full-file counts (below), but ship
only after an offline compaction transform, because the raw Kaikki
files run 83MB to 1.2GB per language against the free tier's
first-boot download pattern. The two numbers are never blurred: 26
live, 33 source-supported.

### Quality bar (set for this upgrade, applied uniformly)

A language ships when a verified open source gives it at least 20,000
structured entries with definitions, or with definitions plus English
translations. Counts are computed from the downloaded files, never
quoted from project pages.

### Source survey (all files downloaded and counted 2026-10-31)

**Open Multilingual Wordnet 1.4** (via the NLTK distribution; one
26.6MB zip; per-wordnet licenses as listed). OMW senses key on
WordNet 3.0 synsets, so every OMW lemma inherits an English gloss and
an English lemma list (translations) from WordNet 3.0. Fields:
definitions (English gloss for all; own-language definitions where
the wordnet carries them), translations to English (all), examples
(own-language, where carried), pronunciation/IPA (none).

| OMW code | Language | Unique lemmas | With definition | Local def synsets | Example rows | License |
|---|---|---|---|---|---|---|
| als | Albanian | 5,985 | 5,985 | 4,675 | 3,324 | CC BY 3.0 |
| arb | Arabic | 17,783 | 17,783 | 0 | 0 | CC BY-SA 3.0 |
| bul | Bulgarian | 6,719 | 6,719 | 4,959 | 14,473 | CC BY 3.0 |
| cat | Catalan | 46,345 | 46,345 | 0 | 0 | CC BY 3.0 |
| cmn | Chinese (Mandarin) | 61,533 | 61,525 | 0 | 0 | WordNet license |
| dan | Danish | 4,467 | 4,467 | 0 | 0 | WordNet license |
| ell | Greek | 18,194 | 18,194 | 18,108 | 0 | Apache 2.0 |
| eus | Basque | 26,200 | 26,200 | 0 | 0 | CC BY 3.0 |
| fin | Finnish | 129,225 | 129,225 | 0 | 0 | CC BY 3.0 |
| fra | French | 51,339 | 51,339 | 0 | 0 | CeCILL-C |
| glg | Galician | 23,057 | 23,056 | 0 | 0 | CC BY 3.0 |
| heb | Hebrew | 5,325 | 5,325 | 3,748 | 0 | WordNet license |
| hrv | Croatian | 28,888 | 28,881 | 0 | 0 | CC BY 3.0 |
| ind | Indonesian | 36,608 | 36,608 | 12,663 | 0 | MIT |
| isl | Icelandic | 11,502 | 11,502 | 0 | 0 | CC BY 3.0 |
| ita+itx | Italian | 87,268 senses | 46,743 | 14,069 | 1,955 | CC BY 3.0 / ODC-BY 1.0 |
| jpn | Japanese | 91,936 | 91,936 | 117,659 synsets* | 96,552 | WordNet license |
| lit | Lithuanian | 11,379 | 10,042 | 0 | 0 | CC BY-SA 3.0 |
| nld | Dutch | 42,777 | 42,776 | 0 | 0 | CC BY-SA 4.0 |
| nno | Norwegian Nynorsk | 3,387 | 3,387 | 0 | 0 | WordNet license |
| nob | Norwegian Bokmal | 4,186 | 4,186 | 0 | 0 | WordNet license |
| pol | Polish | 45,140 | 45,140 | 0 | 0 | WordNet license |
| por | Portuguese | 47,086 | 47,086 | 0 | 0 | CC BY-SA |
| ron | Romanian | 49,831 | 49,831 | 58,754 | 0 | CC BY-SA |
| slk | Slovak | 29,087 | 27,075 | 0 | 0 | CC BY-SA 3.0 |
| slv | Slovenian | 40,052 | 40,052 | 3,177 | 4,162 | CC BY-SA 3.0 |
| spa | Spanish | 36,370 | 36,370 | 0 | 0 | CC BY 3.0 |
| swe | Swedish | 5,823 | 5,823 | 0 | 0 | CC BY 3.0 |
| tha | Thai | 82,504 | 82,504 | 0 | 0 | WordNet license |
| zsm | Malay | 33,903 | 33,903 | 0 | 0 | MIT |

*jpn local-def figure counts synsets with a Japanese definition row;
the file pairs each with an English gloss row (that pairing is what
the API serves as definition + englishDefinition).

19 OMW languages clear the bar on definitions alone. 11 fall under it
(Albanian, Bulgarian, Danish, Hebrew, Icelandic, Lithuanian, both
Norwegians, Swedish in OMW, Arabic, Greek) and do not ship from OMW;
Arabic and Greek are rescued by FreeDict (below).

**FreeDict** (bilingual dictionaries, dictd editions; headword counts
from freedict-database.json, verified against the downloaded dictd
index line counts, which match within the format's special entries).
Fields: English translations (all), IPA pronunciation (most entries),
part of speech / gender (where tagged), no definitions: these are
translation dictionaries and the API labels them as such
(definitionSource). Direction matters: only X-to-English pairs give
lookup in X.

| Pair | Headwords (verified) | License (package COPYING / info) |
|---|---|---|
| deu-eng (German) | 517,534 published; 519,343 entries parsed; 382,294 unique headwords | GPL-2.0 |
| hun-eng (Hungarian) | 139,935; 138,812 unique | GPL-2.0 |
| epo-eng (Esperanto) | 63,895; 63,463 unique | CC BY 3.0 |
| ara-eng (Arabic) | 52,996 | GPL (Arabeyes) |
| rus-eng (Russian) | 42,600; 42,281 unique | CC BY-SA 3.0 |
| ell-eng (Greek) | 41,714 | CC BY-SA 3.0 |

German, Russian, Hungarian and Esperanto clear the bar as new
languages. Arabic (OMW 17,783 + FreeDict 52,996, union 69,086) and
Greek (OMW 18,194 + FreeDict 41,714, union 51,174) clear it merged.
FreeDict pairs for already-shipped OMW languages (hrv, pol, fin, ita,
cat, nld) were surveyed but not integrated: diminishing returns for
v2; recorded here as an enrichment path.

**Kaikki.org Wiktionary extracts** (CC BY-SA / GFDL via Wiktionary).
Two forms, both verified by download on 2026-10-31:
- English-edition per-language JSONL: full structured entries
  (glosses in English, IPA, examples, translations), but the raw
  files are 28MB to 4.7GB per language (Finnish 4.66GB, English
  3.43GB, Chinese 1.21GB, Spanish 1.12GB, German 1.10GB). Not a
  first-boot source; needs an offline transform into the same
  compact SQLite shape. Full-file counts for the languages that
  would add coverage (unique words with at least one gloss):
  Swedish 303,137; Czech 68,729; Ukrainian 55,738; Korean 51,670;
  Turkish 41,476; Vietnamese 39,618; Hindi 36,169; Hebrew 14,613
  (under the bar). These 7 passers are the ceiling's +7.
- Language-edition extracts (20 editions: zh, cs, nl, fr, de, el,
  id, it, ja, ko, ku, ms, pl, pt, ru, simple, es, th, tr, vi):
  monolingual definitions in the edition's own language, 2.9MB to
  737MB gz per edition. Not counted per language for the ceiling;
  noted as a further expansion source (Czech and Kurdish editions
  have no English-edition equivalent counted above).

### Shipped in v2 (live counts from /health after build)

English (WordNet 3.1: 147,478 lemmas, 126,052 pronunciations,
50,000 frequency words) plus: ar 69,086 / ca 46,345 / de 382,294 /
el 51,174 / eo 63,463 / es 36,370 / eu 26,200 / fi 129,225 /
fr 51,339 / gl 23,056 / hr 28,881 / hu 138,812 / id 36,608 /
it 46,743 / ja 91,936 / ms 33,903 / nl 42,777 / pl 45,140 /
pt 47,086 / ro 49,831 / ru 42,281 / sk 29,087 / sl 40,052 /
th 82,504 / zh 61,525 entries (1,695,718 total non-English).
Senses per language are reported by /health and /languages.

### Design

- Backward compatible, hard: no lang parameter means byte-for-byte
  v1 English on every endpoint (golden-tested). lang accepts ISO
  639-1, ISO 639-3 and English names (lang=spa, lang=Spanish,
  lang=es all resolve); unknown codes return 400
  unsupported_language with the full supported list.
- Storage: one SQLite index (stdlib) built at first boot from the
  downloaded OMW tabs, WordNet 3.0 data files and FreeDict dictd
  files; raw OMW/FreeDict files are deleted after a successful
  build (they re-download if the index is absent). The build runs
  in a background thread: the server binds and serves English
  immediately, /health reports multilingual_status "building", and
  the language endpoints answer an honest 503 until the index
  lands (about 45-100 seconds locally). This shape was adopted
  after the first v2 deploy sat in update_in_progress without
  binding: a synchronous multi-minute build at boot is the wrong
  shape for the free tier. Build peak RSS measured 335MB (ceiling
  512MB); steady state 191MB; data dir about 465MB (413MB of it
  the SQLite index).
- Response shape: same record shape as English, plus lang and
  language on the record, translations on OMW/FreeDict senses,
  definitionLanguage + englishDefinition where a local definition
  exists, and sources on the record. FreeDict senses are labelled
  definitionSource: "translation (FreeDict)".
- Pronunciation: only German, Russian, Hungarian, Esperanto, Arabic
  and Greek carry it (real FreeDict IPA). Everywhere else the field
  and the /pronunciation relation return the honest 404
  pronunciation_not_found; nothing is synthesized.
- English-only filters (syllablesMin/Max, frequencyMin/Max) return
  400 unsupported_filter for other languages rather than silently
  ignoring the caller's constraint. Search otherwise mirrors the
  English semantics and response shape, and /languages lists every
  language with entries, senses, kind, sources and licenses.
- Relations for non-English words: definitions, synonyms,
  translations, examples, pronunciation (where sourced), and the
  synset relations (typeOf, hasTypes, partOf, ...) resolved through
  WordNet 3.0 pointers to same-language lemmas. Lemma-level
  relations OMW cannot support (antonyms, derivation, pertainsTo)
  and CMU-derived ones (rhymes, syllables, frequency) are not
  offered for other languages; the relation error lists what is
  supported.

### Known data traits (disclosed, not hidden)

- FreeDict/WikDict translation lists can include translated example
  phrases and, in rus-eng, occasional Russian explanatory lines
  alongside the English gloss; they are source lines, served as-is.
- A small number of OMW lemmas are Wiktionary markup artifacts or
  contain "/" and so cannot be addressed through the /words/{word}
  path; they are counted in the source counts and left in place
  rather than silently rewriting the source.
- German's 519,343 parsed entries include inflected forms published
  as their own entries by WikDict; unique headwords are 382,294.
- Japanese definitions pair one Japanese gloss per synset; where a
  synset carries several numbered glosses in the source, the first
  is served (the English gloss is always complete).

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
