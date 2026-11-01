"""SwiftHumanize - writing that reads like a person wrote it.

One job, distinct from SwiftRewrite (a general paraphraser): keep the
writer's meaning, facts, and as much wording as possible while removing
the patterns that make text read as AI-generated, and restore natural
human rhythm. Plus /score, a heuristic pattern analysis (never a
detector verdict).

Endpoints:
  GET  /health    open
  POST /humanize  {text, tone?, strength?, style_sample?}
  POST /score     {text}
(GET with query parameters also works on /humanize and /score, the
fleet convention.)

Engine: Gemini Flash when GEMINI_API_KEY is set (GEMINI_BASE_URL may
override the API base, which is how the home instance reaches the
engine through the local connector bridge with no key stored on the
machine). Without a key, a labeled built-in cleanup answers instead;
nothing is ever faked. Names, numbers, and quoted spans are extracted
before the model call and verified in the output, with one corrective
retry. No em-dash character ever leaves this service: post-processing
replaces any the model produces.

Gates: RAPIDAPI_PROXY_SECRET (fleet lane, X-RapidAPI-Proxy-Secret) and
SWIFTHUMANIZE_SECRET (home lane, X-SwiftHumanize-Secret); /health is
always open. Zero dependencies. Run: python3 app.py (PORT env, default
8115; BIND env, default 0.0.0.0).
"""
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

MIN_CHARS = 10
MAX_CHARS = 5000
MAX_SAMPLE_CHARS = 3000
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
GEMINI_BASE = os.environ.get("GEMINI_BASE_URL",
                             "https://generativelanguage.googleapis.com/v1beta")
TONES = ("keep", "casual", "professional")
STRENGTHS = {"light": 0.5, "standard": 0.7, "strong": 0.85}
EM_DASH = "—"
EN_DASH = "–"

# ---------------------------------------------------------------- score

TELL_PHRASES = [
    # stock transitions and filler
    ("moreover", "stock transition"), ("furthermore", "stock transition"),
    ("additionally", "stock transition"), ("in conclusion", "stock transition"),
    ("it is important to note", "filler"), ("it's important to note", "filler"),
    ("it is worth noting", "filler"), ("it is important to understand", "filler"),
    ("when it comes to", "filler"), ("in today's fast-paced world", "filler opener"),
    ("in today's digital age", "filler opener"), ("in the ever-evolving", "filler opener"),
    ("in the realm of", "filler"), ("at the end of the day", "filler"),
    ("needless to say", "filler"), ("first and foremost", "filler"),
    ("last but not least", "filler"), ("a wide range of", "padding"),
    ("a variety of", "padding"), ("in order to", "padding"),
    ("due to the fact that", "padding"), ("plays a crucial role", "stock phrase"),
    ("plays a vital role", "stock phrase"), ("serves as a testament", "stock phrase"),
    ("a testament to", "stock phrase"), ("stands as", "stock phrase"),
    # AI verbs and adjectives
    ("delve", "AI verb"), ("delving", "AI verb"), ("leverage", "AI verb"),
    ("leveraging", "AI verb"), ("utilize", "AI verb"), ("utilizing", "AI verb"),
    ("harness", "AI verb"), ("elevate", "AI verb"), ("unlock the", "AI verb"),
    ("streamline", "AI verb"), ("foster", "AI verb"), ("underscore", "AI verb"),
    ("showcase", "AI verb"), ("showcasing", "AI verb"), ("boasts", "AI verb"),
    ("robust", "padded adjective"), ("seamless", "padded adjective"),
    ("seamlessly", "padded adjective"), ("comprehensive", "padded adjective"),
    ("cutting-edge", "padded adjective"), ("state-of-the-art", "padded adjective"),
    ("game-changer", "hype"), ("game-changing", "hype"), ("vibrant", "padded adjective"),
    ("intricate", "padded adjective"), ("pivotal", "padded adjective"),
    ("crucial", "padded adjective"), ("esteemed", "padded adjective"),
    ("meticulous", "padded adjective"), ("meticulously", "padded adjective"),
    ("transformative", "hype"), ("revolutionize", "hype"), ("ever-evolving", "hype"),
    ("dynamic landscape", "hype"), ("tapestry", "AI metaphor"), ("landscape of", "AI metaphor"),
]


def split_sentences(text):
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p.strip()]


def score_text(text):
    lower = text.lower()
    words = re.findall(r"\b[\w']+\b", text)
    n_words = max(len(words), 1)
    found = []
    total_tells = 0
    for phrase, category in TELL_PHRASES:
        hits = len(re.findall(r"\b" + re.escape(phrase) + r"\b", lower))
        if hits:
            total_tells += hits
            found.append({"phrase": phrase, "category": category, "count": hits})
    found.sort(key=lambda f: -f["count"])
    em_dashes = text.count(EM_DASH)
    triplets = len(re.findall(r"\b[\w'-]+,\s+[\w'-]+,\s+and\s+[\w'-]+", text))
    formatting = len(re.findall(r"(?m)^\s*(#{1,6}\s|[-*]\s)", text)) \
        + text.count("**") // 2
    sentences = split_sentences(text)
    lengths = [len(re.findall(r"\b[\w']+\b", s)) for s in sentences]
    if len(lengths) >= 2:
        mean = sum(lengths) / len(lengths)
        var = sum((x - mean) ** 2 for x in lengths) / len(lengths)
        stdev = math.sqrt(var)
        cv = round(stdev / mean, 3) if mean else 0.0
    elif lengths:
        mean, stdev, cv = float(lengths[0]), 0.0, 0.0
    else:
        mean, stdev, cv = 0.0, 0.0, 0.0
    if len(lengths) < 3:
        uniformity = "too few sentences to judge"
    elif cv < 0.25:
        uniformity = "very uniform (a common AI pattern)"
    elif cv < 0.45:
        uniformity = "somewhat uniform"
    else:
        uniformity = "varied (a common human pattern)"
    penalty = min(40.0, total_tells / n_words * 100 * 6)
    penalty += min(12.0, em_dashes * 4)
    penalty += min(9.0, triplets * 3)
    penalty += min(8.0, formatting * 2)
    if len(lengths) >= 3:
        if cv < 0.25:
            penalty += 20
        elif cv < 0.35:
            penalty += 10
        elif cv < 0.45:
            penalty += 4
    score = int(max(0, min(100, round(100 - penalty))))
    if score >= 85:
        band = "reads human"
    elif score >= 65:
        band = "mostly human, some AI patterns"
    elif score >= 45:
        band = "mixed, noticeable AI patterns"
    else:
        band = "strong AI patterns"
    return {
        "human_likeness_score": score,
        "assessment": band,
        "method": "heuristic pattern analysis of surface features; not an AI detector verdict",
        "words": len(words),
        "ai_tell_phrases": {"total": total_tells, "found": found},
        "em_dash_count": em_dashes,
        "triplet_list_patterns": triplets,
        "formatting_artifacts": formatting,
        "sentences": {"count": len(lengths),
                      "mean_words": round(mean, 1),
                      "stdev_words": round(stdev, 1),
                      "length_variation_cv": cv,
                      "uniformity": uniformity},
    }


# ------------------------------------------------------------- humanize

_CLEANUPS = [
    (r"\bIt is important to note that\s+", ""),
    (r"\bIt's important to note that\s+", ""),
    (r"\bIt is worth noting that\s+", ""),
    (r"\bIn today's fast-paced world,\s+", ""),
    (r"\bIn today's digital age,\s+", ""),
    (r"\bMoreover,\s+", "Also, "),
    (r"\bFurthermore,\s+", "Also, "),
    (r"\bAdditionally,\s+", "Also, "),
    (r"\bdelve into\b", "look at"), (r"\bdelves into\b", "looks at"),
    (r"\butilize\b", "use"), (r"\butilizes\b", "uses"), (r"\butilizing\b", "using"),
    (r"\bleverage\b", "use"), (r"\bleveraging\b", "using"),
    (r"\bin order to\b", "to"),
    (r"\bdue to the fact that\b", "because"),
    (r"\ba wide range of\b", "many"), (r"\ba variety of\b", "several"),
    (r"\bplays a crucial role in\b", "matters for"),
    (r"\bplays a vital role in\b", "matters for"),
]


def builtin_cleanup(text):
    out = text
    for pattern, repl in _CLEANUPS:
        out = re.sub(pattern, repl, out, flags=re.IGNORECASE)
    out = re.sub(r"(?<=[.!?]\s)([a-z])", lambda m: m.group(1).upper(), out)
    if out and out[0].islower():
        out = out[0].upper() + out[1:]
    return out


def strip_em_dashes(text):
    out = text.replace(" " + EM_DASH + " ", ", ")
    out = out.replace(EM_DASH, ", ")
    out = re.sub(r",\s*,", ",", out)
    out = re.sub(r"\s+", " ", out) if "\n" not in out else out
    out = re.sub(r" +", " ", out)
    out = re.sub(r"\(,", "(", out)
    return out.strip()


def extract_names(text):
    names = re.findall(r"\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b", text)
    starts = set()
    for sent in split_sentences(text):
        m = re.match(r"\s*([A-Z][a-z]+)", sent or "")
        if m:
            starts.add(m.group(1))
    return sorted({n for n in names if n not in starts or " " in n})


def extract_numbers(text):
    raw = re.findall(r"\$?\d[\d,]*(?:\.\d+)?%?", text)
    return sorted({r for r in raw if re.search(r"\d", r)})


def extract_quotes(text):
    return [q for q in re.findall(r'"([^"]{3,})"', text)]


def _norm_num(value):
    return value.replace(",", "").replace("$", "").rstrip("%")


def verify_preservation(original, output):
    names = extract_names(original)
    numbers = extract_numbers(original)
    quotes = extract_quotes(original)
    out_norm = {_norm_num(n) for n in extract_numbers(output)}
    return {
        "names": names,
        "names_preserved": all(n in output for n in names),
        "numbers": numbers,
        "numbers_preserved": all(_norm_num(n) in out_norm for n in numbers),
        "quotes": quotes,
        "quotes_preserved": all(q in output for q in quotes),
    }


TONE_LINES = {
    "keep": "Keep the original tone and register. Do not make it more casual or more formal than it already is.",
    "casual": "Make it sound like a person writing to someone they know: contractions, plain everyday words, a relaxed rhythm. Keep it appropriate to the content.",
    "professional": "Keep it business-appropriate and clear, the way a person writes a good email: no hype, no stock phrases, contractions are fine.",
}
STRENGTH_LINES = {
    "light": "Change as little as possible. Only remove AI tells and obvious padding; keep the original sentences and wording wherever they already sound natural.",
    "standard": "Rework the rhythm freely: split or merge sentences, vary their lengths, cut padding. Keep the content, the order, and every fact.",
    "strong": "Rewrite with a freer hand wherever the phrasing sounds machine-made. Every fact stays exactly; the wording can change substantially.",
}


def build_prompt(text, tone, strength, style_sample, correction=None):
    lines = [
        "You are a line editor whose only job is to make text read like a specific human wrote it, not an AI.",
        "",
        "Rules, all mandatory:",
        "1. Preserve every fact, name, number, date, and quotation exactly as written. Add no facts, examples, or claims that are not in the original. Drop no information.",
        "2. Remove AI stock language: filler openers (\"in today's fast-paced world\"), stock transitions (\"moreover\", \"furthermore\", \"it is important to note\"), AI verbs (\"delve\", \"leverage\", \"utilize\"), padded adjective stacks, and hype words.",
        "3. Vary sentence length on purpose. Mix short, plain sentences with longer ones. An occasional short fragment is fine where it sounds natural for the tone.",
        "4. Cut padding: throat-clearing first sentences, summaries that repeat what was just said, and three-item lists padded to sound complete (keep the strongest items; keep a list whole only when every item is factual content).",
        "5. Use contractions naturally where the tone allows. Prefer plain words over formal ones when both mean the same thing.",
        "6. Prefer active voice. Passive constructions that hide who is acting (\"the client will be notified through the appropriate channels\") are a machine habit; use the natural actor the context implies (\"we will let the client know\") without inventing new people or facts.",
        "7. Make sentence lengths visibly uneven: follow a long sentence with a short one. Do not let consecutive sentences land at the same length. If the original is a run of similar-length statements, break the pattern on purpose: combine two into one longer sentence, then land one short sentence of under eight words.",
        "8. Never use the em-dash character. Use commas, periods, colons, or parentheses instead.",
        "9. Return plain text only: no markdown, no headings, no bullet points, no quotation marks around the result, no commentary before or after. Keep the paragraph breaks of the original. Always finish your last sentence; never stop mid-thought.",
        "",
        "Tone: " + TONE_LINES[tone],
        "Strength: " + STRENGTH_LINES[strength],
    ]
    if style_sample:
        lines += ["",
                  "Match the voice of this writing sample: its sentence lengths, vocabulary, punctuation habits, and level of formality. Do not reuse its content or facts.",
                  "VOICE SAMPLE:",
                  style_sample]
    if correction:
        lines += ["",
                  "A previous attempt changed or dropped these items, which must appear exactly as in the original: "
                  + "; ".join(correction)]
    lines += ["", "TEXT TO EDIT:", text]
    return "\n".join(lines)


def gemini_humanize(text, tone, strength, style_sample, correction=None, budget=None):
    prompt = build_prompt(text, tone, strength, style_sample, correction)
    payload = {"contents": [{"parts": [{"text": prompt}]}],
               "generationConfig": {"temperature": STRENGTHS[strength],
                                    "thinkingConfig": {"thinkingBudget": 0},
                                    "maxOutputTokens": budget or min(8192, max(2048, len(text)))}}
    req = urllib.request.Request(
        f"{GEMINI_BASE}/models/{GEMINI_MODEL}:generateContent",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": GEMINI_KEY},
        method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    candidate = data["candidates"][0]
    if candidate.get("finishReason") == "MAX_TOKENS":
        if not budget:
            return gemini_humanize(text, tone, strength, style_sample,
                                   correction, budget=8192)
        raise ValueError("model output truncated at maximum budget")
    parts = candidate["content"]["parts"]
    out = "".join(p.get("text", "") for p in parts).strip()
    out = re.sub(r"^```[a-z]*\n?|\n?```$", "", out).strip()
    if len(out) >= 2 and out[0] == '"' and out[-1] == '"' and text[0] != '"':
        out = out[1:-1].strip()
    return out


def do_humanize(params):
    text = params.get("text", "")
    if not isinstance(text, str):
        return 422, {"error": "invalid_parameter", "detail": "text must be a string."}
    tone = str(params.get("tone", "keep")).lower()
    strength = str(params.get("strength", "standard")).lower()
    style_sample = params.get("style_sample") or None
    if tone not in TONES:
        return 422, {"error": "invalid_parameter",
                     "detail": f"tone must be one of: {', '.join(TONES)}."}
    if strength not in STRENGTHS:
        return 422, {"error": "invalid_parameter",
                     "detail": f"strength must be one of: {', '.join(STRENGTHS)}."}
    n = len(text)
    if n < MIN_CHARS:
        return 422, {"error": "text_too_short",
                     "detail": f"Text is {n} characters; the minimum is {MIN_CHARS}."}
    if n > MAX_CHARS:
        return 422, {"error": "text_too_long",
                     "detail": f"Text is {n} characters; the maximum is {MAX_CHARS}. Split longer text into chunks."}
    if style_sample is not None:
        if not isinstance(style_sample, str):
            return 422, {"error": "invalid_parameter", "detail": "style_sample must be a string."}
        if len(style_sample) > MAX_SAMPLE_CHARS:
            return 422, {"error": "style_sample_too_long",
                         "detail": f"style_sample is {len(style_sample)} characters; the maximum is {MAX_SAMPLE_CHARS}."}
    before = score_text(text)
    engine, note, out = "gemini", None, None
    if GEMINI_KEY:
        try:
            out = gemini_humanize(text, tone, strength, style_sample)
            if not out:
                raise ValueError("empty model response")
            check = verify_preservation(text, strip_em_dashes(out))
            if not (check["names_preserved"] and check["numbers_preserved"]
                    and check["quotes_preserved"]):
                missing = [x for x in check["names"] if x not in out] \
                    + [x for x in check["numbers"] if _norm_num(x) not in
                       {_norm_num(y) for y in extract_numbers(out)}] \
                    + [q for q in check["quotes"] if q not in out]
                retry = gemini_humanize(text, tone, strength, style_sample,
                                        correction=missing)
                if retry:
                    out = retry
        except Exception as exc:
            out = builtin_cleanup(text)
            engine = "builtin-cleanup"
            note = f"Model engine unavailable ({type(exc).__name__}); answered with the built-in cleanup engine."
    else:
        out = builtin_cleanup(text)
        engine = "builtin-cleanup"
        note = "AI engine key not configured on this deployment yet; answered with the built-in cleanup engine, which removes stock phrases but does not do the full voice pass."
    out = strip_em_dashes(out)
    preserved = verify_preservation(text, out)
    return 200, {
        "original": text,
        "humanized": out,
        "tone": tone,
        "strength": strength,
        "style_sample_used": bool(style_sample),
        "engine": engine,
        "engine_note": note,
        "preserved": {
            "names": preserved["names"],
            "names_preserved": preserved["names_preserved"],
            "numbers": preserved["numbers"],
            "numbers_preserved": preserved["numbers_preserved"],
            "quotes_preserved": preserved["quotes_preserved"],
        },
        "score_before": before["human_likeness_score"],
        "score_after": score_text(out)["human_likeness_score"],
        "characters": n,
        "note": "Scores are heuristic pattern readings, not AI detector verdicts.",
    }


def do_score(params):
    text = params.get("text", "")
    if not isinstance(text, str):
        return 422, {"error": "invalid_parameter", "detail": "text must be a string."}
    n = len(text)
    if n < MIN_CHARS:
        return 422, {"error": "text_too_short",
                     "detail": f"Text is {n} characters; the minimum is {MIN_CHARS}."}
    if n > MAX_CHARS:
        return 422, {"error": "text_too_long",
                     "detail": f"Text is {n} characters; the maximum is {MAX_CHARS}. Split longer text into chunks."}
    result = score_text(text)
    result["characters"] = n
    return 200, result


def health(params):
    return 200, {
        "status": "ok",
        "service": "swifthumanize",
        "uptime_target": "99.9%",
        "ai_engine": "configured" if GEMINI_KEY else "awaiting key (built-in cleanup active)",
        "limits": {"min_chars": MIN_CHARS, "max_chars": MAX_CHARS,
                   "max_style_sample_chars": MAX_SAMPLE_CHARS},
        "endpoints": {"POST /humanize": "rewrite text so it reads human-written",
                      "POST /score": "heuristic AI-pattern analysis, no rewrite",
                      "GET /health": "this"},
        "honesty": "Improves naturalness and removes common AI tells. Does not guarantee passing any AI detector; detectors are themselves unreliable, and /score is a heuristic, not a verdict.",
    }


ROUTES = {"/humanize": do_humanize, "/score": do_score, "/health": health}
PROXY_SECRET = os.environ.get("RAPIDAPI_PROXY_SECRET")
HOME_SECRET = os.environ.get("SWIFTHUMANIZE_SECRET")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _authorized(self, path):
        if path == "/health":
            return True
        if PROXY_SECRET and self.headers.get("X-RapidAPI-Proxy-Secret") != PROXY_SECRET:
            return False
        if HOME_SECRET and self.headers.get("X-SwiftHumanize-Secret") != HOME_SECRET:
            return False
        return True

    def _send(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _dispatch(self, params):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        started = time.time()
        if not self._authorized(path):
            return self._send(401, {"error": "unauthorized",
                                    "detail": "Missing or invalid service secret."})
        handler = ROUTES.get(path)
        if handler is None:
            return self._send(404, {"error": "not_found",
                                    "detail": f"No endpoint at {path}. See /health for service info."})
        try:
            status, payload = handler(params)
        except Exception as exc:
            status, payload = 502, {"error": "upstream_error",
                                    "detail": f"{type(exc).__name__}: {exc}"}
        if isinstance(payload, dict):
            payload.setdefault("_meta", {"service": "swifthumanize",
                                         "latency_ms": round((time.time() - started) * 1000)})
        self._send(status, payload)

    def do_GET(self):
        parsed = urlparse(self.path)
        params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        self._dispatch(params)

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        params = {}
        if raw:
            try:
                params = json.loads(raw.decode("utf-8"))
                if not isinstance(params, dict):
                    raise ValueError("body must be a JSON object")
            except Exception as exc:
                return self._send(400, {"error": "invalid_json",
                                        "detail": f"Request body is not valid JSON ({type(exc).__name__})."})
        parsed = urlparse(self.path)
        for k, v in parse_qs(parsed.query).items():
            params.setdefault(k, v[0])
        self._dispatch(params)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8115"))
    bind = os.environ.get("BIND", "0.0.0.0")
    ThreadingHTTPServer((bind, port), Handler).serve_forever()
