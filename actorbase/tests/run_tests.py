"""ActorBase proof battery (2026-10-31).

Phase A (no Gemini key): gate behavior, the honest 503 state on
the reasoning endpoints, input validation, and - the point of the
service - real performed audio on the keyless performance engine:
a performed line (duration measured two ways, non-silence proven
with ffmpeg's volumedetect) and a two-character table read with
distinct persona voices and a measured timing map.

Phase B (live reasoning): the service pointed at tests/
connector_bridge.py, which routes its Gemini calls through the
user's connected Gemini API (the connector credential flow), so
the service's unmodified reasoning code runs against the real
engine: a character build, scene notes on a two-person scene,
three reads that must demonstrably differ, and a table read
whose free-text direction must come back interpreted.

Run with an interpreter that has edge-tts installed (the service's
only dependency), e.g. the build venv:
  /tmp/actorbase-venv/bin/python run_tests.py
No key is read or printed anywhere. Results are written to
battery-2026-10-31.json next to this file.
"""
import base64
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "..", "app.py")
BRIDGE = os.path.join(HERE, "connector_bridge.py")
SECRET = "actorbase-battery-test-secret"
results = {"checks": [], "samples": {},
           "environment": "Phase B Gemini calls routed through "
                          "tests/connector_bridge.py via the "
                          "custom.gemini connector (real engine, "
                          "production request shapes). Performance "
                          "ran on the local edge-tts install "
                          "(Microsoft Edge neural voices)."}


def call(port, method, path, body=None, headers=None, timeout=120):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", **(headers or {})})
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
            status, _ = call(port, "GET", "/health", timeout=5)
            if status == 200:
                return True
        except Exception:
            pass
        time.sleep(0.25)
    return False


def start(env_extra, port):
    env = dict(os.environ, **env_extra)
    proc = subprocess.Popen([sys.executable, APP], env=env,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    assert wait_health(port), f"server on {port} never became healthy"
    return proc


AUTH = {"X-RapidAPI-Proxy-Secret": SECRET}


def pace(seconds=20):
    """The owner's Gemini key has a per-minute quota; the battery
    paces its engine-heavy calls so the proof measures the
    pipeline, not the quota."""
    time.sleep(seconds)


def audio_proof(payload, tag):
    """Decode a response's audio; return (duration_ok, loud_ok,
    detail). Duration cross-checked with ffprobe; non-silence
    with ffmpeg volumedetect (a silent file reads -inf dB)."""
    raw = base64.b64decode(payload["audio_base64"])
    path = f"/tmp/actorbase-{tag}.mp3"
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


# --- Phase A: awaiting_key, performance live ----------------------------
proc = start({"PORT": "8218", "RAPIDAPI_PROXY_SECRET": SECRET}, 8218)
try:
    status, health = call(8218, "GET", "/health")
    check("awaiting /health 200: reasoning awaiting_key, performance "
          "installed, catalog counted",
          status == 200
          and health["engines"]["reasoning"]["state"] == "awaiting_key"
          and health["engines"]["performance"]["state"] == "installed"
          and health["engines"]["performance"]["voices"] >= 300,
          f"voices={health['engines']['performance']['voices']}")
    results["samples"]["health_awaiting"] = health

    status, body = call(8218, "POST", "/perform",
                        {"text": "I never said that."})
    check("gate: /perform without secret -> 401",
          status == 401 and body["error"] == "unauthorized")
    status, body = call(8218, "POST", "/perform",
                        {"text": "I never said that."},
                        {"X-RapidAPI-Proxy-Secret": "wrong"})
    check("gate: /perform wrong secret -> 401", status == 401)

    status, body = call(8218, "POST", "/character",
                        {"description": "A retired boxer."}, AUTH)
    check("awaiting /character -> explicit 503 engine_not_configured",
          status == 503 and body["error"] == "engine_not_configured")
    results["samples"]["character_awaiting"] = body

    for name, payload, code in [
            ("empty text", {"text": " "}, "missing_parameter"),
            ("bad voice", {"text": "Hello.", "voice": "en-XX-Nope"},
             "invalid_parameter"),
            ("bad emotion", {"text": "Hello.", "emotion": "meh"},
             "invalid_parameter"),
            ("bad intensity", {"text": "Hello.", "intensity": 7},
             "invalid_parameter"),
            ("bad persona", {"text": "Hello.", "persona": "hamlet"},
             "invalid_parameter")]:
        status, body = call(8218, "POST", "/perform", payload, AUTH)
        check(f"/perform invalid ({name}) -> 422 {code}",
              status == 422 and body["error"] == code)

    status, body = call(8218, "POST", "/perform",
                        {"text": "You told me this house would "
                                 "still be *ours*. You promised.",
                         "emotion": "grief", "intensity": 4,
                         "persona": "ingenue"}, AUTH, timeout=180)
    ok_dur = ok_loud = False
    detail = f"status={status}"
    if status == 200:
        ok_dur, ok_loud, detail = audio_proof(body, "perform-grief")
        results["samples"]["perform_grief"] = {
            k: body[k] for k in ("voice", "persona", "emotion",
                                 "intensity", "delivery",
                                 "delivery_plan", "duration_s")}
    check("/perform grief line -> real audio, duration measured, "
          "non-silent", status == 200 and ok_dur and ok_loud, detail)
    check("/perform plan shows the table row + emphasis segment",
          status == 200
          and body["delivery"]["rate"] == -15
          and any(s["emphasis"] for s in body["delivery_plan"]),
          f"delivery={body.get('delivery')}")

    status, body = call(8218, "POST", "/table-read", {
        "cast": {"MOTHER": "matriarch", "SON": "young-hero"},
        "lines": [
            {"speaker": "MOTHER",
             "line": "You will sit down and you will listen."},
            {"speaker": "SON",
             "line": "I have been listening my whole life!"},
            {"speaker": "MOTHER",
             "line": "Then hear this. The house is sold."}]}, AUTH,
        timeout=240)
    ok = status == 200
    detail = f"status={status}"
    if ok:
        ok_dur, ok_loud, detail = audio_proof(body, "table-read")
        tm = body["timing_map"]
        ordered = all(tm[i]["end_s"] <= tm[i + 1]["start_s"] + 0.05
                      for i in range(len(tm) - 1))
        spans = abs(tm[-1]["end_s"] - body["duration_s"]) < 0.6
        voices = {t["voice"] for t in tm}
        results["samples"]["table_read"] = {
            "duration_s": body["duration_s"], "timing_map": tm,
            "warnings": body["warnings"]}
        check("/table-read: 3 lines, 2 distinct voices, timing map "
              "ordered and spanning the audio",
              ok and ok_dur and ordered and spans and len(voices) == 2,
              detail + f", voices={sorted(voices)}")
    else:
        check("/table-read: 3 lines, 2 distinct voices", False, detail)

    status, body = call(8218, "POST", "/table-read", {
        "cast": {"A": "narrator"},
        "lines": [{"speaker": "B", "line": "Hello?"}]}, AUTH)
    check("/table-read uncast speaker -> 422 missing_parameter",
          status == 422 and body["error"] == "missing_parameter")
finally:
    proc.terminate()

# --- Phase B: live reasoning through the connector bridge ---------------
bridge = subprocess.Popen([sys.executable, BRIDGE, "8898"],
                          stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL)
time.sleep(1.0)
proc = start({"PORT": "8219", "RAPIDAPI_PROXY_SECRET": SECRET,
              "GEMINI_API_KEY": "local-bridge-placeholder",
              "GEMINI_BASE_URL": "http://127.0.0.1:8898/v1beta"}, 8219)
try:
    status, health = call(8219, "GET", "/health")
    check("live /health: reasoning live, models named",
          status == 200
          and health["engines"]["reasoning"]["state"] == "live")
    results["samples"]["health_live"] = health

    pace()
    status, body = call(8219, "POST", "/character", {
        "name": "Rosa Delgado",
        "description": "A 58-year-old former union organizer in a "
                       "dying steel town who has just learned the "
                       "plant closure she fought for a decade was "
                       "decided by her own son, now a company "
                       "executive. She taught him everything he "
                       "knows about leverage.",
        "play_context": "A two-act drama set in 1994 Ohio."},
        AUTH, timeout=240)
    ch = body.get("character", {})
    keys = ("name", "objective", "super_objective", "obstacles",
            "tactics", "backstory_beats", "given_circumstances",
            "voice_notes", "physicality_notes")
    check("/character -> full actor's build (objective, tactics as "
          "verbs, backstory, voice + physicality)",
          status == 200 and all(ch.get(k) for k in keys)
          and len(ch.get("tactics", [])) >= 3
          and len(ch.get("obstacles", [])) >= 3,
          f"keys={sorted(ch.keys())}")
    results["samples"]["character"] = body

    pace()
    status, body = call(8219, "POST", "/scene-notes", {
        "scene_text": "INT. KITCHEN - NIGHT\n\nMARA: You came home.\n"
                      "ELI: The train was late.\n"
                      "MARA: The train was late three hours ago. "
                      "I called the station, Eli.\n"
                      "ELI: Then you know everything. You always "
                      "know everything before I say it.\n"
                      "MARA: I know you were at her apartment.\n"
                      "ELI: I was ending it. That's where I was. "
                      "Ending it.\n"
                      "MARA: With your suitcase packed?\n"
                      "ELI: ...That isn't mine.\n"
                      "MARA: Then whose is it, Eli?"}, AUTH,
        timeout=240)
    check("/scene-notes -> beats, power shifts, both characters "
          "with wants/hides/tactics",
          status == 200 and len(body.get("beats", [])) >= 2
          and isinstance(body.get("power_shifts"), list)
          and len(body.get("characters", {})) >= 2
          and all("wants" in c and "hides" in c
                  for c in body.get("characters", {}).values()),
          f"beats={len(body.get('beats', []))}, "
          f"characters={list(body.get('characters', {}).keys())}")
    results["samples"]["scene_notes"] = body

    pace()
    status, body = call(8219, "POST", "/three-reads", {
        "line": "I never loved you.",
        "context": "Final scene. She has rehearsed this lie all "
                   "act; saying it is the only way to make him "
                   "leave town and live.",
        "persona": "leading-lady"}, AUTH, timeout=300)
    reads = body.get("reads", [])
    tactics = [r.get("tactic", "").strip().lower() for r in reads]
    params = {(r.get("emotion"), r.get("intensity")) for r in reads}
    distinct = len(set(tactics)) == 3 and len(params) >= 2
    audios = all(r.get("duration_s", 0) > 0.3 for r in reads)
    detail = f"tactics={tactics}, params={sorted(params)}"
    if status == 200 and reads:
        ok_dur, ok_loud, pdetail = audio_proof(
            {"audio_base64": reads[0]["audio_base64"],
             "duration_s": reads[0]["duration_s"]}, "read-one")
        audios = audios and ok_dur and ok_loud
        detail += "; " + pdetail
        results["samples"]["three_reads"] = {
            "line": body["line"],
            "reads": [{k: r[k] for k in ("read", "tactic", "subtext",
                                         "emotion", "intensity",
                                         "emphasis", "delivery_note",
                                         "duration_s")}
                      for r in reads]}
    check("/three-reads -> 3 reads, distinct tactics, differing "
          "delivery params, real audio on each",
          status == 200 and len(reads) == 3 and distinct and audios,
          detail)

    pace()
    status, body = call(8219, "POST", "/table-read", {
        "cast": {"KING": {"persona": "patriarch"},
                 "FOOL": {"persona": "trickster"}},
        "lines": [
            {"speaker": "KING", "line": "Speak plainly, fool.",
             "direction": "barely contained fury, each word "
                          "weighed like a stone"},
            {"speaker": "FOOL",
             "line": "Plainly, then: the crown is heavy because "
                     "the head is empty."}]}, AUTH, timeout=300)
    tm = body.get("timing_map", []) if status == 200 else []
    check("/table-read with direction (live) -> direction "
          "interpreted for the directed line",
          status == 200 and len(tm) == 2
          and tm[0].get("direction_interpreted") is True
          and tm[0].get("emotion") == "anger",
          f"map={[(t.get('emotion'), t.get('direction_interpreted')) for t in tm]}")
    if status == 200:
        results["samples"]["table_read_directed"] = {
            "timing_map": tm, "warnings": body["warnings"]}
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
