"""XBase - X (Twitter) news search API (the user's own product,
2026-10-31; RapidAPI lane build #13).

Wraps the OFFICIAL X API v2 recent-search endpoint. No scraping: X's
Terms prohibit crawling the platform, so every byte comes through
api.twitter.com with the operator's own Bearer token, on the
pay-per-post plan ($0.005 per post returned at the time of build).
Built first as the user's own news engine: the /news-scan presets
("hiphop", "black-news-us", "black-news-international") are the
curated query sets his twice-daily feed checks will call for
HipHopolis News and the All Black Towns Black News feed (America and
International tabs).

The server keeps the lane scaffold's exact conventions (shared with
SwiftRead and DriftCheck): stdlib only, the RapidAPI proxy-secret
gate (401 JSON without the X-RapidAPI-Proxy-Secret header, /health
always open), and explicit structured JSON errors for every failure.

Engine states, reported honestly in /health and per response:
- live: X_BEARER_TOKEN is set; calls go to the real X API.
- mock: XBASE_MOCK=1; the X client returns built-in fixture payloads
  that pass through the SAME normalization code as live responses.
  Used only to prove the service end to end before a token exists.
  Every mock response is labeled "engine": "mock" in its meta -
  fixtures are never passed off as live data.
- awaiting_token: neither is set; /search and /news-scan answer an
  explicit 503 engine_not_configured instead of guessing.

Endpoints:
  POST /search     {query, max_results? (cap 100), hours_back?}
                   -> normalized posts, newest first
  POST /news-scan  {preset} -> the preset's posts, de-duplicated
                   across its queries, newest first
  GET  /health     -> service status, engine state, limits, presets
Run: python3 app.py (PORT env, default 8114). No dependencies.
"""
import json
import os
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlencode, urlparse

SERVICE = "xbase"
VERSION = "1.0.0"
BUILD = "2026-10-31-v1"
RECENT = []                       # last request outcomes (see /health)

X_API_URL = "https://api.twitter.com/2/tweets/search/recent"
MAX_RESULTS_CAP = 100             # per-request post cap (X charges per post)
X_MIN_RESULTS = 10                # the X API's own floor per search call
DEFAULT_MAX_RESULTS = 25
DEFAULT_HOURS_BACK = 24
MAX_HOURS_BACK = 168              # recent search reaches back 7 days
MAX_BODY = 100_000
FETCH_TIMEOUT = 30
UA = "XBase/1.0 (+https://rapidapi.com/YamilLittle/api/xbase)"

# Curated preset query sets for /news-scan. Each preset runs every
# query, merges the results, de-duplicates by post id, and returns
# them newest first. Queries use the X API's own search grammar and
# exclude retweets so scans surface original posts.
PRESETS = {
    "hiphop": {
        "label": "Hip-hop: releases, tours, business, culture",
        "queries": [
            "(hip hop OR hiphop) (new album OR new single OR album release) -is:retweet lang:en",
            "(rapper OR hip hop) (tour OR concert OR festival) announces -is:retweet lang:en",
            "(record label OR streaming) (hip hop OR rapper) deal -is:retweet lang:en",
        ],
        "max_results_per_query": 25,
        "hours_back": 24,
    },
    "black-news-us": {
        "label": "Black news: United States",
        "queries": [
            "(Black Americans OR African American) (city council OR mayor OR policy OR community) -is:retweet lang:en",
            "(HBCU OR Black entrepreneurs OR Black-owned) -is:retweet lang:en",
            "(Black history OR Black heritage) (museum OR archive OR landmark) -is:retweet lang:en",
        ],
        "max_results_per_query": 25,
        "hours_back": 24,
    },
    "black-news-international": {
        "label": "Black news: the African diaspora worldwide (Africa, the Caribbean, the UK, Canada, Latin America)",
        "queries": [
            "(African diaspora OR Afro-Caribbean OR Black British) -is:retweet lang:en",
            "(Nigeria OR Ghana OR Kenya OR Jamaica OR Barbados) (culture OR festival OR heritage) -is:retweet",
            "(Afro-Latino OR Black Canadian) (community OR arts OR history) -is:retweet",
        ],
        "max_results_per_query": 25,
        "hours_back": 24,
    },
}


# --------------------------------------------------------------------------
# X API client (live) and the mock fixture source. Both return a raw
# X API v2-shaped payload; normalization below is shared, so the mock
# path proves the real output shape.
# --------------------------------------------------------------------------
def engine_state():
    if os.environ.get("XBASE_MOCK") == "1":
        return "mock"
    if os.environ.get("X_BEARER_TOKEN"):
        return "live"
    return "awaiting_token"


def _fixture_payload(query, max_results):
    """A small canned X API v2 response. Post texts are plainly
    synthetic (they say so) so a fixture can never be mistaken for a
    real post downstream."""
    now = datetime.now(timezone.utc)
    posts = []
    users = [
        {"id": "900000001", "username": "fixture_beats", "name": "Fixture Beats"},
        {"id": "900000002", "username": "fixture_wire", "name": "Fixture Wire"},
        {"id": "900000003", "username": "fixture_archive", "name": "Fixture Archive"},
    ]
    for i in range(3):
        created = now - timedelta(minutes=17 * (i + 1))
        posts.append({
            "id": f"199900000000000000{i + 1}",
            "text": (f"FIXTURE post {i + 1} for query [{query}]: synthetic sample "
                     "text used to prove the response shape. Not a real post."),
            "author_id": users[i]["id"],
            "created_at": created.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "lang": "en",
            "public_metrics": {"like_count": 40 - i * 9, "retweet_count": 12 - i * 3,
                               "reply_count": 5 - i, "quote_count": 2},
        })
    return {"data": posts[:max_results], "includes": {"users": users},
            "meta": {"result_count": min(3, max_results)}}


def x_search(query, max_results, hours_back):
    """One X API v2 recent-search call. Returns (payload, error) where
    error is a (status, dict) tuple or None."""
    state = engine_state()
    if state == "mock":
        return _fixture_payload(query, max_results), None
    if state == "awaiting_token":
        return None, (503, {"error": "engine_not_configured",
                            "detail": "No X Bearer token is configured on this "
                                      "deployment yet, so live search is not "
                                      "available. The service owner must add "
                                      "X_BEARER_TOKEN to enable it."})
    ask = max(X_MIN_RESULTS, min(int(max_results), MAX_RESULTS_CAP))
    start = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    params = {
        "query": query,
        "max_results": ask,
        "start_time": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tweet.fields": "created_at,public_metrics,lang,author_id",
        "expansions": "author_id",
        "user.fields": "username,name",
    }
    req = urllib.request.Request(
        f"{X_API_URL}?{urlencode(params)}",
        headers={"Authorization": f"Bearer {os.environ['X_BEARER_TOKEN']}",
                 "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8")), None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        if exc.code == 429:
            return None, (429, {"error": "x_rate_limited",
                                "detail": "The X API rate limit for this app "
                                          "was hit (450 requests per 15 "
                                          "minutes). Wait and retry."})
        return None, (502, {"error": "x_upstream_error",
                            "detail": f"X API answered HTTP {exc.code}: {detail}"})
    except Exception as exc:
        return None, (502, {"error": "x_upstream_error",
                            "detail": f"{type(exc).__name__}: {exc}"})


# --------------------------------------------------------------------------
# Normalization: raw X API v2 payload -> the service's post shape.
# --------------------------------------------------------------------------
def normalize(payload, limit):
    users = {u["id"]: u for u in (payload.get("includes") or {}).get("users", [])}
    posts = []
    for t in payload.get("data") or []:
        author = users.get(t.get("author_id"), {})
        username = author.get("username")
        metrics = t.get("public_metrics") or {}
        posts.append({
            "id": t.get("id"),
            "text": t.get("text"),
            "author": {"username": username, "name": author.get("name")},
            "created_at": t.get("created_at"),
            "metrics": {"likes": metrics.get("like_count", 0),
                        "reposts": metrics.get("retweet_count", 0),
                        "replies": metrics.get("reply_count", 0),
                        "quotes": metrics.get("quote_count", 0)},
            "url": (f"https://x.com/{username}/status/{t.get('id')}"
                    if username else None),
            "lang": t.get("lang"),
        })
    posts.sort(key=lambda p: p.get("created_at") or "", reverse=True)
    return posts[:limit]


def do_search(query, max_results, hours_back):
    payload, err = x_search(query, max_results, hours_back)
    if err:
        return err
    posts = normalize(payload, max_results)
    return 200, {"query": query, "count": len(posts), "posts": posts}


def do_news_scan(preset_name):
    preset = PRESETS[preset_name]
    merged = {}
    per_query = {}
    for q in preset["queries"]:
        payload, err = x_search(q, preset["max_results_per_query"],
                                preset["hours_back"])
        if err:
            return err
        posts = normalize(payload, preset["max_results_per_query"])
        per_query[q] = len(posts)
        for p in posts:
            merged[p["id"]] = p
    posts = sorted(merged.values(),
                   key=lambda p: p.get("created_at") or "", reverse=True)
    return 200, {"preset": preset_name, "label": preset["label"],
                 "queries": preset["queries"], "posts_per_query": per_query,
                 "count": len(posts), "posts": posts}


# --------------------------------------------------------------------------
# Health.
# --------------------------------------------------------------------------
def health():
    state = engine_state()
    return 200, {"status": "ok", "service": SERVICE, "version": VERSION,
                 "build": BUILD,
                 "engine": {"state": state,
                            "source": ("built-in fixtures (XBASE_MOCK=1): "
                                       "responses are labeled mock and are "
                                       "NOT live X data"
                                       if state == "mock" else
                                       "official X API v2 recent search"
                                       if state == "live" else
                                       "no X Bearer token configured yet; "
                                       "/search and /news-scan return an "
                                       "explicit 503 until the owner adds one"),
                            "pricing_note": "X charges the token owner "
                                            "per post returned ($0.005 per "
                                            "post on the pay-per-use plan at "
                                            "build time)"},
                 "presets": {name: p["label"] for name, p in PRESETS.items()},
                 "limits": {"max_results_cap": MAX_RESULTS_CAP,
                            "max_hours_back": MAX_HOURS_BACK,
                            "x_rate_limit": "450 requests per 15 minutes per app"},
                 "endpoints": ["POST /search", "POST /news-scan", "GET /health"],
                 "recent_requests": RECENT[-5:],
                 "note": "Official-API wrapper only: no scraping. Posts are "
                         "normalized to id, text, author, timestamp, public "
                         "metrics, URL, and language."}


# --------------------------------------------------------------------------
# Server: scaffold conventions (gate + structured errors), JSON bodies.
# --------------------------------------------------------------------------
def _clamp_int(value, default, lo, hi):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(n, hi))


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

        def do_GET(self):
            path = urlparse(self.path).path.rstrip("/") or "/"
            if not self._gate_ok(path):
                return
            if path == "/health":
                status, payload = health()
                return self._json(status, payload)
            return self._json(404, {"error": "not_found",
                                    "detail": f"No endpoint at {path}. See /health for service info."})

        def do_POST(self):
            path = urlparse(self.path).path.rstrip("/") or "/"
            if not self._gate_ok(path):
                return
            if path not in ("/search", "/news-scan"):
                return self._json(404, {"error": "not_found",
                                        "detail": f"No endpoint at {path}. See /health for service info."})
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = 0
            if length <= 0 or length > MAX_BODY:
                return self._json(422, {"error": "invalid_body",
                                        "detail": f"Send a JSON body of at most {MAX_BODY} bytes."})
            raw = self.rfile.read(length)
            started = time.time()
            try:
                body = json.loads(raw.decode("utf-8"))
                if not isinstance(body, dict):
                    raise ValueError("body must be a JSON object")
            except Exception:
                return self._json(422, {"error": "invalid_body",
                                        "detail": "Request body must be a JSON object."})

            if path == "/search":
                query = (body.get("query") or "").strip()
                if not query:
                    return self._record(path, (422, {"error": "missing_parameter",
                                                     "detail": "Provide a non-empty 'query' (X search grammar)."}), started)
                max_results = _clamp_int(body.get("max_results"),
                                         DEFAULT_MAX_RESULTS, 1, MAX_RESULTS_CAP)
                hours_back = _clamp_int(body.get("hours_back"),
                                        DEFAULT_HOURS_BACK, 1, MAX_HOURS_BACK)
                status, payload = do_search(query, max_results, hours_back)
            else:
                preset = (body.get("preset") or "").strip()
                if preset not in PRESETS:
                    return self._record(path, (422, {"error": "unknown_preset",
                                                     "detail": f"preset must be one of: {', '.join(PRESETS)}."}), started)
                status, payload = do_news_scan(preset)

            if status == 200:
                return self._ok(path, payload, started)
            return self._record(path, (status, payload), started)

        def _record(self, path, err, started):
            status, payload = err
            RECENT.append({"endpoint": path, "status": status,
                           "seconds": round(time.time() - started, 1),
                           "error": payload.get("error")})
            del RECENT[:-10]
            return self._json(status, payload)

        def _ok(self, path, result, started):
            RECENT.append({"endpoint": path, "status": 200,
                           "seconds": round(time.time() - started, 1),
                           "count": result.get("count")})
            del RECENT[:-10]
            result = dict(result)
            result["_meta"] = {"service": SERVICE, "version": VERSION,
                               "engine": engine_state(),
                               "latency_ms": round((time.time() - started) * 1000)}
            return self._json(200, result)

    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    run_server(int(os.environ.get("PORT", "8114")))
