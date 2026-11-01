"""SentimentBase: lexicon sentiment analysis (VADER) as a fleet service.

Endpoints:
  GET  /analyze?text=...[&lang=en]
  POST /analyze            {"text": "...", "lang": "en" (optional)}
  POST /analyze/bulk       {"texts": ["...", ...], "lang": "en" (optional)}  (cap 100)
  GET  /health

Conventions follow the fleet scaffold (shared/rapidapi_server.py) and the
driftcheck own-server pattern: stdlib only, structured error objects,
and the RAPIDAPI_PROXY_SECRET gate (401 when the env var is set and the
X-RapidAPI-Proxy-Secret header does not match; /health is exempt).

Engine: vendored VADER (vaderSentiment 3.3.2, MIT) - see VENDORED.md.
The vendored module and lexicon sit next to this file and are imported
with plain python3; no nltk, no model download, no per-call cost.

Magnitude definition (also returned in every result as magnitude_basis):
  magnitude_raw = sum of abs(raw lexicon valence) over every token in
                  the caller's text that matches the VADER lexicon
                  (per occurrence, before VADER's rule adjustments
                  such as negation, boosters, caps and punctuation).
  magnitude     = magnitude_raw / (magnitude_raw + 15.0), using the
                  same alpha=15 normalization constant VADER itself
                  uses for its compound score. Range 0..1: 0 means no
                  lexicon terms matched, and the value approaches 1
                  as total absolute valence grows. Magnitude measures
                  how much sentiment-bearing material is present,
                  regardless of direction; `score` gives the direction.

Label thresholds (also returned in every result):
  score >=  0.05 -> "positive"
  score <= -0.05 -> "negative"
  otherwise      -> "neutral"
These are VADER's own documented compound thresholds.
"""
import json
import os
import re
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vaderSentiment import SentimentIntensityAnalyzer  # vendored, MIT

SERVICE = "sentimentbase"
ENGINE = "VADER (vaderSentiment)"
ENGINE_VERSION = "3.3.2"
LEXICON_VERSION = "vaderSentiment 3.3.2 lexicon"
MAX_TEXT_CHARS = 10_000
MAX_BULK_ITEMS = 100
MAX_BODY_BYTES = 2_000_000
TOP_TERMS_LIMIT = 5

POS_THRESHOLD = 0.05
NEG_THRESHOLD = -0.05
THRESHOLDS = {"positive_at_or_above": POS_THRESHOLD,
              "negative_at_or_below": NEG_THRESHOLD,
              "neutral_between": [NEG_THRESHOLD, POS_THRESHOLD]}

MAGNITUDE_BASIS = (
    "sum of absolute raw lexicon valences of matched tokens (per occurrence, "
    "before VADER rule adjustments), normalized to 0..1 as raw/(raw+15) "
    "using VADER's alpha=15 normalization constant"
)

ANALYZER = SentimentIntensityAnalyzer()

# Sentence split: break after ., ! or ? (plus any closing quotes/brackets)
# followed by whitespace or end of text. Honest stdlib splitter: it does
# not special-case every abbreviation, which is a stated /health limit.
_SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?])["\'”’)\]]*\s+')
# Word tokens for term extraction: keep internal apostrophes, strip the rest.
_TOKEN_RE = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")


def label_for(score):
    if score >= POS_THRESHOLD:
        return "positive"
    if score <= NEG_THRESHOLD:
        return "negative"
    return "neutral"


def split_sentences(text):
    parts = [p.strip() for p in _SENTENCE_SPLIT_RE.split(text.strip())]
    return [p for p in parts if p]


def _matched_terms(text):
    """(term, raw lexicon valence) for each token occurrence matching the lexicon."""
    out = []
    for tok in _TOKEN_RE.findall(text.lower()):
        valence = ANALYZER.lexicon.get(tok)
        if valence is not None and valence != 0:
            out.append((tok, valence))
    # Emoticons / multi-char lexicon entries (e.g. ":)") are space-delimited
    # in VADER; catch lexicon keys that are not plain word tokens.
    for token in text.split():
        cleaned = token.strip().lower()
        if cleaned and not _TOKEN_RE.fullmatch(cleaned) and cleaned in ANALYZER.lexicon:
            valence = ANALYZER.lexicon[cleaned]
            if valence != 0:
                out.append((cleaned, valence))
    return out


def _top_terms(matched, positive):
    agg = {}
    for term, valence in matched:
        if (valence > 0) != positive:
            continue
        entry = agg.setdefault(term, {"term": term, "valence": valence, "count": 0})
        entry["count"] += 1
    ranked = sorted(agg.values(), key=lambda e: (-abs(e["valence"]), e["term"]))
    return ranked[:TOP_TERMS_LIMIT]


def analyze_text(text):
    """Full per-text result dict (assumes text already validated)."""
    scores = ANALYZER.polarity_scores(text)
    compound = round(scores["compound"], 4)
    matched = _matched_terms(text)
    raw = sum(abs(v) for _, v in matched)
    magnitude = round(raw / (raw + 15.0), 4) if raw else 0.0
    sentences = []
    for sentence in split_sentences(text):
        s_compound = round(ANALYZER.polarity_scores(sentence)["compound"], 4)
        sentences.append({"sentence": sentence,
                          "score": s_compound,
                          "label": label_for(s_compound)})
    return {
        "text": text,
        "score": compound,
        "magnitude": magnitude,
        "magnitude_raw": round(raw, 4),
        "magnitude_basis": MAGNITUDE_BASIS,
        "label": label_for(compound),
        "label_thresholds": THRESHOLDS,
        "scores": {"pos": scores["pos"], "neu": scores["neu"], "neg": scores["neg"]},
        "sentences": sentences,
        "top_positive_terms": _top_terms(matched, positive=True),
        "top_negative_terms": _top_terms(matched, positive=False),
        "lexicon_version": LEXICON_VERSION,
        "engine": ENGINE,
        "engine_version": ENGINE_VERSION,
    }


def validate_text(text):
    """Return an error payload dict, or None when the text is usable."""
    if text is None:
        return {"error": "missing_parameter",
                "detail": "Parameter 'text' is required."}
    if not isinstance(text, str):
        return {"error": "missing_parameter",
                "detail": "Parameter 'text' must be a string."}
    if not text.strip():
        return {"error": "text_empty",
                "detail": "Parameter 'text' was provided but is empty."}
    if len(text) > MAX_TEXT_CHARS:
        return {"error": "text_too_long",
                "detail": f"Text is {len(text)} characters; the limit is {MAX_TEXT_CHARS}.",
                "received_length": len(text),
                "max_length": MAX_TEXT_CHARS}
    return None


def check_lang(lang):
    """Return an error payload dict, or None. Absent lang means English."""
    if lang is None:
        return None
    if str(lang).strip().lower() == "en":
        return None
    return {"error": "unsupported_language",
            "detail": ("SentimentBase is English-first (VADER lexicon). "
                       f"lang={lang!r} is not supported; omit lang or use 'en'."),
            "lang": lang,
            "supported_languages": ["en"]}


def health():
    return 200, {
        "status": "ok",
        "service": SERVICE,
        "engine": ENGINE,
        "engine_version": ENGINE_VERSION,
        "lexicon_version": LEXICON_VERSION,
        "limits": {
            "max_text_chars": MAX_TEXT_CHARS,
            "max_bulk_items": MAX_BULK_ITEMS,
            "languages": ["en"],
            "language_note": ("English-first. Non-English detection is not "
                              "attempted: pass lang explicitly and any value "
                              "other than 'en' returns 422 unsupported_language; "
                              "with no lang, text is analyzed as English."),
            "method": ("Lexicon sentiment (VADER), not deep understanding: "
                       "sarcasm, domain jargon, and mixed-aspect text score "
                       "approximately. The per-sentence breakdown is returned "
                       "so callers can see a mixed text instead of trusting "
                       "one averaged number."),
            "sentence_split": ("Stdlib regex splitter on ., ! and ?; unusual "
                               "abbreviations can split imperfectly."),
        },
        "endpoints": ["GET /analyze?text=", "POST /analyze",
                      "POST /analyze/bulk", "GET /health"],
    }


def run_server(port):
    proxy_secret = os.environ.get("RAPIDAPI_PROXY_SECRET")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, status, payload, started=None):
            if isinstance(payload, dict):
                payload = dict(payload)
                meta = {"service": SERVICE}
                if started is not None:
                    meta["latency_ms"] = round((time.time() - started) * 1000)
                payload.setdefault("_meta", meta)
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _gate_ok(self, path):
            if not proxy_secret or path == "/health":
                return True
            if self.headers.get("X-RapidAPI-Proxy-Secret") != proxy_secret:
                self._send(401, {"error": "unauthorized",
                                 "detail": "Missing or invalid RapidAPI proxy secret."})
                return False
            return True

        def _handle_analyze(self, text, lang, started):
            err = check_lang(lang)
            if err:
                return self._send(422, err, started)
            err = validate_text(text)
            if err:
                return self._send(422, err, started)
            return self._send(200, analyze_text(text), started)

        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            if not self._gate_ok(path):
                return
            started = time.time()
            if path == "/health":
                status, payload = health()
                return self._send(status, payload, started)
            if path == "/analyze":
                params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
                return self._handle_analyze(params.get("text"), params.get("lang"), started)
            return self._send(404, {"error": "not_found",
                                    "detail": f"No endpoint at {path}. See /health for service info."},
                              started)

        def do_POST(self):
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            if not self._gate_ok(path):
                return
            started = time.time()
            if path not in ("/analyze", "/analyze/bulk"):
                return self._send(404, {"error": "not_found",
                                        "detail": f"No endpoint at {path}. See /health for service info."},
                                  started)
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = 0
            if length <= 0 or length > MAX_BODY_BYTES:
                return self._send(422, {"error": "invalid_body",
                                        "detail": f"Send a JSON body of at most {MAX_BODY_BYTES} bytes."},
                                  started)
            raw = self.rfile.read(length)
            try:
                body = json.loads(raw.decode("utf-8"))
                if not isinstance(body, dict):
                    raise ValueError("body must be a JSON object")
            except Exception as exc:
                return self._send(422, {"error": "invalid_body", "detail": str(exc)}, started)

            if path == "/analyze":
                return self._handle_analyze(body.get("text"), body.get("lang"), started)

            # POST /analyze/bulk
            err = check_lang(body.get("lang"))
            if err:
                return self._send(422, err, started)
            texts = body.get("texts")
            if texts is None:
                return self._send(422, {"error": "missing_parameter",
                                        "detail": "Field 'texts' (array of strings) is required."},
                                  started)
            if not isinstance(texts, list):
                return self._send(422, {"error": "invalid_body",
                                        "detail": "Field 'texts' must be an array of strings."},
                                  started)
            if len(texts) > MAX_BULK_ITEMS:
                return self._send(422, {"error": "bulk_too_large",
                                        "detail": f"Bulk cap is {MAX_BULK_ITEMS} texts; received {len(texts)}.",
                                        "received_count": len(texts),
                                        "max_items": MAX_BULK_ITEMS}, started)
            results = []
            analyzed = 0
            for i, item in enumerate(texts):
                item_err = validate_text(item)
                if item_err:
                    results.append({"index": i, **item_err})
                else:
                    analyzed += 1
                    results.append({"index": i, **analyze_text(item)})
            return self._send(200, {
                "count": len(texts),
                "analyzed": analyzed,
                "results": results,
                "metering_note": "one request counted per text analyzed",
                "lexicon_version": LEXICON_VERSION,
            }, started)

    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    run_server(int(os.environ.get("PORT", "8119")))
