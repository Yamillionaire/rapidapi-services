#!/usr/bin/env python3
"""Local battery for SwiftRender: boots the real server on a test
port with a test proxy secret and exercises the full pipeline with
small synthetic media built by ffmpeg (a moving clip, a frozen
clip). Writes battery-2026-10-31.json next to this script."""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SVC = os.path.dirname(HERE)
PORT = 8217
BASE = "http://127.0.0.1:%d" % PORT
SECRET = "local-test-secret"
CHECKS = []


def req(method, path, body=None, headers=None, raw=None):
    h = {"x-rapidapi-proxy-secret": SECRET}
    if headers:
        h.update(headers)
    data = raw
    if body is not None:
        data = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers=h)
    try:
        with urllib.request.urlopen(r, timeout=300) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def jreq(method, path, body=None, raw=None, headers=None):
    s, b = req(method, path, body=body, raw=raw, headers=headers)
    try:
        return s, json.loads(b.decode())
    except Exception:
        return s, {"raw": b[:200].decode("utf-8", "replace")}


def check(name, ok, detail=""):
    CHECKS.append({"name": name, "pass": bool(ok), "detail": str(detail)})
    print(("PASS " if ok else "FAIL ") + name + " " + str(detail)[:160])


def multipart(fields, files):
    boundary = "----srtest7f3a"
    out = b""
    for k, v in fields.items():
        out += ("--%s\r\nContent-Disposition: form-data; name=\"%s\""
                "\r\n\r\n%s\r\n" % (boundary, k, v)).encode()
    for k, (fn, data) in files.items():
        out += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"; "
                "filename=\"%s\"\r\nContent-Type: video/mp4\r\n\r\n"
                % (boundary, k, fn)).encode() + data + b"\r\n"
    out += ("--%s--\r\n" % boundary).encode()
    return out, {"Content-Type": "multipart/form-data; boundary=%s"
                 % boundary}


def make_clip(path, kind):
    if kind == "moving":
        vf = "testsrc2=size=640x360:rate=30"
        cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", vf, "-t", "6",
               "-c:v", "libx264", "-pix_fmt", "yuv420p", path]
    else:  # frozen: one still frame looped
        cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i",
               "color=c=red:size=640x360:rate=30", "-t", "6",
               "-c:v", "libx264", "-pix_fmt", "yuv420p", path]
    subprocess.run(cmd, capture_output=True, check=True)


def make_audio(path):
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                    "sine=frequency=440:duration=9", "-c:a",
                    "libmp3lame", path], capture_output=True,
                   check=True)


def main():
    work = os.path.join(HERE, "_battery_work")
    os.makedirs(work, exist_ok=True)
    moving = os.path.join(work, "moving.mp4")
    frozen = os.path.join(work, "frozen.mp4")
    audio = os.path.join(work, "tone.mp3")
    make_clip(moving, "moving")
    make_clip(frozen, "frozen")
    make_audio(audio)
    env = dict(os.environ)
    env["RAPIDAPI_PROXY_SECRET"] = SECRET
    env["PORT"] = str(PORT)
    env["SWIFTRENDER_DATA_DIR"] = os.path.join(work, "data")
    proc = subprocess.Popen(
        [sys.executable, os.path.join(SVC, "app.py")],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        up = False
        for _ in range(60):
            time.sleep(0.5)
            try:
                s, b = req("GET", "/health",
                           headers={"x-rapidapi-proxy-secret": "x"})
                # health is open: retry without gate header logic
                up = True
                break
            except Exception:
                continue
        check("server_boots", up)
        # health open without the secret
        r = urllib.request.Request(BASE + "/health", method="GET")
        with urllib.request.urlopen(r, timeout=30) as resp:
            health = json.loads(resp.read().decode())
        check("health_open", health["engines"]["drift_gate"] == "live"
              and health["engines"]["adapters"]["import"] == "live",
              health["engines"])
        check("health_replicate_parked",
              health["engines"]["adapters"]["replicate"]
              == "provider_not_configured")
        # gate: 401 without header
        r = urllib.request.Request(BASE + "/jobs/x", method="GET")
        try:
            urllib.request.urlopen(r, timeout=30)
            check("gate_401_no_header", False)
        except urllib.error.HTTPError as e:
            check("gate_401_no_header", e.code == 401, e.code)
        s, _ = jreq("GET", "/jobs/x",
                    headers={"x-rapidapi-proxy-secret": "wrong"})
        check("gate_401_wrong_secret", s == 401, s)
        # create job (multipart with audio upload)
        timing = [{"line_id": "1", "start": 0.0, "end": 2.5},
                  {"line_id": "2", "start": 4.0, "end": 6.5}]
        clips = [{"line_id": "1", "prompt": "a street at dawn"},
                 {"line_id": "2", "prompt": "a church interior"}]
        body, hdr = multipart(
            {"title": "battery job",
             "timing_map": json.dumps(timing),
             "clips": json.dumps(clips)},
            {"audio": ("tone.mp3", open(audio, "rb").read())})
        s, job = jreq("POST", "/jobs", raw=body, headers=hdr)
        check("job_created", s == 201, s)
        jid = job["id"]
        c1 = job["clips"]["1"]["generation"]
        check("duration_math_line1", c1["requested_duration_s"] == 4
              and c1["needed_span_s"] == 2.5, c1)
        check("duration_totals", job["totals"]
              ["requested_duration_s_total"] == 8
              and job["totals"]["manual_flat_default_s_total"] == 20
              and job["totals"]["generation_seconds_saved"] == 12,
              job["totals"])
        check("audio_recorded", job["audio"]["source"] == "upload"
              and len(job["audio"]["sha256"]) == 64)
        # generate through the parked adapter: clean 503
        s, gen = jreq("POST", "/jobs/%s/clips/1/generate" % jid,
                      body={})
        check("replicate_parked_503",
              s == 503 and gen["error"] == "provider_not_configured", s)
        # import the moving clip for line 1: gates pass/warn, installs
        body, hdr = multipart({}, {"video": (
            "moving.mp4", open(moving, "rb").read())})
        s, imp = jreq("POST", "/jobs/%s/clips/1/import" % jid,
                      raw=body, headers=hdr)
        check("import_moving_installs",
              s == 200 and imp["line_status"] in ("gated_pass",
                                                  "gated_warn"),
              imp.get("line_status"))
        # import the frozen clip for line 2: must NOT install
        body, hdr = multipart({}, {"video": (
            "frozen.mp4", open(frozen, "rb").read())})
        s, imp2 = jreq("POST", "/jobs/%s/clips/2/import" % jid,
                       raw=body, headers=hdr)
        check("import_frozen_not_installed",
              s == 200 and imp2["line_status"] == "gate_failed"
              and imp2["current_import"] is None,
              imp2.get("line_status"))
        check("frozen_corrected_prompt",
              imp2["import"]["failure_class"] in ("frozen",)
              and "continuous visible" in
              (imp2["import"]["corrected_prompt"] or ""),
              imp2["import"].get("failure_class"))
        # visual_failure attestation path (text artifact)
        body, hdr = multipart({"visual_failure": "text_artifact"},
                              {"video": ("moving.mp4",
                                         open(moving, "rb").read())})
        s, imp3 = jreq("POST", "/jobs/%s/clips/2/import" % jid,
                       raw=body, headers=hdr)
        check("text_artifact_retry_path",
              imp3["line_status"] == "gate_failed"
              and "text-bearing surfaces" in
              (imp3["import"]["corrected_prompt"] or ""))
        # assembly refuses while line 2 lacks a passing clip
        s, asm = jreq("POST", "/jobs/%s/assemble" % jid, body={})
        check("assemble_refuses_missing",
              s == 409 and asm["missing_lines"] == ["2"], asm)
        # now a real moving clip for line 2, then assembly succeeds
        body, hdr = multipart({}, {"video": (
            "moving.mp4", open(moving, "rb").read())})
        jreq("POST", "/jobs/%s/clips/2/import" % jid, raw=body,
             headers=hdr)
        s, asm = jreq("POST", "/jobs/%s/assemble" % jid, body={})
        check("assemble_ok", s == 200, asm if s != 200 else "")
        if s == 200:
            rep = asm["assembly"]
            check("assembly_duration", rep["output_duration_s"]
                  and abs(rep["duration_delta_s"]) <= 0.6,
                  rep["duration_delta_s"])
            check("assembly_decode_loudness",
                  rep["decode_clean"] is True
                  and rep["loudness_lufs_integrated"] is not None,
                  rep["loudness_lufs_integrated"])
            s2, raw = req("GET", "/jobs/%s/output" % jid)
            check("output_download", s2 == 200 and len(raw) > 10000,
                  len(raw))
        s, status = jreq("GET", "/jobs/%s" % jid)
        check("job_status_shape", s == 200
              and status["missing_lines"] == []
              and status["retry_queue"] == [], status.get("id"))
    finally:
        proc.terminate()
    passed = sum(1 for c in CHECKS if c["pass"])
    out = {"passed": passed, "total": len(CHECKS), "checks": CHECKS}
    with open(os.path.join(HERE, "battery-2026-10-31.json"), "w") as f:
        json.dump(out, f, indent=1)
    print("%d/%d checks passed" % (passed, len(CHECKS)))
    return 0 if passed == len(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
