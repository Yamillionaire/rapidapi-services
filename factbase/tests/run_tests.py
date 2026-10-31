"""FactBase proof battery (2026-10-31).

Phase A (awaiting): the service with no Gemini key behind a test
proxy secret - gate behavior and the honest 503 state.

Phase B (live pipeline): the service pointed at tests/
connector_bridge.py, which routes its Gemini calls through the
user's connected Gemini API (the connector credential flow), so the
service's unmodified pipeline runs against the real engine: claim
extraction, keyless web/Wikipedia evidence retrieval, verdict
synthesis, and Gemini audio transcription. Proof claims have known
outcomes: a well-known true claim, a well-known false claim, a
commonly-misleading claim, and an obscure claim that should
honestly return unverified. Audio proofs: a synthesized claim clip
(Gemini TTS, made for this battery) and the real JFK speech clip
(the Whisper test file).

No key is read or printed anywhere. Results (checks + full sample
responses) are written to battery-2026-10-31.json next to this file.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "..", "app.py")
BRIDGE = os.path.join(HERE, "connector_bridge.py")
SECRET = "factbase-battery-test-secret"
CLAIM_CLIP = "/tmp/factbase-claim-clip.mp3"
JFK_CLIP = "/tmp/jfk.flac"
results = {"checks": [], "samples": {},
           "environment": "Phase B Gemini calls routed through "
                          "tests/connector_bridge.py via the "
                          "custom.gemini connector (real engine, "
                          "production request shapes); evidence "
                          "retrieval ran live (DuckDuckGo HTML + "
                          "Wikipedia, keyless). Fact Check Tools API "
                          "layer inactive locally (no key for that "
                          "host on this machine)."}


def call(port, method, path, body=None, headers=None, timeout=30):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


def call_multipart(port, path, filename, data, timeout=240):
    boundary = "----factbase" + uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", method="POST", data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}",
                 "X-RapidAPI-Proxy-Secret": SECRET})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


def check(name, cond, detail=""):
    results["checks"].append(
        {"name": name, "pass": bool(cond), "detail": detail})
    print(("PASS " if cond else "FAIL ") + name
          + (f" - {detail}" if detail else ""))


def wait_health(port):
    for _ in range(60):
        try:
            status, _ = call(port, "GET", "/health")
            if status == 200:
                return True
        except Exception:
            pass
        time.sleep(0.25)
    return False


def start(args, env_extra, port):
    env = dict(os.environ, **env_extra)
    proc = subprocess.Popen([sys.executable] + args, env=env,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    assert wait_health(port), f"server on {port} never became healthy"
    return proc


AUTH = {"X-RapidAPI-Proxy-Secret": SECRET}


def pace(seconds=20):
    """The owner's Gemini key has a per-minute quota; the battery
    paces its engine-heavy calls so the proof measures the pipeline,
    not the quota. (The service itself retries 429s and falls back
    to a second model; a single subscriber request is a handful of
    calls and does not need pacing.)"""
    time.sleep(seconds)

# --- Phase A: awaiting_key ---------------------------------------------
proc = start([APP], {"PORT": "8216", "RAPIDAPI_PROXY_SECRET": SECRET},
             8216)
try:
    status, health = call(8216, "GET", "/health")
    check("awaiting /health 200, reasoning state awaiting_key",
          status == 200
          and health["engines"]["reasoning"]["state"] == "awaiting_key")
    results["samples"]["health_awaiting"] = health

    status, body = call(8216, "POST", "/check-text", {"text": "Paris is in France."})
    check("gate: /check-text without secret -> 401",
          status == 401 and body["error"] == "unauthorized")

    status, body = call(8216, "POST", "/check-text",
                        {"text": "Paris is in France."},
                        {"X-RapidAPI-Proxy-Secret": "wrong"})
    check("gate: /check-text wrong secret -> 401", status == 401)

    status, body = call(8216, "POST", "/check-text",
                        {"text": "Paris is in France."}, AUTH)
    check("awaiting /check-text -> explicit 503 engine_not_configured",
          status == 503 and body["error"] == "engine_not_configured")
    results["samples"]["check_text_awaiting"] = body

    status, body = call(8216, "POST", "/check-audio", {"x": 1}, AUTH)
    check("awaiting /check-audio -> explicit 503 engine_not_configured",
          status == 503 and body["error"] == "engine_not_configured")
finally:
    proc.terminate()

# --- Phase B: live pipeline through the connector bridge ----------------
bridge = subprocess.Popen([sys.executable, BRIDGE, "8899"],
                          stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL)
time.sleep(1.0)
proc = start([APP], {"PORT": "8217", "RAPIDAPI_PROXY_SECRET": SECRET,
                     "GEMINI_API_KEY": "local-bridge-placeholder",
                     "GEMINI_BASE_URL": "http://127.0.0.1:8899/v1beta"},
             8217)
try:
    status, health = call(8217, "GET", "/health")
    check("live /health: reasoning + transcription live, engine named",
          status == 200
          and health["engines"]["reasoning"]["state"] == "live"
          and health["engines"]["transcription"]["engine"] == "gemini-audio")
    results["samples"]["health_live"] = health

    status, body = call(8217, "POST", "/check-claim", {}, AUTH)
    check("live /check-claim empty -> 422 missing_parameter",
          status == 422 and body["error"] == "missing_parameter")

    def evidence_ok(claim_result):
        ev = claim_result.get("evidence", [])
        return all(e.get("source") and e.get("url") and e.get("snippet")
                   for e in ev)

    pace()
    status, body = call(8217, "POST", "/check-claim",
                        {"claim": "The Eiffel Tower was completed in 1889."},
                        AUTH, timeout=240)
    check("TRUE claim (Eiffel Tower completed 1889) -> supported, sourced",
          status == 200 and body.get("verdict") == "supported"
          and len(body.get("evidence", [])) >= 1 and evidence_ok(body),
          f"verdict={body.get('verdict')}, evidence={len(body.get('evidence', []))}")
    results["samples"]["claim_true"] = body

    pace()
    status, body = call(8217, "POST", "/check-claim",
                        {"claim": "The Great Wall of China is visible from the Moon with the naked eye."},
                        AUTH, timeout=240)
    check("FALSE claim (Great Wall visible from the Moon) -> refuted, sourced",
          status == 200 and body.get("verdict") == "refuted"
          and len(body.get("evidence", [])) >= 1 and evidence_ok(body),
          f"verdict={body.get('verdict')}, evidence={len(body.get('evidence', []))}")
    results["samples"]["claim_false"] = body

    pace()
    status, body = call(8217, "POST", "/check-claim",
                        {"claim": "The Amazon rainforest produces 20 percent of the world's oxygen."},
                        AUTH, timeout=240)
    check("MISLEADING claim (Amazon 20% of oxygen) -> mixed or refuted, sourced",
          status == 200 and body.get("verdict") in ("mixed", "refuted")
          and len(body.get("evidence", [])) >= 1 and evidence_ok(body),
          f"verdict={body.get('verdict')}, evidence={len(body.get('evidence', []))}")
    results["samples"]["claim_misleading"] = body

    pace()
    status, body = call(8217, "POST", "/check-claim",
                        {"claim": "The Millersville town council approved exactly fourteen parking permits in March 1974."},
                        AUTH, timeout=240)
    check("OBSCURE claim (1974 parking permits) -> honestly unverified",
          status == 200 and body.get("verdict") == "unverified",
          f"verdict={body.get('verdict')}, evidence={len(body.get('evidence', []))}")
    results["samples"]["claim_obscure"] = body

    pace()
    status, body = call(8217, "POST", "/check-text",
                        {"text": "Barack Obama was born in Hawaii and was the 44th President of the United States. Barack Obama was born in Kenya."},
                        AUTH, timeout=300)
    verdicts = [c.get("verdict") for c in body.get("claims", [])]
    check("/check-text two claims -> one supported + one refuted",
          status == 200 and body.get("claims_found", 0) >= 2
          and "supported" in verdicts and "refuted" in verdicts,
          f"verdicts={verdicts}")
    results["samples"]["text_two_claims"] = body

    pace()
    status, body = call(8217, "POST", "/check-text",
                        {"text": "I think pizza is the best food and everyone should love it."},
                        AUTH, timeout=120)
    check("/check-text opinion only -> claims_found 0 with note",
          status == 200 and body.get("claims_found") == 0
          and "note" in body)
    results["samples"]["text_opinion"] = body

    with open(CLAIM_CLIP, "rb") as fh:
        clip = fh.read()
    pace()
    status, body = call_multipart(8217, "/check-audio",
                                  "claim-clip.mp3", clip)
    verdicts = [c.get("verdict") for c in body.get("claims", [])]
    check("/check-audio claim clip -> transcript + supported verdict",
          status == 200
          and "Eiffel Tower" in body.get("transcript", "")
          and "supported" in verdicts,
          f"transcript={body.get('transcript', '')[:80]!r}, verdicts={verdicts}")
    results["samples"]["audio_claim_clip"] = body

    with open(JFK_CLIP, "rb") as fh:
        jfk = fh.read()
    pace()
    status, body = call_multipart(8217, "/check-audio", "jfk.flac", jfk)
    check("/check-audio JFK clip -> accurate transcript",
          status == 200
          and "ask not what your country can do for you"
          in body.get("transcript", "").lower(),
          f"transcript={body.get('transcript', '')[:100]!r}")
    results["samples"]["audio_jfk"] = {
        "transcript": body.get("transcript"),
        "claims_found": body.get("claims_found"),
        "claims": body.get("claims")}
finally:
    proc.terminate()
    bridge.terminate()

failed = [c for c in results["checks"] if not c["pass"]]
out = os.path.join(HERE, "battery-2026-10-31.json")
with open(out, "w") as fh:
    json.dump(results, fh, indent=2)
print(f"\n{len(results['checks']) - len(failed)}/{len(results['checks'])} "
      f"checks passed; battery at {out}")
sys.exit(1 if failed else 0)
