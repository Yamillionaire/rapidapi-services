#!/usr/bin/env python3
"""WordBase v2 (multilingual) test battery.

Runs against a base URL with the proxy secret in the WORDBASE_SECRET
environment variable (never an argument, never printed). Without a
secret it runs the open checks only (health + gate) and says so.

Usage: WORDBASE_SECRET=... python3 run_tests.py [base_url] [out_json]
Default base: http://127.0.0.1:18108
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:18108"
OUT = sys.argv[2] if len(sys.argv) > 2 else ""
SECRET = os.environ.get("WORDBASE_SECRET", "")
RESULTS = []


def call(path, secret=SECRET):
    req = urllib.request.Request(BASE + path)
    if secret:
        req.add_header("X-RapidAPI-Proxy-Secret", secret)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}


def check(name, ok, detail=""):
    RESULTS.append({"check": name, "pass": bool(ok), "detail": str(detail)[:300]})
    print(("PASS " if ok else "FAIL ") + name + ((" :: " + str(detail)[:160]) if detail and not ok else ""))


def wait_ready(timeout=300):
    """The multilingual index builds in a background thread at boot;
    poll /health until it reports all languages (or time out)."""
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        st, health = call("/health", secret="")
        if st == 200 and health.get("language_count") == 26:
            return health
        time.sleep(5)
    return health


def main():
    # ---- open checks -------------------------------------------------------
    st, health = wait_ready(), None
    health = st
    st = 200 if health.get("status") == "ok" else 0
    check("health_open_200", st == 200, st)
    check("health_english_legacy", health.get("lemmas") == 147478
          and health.get("pronunciations") == 126052
          and health.get("frequency_words") == 50000, health.get("lemmas"))
    langs = health.get("languages", {})
    check("health_language_count_26", health.get("language_count") == 26,
          health.get("language_count"))
    expected_entries = {"es": 36370, "fr": 51339, "it": 46743, "pt": 47086,
                        "nl": 42777, "pl": 45140, "zh": 61525, "ja": 91936,
                        "fi": 129225, "th": 82504, "ro": 49831, "ms": 33903,
                        "id": 36608, "ca": 46345, "eu": 26200, "gl": 23056,
                        "hr": 28881, "sl": 40052, "sk": 29087, "de": 382294,
                        "ru": 42281, "hu": 138812, "eo": 63463, "ar": 69086,
                        "el": 51174}
    bad = {c: (langs.get(c, {}).get("entries"), n)
           for c, n in expected_entries.items()
           if langs.get(c, {}).get("entries") != n}
    check("health_per_language_entries_match_survey_build", not bad, bad)
    st, _ = call("/words/serendipity", secret="")
    check("gate_401_without_header", st == 401, st)
    st, _ = call("/words/serendipity", secret="definitely-wrong")
    check("gate_401_wrong_header", st == 401, st)
    if not SECRET:
        print("NO SECRET: skipping authenticated checks")
        return finish()

    # ---- English regression --------------------------------------------------
    st, rec = call("/words/serendipity")
    r0 = rec["results"][0]
    check("en_serendipity_record", st == 200
          and r0["definition"] == "good luck in making unexpected and fortunate discoveries"
          and rec["syllables"]["count"] == 5
          and rec["frequency"]["zipf"] == 2.54, json.dumps(r0)[:120])
    st, rec = call("/words/run")
    check("en_run_57_senses", st == 200 and len(rec["results"]) == 57,
          len(rec.get("results", [])))
    st, rec = call("/words/geese")
    check("en_geese_morphology", st == 200
          and rec.get("morphology", {}).get("baseForm") == "goose", rec.get("morphology"))
    st, body = call("/words/zzqxw")
    check("en_unknown_word_404", st == 404 and body.get("error") == "word_not_found", st)

    # ---- language plumbing ---------------------------------------------------
    st, body = call("/words/casa?lang=xx")
    check("unknown_language_400_lists_supported", st == 400
          and body.get("error") == "unsupported_language"
          and len(body.get("supportedLanguages", [])) == 26
          and "de" in body["supportedLanguages"], st)
    st, body = call("/languages")
    check("languages_endpoint_26", st == 200 and body.get("languageCount") == 26,
          body.get("languageCount"))

    # ---- curated per-language lookups (source-verified) ----------------------
    def word(w, lang):
        return call("/words/" + urllib.parse.quote(w) + "?lang=" + lang)

    st, rec = word("entidad", "es")
    check("es_entidad_translations_entity", st == 200
          and any("entity" in r.get("translations", []) for r in rec["results"]), st)
    st, rec = word("猫", "ja")
    r0 = rec["results"][0] if rec.get("results") else {}
    check("ja_neko_local_definition", st == 200
          and r0.get("definitionLanguage") == "ja"
          and "feline mammal" in r0.get("englishDefinition", "")
          and "cat" in r0.get("translations", []), json.dumps(r0, ensure_ascii=False)[:120])
    st, rec = word("Haus", "de")
    check("de_haus_house_and_ipa", st == 200
          and any("house" in r.get("translations", []) for r in rec["results"])
          and rec.get("pronunciation", {}).get("all") == "hˈaʊs",
          json.dumps(rec.get("pronunciation"), ensure_ascii=False))
    st, rec = word("собака", "ru")
    check("ru_sobaka_dog", st == 200
          and any(any(t.startswith("dog") for t in r.get("translations", []))
                  for r in rec["results"]), st)
    st, rec = word("ház", "hu")
    check("hu_haz_house", st == 200
          and any(any("house" in t for t in r.get("translations", []))
                  for r in rec["results"]), st)
    st, rec = word("hundo", "eo")
    check("eo_hundo_dog", st == 200
          and any(any(t == "dog" or t.startswith("dog") for t in r.get("translations", []))
                  for r in rec["results"]), st)
    st, rec = word("كتاب", "ar")
    check("ar_kitab_ipa", st == 200
          and rec.get("pronunciation", {}).get("all") == "kitˈaab",
          json.dumps(rec.get("pronunciation"), ensure_ascii=False))
    st, rec = word("κοσμοδρόμιο", "el")
    check("el_kosmodromio_cosmodrome", st == 200
          and any("cosmodrome" in r.get("translations", []) for r in rec["results"]), st)
    st, rec = word("casa", "it")
    check("it_casa_house", st == 200
          and any("house" in r.get("translations", []) for r in rec["results"]), st)
    st, rec = word("talo", "fi")
    check("fi_talo_house", st == 200
          and any("house" in r.get("translations", []) for r in rec["results"]), st)

    # generic smoke: one real lookup per shipped language via its own search
    for code in sorted(expected_entries):
        st, sres = call("/words?lang=%s&limit=10" % code)
        data = [d for d in sres.get("results", {}).get("data", []) if "/" not in d]
        if not data:
            check("smoke_" + code, False, "search returned nothing")
            continue
        st2, rec = word(data[0], code)
        ok = st2 == 200 and any(r.get("definition") for r in rec.get("results", []))
        check("smoke_" + code, ok, "%s -> %s" % (data[0], st2))

    # ---- relations / search / honest gaps ------------------------------------
    st, rec = call("/words/Haus/translations?lang=de")
    check("de_relation_translations", st == 200 and "house" in rec.get("translations", []), st)
    st, rec = call("/words/entidad/definitions?lang=es")
    check("es_relation_definitions", st == 200 and len(rec.get("definitions", [])) >= 1, st)
    st, body = call("/words/chat/pronunciation?lang=fr")
    check("fr_pronunciation_honest_404", st == 404
          and body.get("error") == "pronunciation_not_found", st)
    st, body = call("/words?lang=fr&frequencyMin=3")
    check("fr_frequency_filter_400", st == 400
          and body.get("error") == "unsupported_filter", st)
    st, sres = call("/words?lang=es&letterPattern=%5Ecas&limit=5")
    check("es_search_cas", st == 200 and sres.get("results", {}).get("total", 0) > 50
          and "casa" in sres["results"]["data"], sres.get("results", {}).get("total"))
    st, sres = call("/words?lang=de&hasDetails=pronunciation&limit=3")
    check("de_search_has_pronunciation", st == 200
          and sres.get("results", {}).get("total", 0) > 1000,
          sres.get("results", {}).get("total"))
    st, body = call("/words/zzqxw?lang=es")
    check("es_unknown_word_404", st == 404 and body.get("error") == "word_not_found", st)
    return finish()


def finish():
    passed = sum(1 for r in RESULTS if r["pass"])
    print(f"\n{passed}/{len(RESULTS)} checks passed")
    if OUT:
        json.dump({"base": BASE, "passed": passed, "total": len(RESULTS),
                   "results": RESULTS}, open(OUT, "w"), ensure_ascii=False, indent=1)
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
