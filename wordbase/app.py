"""WordBase Dictionary - competitor to WordsAPI (dpventures) on RapidAPI.

Incumbent verified 2026-10-28: 1,561 subscribers, rated 2/5 (53 votes),
pricing $0/$10/$49/$89. Complaints in its Discussions and reviews: valid
keys rejected with 403s, Discussions abandoned and spam-filled, partial
word records with silently empty fields.
This service: the same public data the incumbent's product is built on
(Princeton WordNet 3.1, WordNet license), plus the CMU Pronouncing
Dictionary (pronunciation, syllables, rhymes) and the FrequencyWords
OpenSubtitles list (frequency, labeled a Zipf-scale estimate), served on
the shared scaffold. Every rejection is an explicit JSON error; a word
the data does not know returns a clean documented 404, never a partial
record and never a spurious 403.
Datasets download at boot when absent (GeoBase pattern): the WordNet
tarball is 16MB, too large for the repo snapshot route.
v2 (2026-10-31) adds 25 more languages via Open Multilingual Wordnet
and FreeDict, selected with ?lang=<code>; see the multilingual engine
section below and docs/spec-wordsapi.md. Zero dependencies beyond the
shared scaffold (stdlib sqlite3 for the multilingual index).
Run: python3 app.py (PORT env, default 8107).
"""
import io
import math
import os
import re
import sys
import tarfile
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))
from rapidapi_server import run

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
WN_TARBALL = "https://wordnetcode.princeton.edu/wn3.1.dict.tar.gz"
CMU_URL = "https://raw.githubusercontent.com/cmusphinx/cmudict/master/cmudict.dict"
FREQ_URL = "https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/en/en_50k.txt"
POS_FILES = {"n": "noun", "v": "verb", "a": "adj", "r": "adv"}
POS_NAMES = {"n": "noun", "v": "verb", "a": "adjective", "s": "adjective", "r": "adverb"}


def ensure_data():
    """Load from local files when present; otherwise pull the datasets.

    WordNet's dict files are ~32MB of text, too large for the repo
    snapshot route, so the service fetches them at boot (GeoBase pattern).
    """
    wanted = ([f"data.{s}" for s in POS_FILES.values()]
              + [f"index.{s}" for s in POS_FILES.values()]
              + [f"{s}.exc" for s in POS_FILES.values()]
              + ["cmudict.dict", "en_50k.txt"])
    if all(os.path.exists(os.path.join(DATA_DIR, f)) for f in wanted):
        return
    os.makedirs(DATA_DIR, exist_ok=True)
    last_error = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(WN_TARBALL, timeout=120) as resp:
                blob = resp.read()
            with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tf:
                for name in wanted[:12]:
                    member = tf.getmember(f"dict/{name}")
                    with tf.extractfile(member) as src, open(os.path.join(DATA_DIR, name), "wb") as fh:
                        fh.write(src.read())
            for url, name in ((CMU_URL, "cmudict.dict"), (FREQ_URL, "en_50k.txt")):
                with urllib.request.urlopen(url, timeout=60) as resp:
                    payload = resp.read()
                with open(os.path.join(DATA_DIR, name), "wb") as fh:
                    fh.write(payload)
            return
        except Exception as exc:  # retry a few times, then fail loudly at boot
            last_error = exc
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"dataset download failed: {last_error}")


ensure_data()

# ---------------------------------------------------------------- WordNet
# Lemma index: normalized lemma -> [(index_pos, byte_offset)], parsed from
# index.* at boot. Synsets are parsed on demand by seeking into data.*.

lemma_index = {}
for _pos, _suffix in POS_FILES.items():
    with open(os.path.join(DATA_DIR, f"index.{_suffix}"), encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith(" ") or not line.strip():
                continue  # license header
            parts = line.split()
            lemma, synset_cnt = parts[0], int(parts[2])
            offsets = [int(x) for x in parts[-synset_cnt:]] if synset_cnt else []
            lemma_index.setdefault(lemma.lower(), []).extend((_pos, off) for off in offsets)

_data_handles = {suffix: open(os.path.join(DATA_DIR, f"data.{suffix}"), "rb")
                 for suffix in POS_FILES.values()}
_synset_cache = {}


def parse_synset(file_pos, offset):
    """Parse one synset line from data.<file_pos> at byte offset."""
    key = (file_pos, offset)
    if key in _synset_cache:
        return _synset_cache[key]
    fh = _data_handles[POS_FILES[file_pos]]
    fh.seek(offset)
    line = fh.readline().decode("utf-8", errors="replace")
    head, _, gloss = line.partition("|")
    tokens = head.split()
    ss_type = tokens[2]
    w_cnt = int(tokens[3], 16)
    lemmas, idx = [], 4
    for i in range(w_cnt):
        lemmas.append(tokens[idx].replace("_", " "))
        idx += 2  # word, lex_id
    p_cnt = int(tokens[idx])
    idx += 1
    pointers = []
    for _ in range(p_cnt):
        symbol, target, t_pos, src_tgt = tokens[idx:idx + 4]
        pointers.append((symbol, int(target), t_pos, int(src_tgt[:2], 16), int(src_tgt[2:], 16)))
        idx += 4
    gloss = gloss.strip()
    gloss_parts = [p.strip() for p in gloss.split("; ")] if gloss else []
    definition = gloss_parts[0] if gloss_parts else ""
    examples = [p.strip('"') for p in gloss_parts[1:] if p.startswith('"')]
    parsed = {"pos": POS_NAMES.get(ss_type, ss_type), "ss_type": ss_type,
              "lemmas": lemmas, "definition": definition, "examples": examples,
              "pointers": pointers}
    if len(_synset_cache) > 40000:
        _synset_cache.clear()
    _synset_cache[key] = parsed
    return parsed


def synset_lemmas(file_pos, offset):
    try:
        return parse_synset(file_pos, offset)["lemmas"]
    except Exception:
        return []


SYNSET_RELATIONS = {  # response key -> WordNet pointer symbols (synset level)
    "typeOf": ("@", "@i"), "hasTypes": ("~", "~i"),
    "partOf": ("#p", "#m", "#s"), "hasParts": ("%p", "%m", "%s"),
    "memberOf": ("#m",), "hasMembers": ("%m",),
    "substanceOf": ("#s",), "hasSubstances": ("%s",),
    "similarTo": ("&",), "also": ("^",),
    "entails": ("*",), "cause": (">",),
}
LEMMA_RELATIONS = {"derivation": ("+",), "pertainsTo": ("\\",)}


def build_result(word_norm, file_pos, offset):
    syn = parse_synset(file_pos, offset)
    result = {"definition": syn["definition"], "partOfSpeech": syn["pos"]}
    word_lower = word_norm.replace("_", " ").lower()
    synonyms = [lm for lm in syn["lemmas"] if lm.lower() != word_lower]
    if synonyms:
        result["synonyms"] = synonyms
    antonyms, lemma_rel = [], {}
    for symbol, target, t_pos, src_w, tgt_w in syn["pointers"]:
        if symbol == "!" and src_w > 0:
            targets = synset_lemmas(t_pos if t_pos in POS_FILES else file_pos, target)
            if targets and tgt_w > 0 and tgt_w <= len(targets):
                antonyms.append(targets[tgt_w - 1])
        for key, symbols in LEMMA_RELATIONS.items():
            if symbol in symbols and src_w > 0:
                targets = synset_lemmas(t_pos if t_pos in POS_FILES else file_pos, target)
                if targets and tgt_w > 0 and tgt_w <= len(targets):
                    lemma_rel.setdefault(key, []).append(targets[tgt_w - 1])
    if antonyms:
        result["antonyms"] = list(dict.fromkeys(antonyms))
    for key, symbols in SYNSET_RELATIONS.items():
        values = []
        for symbol, target, t_pos, src_w, _tgt_w in syn["pointers"]:
            if symbol in symbols and src_w == 0:
                values.extend(synset_lemmas(t_pos if t_pos in POS_FILES else file_pos, target))
        if values:
            result[key] = list(dict.fromkeys(values))
    for key, values in lemma_rel.items():
        result[key] = list(dict.fromkeys(values))
    if syn["examples"]:
        result["examples"] = syn["examples"]
    return result


def word_senses(word_norm):
    """All (file_pos, offset) senses for a normalized lemma key."""
    return lemma_index.get(word_norm, [])


# Morphology: WordNet exception lists + a lite detachment rule set, so
# inflected queries ("running", "cats", "geese") resolve to base forms.
exceptions = {}
for _pos, _suffix in POS_FILES.items():
    path = os.path.join(DATA_DIR, f"{_suffix}.exc")
    if os.path.exists(path):
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) == 2:
                    exceptions[parts[0].lower()] = parts[1].lower()
MORPH_RULES = [
    ("s", ""), ("ses", "ss"), ("xes", "x"), ("zes", "z"), ("ches", "ch"),
    ("shes", "sh"), ("men", "man"), ("ies", "y"), ("es", "e"), ("es", ""),
    ("ed", "e"), ("ed", ""), ("ing", "e"), ("ing", ""), ("er", ""), ("er", "e"),
    ("est", ""), ("est", "e"),
]


def resolve_word(raw):
    """Return (lemma_key, display) for a query word, or (None, None)."""
    norm = re.sub(r"\s+", "_", raw.strip().lower())
    if norm in lemma_index:
        return norm, norm.replace("_", " ")
    candidates = []
    if norm in exceptions:
        candidates.append(exceptions[norm])
    for suffix, replacement in MORPH_RULES:
        if norm.endswith(suffix) and len(norm) > len(suffix) + 1:
            candidates.append(norm[:-len(suffix)] + replacement)
    for cand in candidates:
        if cand in lemma_index:
            return cand, cand.replace("_", " ")
    return None, None


# ---------------------------------------------------------------- CMU dict
ARPA_TO_IPA = {
    "AA": "ɑ", "AE": "æ", "AH": "ʌ", "AO": "ɔ", "AW": "aʊ", "AY": "aɪ",
    "EH": "ɛ", "ER": "ɝ", "EY": "eɪ", "IH": "ɪ", "IY": "i", "OW": "oʊ",
    "OY": "ɔɪ", "UH": "ʊ", "UW": "u", "B": "b", "CH": "tʃ", "D": "d",
    "DH": "ð", "F": "f", "G": "ɡ", "HH": "h", "JH": "dʒ", "K": "k",
    "L": "l", "M": "m", "N": "n", "NG": "ŋ", "P": "p", "R": "r", "S": "s",
    "SH": "ʃ", "T": "t", "TH": "θ", "V": "v", "W": "w", "Y": "j",
    "Z": "z", "ZH": "ʒ",
}
VOWELS = {"AA", "AE", "AH", "AO", "AW", "AY", "EH", "ER", "EY", "IH",
          "IY", "OW", "OY", "UH", "UW"}

pronunciations = {}  # word -> [phoneme list, ...]
with open(os.path.join(DATA_DIR, "cmudict.dict"), encoding="utf-8", errors="replace") as fh:
    for line in fh:
        if line.startswith(";;;") or " " not in line:
            continue
        word, _, phones = line.partition("  ")
        if not phones.strip():
            word, _, phones = line.partition(" ")
        word = re.sub(r"\(\d+\)$", "", word.strip().lower())
        pronunciations.setdefault(word, []).append(phones.split())

rhyme_index = {}


def rhyme_key(phones):
    stripped = [re.sub(r"\d", "", p) for p in phones]
    vowel_positions = [i for i, p in enumerate(stripped) if p in VOWELS]
    if not vowel_positions:
        return None
    for stress in ("1", "2"):
        hits = [i for i in vowel_positions if phones[i].endswith(stress)]
        if hits:
            return tuple(stripped[hits[-1]:])
    return tuple(stripped[vowel_positions[-1]:])


for _word, _variants in pronunciations.items():
    _key = rhyme_key(_variants[0])
    if _key:
        rhyme_index.setdefault(_key, []).append(_word)


def ipa_string(phones):
    """IPA with stress marks: group phonemes into vowel-nucleus syllables,
    consonants between vowels join the following syllable's onset."""
    syllables, current = [], []
    for phone in phones:
        current.append(phone)
        if re.sub(r"\d", "", phone) in VOWELS:
            syllables.append(current)
            current = []
    if current:
        if syllables:
            syllables[-1].extend(current)
        else:
            syllables.append(current)
    out = []
    for syl in syllables:
        text = ""
        for phone in syl:
            base = re.sub(r"\d", "", phone)
            symbol = ARPA_TO_IPA.get(base, base.lower())
            if base == "AH":
                symbol = "ə" if phone.endswith("0") else "ʌ"
            if base == "ER":
                symbol = "ɚ" if phone.endswith("0") else "ɝ"
            text += symbol
        stress = next((p[-1] for p in syl if p[-1:].isdigit()), "")
        if stress == "1":
            text = "ˈ" + text
        elif stress == "2":
            text = "ˌ" + text
        out.append(text)
    return "".join(out)


def syllable_count_phones(phones):
    return sum(1 for p in phones if re.sub(r"\d", "", p) in VOWELS)


# Orthographic syllable splitter (documented approximation).
def split_syllables(word):
    w = word.lower()
    if len(w) <= 3:
        return [w]
    vowel_at = []
    for i, ch in enumerate(w):
        if ch in "aeiou":
            vowel_at.append(i)
        elif ch == "y" and i > 0 and w[i - 1] not in "aeiouy" and (i == len(w) - 1 or w[i + 1] not in "aeiou"):
            vowel_at.append(i)
    groups = []
    for i in vowel_at:
        if groups and i == groups[-1][-1] + 1:
            groups[-1].append(i)
        else:
            groups.append([i])
    # Silent trailing e (but consonant+le counts: "table" -> ta-ble).
    if (len(groups) > 1 and groups[-1] == [len(w) - 1] and w.endswith("e")
            and not (len(w) >= 3 and w[-2] == "l" and w[-3] not in "aeiouy")):
        groups.pop()
    if len(groups) <= 1:
        return [w]
    syllables, start = [], 0
    for gi in range(len(groups) - 1):
        end_of_group = groups[gi][-1] + 1
        next_start = groups[gi + 1][0]
        consonants = next_start - end_of_group
        cut = end_of_group if consonants <= 1 else end_of_group + 1
        syllables.append(w[start:cut])
        start = cut
    syllables.append(w[start:])
    return [s for s in syllables if s]


_syllable_cache = {}


def syllables_for(word):
    key = word.lower()
    if key in _syllable_cache:
        return _syllable_cache[key]
    parts = []
    for token in key.split():
        parts.extend(split_syllables(token))
    count = None
    if key in pronunciations:
        count = syllable_count_phones(pronunciations[key][0])
    if count is None:
        count = len(parts)
    while len(parts) > count and len(parts) > 1:
        parts[-2:] = [parts[-2] + parts[-1]]
    result = {"count": count, "list": parts}
    _syllable_cache[key] = result
    return result


# ---------------------------------------------------------------- Frequency
freq_counts = {}
_freq_total = 0
with open(os.path.join(DATA_DIR, "en_50k.txt"), encoding="utf-8", errors="replace") as fh:
    for line in fh:
        parts = line.split()
        if len(parts) == 2 and parts[1].isdigit():
            freq_counts[parts[0]] = int(parts[1])
            _freq_total += int(parts[1])


def frequency_for(word):
    count = freq_counts.get(word.lower())
    if count is None:
        return None
    return {"zipf": round(math.log10(count / _freq_total * 1e9), 2),
            "perMillion": round(count / _freq_total * 1e6, 2)}


# ---------------------------------------------------------------------------
# Multilingual engine (v2, added 2026-10-31)
#
# WordBase v1 was English-only. v2 adds word lookup, relations and search
# for 23 more languages, selected with ?lang=<code> on the existing
# endpoints. With no lang parameter the English behaviour above is
# byte-for-byte v1. Sources are all openly licensed and were verified by
# downloading the real files:
#
# - Open Multilingual Wordnet 1.4 (OMW; per-wordnet licenses, mostly
#   CC BY / CC BY-SA; via the NLTK data distribution). OMW senses key on
#   Princeton WordNet 3.0 synsets, so WordNet 3.0 is loaded as an auxiliary
#   English dataset: it supplies the English gloss and the English lemma
#   list (the translations) for every OMW synset, plus synset relations.
#   Languages whose wordnet carries its own definitions/examples in OMW
#   (Albanian, Bulgarian, Greek, Hebrew, Indonesian, Italian, Japanese,
#   Romanian, Slovenian) serve those first, with the English gloss kept in
#   the englishDefinition field.
# - FreeDict bilingual dictionaries in dictd format (WikDict / Arabeyes
#   builds from Wiktionary data; GPL-2.0 or CC BY-SA 3.0 / CC BY 3.0 per
#   dictionary). These are translation dictionaries: the English
#   translation is the sense gloss and is labelled as such
#   (definitionSource). They add German, Russian, Hungarian and Esperanto,
#   and lift Arabic and Greek over the quality bar. FreeDict entries carry
#   real IPA transcriptions, so they are the one non-English source of the
#   pronunciation field; everywhere else it is omitted, never invented.
#
# Quality bar (stated in docs/spec-wordsapi.md): a language ships when a
# verified open source gives it at least 20,000 structured entries with
# definitions, or with definitions plus English translations.
#
# Storage: a SQLite index (stdlib) built once at first boot into the data
# dir; the raw OMW/FreeDict files are removed after a successful build to
# fit the free tier's disk, and re-download automatically if the index is
# absent. If the multilingual build fails (e.g. no network), English keeps
# serving and /health reports multilingual_error instead of guessing.
# ---------------------------------------------------------------------------
import gzip
import json
import sqlite3
import threading
import zipfile

MULTI_DIR = os.path.join(DATA_DIR, "multi")
MULTI_DB = os.path.join(MULTI_DIR, "multilingual.sqlite3")
MULTI_BUILD_VERSION = "2026-10-31-v5"
OMW_ZIP_URL = "https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/packages/corpora/omw-1.4.zip"
WN30_ZIP_URL = "https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/packages/corpora/wordnet.zip"

# canonical code -> (display name, OMW filename code or None, FreeDict pair or None)
MULTI_LANGS = {
    "es": ("Spanish", "spa", None),
    "fr": ("French", "fra", None),
    "it": ("Italian", "ita", None),
    "pt": ("Portuguese", "por", None),
    "nl": ("Dutch", "nld", None),
    "pl": ("Polish", "pol", None),
    "zh": ("Chinese (Mandarin)", "cmn", None),
    "ja": ("Japanese", "jpn", None),
    "fi": ("Finnish", "fin", None),
    "th": ("Thai", "tha", None),
    "ro": ("Romanian", "ron", None),
    "ms": ("Malay", "zsm", None),
    "id": ("Indonesian", "ind", None),
    "ca": ("Catalan", "cat", None),
    "eu": ("Basque", "eus", None),
    "gl": ("Galician", "glg", None),
    "hr": ("Croatian", "hrv", None),
    "sl": ("Slovenian", "slv", None),
    "sk": ("Slovak", "slk", None),
    "de": ("German", None, "deu-eng"),
    "ru": ("Russian", None, "rus-eng"),
    "hu": ("Hungarian", None, "hun-eng"),
    "eo": ("Esperanto", None, "epo-eng"),
    "ar": ("Arabic", "arb", "ara-eng"),
    "el": ("Greek", "ell", "ell-eng"),
}
OMW_EXTRA_FILES = {"ita": ["itx"]}  # ItalWordNet ships beside MultiWordNet

FREEDICT_URLS = {
    "deu-eng": "https://download.freedict.org/dictionaries/deu-eng/1.9-fd1/freedict-deu-eng-1.9-fd1.dictd.tar.xz",
    "rus-eng": "https://download.freedict.org/dictionaries/rus-eng/2025.11.23/freedict-rus-eng-2025.11.23.dictd.tar.xz",
    "hun-eng": "https://download.freedict.org/dictionaries/hun-eng/0.4.1/freedict-hun-eng-0.4.1.dictd.tar.xz",
    "ara-eng": "https://download.freedict.org/dictionaries/ara-eng/0.6.3/freedict-ara-eng-0.6.3.dictd.tar.xz",
    "ell-eng": "https://download.freedict.org/dictionaries/ell-eng/2025.11.23/freedict-ell-eng-2025.11.23.dictd.tar.xz",
    "epo-eng": "https://download.freedict.org/dictionaries/epo-eng/2024.10.06%2Bfd1/freedict-epo-eng-2024.10.06%2Bfd1.dictd.tar.xz",
}
FREEDICT_LICENSES = {
    "deu-eng": "GPL-2.0 (FreeDict/WikDict)",
    "rus-eng": "CC BY-SA 3.0 (FreeDict/WikDict)",
    "hun-eng": "GPL-2.0 (FreeDict/WikDict)",
    "ara-eng": "GPL (FreeDict/Arabeyes)",
    "ell-eng": "CC BY-SA 3.0 (FreeDict/WikDict)",
    "epo-eng": "CC BY 3.0 (FreeDict)",
}
OMW_LICENSES = {
    "als": "CC BY 3.0", "arb": "CC BY-SA 3.0", "bul": "CC BY 3.0",
    "cat": "CC BY 3.0", "cmn": "WordNet license", "dan": "WordNet license",
    "ell": "Apache 2.0", "eus": "CC BY 3.0", "fin": "CC BY 3.0",
    "fra": "CeCILL-C", "glg": "CC BY 3.0", "heb": "WordNet license",
    "hrv": "CC BY 3.0", "ind": "MIT", "isl": "CC BY 3.0",
    "ita": "CC BY 3.0 / ODC-BY 1.0", "jpn": "WordNet license",
    "lit": "CC BY-SA 3.0", "nld": "CC BY-SA 4.0", "nno": "WordNet license",
    "nob": "WordNet license", "pol": "WordNet license",
    "por": "CC BY-SA", "ron": "CC BY-SA", "slk": "CC BY-SA 3.0",
    "slv": "CC BY-SA 3.0", "spa": "CC BY 3.0", "swe": "CC BY 3.0",
    "tha": "WordNet license", "zsm": "MIT",
}

LANG_ALIASES = {}


def _alias(code, *names):
    for n in names:
        LANG_ALIASES[n] = code


_alias("en", "en", "eng", "english")
for _code, (_name, _omw, _fd) in MULTI_LANGS.items():
    _alias(_code, _code, _name.lower())
    if _omw:
        LANG_ALIASES[_omw] = _code
_alias("de", "deu", "ger")
_alias("ru", "rus")
_alias("hu", "hun")
_alias("eo", "epo")
_alias("ar", "arb")
_alias("el", "ell", "gre")
_alias("zh", "cmn", "zho", "chi", "chinese", "mandarin")
_alias("ja", "jpn")
_alias("pt", "por")
_alias("nl", "nld", "dut")
_alias("fr", "fra", "fre")
_alias("it", "ita")
_alias("fi", "fin")
_alias("th", "tha")
_alias("ro", "ron", "rum")
_alias("ms", "zsm", "msa", "may")
_alias("id", "ind")
_alias("ca", "cat")
_alias("eu", "eus", "baq")
_alias("gl", "glg")
_alias("hr", "hrv")
_alias("sl", "slv")
_alias("sk", "slk")
_alias("pl", "pol")

MULTI_META = {}          # code -> meta dict, loaded after build
MULTI_ERROR = None       # string when the multilingual build failed
MULTI_BUILDING = False   # True while the background build thread runs
WN30_FILES = {}          # pos letter -> open WordNet 3.0 data file handle
WN30_KEYS = set()        # "00001740-n" style keys present in WordNet 3.0
_WN30_LOCK = threading.Lock()
_SYN30_CACHE = {}


def supported_lang_codes():
    return ["en"] + sorted(MULTI_LANGS.keys())


def resolve_lang(raw):
    """Return (code, error_tuple). code is None when raw is absent."""
    if raw is None:
        return None, None
    code = LANG_ALIASES.get(str(raw).strip().lower())
    if code is None or (code != "en" and code not in MULTI_LANGS):
        return None, (400, {
            "error": "unsupported_language",
            "detail": f"Language '{raw}' is not supported by WordBase.",
            "supportedLanguages": supported_lang_codes(),
        })
    return code, None


def _multi_norm(text):
    return re.sub(r"\s+", " ", text.replace("_", " ")).strip().lower()


def _download(url, dest, attempts=4):
    last = None
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "wordbase-dictionary"})
            with urllib.request.urlopen(req, timeout=180) as r, open(dest, "wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
            return
        except Exception as e:  # noqa: BLE001 - report the last failure
            last = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"download failed for {url}: {last}")


def _ensure_multi_sources():
    """Download and extract the multilingual source files (idempotent)."""
    os.makedirs(MULTI_DIR, exist_ok=True)
    omw_dir = os.path.join(MULTI_DIR, "omw")
    wn30_dir = os.path.join(MULTI_DIR, "wn30")
    fd_dir = os.path.join(MULTI_DIR, "freedict")
    if not os.path.exists(os.path.join(omw_dir, "wn-data-spa.tab")):
        zp = os.path.join(MULTI_DIR, "omw-1.4.zip")
        _download(OMW_ZIP_URL, zp)
        os.makedirs(omw_dir, exist_ok=True)
        with zipfile.ZipFile(zp) as z:
            for name in z.namelist():
                base = os.path.basename(name)
                if base.startswith("wn-data-") and base.endswith(".tab"):
                    if "/iwn/" in name:
                        # ItalWordNet ships a second wn-data-ita.tab; keep
                        # it under its own code so it cannot overwrite
                        # MultiWordNet's file of the same name.
                        base = "wn-data-itx.tab"
                    with z.open(name) as src, open(os.path.join(omw_dir, base), "wb") as dst:
                        dst.write(src.read())
        os.unlink(zp)
    if not os.path.exists(os.path.join(wn30_dir, "data.noun")):
        zp = os.path.join(MULTI_DIR, "wordnet.zip")
        _download(WN30_ZIP_URL, zp)
        os.makedirs(wn30_dir, exist_ok=True)
        with zipfile.ZipFile(zp) as z:
            for suffix in ("noun", "verb", "adj", "adv"):
                with z.open("wordnet/data." + suffix) as src, open(
                        os.path.join(wn30_dir, "data." + suffix), "wb") as dst:
                    dst.write(src.read())
        os.unlink(zp)
    for pair, url in FREEDICT_URLS.items():
        pair_dir = os.path.join(fd_dir, pair)
        if os.path.isdir(pair_dir) and any(f.endswith(".index") for f in os.listdir(pair_dir)):
            continue
        os.makedirs(pair_dir, exist_ok=True)
        tp = os.path.join(pair_dir, "dictd.tar.xz")
        _download(url, tp)
        with tarfile.open(tp, "r:xz") as tf:
            for member in tf.getmembers():
                base = os.path.basename(member.name)
                if base.endswith(".dict.dz") or base.endswith(".index"):
                    with tf.extractfile(member) as src, open(
                            os.path.join(pair_dir, base), "wb") as dst:
                        dst.write(src.read())
        os.unlink(tp)


def _load_wn30_keys():
    """Collect the set of WordNet 3.0 synset keys and open its data files."""
    global WN30_KEYS
    wn30_dir = os.path.join(MULTI_DIR, "wn30")
    keys = set()
    for suffix, letter in (("noun", "n"), ("verb", "v"), ("adj", "a"), ("adv", "r")):
        path = os.path.join(wn30_dir, "data." + suffix)
        fh = open(path, "rb")
        WN30_FILES[letter] = fh
        if letter == "a":
            WN30_FILES["s"] = fh
        with open(path, "rb") as rf:
            for line in rf:
                if line[:1].isdigit():
                    keys.add(line[:8].decode() + "-" + letter)
                    if letter == "a":
                        keys.add(line[:8].decode() + "-s")
    WN30_KEYS = keys


def parse_synset30(offset, pos_letter):
    """Parse one WordNet 3.0 synset by byte offset (OMW keys are WN3.0)."""
    key = (offset, pos_letter)
    if key in _SYN30_CACHE:
        return _SYN30_CACHE[key]
    fh = WN30_FILES.get(pos_letter)
    if fh is None:
        return None
    with _WN30_LOCK:
        fh.seek(offset)
        line = fh.readline().decode("utf-8", "replace")
    if not line or not line[:8].isdigit() or "|" not in line:
        return None
    head, gloss = line.split("|", 1)
    tokens = head.split()
    w_cnt = int(tokens[3], 16)
    idx = 4
    lemmas = []
    for _ in range(w_cnt):
        lemmas.append(tokens[idx].replace("_", " "))
        idx += 2
    p_cnt = int(tokens[idx])
    idx += 1
    pointers = {}
    for _ in range(p_cnt):
        sym, off, ppos = tokens[idx], int(tokens[idx + 1]), tokens[idx + 2]
        pointers.setdefault(sym, []).append((off, ppos))
        idx += 4
    gloss = gloss.strip()
    gloss_parts = [p.strip() for p in gloss.split("; ")] if gloss else []
    definition = gloss_parts[0] if gloss_parts else ""
    examples = [p.strip('"') for p in gloss_parts[1:] if p.startswith('"')]
    syn = {"lemmas": lemmas, "definition": definition,
           "examples": examples, "pointers": pointers}
    if len(_SYN30_CACHE) > 60000:
        _SYN30_CACHE.clear()
    _SYN30_CACHE[key] = syn
    return syn


_B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


def _b64val(s):
    v = 0
    for ch in s:
        v = v * 64 + _B64.index(ch)
    return v


_FD_POS = [
    (("pn",), "noun"), (("n",), "noun"), (("v", "vt", "vi", "vr", "vb"), "verb"),
    (("adj",), "adjective"), (("adv",), "adverb"), (("prep",), "preposition"),
    (("conj",), "conjunction"), (("pron",), "pronoun"),
    (("interj", "intj"), "interjection"), (("num",), "numeral"),
    (("art",), "article"),
]


def _fd_parse_entry(text):
    """Parse one dictd entry text -> (display, ipa, pos, translations, see)."""
    lines = text.split("\n")
    first = lines[0].strip()
    ipa = None
    m = re.search(r"/([^/]{1,80})/", first)
    head = first
    if m:
        ipa = m.group(1)
        head = (first[:m.start()] + first[m.end():]).strip()
    grammar = ""
    gm = re.search(r"<([^>]*)>", head)
    if gm:
        grammar = gm.group(1)
        head = (head[:gm.start()] + head[gm.end():]).strip()
    head = re.sub(r"\([^)]*\)", "", head).strip()
    display = head
    pos = ""
    if grammar:
        toks = [t.strip().lower() for t in re.split(r"[,\s]+", grammar) if t.strip()]
        for names, full in _FD_POS:
            if any(t in names for t in toks):
                pos = full
                break
    translations = []
    see = None
    for raw_line in lines[1:]:
        line = raw_line.strip()
        if not line:
            continue
        low = line.lower()
        if low.startswith("synonym"):
            continue
        if low.startswith("see:") or low.startswith("see "):
            sm = re.search(r"\{([^}]+)\}", line)
            if sm and see is None:
                see = sm.group(1)
            continue
        line = re.sub(r"^\d+[.\)]\s*", "", line)
        line = re.sub(r"<[^>]*>", "", line).strip()
        line = re.sub(r"\{[^}]*\}", "", line).strip()
        if line:
            translations.append(line)
    return display, ipa, pos, translations, see


def _build_multi_db():
    """Build the SQLite multilingual index from the extracted sources.

    Memory-lean by design (the free tier gives the process ~512MB and the
    English engine already holds ~150MB): aggregation happens in SQLite,
    never in Python dicts, and source files are streamed, not loaded.
    """
    if os.path.exists(MULTI_DB):
        os.unlink(MULTI_DB)
    con = sqlite3.connect(MULTI_DB)
    con.execute("PRAGMA journal_mode=OFF")
    con.execute("PRAGMA synchronous=OFF")
    con.execute("PRAGMA temp_store=FILE")
    con.executescript("""
        CREATE TABLE omw_lemmas(lang TEXT, norm TEXT, display TEXT, synset TEXT, pos TEXT, has_ex INTEGER, has_tr INTEGER, has_syn INTEGER);
        CREATE TABLE defs(lang TEXT, synset TEXT, definition TEXT, examples TEXT);
        CREATE TABLE fd_entries(lang TEXT, norm TEXT, display TEXT, ipa TEXT, pos TEXT, translations TEXT);
        CREATE TABLE fd_alias(lang TEXT, norm TEXT, target TEXT);
        CREATE TABLE words(lang TEXT, norm TEXT, display TEXT, pos_set TEXT, has_syn INTEGER, has_ex INTEGER, has_tr INTEGER, has_pron INTEGER);
        CREATE TABLE meta(lang TEXT, name TEXT, entries INTEGER, senses INTEGER, kind TEXT, sources TEXT, licenses TEXT);
        CREATE TABLE build_info(k TEXT, v TEXT);
    """)

    # ---- OMW languages -----------------------------------------------------
    omw_dir = os.path.join(MULTI_DIR, "omw")
    omw_senses = {}
    for code, (_name, omw_code, _fd) in MULTI_LANGS.items():
        if not omw_code:
            continue
        files = [omw_code] + OMW_EXTRA_FILES.get(omw_code, [])
        defs_rows = {}
        syn_count = {}
        for fcode in files:
            path = os.path.join(omw_dir, "wn-data-%s.tab" % fcode)
            if not os.path.exists(path):
                continue
            with open(path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    if line.startswith("#") or "\t" not in line:
                        continue
                    parts = line.rstrip("\n").split("\t")
                    if len(parts) < 3:
                        continue
                    synset, kind = parts[0], parts[1]
                    if kind == "lemma" or kind.endswith(":lemma"):
                        syn_count[synset] = syn_count.get(synset, 0) + 1
                        continue
                    if len(parts) < 4:
                        continue
                    if kind == fcode + ":def":
                        if synset not in defs_rows:
                            defs_rows[synset] = [parts[3], ""]
                    elif kind == fcode + ":exe":
                        cur = defs_rows.setdefault(synset, ["", ""])
                        ex = json.loads(cur[1]) if cur[1] else []
                        if len(ex) < 3:
                            ex.append(parts[3])
                        cur[1] = json.dumps(ex, ensure_ascii=False)
        con.executemany("INSERT INTO defs VALUES (?,?,?,?)",
                        [(code, s, d[0], d[1]) for s, d in defs_rows.items() if d[0] or d[1]])
        def_synsets = set(defs_rows.keys())
        ex_synsets = {s for s, d in defs_rows.items() if d[1]}
        defs_rows.clear()
        lemma_rows = []
        senses = 0
        for fcode in files:
            path = os.path.join(omw_dir, "wn-data-%s.tab" % fcode)
            if not os.path.exists(path):
                continue
            with open(path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    if line.startswith("#") or "\t" not in line:
                        continue
                    parts = line.rstrip("\n").split("\t")
                    if len(parts) < 3:
                        continue
                    synset, kind = parts[0], parts[1]
                    if kind != "lemma" and not kind.endswith(":lemma"):
                        continue
                    in30 = synset in WN30_KEYS
                    if not in30 and synset not in def_synsets:
                        continue
                    display = parts[-1].replace("_", " ").strip()
                    if not display:
                        continue
                    lemma_rows.append((code, _multi_norm(display), display, synset,
                                       synset[-1],
                                       1 if synset in ex_synsets else 0,
                                       1 if in30 else 0,
                                       1 if syn_count.get(synset, 0) > 1 else 0))
                    senses += 1
                    if len(lemma_rows) >= 20000:
                        con.executemany("INSERT INTO omw_lemmas VALUES (?,?,?,?,?,?,?,?)", lemma_rows)
                        lemma_rows = []
            if lemma_rows:
                con.executemany("INSERT INTO omw_lemmas VALUES (?,?,?,?,?,?,?,?)", lemma_rows)
                lemma_rows = []
        omw_senses[code] = senses

    # ---- FreeDict languages -------------------------------------------------
    fd_dir = os.path.join(MULTI_DIR, "freedict")
    fd_senses = {}
    for code, (_name, _omw, pair) in MULTI_LANGS.items():
        if not pair:
            continue
        pair_dir = os.path.join(fd_dir, pair)
        index_name = None
        dict_name = None
        for fn in os.listdir(pair_dir):
            if fn.endswith(".index"):
                index_name = fn
            elif fn.endswith(".dict.dz"):
                dict_name = fn
        if not index_name or not dict_name:
            continue
        with open(os.path.join(pair_dir, index_name), encoding="utf-8", errors="replace") as f:
            index_lines = f.read().splitlines()
        with open(os.path.join(pair_dir, dict_name), "rb") as f:
            raw = gzip.decompress(f.read())
        entries = []
        aliases = []
        senses = 0
        for line in index_lines:
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            headword, off, ln = parts[0], _b64val(parts[1]), _b64val(parts[2])
            if headword.startswith("00database"):
                continue
            text = raw[off:off + ln].decode("utf-8", "replace")
            display, ipa, pos, translations, see = _fd_parse_entry(text)
            if not display or display.startswith("00-database"):
                continue
            norm = _multi_norm(display)
            if translations:
                entries.append((code, norm, display, ipa or "", pos,
                                "\x1f".join(translations[:12])))
                senses += 1
            elif see:
                aliases.append((code, norm, _multi_norm(see)))
            if len(entries) >= 20000:
                con.executemany("INSERT INTO fd_entries VALUES (?,?,?,?,?,?)", entries)
                entries = []
        if entries:
            con.executemany("INSERT INTO fd_entries VALUES (?,?,?,?,?,?)", entries)
        if aliases:
            con.executemany("INSERT INTO fd_alias VALUES (?,?,?)", aliases)
        fd_senses[code] = senses

    # ---- indexes, then SQL-side aggregation into words + meta ---------------
    con.execute("CREATE INDEX idx_omw_lookup ON omw_lemmas(lang, norm)")
    con.execute("CREATE INDEX idx_omw_synset ON omw_lemmas(lang, synset)")
    con.execute("CREATE INDEX idx_defs ON defs(lang, synset)")
    con.execute("CREATE INDEX idx_fd_lookup ON fd_entries(lang, norm)")
    con.execute("CREATE INDEX idx_fd_alias ON fd_alias(lang, norm)")
    con.execute("""
        INSERT INTO words
        SELECT lang, norm, MIN(display), '',
               MAX(has_syn), MAX(has_ex), MAX(has_tr), MAX(has_pron)
        FROM (
            SELECT lang, norm, display, has_ex, has_tr, has_syn, 0 AS has_pron FROM omw_lemmas
            UNION ALL
            SELECT lang, norm, display, 0, 1, 0, CASE WHEN ipa <> '' THEN 1 ELSE 0 END FROM fd_entries
        )
        GROUP BY lang, norm""")
    con.execute("CREATE INDEX idx_words_lang ON words(lang, norm)")
    # pos_set: one streaming pass over distinct (lang, norm, pos) rows.
    updates = []
    cur_key = None
    cur_pos = []
    pos_rows = con.execute("""
        SELECT lang, norm, pos FROM (
            SELECT DISTINCT lang, norm, pos FROM omw_lemmas
            UNION
            SELECT DISTINCT lang, norm, pos FROM fd_entries
        ) ORDER BY lang, norm""")
    for lang, norm, pos in pos_rows:
        full = POS_NAMES.get(pos, pos) if len(pos) <= 1 else pos
        if (lang, norm) != cur_key:
            if cur_key is not None:
                updates.append((",".join(sorted(set(cur_pos))), cur_key[0], cur_key[1]))
            cur_key = (lang, norm)
            cur_pos = []
        if full:
            cur_pos.append(full)
        if len(updates) >= 20000:
            con.executemany("UPDATE words SET pos_set=? WHERE lang=? AND norm=?", updates)
            updates = []
    if cur_key is not None:
        updates.append((",".join(sorted(set(cur_pos))), cur_key[0], cur_key[1]))
    if updates:
        con.executemany("UPDATE words SET pos_set=? WHERE lang=? AND norm=?", updates)
    for code, (name, omw_code, pair) in MULTI_LANGS.items():
        entries = con.execute("SELECT COUNT(*) FROM words WHERE lang=?", (code,)).fetchone()[0]
        senses = omw_senses.get(code, 0) + fd_senses.get(code, 0)
        sources, licenses = [], []
        if omw_code:
            sources.append(f"Open Multilingual Wordnet 1.4 ({omw_code})")
            licenses.append(OMW_LICENSES.get(omw_code, "see OMW"))
        if pair:
            sources.append(f"FreeDict {pair} (dictd)")
            licenses.append(FREEDICT_LICENSES[pair])
        kind = "wordnet+translation" if (omw_code and pair) else ("wordnet" if omw_code else "translation")
        con.execute("INSERT INTO meta VALUES (?,?,?,?,?,?,?)",
                    (code, name, entries, senses, kind,
                     json.dumps(sources), json.dumps(licenses)))
    con.execute("INSERT INTO build_info VALUES ('version', ?)", (MULTI_BUILD_VERSION,))
    con.commit()
    con.close()


def _multi_db():
    return sqlite3.connect(f"file:{MULTI_DB}?mode=ro", uri=True)


def _load_multi_meta():
    global MULTI_META
    con = _multi_db()
    MULTI_META = {}
    for lang, name, entries, senses, kind, sources, licenses in con.execute(
            "SELECT lang, name, entries, senses, kind, sources, licenses FROM meta"):
        MULTI_META[lang] = {"name": name, "entries": entries, "senses": senses,
                            "kind": kind, "sources": json.loads(sources),
                            "licenses": json.loads(licenses)}
    con.close()


def init_multi():
    """Download, build and open the multilingual index. Never fatal.

    Runs in a background thread (see __main__): the server binds and
    serves English immediately, /health reports
    multilingual_status "building", and the language endpoints answer
    an honest 503 until the index lands.
    """
    global MULTI_ERROR, MULTI_BUILDING
    MULTI_BUILDING = True
    try:
        _ensure_multi_sources()
        _load_wn30_keys()
        fresh = False
        if os.path.exists(MULTI_DB):
            try:
                con = _multi_db()
                row = con.execute("SELECT v FROM build_info WHERE k='version'").fetchone()
                con.close()
                fresh = bool(row and row[0] == MULTI_BUILD_VERSION)
            except Exception:  # noqa: BLE001 - rebuild a corrupt index
                fresh = False
        if not fresh:
            _build_multi_db()
            # Raw sources are not needed at runtime except the WordNet 3.0
            # data files; drop the rest to fit the free tier's disk.
            omw_dir = os.path.join(MULTI_DIR, "omw")
            if os.path.isdir(omw_dir):
                for fn in os.listdir(omw_dir):
                    os.unlink(os.path.join(omw_dir, fn))
                os.rmdir(omw_dir)
            fd_dir = os.path.join(MULTI_DIR, "freedict")
            if os.path.isdir(fd_dir):
                for pair in os.listdir(fd_dir):
                    pdir = os.path.join(fd_dir, pair)
                    for fn in os.listdir(pdir):
                        os.unlink(os.path.join(pdir, fn))
                    os.rmdir(pdir)
                os.rmdir(fd_dir)
        _load_multi_meta()
    except Exception as e:  # noqa: BLE001 - English must keep serving
        MULTI_ERROR = f"{type(e).__name__}: {e}"
    finally:
        MULTI_BUILDING = False


def _synset_key(offset, pos_letter):
    return f"{offset:08d}-{pos_letter}"


def _multi_results(con, code, norm):
    """Build the results array for one non-English word."""
    results = []
    ipas = []
    omw_rows = con.execute(
        "SELECT display, synset, pos FROM omw_lemmas WHERE lang=? AND norm=? ORDER BY synset",
        (code, norm)).fetchall()
    seen_synsets = set()
    for _display, synset, _pos in omw_rows:
        if synset in seen_synsets:
            continue
        seen_synsets.add(synset)
        offset = int(synset[:8])
        pos_letter = synset[-1]
        syn = parse_synset30(offset, pos_letter)
        d = con.execute("SELECT definition, examples FROM defs WHERE lang=? AND synset=?",
                        (code, synset)).fetchone()
        local_def = d[0] if d and d[0] else None
        local_ex = json.loads(d[1]) if d and d[1] else []
        result = {"definition": local_def or (syn["definition"] if syn else ""),
                  "partOfSpeech": POS_NAMES.get(pos_letter, pos_letter)}
        if local_def:
            result["definitionLanguage"] = code
            if syn:
                result["englishDefinition"] = syn["definition"]
        synonyms = [r[0] for r in con.execute(
            "SELECT DISTINCT display FROM omw_lemmas WHERE lang=? AND synset=? AND norm<>? ORDER BY display",
            (code, synset, norm)).fetchall()]
        if synonyms:
            result["synonyms"] = synonyms[:25]
        if syn and syn["lemmas"]:
            result["translations"] = syn["lemmas"][:25]
        if local_ex:
            result["examples"] = local_ex
        if syn:
            for rel_name, symbols in SYNSET_RELATIONS.items():
                targets = []
                for sym in symbols:
                    for (t_off, t_pos) in syn["pointers"].get(sym, []):
                        keys = [_synset_key(t_off, t_pos)]
                        if t_pos in ("a", "s"):
                            keys.append(_synset_key(t_off, "s" if t_pos == "a" else "a"))
                        for k in keys:
                            for r in con.execute(
                                    "SELECT DISTINCT display FROM omw_lemmas WHERE lang=? AND synset=?",
                                    (code, k)).fetchall():
                                if r[0] not in targets:
                                    targets.append(r[0])
                if targets:
                    result[rel_name] = targets[:25]
        results.append(result)
    for display, ipa, pos, translations in con.execute(
            "SELECT display, ipa, pos, translations FROM fd_entries WHERE lang=? AND norm=?",
            (code, norm)).fetchall():
        trs = translations.split("\x1f") if translations else []
        if not trs:
            continue
        result = {"definition": trs[0],
                  "partOfSpeech": pos or "unknown",
                  "translations": trs,
                  "definitionSource": "translation (FreeDict)"}
        results.append(result)
        if ipa and ipa not in ipas:
            ipas.append(ipa)
    return results, ipas


def _multi_unavailable():
    detail = MULTI_ERROR or ("Multilingual index is building; try again shortly."
                             if MULTI_BUILDING else "Multilingual index is not built.")
    return 503, {"error": "multilingual_unavailable", "detail": detail}


def multi_word(code, params):
    if not MULTI_META:
        return _multi_unavailable()
    word = urllib.parse.unquote(params.get("word", ""))
    norm = _multi_norm(word)
    if not norm:
        return 400, {"error": "missing_word", "detail": "Provide a word."}
    con = _multi_db()
    try:
        row = con.execute("SELECT display FROM words WHERE lang=? AND norm=?",
                          (code, norm)).fetchone()
        results, ipas = [], []
        if row:
            results, ipas = _multi_results(con, code, norm)
        if not results:
            alias = con.execute("SELECT target FROM fd_alias WHERE lang=? AND norm=?",
                                (code, norm)).fetchone()
            if alias:
                row = con.execute("SELECT display FROM words WHERE lang=? AND norm=?",
                                  (code, alias[0])).fetchone()
                if row:
                    results, ipas = _multi_results(con, code, alias[0])
        if not results:
            return 404, {"error": "word_not_found",
                         "detail": f"No {MULTI_META[code]['name']} dictionary entry for '{word}'.",
                         "lang": code}
        record = {"word": row[0], "lang": code,
                  "language": MULTI_META[code]["name"], "results": results}
        if ipas:
            record["pronunciation"] = {"all": ipas[0]}
            if len(ipas) > 1:
                record["pronunciation"]["variants"] = ipas
        record["sources"] = MULTI_META[code]["sources"]
        return 200, record
    finally:
        con.close()


_MULTI_RELATIONS = ["definitions", "synonyms", "translations", "examples",
                    "pronunciation"] + sorted(SYNSET_RELATIONS.keys())


def multi_relation(code, params):
    if not MULTI_META:
        return _multi_unavailable()
    word = urllib.parse.unquote(params.get("word", ""))
    relation = params.get("relation", "")
    status, rec = multi_word(code, params)
    if status != 200:
        return status, rec
    results = rec["results"]

    def agg(field):
        out = []
        for r in results:
            for v in r.get(field, []):
                if v not in out:
                    out.append(v)
        return sorted(out)

    if relation == "definitions":
        return 200, {"word": rec["word"], "lang": code,
                     "definitions": [{"definition": r["definition"],
                                      "partOfSpeech": r["partOfSpeech"]} for r in results]}
    if relation in ("synonyms", "translations", "examples"):
        # English parity: a known word with no values for the relation
        # returns 200 with an empty list, not an error.
        return 200, {"word": rec["word"], "lang": code, relation: agg(relation)}
    if relation == "pronunciation":
        pron = rec.get("pronunciation")
        if not pron:
            return 404, {"error": "pronunciation_not_found",
                         "detail": f"No pronunciation source for {MULTI_META[code]['name']} in WordBase; "
                                   f"the field is omitted rather than invented.",
                         "lang": code}
        return 200, {"word": rec["word"], "lang": code, "pronunciation": pron}
    if relation in SYNSET_RELATIONS:
        return 200, {"word": rec["word"], "lang": code, relation: agg(relation)}
    return 404, {"error": "not_found",
                 "detail": f"No relation '{relation}' for {MULTI_META[code]['name']}. "
                           f"Supported: {', '.join(_MULTI_RELATIONS)}.",
                 "lang": code}


def multi_search(code, params):
    if not MULTI_META:
        return _multi_unavailable()
    for bad in ("syllablesMin", "syllablesMax", "frequencyMin", "frequencyMax"):
        if params.get(bad) is not None:
            return 400, {"error": "unsupported_filter",
                         "detail": f"Filter '{bad}' exists only for English "
                                   f"(CMUdict / FrequencyWords coverage).",
                         "lang": code}
    letter_pattern = params.get("letterPattern")
    regex = None
    if letter_pattern:
        try:
            regex = re.compile(letter_pattern, re.IGNORECASE)
        except re.error as exc:
            return 400, {"error": "invalid_pattern",
                         "detail": f"letterPattern is not a valid regex: {exc}"}

    def as_int(name):
        try:
            return int(params[name]) if params.get(name) else None
        except ValueError:
            return None

    letters_min, letters_max = as_int("lettersMin"), as_int("lettersMax")
    pos_filter = params.get("partOfSpeech")
    has_details = [h for h in params.get("hasDetails", "").split(",") if h]
    has_map = {"synonyms": 5, "examples": 6, "translations": 7, "pronunciation": 8}
    for h in has_details:
        if h not in has_map and h != "definitions":
            return 400, {"error": "unsupported_filter",
                         "detail": f"hasDetails '{h}' is not available for {MULTI_META[code]['name']}. "
                                   f"Supported: definitions, examples, pronunciation, synonyms, translations.",
                         "lang": code}
    limit = min(as_int("limit") or 100, 500)
    page = as_int("page") or 1
    con = _multi_db()
    try:
        rows = con.execute(
            "SELECT norm, display, pos_set, has_syn, has_ex, has_tr, has_pron "
            "FROM words WHERE lang=?", (code,)).fetchall()
    finally:
        con.close()
    matched = []
    for norm, display, pos_set, h_syn, h_ex, h_tr, h_pron in rows:
        if regex and not regex.search(display):
            continue
        letters = len(norm.replace(" ", ""))
        if letters_min is not None and letters < letters_min:
            continue
        if letters_max is not None and letters > letters_max:
            continue
        if pos_filter and pos_filter.lower() not in pos_set.split(","):
            continue
        flags = {5: h_syn, 6: h_ex, 7: h_tr, 8: h_pron}
        if any(h in has_map and not flags[has_map[h]] for h in has_details):
            continue
        matched.append(display)
    matched = sorted(set(matched), key=_multi_norm)
    total = len(matched)
    start = (page - 1) * limit
    return 200, {"query": {k: v for k, v in params.items()},
                 "lang": code,
                 "results": {"total": total, "data": matched[start:start + limit]}}


def handle_languages(params):
    langs = [{"code": "en", "name": "English",
              "entries": len(lemma_index), "kind": "wordnet",
              "sources": ["Princeton WordNet 3.1", "CMU Pronouncing Dictionary 0.7b",
                          "FrequencyWords en_50k"],
              "licenses": ["WordNet license", "BSD-style (CMUdict)", "MIT"]}]
    for code in sorted(MULTI_META.keys()):
        m = MULTI_META[code]
        langs.append({"code": code, "name": m["name"], "entries": m["entries"],
                      "senses": m["senses"], "kind": m["kind"],
                      "sources": m["sources"], "licenses": m["licenses"]})
    return 200, {"languageCount": len(langs), "languages": langs}


# ---------------------------------------------------------------- Handlers
RELATION_KEYS = set(SYNSET_RELATIONS) | set(LEMMA_RELATIONS) | {
    "definitions", "synonyms", "antonyms", "examples",
    "pronunciation", "syllables", "frequency", "rhymes"}


def word_not_found(raw):
    return 404, {"error": "word_not_found",
                 "detail": f"'{raw}' is not in the WordNet lexicon this service covers "
                           f"(about 147,000 lemmas; slang and proper names are out of scope). "
                           f"Check the spelling or try the base form of the word."}


def full_record(word_norm, display):
    senses = word_senses(word_norm)
    if not senses:
        return None
    results = [build_result(word_norm, fp, off) for fp, off in senses]
    record = {"word": display, "results": results}
    record["syllables"] = syllables_for(display)
    if display.lower() in pronunciations:
        record["pronunciation"] = {"all": ipa_string(pronunciations[display.lower()][0])}
    freq = frequency_for(display)
    if freq:
        record["frequency"] = freq
    return record


def handle_word(params):
    code, err = resolve_lang(params.get("lang"))
    if err:
        return err
    if code is not None and code != "en":
        return multi_word(code, params)
    raw = urllib.parse.unquote(params["word"])
    norm, display = resolve_word(raw)
    if norm is None:
        return word_not_found(raw)
    record = full_record(norm, display)
    if record is None:
        return word_not_found(raw)
    if norm != re.sub(r"\s+", "_", raw.strip().lower()):
        record["morphology"] = {"input": raw, "baseForm": display,
                                "note": "Inflected form resolved to its WordNet base form."}
    return 200, record


def handle_relation(params):
    code, err = resolve_lang(params.get("lang"))
    if err:
        return err
    if code is not None and code != "en":
        return multi_relation(code, params)
    raw = urllib.parse.unquote(params["word"])
    relation = params["relation"]
    if relation not in RELATION_KEYS:
        return 404, {"error": "not_found",
                     "detail": f"No relation '{relation}'. Supported: {', '.join(sorted(RELATION_KEYS))}."}
    norm, display = resolve_word(raw)
    if norm is None:
        return word_not_found(raw)
    if relation == "pronunciation":
        if display.lower() not in pronunciations:
            return 404, {"error": "pronunciation_not_found",
                         "detail": f"No CMU dictionary pronunciation for '{display}'."}
        return 200, {"word": display,
                     "pronunciation": {"all": ipa_string(pronunciations[display.lower()][0])}}
    if relation == "syllables":
        return 200, {"word": display, "syllables": syllables_for(display)}
    if relation == "frequency":
        freq = frequency_for(display)
        if freq is None:
            return 404, {"error": "frequency_not_found",
                         "detail": f"'{display}' is outside the 50,000-word frequency list."}
        return 200, {"word": display, "frequency": freq}
    if relation == "rhymes":
        variants = pronunciations.get(display.lower())
        if not variants:
            return 404, {"error": "rhymes_not_found",
                         "detail": f"No pronunciation for '{display}', so rhymes cannot be derived."}
        key = rhyme_key(variants[0])
        rhymes = [w for w in rhyme_index.get(key, []) if w != display.lower()]
        return 200, {"word": display, "rhymes": {"all": sorted(rhymes)[:100]}}
    results = [build_result(norm, fp, off) for fp, off in word_senses(norm)]
    if not results:
        return word_not_found(raw)
    if relation == "definitions":
        return 200, {"word": display,
                     "definitions": [{"definition": r["definition"],
                                      "partOfSpeech": r["partOfSpeech"]} for r in results]}
    values = []
    for r in results:
        values.extend(r.get(relation, []))
    return 200, {"word": display, relation: list(dict.fromkeys(values))}


def handle_search(params):
    code, err = resolve_lang(params.get("lang"))
    if err:
        return err
    if code is not None and code != "en":
        return multi_search(code, params)
    letter_pattern = params.get("letterPattern")
    regex = None
    if letter_pattern:
        try:
            regex = re.compile(letter_pattern, re.IGNORECASE)
        except re.error as exc:
            return 400, {"error": "invalid_pattern", "detail": f"letterPattern is not a valid regex: {exc}"}
    def as_int(name):
        try:
            return int(params[name]) if params.get(name) else None
        except ValueError:
            return None
    letters_min, letters_max = as_int("lettersMin"), as_int("lettersMax")
    syl_min, syl_max = as_int("syllablesMin"), as_int("syllablesMax")
    freq_min, freq_max = (float(params["frequencyMin"]) if params.get("frequencyMin") else None,
                          float(params["frequencyMax"]) if params.get("frequencyMax") else None)
    pos_filter = params.get("partOfSpeech")
    has_details = [h for h in params.get("hasDetails", "").split(",") if h]
    limit = min(as_int("limit") or 100, 500)
    page = as_int("page") or 1
    matched = []
    for lemma, senses in lemma_index.items():
        display = lemma.replace("_", " ")
        if regex and not regex.search(display):
            continue
        letters = len(display.replace(" ", ""))
        if letters_min is not None and letters < letters_min:
            continue
        if letters_max is not None and letters > letters_max:
            continue
        if pos_filter:
            names = {POS_NAMES.get(fp, fp) for fp, _ in senses}
            if pos_filter.lower() not in names:
                continue
        if syl_min is not None or syl_max is not None:
            count = syllables_for(display)["count"]
            if syl_min is not None and count < syl_min:
                continue
            if syl_max is not None and count > syl_max:
                continue
        if freq_min is not None or freq_max is not None:
            freq = frequency_for(display)
            if freq is None:
                continue
            if freq_min is not None and freq["zipf"] < freq_min:
                continue
            if freq_max is not None and freq["zipf"] > freq_max:
                continue
        if has_details:
            ok = False
            for fp, off in senses:
                result = build_result(lemma, fp, off)
                if any(result.get(h) for h in has_details):
                    ok = True
                    break
            if not ok:
                continue
        matched.append(display)
    matched.sort()
    total = len(matched)
    start = (page - 1) * limit
    return 200, {"query": {k: v for k, v in params.items()},
                 "results": {"total": total, "data": matched[start:start + limit]}}


def handle_health(params):
    payload = {"status": "ok", "service": "wordbase-dictionary",
               "lemmas": len(lemma_index), "pronunciations": len(pronunciations),
               "frequency_words": len(freq_counts),
               "datasets": {"wordnet": "3.1 (Princeton, WordNet license)",
                            "pronunciation": "CMU Pronouncing Dictionary 0.7b",
                            "frequency": "FrequencyWords en_50k, OpenSubtitles 2018 (MIT)"}}
    if MULTI_META:
        payload["language_count"] = 1 + len(MULTI_META)
        payload["languages"] = {code: {"name": m["name"], "entries": m["entries"],
                                       "senses": m["senses"], "kind": m["kind"]}
                                for code, m in sorted(MULTI_META.items())}
    elif MULTI_ERROR:
        payload["multilingual_error"] = MULTI_ERROR
    elif MULTI_BUILDING:
        payload["multilingual_status"] = "building"
    return 200, payload


if __name__ == "__main__":
    threading.Thread(target=init_multi, daemon=True).start()
    run({
        "/languages": handle_languages,
        "/words": handle_search,
        "/words/{word}": handle_word,
        "/words/{word}/{relation}": handle_relation,
        "/health": handle_health,
    }, int(os.environ.get("PORT", "8107")), "wordbase-dictionary")
