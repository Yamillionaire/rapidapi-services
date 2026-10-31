"""XBase local proof battery (2026-10-31).

Starts the service twice on throwaway ports: once in mock mode behind
a test proxy secret, once with no token and no mock (the awaiting
state). Asserts the gate behavior and the normalized output shape in
both. Writes the raw results to battery-2026-10-31.json next to this
file. No live X call is made: there is no token on this machine.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "..", "app.py")
SECRET = "test-secret-xbase-local"
results = {"checks": [], "samples": {}}


def call(port, method, path, body=None, headers=None):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


def check(name, cond, detail=""):
    results["checks"].append({"name": name, "pass": bool(cond), "detail": detail})
    print(("PASS " if cond else "FAIL ") + name + (f" - {detail}" if detail else ""))


def wait_health(port):
    for _ in range(50):
        try:
            status, _ = call(port, "GET", "/health")
            if status == 200:
                return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


def start(port, env_extra):
    env = dict(os.environ, PORT=str(port), **env_extra)
    proc = subprocess.Popen([sys.executable, APP], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    assert wait_health(port), f"server on {port} never became healthy"
    return proc


POST_KEYS = {"id", "text", "author", "created_at", "metrics", "url", "lang"}


def shape_ok(post):
    return (POST_KEYS <= set(post)
            and {"username", "name"} <= set(post["author"])
            and {"likes", "reposts", "replies", "quotes"} <= set(post["metrics"])
            and post["url"] == f"https://x.com/{post['author']['username']}/status/{post['id']}")


# --- Run 1: mock engine behind the gate -----------------------------------
proc = start(8214, {"XBASE_MOCK": "1", "RAPIDAPI_PROXY_SECRET": SECRET})
try:
    status, health = call(8214, "GET", "/health")
    check("mock /health 200, engine mock", status == 200
          and health["engine"]["state"] == "mock")
    results["samples"]["health_mock"] = health

    status, body = call(8214, "POST", "/search", {"query": "hip hop"})
    check("gate: /search without secret -> 401", status == 401
          and body["error"] == "unauthorized")

    status, body = call(8214, "POST", "/search", {"query": "hip hop"},
                        {"X-RapidAPI-Proxy-Secret": "wrong"})
    check("gate: /search wrong secret -> 401", status == 401)

    status, body = call(8214, "POST", "/search", {},
                        {"X-RapidAPI-Proxy-Secret": SECRET})
    check("gate passed, empty body -> 422 missing_parameter",
          status == 422 and body["error"] == "missing_parameter")

    status, body = call(8214, "POST", "/search",
                        {"query": "(hip hop) new album", "max_results": 5,
                         "hours_back": 24},
                        {"X-RapidAPI-Proxy-Secret": SECRET})
    check("/search mock 200", status == 200)
    check("/search shape: normalized posts", status == 200
          and body["count"] == len(body["posts"]) >= 1
          and all(shape_ok(p) for p in body["posts"]))
    check("/search meta labels engine mock", status == 200
          and body["_meta"]["engine"] == "mock")
    results["samples"]["search_mock"] = body

    for preset in ("hiphop", "black-news-us", "black-news-international"):
        status, body = call(8214, "POST", "/news-scan", {"preset": preset},
                            {"X-RapidAPI-Proxy-Secret": SECRET})
        ids = [p["id"] for p in body.get("posts", [])]
        check(f"/news-scan {preset}: 200, deduped, shaped",
              status == 200 and len(ids) == len(set(ids))
              and all(shape_ok(p) for p in body["posts"]))
        results["samples"][f"scan_{preset}"] = {
            "count": body.get("count"), "posts_per_query": body.get("posts_per_query")}

    status, body = call(8214, "POST", "/news-scan", {"preset": "nope"},
                        {"X-RapidAPI-Proxy-Secret": SECRET})
    check("/news-scan unknown preset -> 422", status == 422
          and body["error"] == "unknown_preset")
finally:
    proc.terminate()

# --- Run 2: no token, no mock (the parked state) ---------------------------
proc = start(8215, {"RAPIDAPI_PROXY_SECRET": SECRET})
try:
    status, health = call(8215, "GET", "/health")
    check("awaiting /health reports awaiting_token", status == 200
          and health["engine"]["state"] == "awaiting_token")
    status, body = call(8215, "POST", "/search", {"query": "hip hop"},
                        {"X-RapidAPI-Proxy-Secret": SECRET})
    check("awaiting /search -> explicit 503 engine_not_configured",
          status == 503 and body["error"] == "engine_not_configured")
    results["samples"]["search_awaiting"] = body
finally:
    proc.terminate()

failed = [c for c in results["checks"] if not c["pass"]]
out = os.path.join(HERE, "battery-2026-10-31.json")
with open(out, "w") as fh:
    json.dump(results, fh, indent=2)
print(f"\n{len(results['checks']) - len(failed)}/{len(results['checks'])} checks passed; battery at {out}")
sys.exit(1 if failed else 0)
