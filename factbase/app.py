"""FactBase - evidence-based fact-checking for text and speech
(the user's own product, 2026-10-31; RapidAPI lane build #14).

Checks factual claims against published fact-checks and retrievable
web evidence, and returns a sourced verdict per claim. It is NOT an
oracle: a claim with no retrievable evidence returns "unverified",
never a guessed verdict, and every non-unverified verdict carries
the sources it rests on.

Pipeline per claim:
1. Claim extraction (Gemini): the checkable factual claims are
   pulled out of the input; opinions, predictions and questions are
   left out. /check-audio transcribes speech with Gemini audio
   first, then runs the identical pipeline on the transcript.
2. Evidence retrieval, three layers, all zero marginal cost:
   - the Google Fact Check Tools API (ClaimReview database of
     published fact-checks) when an API key is configured;
   - general web search (keyless; DuckDuckGo HTML with paced
     retries and fallbacks, including one fact-check-targeted query
     per claim);
   - Wikipedia search (keyless) for entity grounding.
3. Verdict synthesis (Gemini): the model sees ONLY the claim and the
   retrieved evidence and must pick from exactly four verdicts
   (supported / refuted / mixed / unverified). If no evidence was
   retrieved, the verdict is "unverified" by construction and the
   model is never asked. The confidence note is computed in code
   from the evidence composition, not by the model.

Engine states, reported honestly in /health:
- live: GEMINI_API_KEY is set; the full pipeline runs.
- awaiting_key: no key yet; /check-text, /check-claim and
  /check-audio answer an explicit 503 engine_not_configured (the
  lane's standing key step: the owner adds the same Gemini key the
  other Gemini services use). The deployed service rests in this
  state until then and never serves staged verdicts.

The server keeps the lane scaffold's exact conventions (shared with
XBase and DriftCheck): stdlib only, the RapidAPI proxy-secret gate
(401 JSON without the X-RapidAPI-Proxy-Secret header, /health
always open), and explicit structured JSON errors for every failure.

Endpoints:
  POST /check-text   {text, max_claims? (cap 10)}
                     -> per-claim verdicts with evidence
  POST /check-claim  {claim} -> one claim through the same pipeline
  POST /check-audio  multipart audio file -> transcript + verdicts
  GET  /health       -> service status, engine states, limits
Run: python3 app.py (PORT env, default 8115). No dependencies.
"""
import base64
import html as html_lib
import json
import os
import re
import threading
import time
import urllib.request
import urllib.error
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SERVICE = "factbase"
VERSION = "1.0.0"
BUILD = "2026-10-31-v1"
RECENT = []                       # last request outcomes (see /health)

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
# Per-model quotas on the owner's key are separate buckets: when the
# primary model answers 429, the same request is retried against the
# fallback model instead of failing the check.
# Fallback choice, measured at build time on the owner's key:
# gemini-2.5-flash is retired for new users (404), gemini-3.7-flash
# and gemini-3.8-flash answered a trivial prompt in ~77-84s (too
# slow for a checking call), gemini-3.1-flash-lite answered in ~3s
# with clean JSON and has its own quota bucket.
GEMINI_FALLBACK_MODEL = os.environ.get("GEMINI_FALLBACK_MODEL",
                                       "gemini-3.1-flash-lite")
GEMINI_BASE = os.environ.get(
    "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"
).rstrip("/")
# The Fact Check Tools API accepts the same Google API key style; a
# dedicated key wins, otherwise the Gemini key is tried (it works
# when the API is enabled on that key's Google Cloud project).
FACTCHECK_KEY = os.environ.get("FACTCHECK_API_KEY", "") or GEMINI_KEY

MAX_TEXT_CHARS = 8000
MAX_CLAIMS_CAP = 10
DEFAULT_MAX_CLAIMS = 5
MAX_BODY = 1_000_000              # JSON endpoints
MAX_AUDIO_BODY = 12_000_000       # /check-audio multipart envelope
MAX_EVIDENCE_PER_CLAIM = 7
FETCH_TIMEOUT = 12
GEMINI_TIMEOUT = 60
UA = "FactBase/1.0 (+https://rapidapi.com/YamilLittle/api/factbase)"
BROWSER_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

VERDICTS = ("supported", "refuted", "mixed", "unverified")

AUDIO_MIME = {
    ".mp3": "audio/mp3", ".wav": "audio/wav", ".ogg": "audio/ogg",
    ".flac": "audio/flac", ".aac": "audio/aac", ".aiff": "audio/aiff",
    ".aif": "audio/aiff",
}


def engine_state():
    return "live" if GEMINI_KEY else "awaiting_key"


# --------------------------------------------------------------------------
# Gemini client (extraction, verdict synthesis, audio transcription).
# One retry on transient upstream errors (the SwiftTranslate pattern).
# --------------------------------------------------------------------------
def _gemini_once(model, parts, json_mode, timeout):
    payload = {"contents": [{"parts": parts}],
               "generationConfig": {"temperature": 0.1}}
    if json_mode:
        payload["generationConfig"]["responseMimeType"] = "application/json"
    req = urllib.request.Request(
        f"{GEMINI_BASE}/models/{model}:generateContent",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json",
                 "x-goog-api-key": GEMINI_KEY, "User-Agent": UA},
        method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    text = "".join(
        p.get("text", "")
        for cand in data.get("candidates", [])
        for p in cand.get("content", {}).get("parts", []))
    if not text.strip():
        raise ValueError("empty model response")
    return text


def gemini_generate(parts, json_mode=False, timeout=GEMINI_TIMEOUT):
    """One logical Gemini call. Transient 5xx get one spaced retry;
    a 429 (the primary model's quota bucket is exhausted) retries
    once after a pause, then falls back to GEMINI_FALLBACK_MODEL,
    whose quota bucket is separate."""
    models = [GEMINI_MODEL]
    if GEMINI_FALLBACK_MODEL and GEMINI_FALLBACK_MODEL != GEMINI_MODEL:
        models.append(GEMINI_FALLBACK_MODEL)
    last_exc = None
    for model in models:
        for attempt in range(2):
            try:
                return _gemini_once(model, parts, json_mode, timeout)
            except urllib.error.HTTPError as exc:
                last_exc = exc
                if exc.code == 429 and attempt == 0:
                    time.sleep(8)
                    continue
                if exc.code == 429:
                    break  # quota bucket spent; try the fallback model
                if exc.code in (500, 503) and attempt == 0:
                    time.sleep(2)
                    continue
                raise
            except Exception as exc:
                last_exc = exc
                if attempt == 0:
                    time.sleep(2)
                    continue
                raise
    raise last_exc


def _parse_json(text):
    """Defensive JSON parse: strip code fences, fall back to the
    outermost bracket span."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.IGNORECASE)
    try:
        return json.loads(t)
    except Exception:
        start = min([i for i in (t.find("["), t.find("{")) if i >= 0],
                    default=-1)
        end = max(t.rfind("]"), t.rfind("}"))
        if start >= 0 and end > start:
            return json.loads(t[start:end + 1])
        raise


def extract_claims(text, max_claims):
    prompt = (
        "Extract the checkable factual claims from the text below. A "
        "checkable factual claim is a statement about the world that "
        "could in principle be verified against evidence (a date, a "
        "quantity, an event, an attribution, a property of a person, "
        "place or thing). Leave out opinions, predictions, questions, "
        "commands, and pure quotations of what someone believes. Keep "
        "each claim short and self-contained (resolve pronouns). "
        f"Return at most {max_claims} claims as a JSON array of "
        "strings, nothing else.\n\nTEXT:\n" + text)
    raw = gemini_generate([{"text": prompt}], json_mode=True)
    claims = _parse_json(raw)
    if not isinstance(claims, list):
        return []
    out = []
    for c in claims:
        if isinstance(c, str) and c.strip():
            out.append(c.strip())
        if len(out) >= max_claims:
            break
    return out


def transcribe_audio(audio_bytes, mime):
    b64 = base64.b64encode(audio_bytes).decode()
    raw = gemini_generate([
        {"text": "Transcribe the speech in this audio exactly, word "
                 "for word. Return only the transcript text."},
        {"inlineData": {"mimeType": mime, "data": b64}},
    ])
    return raw.strip()


# --------------------------------------------------------------------------
# Evidence retrieval. Every fetcher returns a list of
# {source, url, snippet, kind} and never raises.
# --------------------------------------------------------------------------
def _fetch(url, ua=UA, timeout=FETCH_TIMEOUT):
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def factcheck_evidence(claim):
    """Google Fact Check Tools API (ClaimReview): published
    fact-checks that match the claim. Needs an API key whose project
    has the API enabled; silently empty otherwise (the web layers
    still run)."""
    if not FACTCHECK_KEY:
        return []
    q = urllib.parse.urlencode(
        {"query": claim, "languageCode": "en", "pageSize": 5})
    req = urllib.request.Request(
        f"https://factchecktools.googleapis.com/v1alpha1/claims:search?{q}",
        headers={"X-Goog-Api-Key": FACTCHECK_KEY, "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return []
    out = []
    for entry in data.get("claims", [])[:3]:
        for review in entry.get("claimReview", [])[:1]:
            publisher = (review.get("publisher") or {}).get("name") or "ClaimReview"
            rating = review.get("textualRating") or ""
            title = review.get("title") or entry.get("text") or ""
            snippet = f"Rating: {rating}. {title}".strip()
            out.append({"source": publisher, "url": review.get("url"),
                        "snippet": snippet[:400],
                        "kind": "published_fact_check", "rating": rating})
    return out


_RESULT_A = re.compile(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                       re.DOTALL)
_RESULT_S = re.compile(r'class="result__snippet"[^>]*>(.*?)</a>', re.DOTALL)
_LITE_A = re.compile(r'class=[\'"]result-link[\'"][^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                     re.DOTALL)
_LITE_S = re.compile(r'class=[\'"]result-snippet[\'"][^>]*>(.*?)</td>',
                     re.DOTALL)
_BING_BLOCK = re.compile(
    r'<li class="b_algo".*?<h2[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?<p[^>]*>(.*?)</p>',
    re.DOTALL)

# DuckDuckGo throttles bursts (parallel claim checks otherwise come
# back empty and honest claims degrade to unverified), so DDG calls
# are paced globally and an empty page earns one spaced retry, then
# the lite endpoint, then Bing as the last fallback. All keyless.
_DDG_LOCK = threading.Lock()
_DDG_LAST = [0.0]


def _clean(s):
    return html_lib.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def _ddg_real_url(href):
    if href.startswith("//"):
        href = "https:" + href
    parsed = urllib.parse.urlparse(href)
    if "duckduckgo.com" in parsed.netloc:
        qs = urllib.parse.parse_qs(parsed.query)
        if qs.get("uddg"):
            return qs["uddg"][0]
    return href


def _ddg_fetch(url):
    with _DDG_LOCK:
        wait = 0.6 - (time.time() - _DDG_LAST[0])
        if wait > 0:
            time.sleep(wait)
        _DDG_LAST[0] = time.time()
    return _fetch(url, ua=BROWSER_UA)


def _parse_ddg(page, limit):
    links = _RESULT_A.findall(page)
    snippets = _RESULT_S.findall(page)
    if not links:
        links = _LITE_A.findall(page)
        snippets = _LITE_S.findall(page)
    out = []
    for i, (href, title) in enumerate(links[:limit]):
        snippet = snippets[i] if i < len(snippets) else ""
        out.append({"source": _clean(title)[:160],
                    "url": _ddg_real_url(html_lib.unescape(href)),
                    "snippet": _clean(snippet)[:400], "kind": "web"})
    return out


def _parse_bing(page, limit):
    out = []
    for href, title, snippet in _BING_BLOCK.findall(page)[:limit]:
        out.append({"source": _clean(title)[:160],
                    "url": html_lib.unescape(href),
                    "snippet": _clean(snippet)[:400], "kind": "web"})
    return out


def ddg_evidence(query, limit):
    """Web search evidence (keyless): DuckDuckGo HTML, one spaced
    retry on empty, then the DDG lite endpoint, then Bing. Returns
    result title, real URL and snippet."""
    q = urllib.parse.quote(query)
    for url in (f"https://html.duckduckgo.com/html/?q={q}",
                f"https://html.duckduckgo.com/html/?q={q}",
                f"https://lite.duckduckgo.com/lite/?q={q}"):
        try:
            out = _parse_ddg(_ddg_fetch(url), limit)
        except Exception:
            out = []
        if out:
            return out
        time.sleep(1.2)
    try:
        return _parse_bing(
            _fetch(f"https://www.bing.com/search?q={q}", ua=BROWSER_UA),
            limit)
    except Exception:
        return []


def wiki_evidence(claim):
    q = urllib.parse.urlencode({"action": "query", "list": "search",
                                "srsearch": claim, "format": "json",
                                "srlimit": 3, "utf8": 1})
    try:
        data = json.loads(_fetch(f"https://en.wikipedia.org/w/api.php?{q}"))
    except Exception:
        return []
    out = []
    for hit in (data.get("query") or {}).get("search", [])[:2]:
        title = hit.get("title") or ""
        snippet = html_lib.unescape(
            re.sub(r"<[^>]+>", "", hit.get("snippet") or "")).strip()
        out.append({"source": f"Wikipedia: {title}",
                    "url": "https://en.wikipedia.org/wiki/"
                           + urllib.parse.quote(title.replace(" ", "_")),
                    "snippet": snippet[:400], "kind": "encyclopedia"})
    return out


def gather_evidence(claim):
    with ThreadPoolExecutor(max_workers=4) as pool:
        f_fc = pool.submit(factcheck_evidence, claim)
        f_web = pool.submit(ddg_evidence, claim, 3)
        f_fcweb = pool.submit(ddg_evidence, claim + " fact check", 2)
        f_wiki = pool.submit(wiki_evidence, claim)
        groups = [f_fc.result(), f_web.result(), f_fcweb.result(),
                  f_wiki.result()]
    seen, evidence = set(), []
    for group in groups:
        for item in group:
            if item.get("url") and item["url"] not in seen:
                seen.add(item["url"])
                evidence.append(item)
            if len(evidence) >= MAX_EVIDENCE_PER_CLAIM:
                return evidence
    return evidence


# --------------------------------------------------------------------------
# Verdict synthesis. The model sees only the claim and the evidence.
# The confidence note is computed here, from the evidence itself.
# --------------------------------------------------------------------------
def _confidence(verdict, evidence):
    factchecks = [e for e in evidence if e["kind"] == "published_fact_check"]
    if factchecks and verdict in ("supported", "refuted", "mixed"):
        names = ", ".join(sorted({e["source"] for e in factchecks}))
        return {"level": "high",
                "note": f"Rests on a published fact-check from {names}, "
                        "carried in the evidence."}
    domains = {urllib.parse.urlparse(e["url"]).netloc for e in evidence
               if e.get("url")}
    if verdict != "unverified" and len(domains) >= 3:
        return {"level": "moderate",
                "note": f"Rests on {len(evidence)} sources across "
                        f"{len(domains)} domains; no published fact-check "
                        "of this exact claim was retrieved."}
    if evidence:
        return {"level": "low",
                "note": f"Rests on thin evidence ({len(evidence)} "
                        "source(s)); treat as provisional."}
    return {"level": "low",
            "note": "No retrievable evidence was found for this claim."}


def verify_claim(claim):
    evidence = gather_evidence(claim)
    if not evidence:
        return {"claim": claim, "verdict": "unverified",
                "confidence": _confidence("unverified", []),
                "explanation": "No retrievable evidence was found for "
                               "this claim, so no verdict can be given.",
                "evidence": []}
    ev_lines = "\n".join(
        f"[{i + 1}] ({e['kind']}) {e['source']} - {e['url']}\n    {e['snippet']}"
        for i, e in enumerate(evidence))
    prompt = (
        "You are the verdict step of a fact-checking service. Judge "
        "the CLAIM using ONLY the EVIDENCE below; use no outside "
        "knowledge. Choose exactly one verdict:\n"
        "- \"supported\": the evidence supports the claim.\n"
        "- \"refuted\": the evidence contradicts the claim.\n"
        "- \"mixed\": the evidence partly supports and partly "
        "contradicts it, or supports it only with material caveats.\n"
        "- \"unverified\": the evidence does not actually address the "
        "claim, or is too thin or conflicting to judge. When in doubt, "
        "choose \"unverified\".\n"
        "Write a one or two sentence explanation grounded in the "
        "evidence. Return JSON only: {\"verdict\": \"...\", "
        "\"explanation\": \"...\"}\n\nCLAIM: " + claim +
        "\n\nEVIDENCE:\n" + ev_lines)
    try:
        raw = gemini_generate([{"text": prompt}], json_mode=True)
        parsed = _parse_json(raw)
        verdict = str(parsed.get("verdict", "")).lower()
        explanation = str(parsed.get("explanation", "")).strip()
        if verdict not in VERDICTS:
            raise ValueError(f"model returned verdict {verdict!r}")
        if not explanation:
            raise ValueError("model returned no explanation")
    except Exception as exc:
        return {"claim": claim, "verdict": "unverified",
                "confidence": _confidence("unverified", evidence),
                "explanation": "Evidence was retrieved, but the verdict "
                               "step failed, so this claim is reported "
                               "unverified rather than guessed.",
                "evidence": evidence,
                "error": f"verdict_step_failed: {type(exc).__name__}"}
    return {"claim": claim, "verdict": verdict,
            "confidence": _confidence(verdict, evidence),
            "explanation": explanation, "evidence": evidence}


def check_text_pipeline(text, max_claims):
    claims = extract_claims(text, max_claims)
    if not claims:
        return {"claims_found": 0, "claims": [],
                "note": "No checkable factual claims were found in "
                        "the input."}
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(verify_claim, claims))
    return {"claims_found": len(results), "claims": results}


# --------------------------------------------------------------------------
# Health.
# --------------------------------------------------------------------------
def health():
    state = engine_state()
    return 200, {
        "status": "ok", "service": SERVICE, "version": VERSION,
        "build": BUILD,
        "engines": {
            "reasoning": {"state": state, "model": GEMINI_MODEL,
                          "fallback_model": GEMINI_FALLBACK_MODEL,
                          "role": "claim extraction and verdict synthesis"},
            "transcription": {
                "state": state, "engine": "gemini-audio",
                "model": GEMINI_MODEL,
                "fallback_model": GEMINI_FALLBACK_MODEL,
                "role": "speech-to-text for /check-audio",
                "fallback_evaluated": "faster-whisper (open source): "
                                      "viable only at tiny/base size on "
                                      "the free tier and not needed while "
                                      "the Gemini key is configured"},
            "evidence": {
                "factcheck_api": ("configured" if FACTCHECK_KEY
                                  else "not configured"),
                "factcheck_api_source": "Google Fact Check Tools API "
                                        "(ClaimReview database of "
                                        "published fact-checks)",
                "web_search": "DuckDuckGo HTML (keyless, paced, with "
                              "lite and Bing fallbacks), one general "
                              "and one fact-check-targeted query per claim",
                "encyclopedia": "Wikipedia search API (keyless)"},
        },
        "limits": {"max_claims_cap": MAX_CLAIMS_CAP,
                   "default_max_claims": DEFAULT_MAX_CLAIMS,
                   "max_text_chars": MAX_TEXT_CHARS,
                   "max_audio_bytes": MAX_AUDIO_BODY,
                   "audio_formats": sorted(AUDIO_MIME)},
        "endpoints": ["POST /check-text", "POST /check-claim",
                      "POST /check-audio", "GET /health"],
        "recent_requests": RECENT[-5:],
        "note": "Verdicts summarize retrieved evidence; they do not "
                "settle truth. A claim with no retrievable evidence is "
                "reported unverified, never guessed. Coverage depends "
                "on what fact-checkers and sources have published."}


# --------------------------------------------------------------------------
# Server: scaffold conventions (gate + structured errors).
# --------------------------------------------------------------------------
def _not_configured():
    return 503, {"error": "engine_not_configured",
                 "detail": "No Gemini API key is configured on this "
                           "deployment yet, so checking is not "
                           "available. The service owner must add "
                           "GEMINI_API_KEY to enable it."}


def _parse_multipart(body, content_type):
    """Minimal multipart/form-data parser: returns {field_name:
    (filename, bytes)} for file parts and {field_name: str} for plain
    fields. Enough for a single audio upload."""
    m = re.search(r"boundary=(.+)$", content_type or "")
    if not m:
        return None
    boundary = m.group(1).strip().strip('"').encode()
    parts = {}
    for chunk in body.split(b"--" + boundary):
        if b"\r\n\r\n" not in chunk:
            continue
        head, data = chunk.split(b"\r\n\r\n", 1)
        if data.endswith(b"\r\n"):
            data = data[:-2]
        if data.endswith(b"--"):
            data = data[:-2]
        name_m = re.search(rb'name="([^"]+)"', head)
        if not name_m:
            continue
        name = name_m.group(1).decode("utf-8", "replace")
        file_m = re.search(rb'filename="([^"]*)"', head)
        if file_m:
            parts[name] = (file_m.group(1).decode("utf-8", "replace"), data)
        else:
            parts[name] = data.decode("utf-8", "replace")
    return parts


def run_server(port):
    proxy_secret = os.environ.get("RAPIDAPI_PROXY_SECRET")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _json(self, status, payload):
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
                self._json(401, {"error": "unauthorized",
                                 "detail": "Missing or invalid RapidAPI proxy secret."})
                return False
            return True

        def _record(self, path, status, payload, started, extra=None):
            entry = {"endpoint": path, "status": status,
                     "seconds": round(time.time() - started, 1)}
            if status == 200:
                entry.update(extra or {})
            else:
                entry["error"] = payload.get("error")
            RECENT.append(entry)
            del RECENT[:-10]
            return self._json(status, payload)

        def _read_body(self, cap):
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = 0
            if length <= 0 or length > cap:
                return None
            return self.rfile.read(length)

        def do_GET(self):
            path = urllib.parse.urlparse(self.path).path.rstrip("/") or "/"
            if not self._gate_ok(path):
                return
            if path == "/health":
                status, payload = health()
                return self._json(status, payload)
            return self._json(404, {"error": "not_found",
                                    "detail": f"No endpoint at {path}. See /health for service info."})

        def do_POST(self):
            path = urllib.parse.urlparse(self.path).path.rstrip("/") or "/"
            if not self._gate_ok(path):
                return
            if path not in ("/check-text", "/check-claim", "/check-audio"):
                return self._json(404, {"error": "not_found",
                                        "detail": f"No endpoint at {path}. See /health for service info."})
            started = time.time()

            if path == "/check-audio":
                return self._check_audio(started)
            return self._check_json(path, started)

        # -- JSON endpoints -------------------------------------------
        def _check_json(self, path, started):
            raw = self._read_body(MAX_BODY)
            if raw is None:
                return self._json(422, {"error": "invalid_body",
                                        "detail": f"Send a JSON body of at most {MAX_BODY} bytes."})
            try:
                body = json.loads(raw.decode("utf-8"))
                if not isinstance(body, dict):
                    raise ValueError("body must be a JSON object")
            except Exception:
                return self._json(422, {"error": "invalid_body",
                                        "detail": "Request body must be a JSON object."})
            if engine_state() != "live":
                return self._record(path, *_not_configured(), started)

            if path == "/check-claim":
                claim = (body.get("claim") or "").strip()
                if not claim:
                    return self._record(path, *(422, {
                        "error": "missing_parameter",
                        "detail": "Provide a non-empty 'claim'."}), started)
                if len(claim) > MAX_TEXT_CHARS:
                    return self._record(path, *(422, {
                        "error": "text_too_long",
                        "detail": f"Claim is {len(claim)} characters; the maximum is {MAX_TEXT_CHARS}."}), started)
                try:
                    result = verify_claim(claim)
                except Exception as exc:
                    return self._record(path, *(502, {
                        "error": "engine_upstream_error",
                        "detail": f"{type(exc).__name__}: {exc}"}), started)
                payload = dict(result)
                payload["_meta"] = {"service": SERVICE, "version": VERSION,
                                    "engine": engine_state(),
                                    "latency_ms": round((time.time() - started) * 1000)}
                return self._record(path, 200, payload, started,
                                    {"verdict": result["verdict"]})

            # /check-text
            text = (body.get("text") or "").strip()
            if not text:
                return self._record(path, *(422, {
                    "error": "missing_parameter",
                    "detail": "Provide a non-empty 'text'."}), started)
            if len(text) > MAX_TEXT_CHARS:
                return self._record(path, *(422, {
                    "error": "text_too_long",
                    "detail": f"Text is {len(text)} characters; the maximum is {MAX_TEXT_CHARS}. Split longer text into chunks."}), started)
            max_claims = body.get("max_claims", DEFAULT_MAX_CLAIMS)
            try:
                max_claims = max(1, min(int(max_claims), MAX_CLAIMS_CAP))
            except (TypeError, ValueError):
                max_claims = DEFAULT_MAX_CLAIMS
            try:
                result = check_text_pipeline(text, max_claims)
            except Exception as exc:
                return self._record(path, *(502, {
                    "error": "engine_upstream_error",
                    "detail": f"{type(exc).__name__}: {exc}"}), started)
            payload = dict(result)
            payload["_meta"] = {"service": SERVICE, "version": VERSION,
                                "engine": engine_state(),
                                "latency_ms": round((time.time() - started) * 1000)}
            return self._record(path, 200, payload, started,
                                {"count": result["claims_found"]})

        # -- Audio endpoint --------------------------------------------
        def _check_audio(self, started):
            if engine_state() != "live":
                return self._record("/check-audio", *_not_configured(),
                                    started)
            raw = self._read_body(MAX_AUDIO_BODY)
            if raw is None:
                return self._json(422, {"error": "invalid_body",
                                        "detail": f"Send a multipart audio upload of at most {MAX_AUDIO_BODY} bytes."})
            parts = _parse_multipart(
                raw, self.headers.get("Content-Type") or "")
            if not parts:
                return self._record("/check-audio", *(422, {
                    "error": "invalid_body",
                    "detail": "Request must be multipart/form-data with an audio file part."}), started)
            upload = None
            for value in parts.values():
                if isinstance(value, tuple):
                    upload = value
                    break
            if upload is None:
                return self._record("/check-audio", *(422, {
                    "error": "missing_parameter",
                    "detail": "No file part found in the multipart body."}), started)
            filename, data = upload
            ext = os.path.splitext(filename or "")[1].lower()
            mime = AUDIO_MIME.get(ext)
            if not mime:
                return self._record("/check-audio", *(422, {
                    "error": "unsupported_format",
                    "detail": f"Audio format {ext or '(none)'} is not supported. Supported extensions: {', '.join(sorted(AUDIO_MIME))}."}), started)
            if not data:
                return self._record("/check-audio", *(422, {
                    "error": "missing_parameter",
                    "detail": "The uploaded audio file is empty."}), started)
            try:
                transcript = transcribe_audio(data, mime)
            except Exception as exc:
                return self._record("/check-audio", *(502, {
                    "error": "transcription_failed",
                    "detail": f"{type(exc).__name__}: {exc}"}), started)
            if not transcript:
                return self._record("/check-audio", *(422, {
                    "error": "no_speech_transcribed",
                    "detail": "The transcription step returned no speech for this audio."}), started)
            try:
                result = check_text_pipeline(
                    transcript[:MAX_TEXT_CHARS], DEFAULT_MAX_CLAIMS)
            except Exception as exc:
                return self._record("/check-audio", *(502, {
                    "error": "engine_upstream_error",
                    "detail": f"{type(exc).__name__}: {exc}"}), started)
            payload = {"transcript": transcript, **result}
            payload["_meta"] = {"service": SERVICE, "version": VERSION,
                                "engine": engine_state(),
                                "transcription_engine": "gemini-audio",
                                "latency_ms": round((time.time() - started) * 1000)}
            return self._record("/check-audio", 200, payload, started,
                                {"count": result["claims_found"]})

    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    run_server(int(os.environ.get("PORT", "8115")))
