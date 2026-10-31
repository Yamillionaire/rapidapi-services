#!/usr/bin/env python3
"""Deployed battery for SwiftRender: runs a REAL small job end to
end against the deployed origin through the proxy-secret gate
(create, parked-generate 503, import a moving clip, assemble,
download), because this service is fully functional without any
engine key. Needs the origin's current proxy secret in
SWIFTRENDER_TEST_SECRET. Writes battery-deployed-2026-10-31.json.
"""
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("SWIFTRENDER_BASE",
                      "https://swiftrender.onrender.com")
SECRET = os.environ.get("SWIFTRENDER_TEST_SECRET", "")
CHECKS = []


def req(method, path, raw=None, headers=None, secret=SECRET,
        ctype=None):
    h = {}
    if secret is not None:
        h["x-rapidapi-proxy-secret"] = secret
    if ctype:
        h["Content-Type"] = ctype
    if headers:
        h.update(headers)
    r = urllib.request.Request(BASE + path, data=raw, method=method,
                               headers=h)
    try:
        with urllib.request.urlopen(r, timeout=600) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def jreq(method, path, raw=None, headers=None, secret=SECRET,
         ctype=None):
    s, b = req(method, path, raw=raw, headers=headers, secret=secret,
               ctype=ctype)
    try:
        return s, json.loads(b.decode())
    except Exception:
        return s, {"raw": b[:200].decode("utf-8", "replace")}


def check(name, ok, detail=""):
    CHECKS.append({"name": name, "pass": bool(ok),
                   "detail": str(detail)})
    print(("PASS " if ok else "FAIL ") + name + " "
          + str(detail)[:150])


def multipart(fields, files):
    boundary = "----srdep5b2e"
    out = b""
    for k, v in fields.items():
        out += ("--%s\r\nContent-Disposition: form-data; name=\"%s\""
                "\r\n\r\n%s\r\n" % (boundary, k, v)).encode()
    for k, (fn, data) in files.items():
        out += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"; "
                "filename=\"%s\"\r\nContent-Type: application/"
                "octet-stream\r\n\r\n" % (boundary, k, fn)).encode()
        out += data + b"\r\n"
    out += ("--%s--\r\n" % boundary).encode()
    return out, "multipart/form-data; boundary=%s" % boundary


def main():
    if not SECRET:
        print("SWIFTRENDER_TEST_SECRET not set; cannot run")
        return 1
    tmp = tempfile.mkdtemp(prefix="sr-dep-")
    clip = os.path.join(tmp, "moving.mp4")
    audio = os.path.join(tmp, "tone.mp3")
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                    "testsrc2=size=640x360:rate=30", "-t", "6",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", clip],
                   capture_output=True, check=True)
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                    "sine=frequency=440:duration=9", "-c:a",
                    "libmp3lame", audio], capture_output=True,
                   check=True)
    s, health = jreq("GET", "/health", secret=None)
    check("health_200", s == 200
          and health["engines"]["drift_gate"] == "live", s)
    check("adapters_state",
          health["engines"]["adapters"]["import"] == "live"
          and health["engines"]["adapters"]["replicate"]
          == "provider_not_configured", health["engines"]["adapters"])
    s, _ = jreq("GET", "/jobs/x", secret=None)
    check("gate_401_no_header", s == 401, s)
    s, _ = jreq("GET", "/jobs/x", secret="wrong-value")
    check("gate_401_wrong_secret", s == 401, s)
    timing = [{"line_id": "1", "start": 0.0, "end": 2.5}]
    body, ct = multipart(
        {"title": "deployed battery job",
         "timing_map": json.dumps(timing),
         "clips": json.dumps([{"line_id": "1",
                               "prompt": "a street at dawn"}])},
        {"audio": ("tone.mp3", open(audio, "rb").read())})
    s, job = jreq("POST", "/jobs", raw=body, ctype=ct)
    check("job_created", s == 201
          and job["totals"]["requested_duration_s_total"] == 4, s)
    if s != 201:
        return finish()
    jid = job["id"]
    s, gen = jreq("POST", "/jobs/%s/clips/1/generate" % jid,
                  raw=b"{}", ctype="application/json")
    check("replicate_parked_503",
          s == 503 and gen["error"] == "provider_not_configured", s)
    body, ct = multipart({}, {"video": (
        "moving.mp4", open(clip, "rb").read())})
    s, imp = jreq("POST", "/jobs/%s/clips/1/import" % jid, raw=body,
                  ctype=ct)
    check("import_gates_and_installs",
          s == 200 and imp["line_status"] in ("gated_pass",
                                              "gated_warn"),
          imp.get("line_status"))
    s, asm = jreq("POST", "/jobs/%s/assemble" % jid, raw=b"{}",
                  ctype="application/json")
    check("assemble_ok", s == 200
          and asm["assembly"]["decode_clean"] is True, s)
    if s == 200:
        s2, raw = req("GET", "/jobs/%s/output" % jid)
        check("output_download", s2 == 200 and len(raw) > 10000,
              len(raw))
    return finish()


def finish():
    passed = sum(1 for c in CHECKS if c["pass"])
    out = {"passed": passed, "total": len(CHECKS), "checks": CHECKS,
           "base": BASE}
    with open(os.path.join(HERE, "battery-deployed-2026-10-31.json"),
              "w") as f:
        json.dump(out, f, indent=1)
    print("%d/%d checks passed" % (passed, len(CHECKS)))
    return 0 if passed == len(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
