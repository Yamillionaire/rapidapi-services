"""DesignBase deployed battery (2026-10-31).

Runs against the deployed service (default
https://designbase.onrender.com) while it rests in the honest
awaiting_key state, with the build-time test proxy secret set on
the origin for the duration of the test:

- /health 200, reasoning state awaiting_key, code engines live;
- gate: data endpoints 401 without the secret, 401 with a wrong
  value;
- through the gate: /palette, /design-brief and /critique answer
  the explicit 503 engine_not_configured; /image-prompt answers
  200 (code-assembled, as /health promises);
- /health stays open throughout.

No deployed engine calls are possible until the owner adds
GEMINI_API_KEY to the Render service (the lane's standing key
step); the local battery (run_tests.py) proves the live pipeline
through the connector bridge. After this battery runs, the
build-time test secret is rotated to an unrecorded value, leaving
the origin gated until the Studio step sets the real secret.

Usage: python3 run_tests_deployed.py [base_url]
Reads the test secret from DESIGNBASE_TEST_SECRET (default: the
local battery's test value). Results are written to
battery-deployed-2026-10-31.json next to this file.
"""
import json
import os
import sys
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = (sys.argv[1] if len(sys.argv) > 1
        else "https://designbase.onrender.com").rstrip("/")
SECRET = os.environ.get("DESIGNBASE_TEST_SECRET",
                        "designbase-battery-test-secret")
results = {"checks": [], "samples": {}, "base": BASE}


def call(method, path, body=None, headers=None, timeout=120):
    data = None
    hdrs = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode()
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, method=method, data=data,
                                 headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw)
        except Exception:
            return exc.code, {"raw": raw[:300]}


def check(name, cond, detail=""):
    results["checks"].append(
        {"name": name, "pass": bool(cond), "detail": detail})
    print(("PASS " if cond else "FAIL ") + name
          + (f" - {detail}" if detail else ""))


AUTH = {"X-RapidAPI-Proxy-Secret": SECRET}

status, health = call("GET", "/health")
check("deployed /health 200, reasoning awaiting_key, code engines "
      "live",
      status == 200
      and health.get("engines", {}).get("reasoning", {}).get("state")
      == "awaiting_key"
      and health.get("engines", {}).get("prompt_builder", {})
      .get("state") == "live")
results["samples"]["health"] = health

status, body = call("POST", "/palette", {"brief": "a merch tee"})
check("deployed gate: /palette without secret -> 401",
      status == 401 and body.get("error") == "unauthorized")

status, body = call("POST", "/palette", {"brief": "a merch tee"},
                    {"X-RapidAPI-Proxy-Secret": "wrong"})
check("deployed gate: /palette wrong secret -> 401", status == 401)

status, body = call("POST", "/palette", {"brief": "a merch tee"},
                    AUTH)
check("deployed /palette through gate -> 503 engine_not_configured",
      status == 503 and body.get("error") == "engine_not_configured")
results["samples"]["palette_awaiting"] = body

status, body = call("POST", "/design-brief",
                    {"product": "poster", "audience": "fans",
                     "vibe": "bold"}, AUTH)
check("deployed /design-brief through gate -> 503 "
      "engine_not_configured",
      status == 503 and body.get("error") == "engine_not_configured")

status, body = call("POST", "/critique", {"x": 1}, AUTH)
check("deployed /critique through gate -> 503 engine_not_configured",
      status == 503 and body.get("error") == "engine_not_configured")

status, body = call("POST", "/image-prompt",
                    {"subject": "a lighthouse at dawn",
                     "style": "photorealistic photograph"}, AUTH)
check("deployed /image-prompt through gate -> 200 (code-assembled)",
      status == 200 and "lighthouse" in body.get("prompt", ""))
results["samples"]["image_prompt"] = body

failed = [c for c in results["checks"] if not c["pass"]]
out = os.path.join(HERE, "battery-deployed-2026-10-31.json")
with open(out, "w") as fh:
    json.dump(results, fh, indent=2)
print(f"\n{len(results['checks']) - len(failed)}/{len(results['checks'])} "
      f"checks passed; battery at {out}")
sys.exit(1 if failed else 0)
