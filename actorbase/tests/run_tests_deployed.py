"""ActorBase deployed battery (2026-10-31).

Runs against the deployed service (default
https://actorbase.onrender.com) while it rests in the honest
awaiting_key state, with the build-time test proxy secret set
on the origin for the duration of the test:

- /health 200, reasoning awaiting_key, performance installed;
- gate: /perform 401 without the secret, 401 with a wrong value;
- through the gate: /character, /scene-notes and /three-reads
  answer the explicit 503 engine_not_configured;
- through the gate: /perform and /table-read answer 200 with
  REAL performed audio - the deployed host's egress reaches the
  Edge speech service directly, so these are the end-to-end
  audio proofs the build sandbox's stalled websocket egress
  could not produce locally (see docs/actorbase-reliability.md).
  Downloaded audio is verified locally with ffprobe (duration)
  and ffmpeg volumedetect (non-silence).

After this battery runs, the build-time test secret is rotated
to an unrecorded value, leaving the origin gated until the
Studio step sets the real secret (the DriftCheck/DesignBase
pattern).

Usage: python3 run_tests_deployed.py [base_url]
Reads the test secret from ACTORBASE_TEST_SECRET (default: the
local battery's test value). Results are written to
battery-deployed-2026-10-31.json next to this file.
"""
import base64
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = (sys.argv[1] if len(sys.argv) > 1
        else "https://actorbase.onrender.com").rstrip("/")
SECRET = os.environ.get("ACTORBASE_TEST_SECRET",
                        "actorbase-battery-test-secret")
results = {"checks": [], "samples": {}, "base": BASE}


def call(method, path, body=None, headers=None, timeout=240):
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


def audio_proof(payload, tag):
    raw = base64.b64decode(payload["audio_base64"])
    path = f"/tmp/actorbase-deployed-{tag}.mp3"
    with open(path, "wb") as fh:
        fh.write(raw)
    detail = f"bytes={len(raw)}, service_duration={payload['duration_s']}s"
    dur_ok = payload["duration_s"] > 0.5
    loud_ok = False
    if shutil.which("ffprobe"):
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration", "-of", "csv=p=0", path],
            capture_output=True, text=True).stdout.strip()
        try:
            probe = float(out)
            dur_ok = dur_ok and abs(probe - payload["duration_s"]) < 0.35
            detail += f", ffprobe={probe:.2f}s"
        except ValueError:
            pass
    if shutil.which("ffmpeg"):
        out = subprocess.run(
            ["ffmpeg", "-i", path, "-af", "volumedetect", "-f",
             "null", "-"], capture_output=True, text=True).stderr
        for line in out.splitlines():
            if "mean_volume" in line:
                try:
                    mean = float(line.split(":")[-1].replace("dB", ""))
                    loud_ok = mean > -55.0
                    detail += f", mean_volume={mean} dB"
                except ValueError:
                    pass
    return dur_ok, loud_ok, detail


AUTH = {"X-RapidAPI-Proxy-Secret": SECRET}

status, health = call("GET", "/health")
check("deployed /health 200, reasoning awaiting_key, performance "
      "installed, catalog counted",
      status == 200
      and health.get("engines", {}).get("reasoning", {}).get("state")
      == "awaiting_key"
      and health.get("engines", {}).get("performance", {}).get("state")
      == "installed"
      and health.get("engines", {}).get("performance", {})
      .get("voices", 0) >= 300)
results["samples"]["health"] = health

status, body = call("POST", "/perform", {"text": "I never said that."})
check("deployed gate: /perform without secret -> 401",
      status == 401 and body.get("error") == "unauthorized")

status, body = call("POST", "/perform", {"text": "I never said that."},
                    {"X-RapidAPI-Proxy-Secret": "wrong"})
check("deployed gate: /perform wrong secret -> 401", status == 401)

for path, payload in (("/character", {"description": "A retired boxer."}),
                      ("/scene-notes", {"scene_text": "A: Go. B: No."}),
                      ("/three-reads", {"line": "I never loved you."})):
    status, body = call("POST", path, payload, AUTH)
    check(f"deployed {path} through gate -> 503 engine_not_configured",
          status == 503 and body.get("error") == "engine_not_configured")
    results["samples"][path.strip("/") + "_awaiting"] = body

status, body = call("POST", "/perform",
                    {"text": "You told me this house would still "
                             "be *ours*. You promised.",
                     "emotion": "grief", "intensity": 4,
                     "persona": "ingenue"}, AUTH)
ok_dur = ok_loud = False
detail = f"status={status}"
if status == 200:
    ok_dur, ok_loud, detail = audio_proof(body, "perform-grief")
    results["samples"]["perform_grief"] = {
        k: body[k] for k in ("voice", "persona", "emotion", "intensity",
                             "delivery", "delivery_plan", "duration_s")}
check("deployed /perform grief -> real audio, duration measured "
      "two ways, non-silent",
      status == 200 and ok_dur and ok_loud, detail)
check("deployed /perform plan: grief/4 table row (rate -15) + "
      "emphasis segment realized",
      status == 200 and body.get("delivery", {}).get("rate") == -15
      and any(s.get("emphasis") for s in body.get("delivery_plan", [])),
      f"delivery={body.get('delivery')}")

status, body = call("POST", "/table-read", {
    "cast": {"MOTHER": "matriarch", "SON": "young-hero"},
    "lines": [
        {"speaker": "MOTHER",
         "line": "You will sit down and you will listen."},
        {"speaker": "SON",
         "line": "I have been listening my whole life!"},
        {"speaker": "MOTHER",
         "line": "Then hear this. The house is sold."}]}, AUTH)
detail = f"status={status}"
ok = False
if status == 200:
    ok_dur, ok_loud, detail = audio_proof(body, "table-read")
    tm = body["timing_map"]
    ordered = all(tm[i]["end_s"] <= tm[i + 1]["start_s"] + 0.05
                  for i in range(len(tm) - 1))
    spans = abs(tm[-1]["end_s"] - body["duration_s"]) < 0.6
    voices = {t["voice"] for t in tm}
    ok = ok_dur and ok_loud and ordered and spans and len(voices) == 2
    detail += f", voices={sorted(voices)}, ordered={ordered}, spans={spans}"
    results["samples"]["table_read"] = {
        "duration_s": body["duration_s"], "timing_map": tm,
        "warnings": body["warnings"]}
check("deployed /table-read: 3 lines, 2 distinct voices, timing "
      "map ordered and spanning the audio", ok, detail)

status, body = call("POST", "/perform",
                    {"text": "How kind of you to come. Do sit down.",
                     "persona": "villain"}, AUTH)
check("deployed /perform persona villain -> Christopher voice, "
      "contempt lean",
      status == 200
      and body.get("voice") == "en-US-ChristopherNeural"
      and body.get("emotion") == "contempt",
      f"voice={body.get('voice')}, emotion={body.get('emotion')}")

failed = [c for c in results["checks"] if not c["pass"]]
out = os.path.join(HERE, "battery-deployed-2026-10-31.json")
with open(out, "w") as fh:
    json.dump(results, fh, indent=2)
print(f"\n{len(results['checks']) - len(failed)}/{len(results['checks'])} "
      f"checks passed; battery at {out}")
sys.exit(1 if failed else 0)
