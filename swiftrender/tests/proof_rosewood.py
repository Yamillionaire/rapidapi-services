#!/usr/bin/env python3
"""SwiftRender centerpiece proof, on the owner's real material.

Runs a complete job LOCALLY against the real Rosewood music-video
inputs: the cut sheet timing (cut-sheet-2026-10-31.md), the studio
master MP3 and the 16 installed clips for lines 1-16 in
~/workspace/goals/blacktown-project/files/music-video-rosewood/.

Imports all 16 through the service, compares the auto-gate verdicts
against the manual verdicts recorded in qa-log-batch1/2/3.md,
assembles lines 1-16 against the master audio, and verifies:
duration vs the timing map's line-16 end (63.50 s, tolerance
+/-1.0 s), full decode, frozen spans (split: inside clip-covered
regions vs inside the intentional black gap fills), and that the
assembled audio IS the master (decoded-waveform correlation).

This is a PIPELINE PROOF SEGMENT, not the Gate 5 master: lines
17-46 and the wordless beats are not part of it, and the gaps
(intro before line 1, interlude A, the line 11/12 gap) are black
fill where the finished video will carry generated period imagery.

Outputs (in this tests folder):
- proof-rosewood-lines1-16.mp4  (the assembled proof segment)
- proof-rosewood-2026-10-31.json (machine report)
- proof-rosewood-report-2026-10-31.md (human report)
"""
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SVC = os.path.dirname(HERE)
MV = os.path.expanduser(
    "~/workspace/goals/blacktown-project/files/music-video-rosewood")
PORT = 8219
BASE = "http://127.0.0.1:%d" % PORT
SECRET = "proof-test-secret"

# Timing from cut-sheet-2026-10-31.md: (line, start, clip need).
TIMING = [
    (1, 10.58, 3.10), (2, 13.68, 2.58), (3, 16.26, 2.60),
    (4, 18.86, 2.72), (5, 21.58, 2.46), (6, 24.04, 2.62),
    (7, 26.66, 2.60), (8, 29.26, 3.06), (9, 42.62, 2.46),
    (10, 45.08, 2.62), (11, 47.70, 2.36), (12, 50.78, 2.24),
    (13, 53.02, 2.42), (14, 55.44, 2.80), (15, 58.24, 2.46),
    (16, 60.70, 2.80),
]
CLIP_FILES = {
    1: "clip-01-roots-silence.mp4", 2: "clip-02-rose-bloom-shadows.mp4",
    3: "clip-03-ashes-trees.mp4", 4: "clip-04-fruit-leaves.mp4",
    5: "clip-05-ghosts-grain.mp4", 6: "clip-06-rose-stood-tall.mp4",
    7: "clip-07-doors-closed.mp4", 8: "clip-08-whisper-name-townsite.mp4",
    9: "clip-09-whispers-pine-clay.mp4", 10: "clip-10-ashes-breeze.mp4",
    11: "clip-11-families-scattered.mp4",
    12: "clip-12-truth-locked-back.mp4", 13: "clip-13-paper-trails.mp4",
    14: "clip-14-photo-revoked.mp4", 15: "clip-15-hush-pew.mp4",
    16: "clip-16-grandmas-eyes.mp4",
}
PROMPTS = {
    1: "Dawn over the pine woods, slow push toward the wooden rooftops below, mist in the trees",
    2: "Roses blooming along a wooden house porch, long morning shadows across the yard",
    3: "New green growth in the pine and cedar canopy, light rising through the branches",
    4: "Slow move through leafy branches, small fruit hidden in the foliage above the townsite",
    5: "Cedar wood grain of a weathered period house wall, raking morning light, faint mist",
    6: "African American townspeople in 1920s dress standing tall on a porch and yard, heads high",
    7: "Wooden doors of period houses closing down a quiet street",
    8: "Wide quiet drift over the whole townsite at first light",
    9: "Wind moving through pine tops, red clay earth below at the woods' edge",
    10: "Ash and leaves drifting on a breeze across an empty yard",
    11: "A family with bundles walking a dirt road away from town, train smoke far off",
    12: "A small period cemetery gate, iron latch closing, grass and stones",
    13: "Period paper records on a desk, a page lifting and curling in smoke light (no readable text)",
    14: "A family album closing on a table, photographs face down beside it (no faces in photos)",
    15: "Inside a small wooden church, an empty pew in window light, dust in the air",
    16: "Close on an elderly African American woman's eyes, period dress, window light",
}
# Manual gate verdicts, qa-log-batch1/2/3.md (final installed takes):
# (verdict, worst-frame drift score)
MANUAL = {
    1: ("pass", 49.6), 2: ("warn", 60.6), 3: ("warn", 54.4),
    4: ("warn", 57.8), 5: ("warn", 64.3), 6: ("pass", 46.4),
    7: ("warn", 57.2), 8: ("pass", 38.0), 9: ("warn", 59.4),
    10: ("warn", 59.0), 11: ("warn", 53.3), 12: ("warn", 26.0),
    13: ("pass", 49.8), 14: ("warn", 54.8), 15: ("warn", 59.2),
    16: ("warn", 56.9),
}
# Assembly notes from the manual QA logs: clip 12 is used at its
# latch-drop span (source in-point 5.0 s); every other line at 0.
APPROVED_IN = {12: 5.0}


def req(method, path, raw=None, headers=None):
    h = {"x-rapidapi-proxy-secret": SECRET}
    if headers:
        h.update(headers)
    r = urllib.request.Request(BASE + path, data=raw, method=method,
                               headers=h)
    try:
        with urllib.request.urlopen(r, timeout=900) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def jreq(method, path, raw=None, headers=None):
    s, b = req(method, path, raw=raw, headers=headers)
    try:
        return s, json.loads(b.decode())
    except Exception:
        return s, {"raw": b[:300].decode("utf-8", "replace")}


def multipart(fields, files):
    boundary = "----srproof9c1d"
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
    return out, {"Content-Type":
                 "multipart/form-data; boundary=%s" % boundary}


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def decode_wav(src, out, dur=None):
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", src]
    if dur:
        cmd += ["-t", "%.3f" % dur]
    cmd += ["-ac", "1", "-ar", "22050", "-f", "wav", out]
    subprocess.run(cmd, capture_output=True, check=True)


def audio_fingerprint(assembled, master, total_s, work):
    import numpy as np
    import wave
    a_wav = os.path.join(work, "assembled.wav")
    m_wav = os.path.join(work, "master.wav")
    decode_wav(assembled, a_wav)
    decode_wav(master, m_wav, dur=total_s)

    def samples(p):
        with wave.open(p) as w:
            raw = w.readframes(w.getnframes())
        return np.frombuffer(raw, dtype=np.int16).astype(np.float64)
    a, m = samples(a_wav), samples(m_wav)
    n = min(len(a), len(m))
    a, m = a[:n], m[:n]
    corr = float(np.corrcoef(a, m)[0, 1])
    rms_a = float(np.sqrt(np.mean(a ** 2)))
    rms_m = float(np.sqrt(np.mean(m ** 2)))
    return {"samples_compared": n, "correlation": round(corr, 4),
            "rms_assembled": round(rms_a, 1),
            "rms_master": round(rms_m, 1),
            "is_master_audio": bool(corr > 0.99
                                    and abs(rms_a - rms_m)
                                    / max(rms_m, 1) < 0.05)}


def main():
    master = os.path.join(MV, "rosewood-studio-master.mp3")
    assert md5(master) == "f8a26ca20f409265ae3f3585f978090f", \
        "studio master MD5 mismatch: not the version of record"
    work = os.path.join(HERE, "_proof_work")
    os.makedirs(work, exist_ok=True)
    env = dict(os.environ)
    env["RAPIDAPI_PROXY_SECRET"] = SECRET
    env["PORT"] = str(PORT)
    env["SWIFTRENDER_DATA_DIR"] = os.path.join(work, "data")
    proc = subprocess.Popen(
        [sys.executable, os.path.join(SVC, "app.py")], env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        for _ in range(60):
            time.sleep(0.5)
            try:
                s, _ = req("GET", "/health")
                if s == 200:
                    break
            except Exception:
                continue
        timing_map = [{"line_id": str(n), "start": st,
                       "end": round(st + need, 2)}
                      for n, st, need in TIMING]
        clips_meta = [{"line_id": str(n), "prompt": PROMPTS[n]}
                      for n, _, _ in TIMING]
        body, hdr = multipart(
            {"title": "Rosewood MV proof: lines 1-16",
             "timing_map": json.dumps(timing_map),
             "clips": json.dumps(clips_meta)},
            {"audio": ("rosewood-studio-master.mp3",
                       open(master, "rb").read())})
        s, job = jreq("POST", "/jobs", raw=body, headers=hdr)
        assert s == 201, (s, job)
        jid = job["id"]
        totals = job["totals"]
        print("job", jid, "totals", totals)
        gate_rows = []
        for n, st, need in TIMING:
            path = os.path.join(MV, "clips", CLIP_FILES[n])
            fields = {}
            if n in APPROVED_IN:
                fields["approved_in_s"] = str(APPROVED_IN[n])
            body, hdr = multipart(fields, {"video": (
                CLIP_FILES[n], open(path, "rb").read())})
            s, imp = jreq("POST", "/jobs/%s/clips/%d/import"
                          % (jid, n), raw=body, headers=hdr)
            assert s == 200, (n, s, imp)
            gate = imp["import"]["gate"] or {}
            auto = imp["import"]["verdict"]
            man, man_score = MANUAL[n]
            gate_rows.append({
                "line": n, "manual_verdict": man,
                "manual_worst_drift": man_score,
                "auto_verdict": auto,
                "auto_worst_drift": gate.get("drift_score"),
                "auto_mean_drift": gate.get("mean_drift_score"),
                "agree": auto == man,
                "line_status": imp["line_status"],
            })
            print("line %2d manual=%s auto=%s drift=%s"
                  % (n, man, auto, gate.get("drift_score")))
        s, asm = jreq("POST", "/jobs/%s/assemble" % jid, raw=b"{}",
                      headers={"Content-Type": "application/json"})
        assert s == 200, (s, asm)
        rep = asm["assembly"]
        s, raw = req("GET", "/jobs/%s/output" % jid)
        assert s == 200
        out_mp4 = os.path.join(HERE, "proof-rosewood-lines1-16.mp4")
        with open(out_mp4, "wb") as f:
            f.write(raw)
        total_s = TIMING[-1][1] + TIMING[-1][2]
        # frozen-span split: clip-covered regions vs black gap fills
        covered = [(st, st + need) for _, st, need in TIMING]
        in_clip, in_gap = [], []
        for span in rep["frozen_spans"]:
            mid = (span["start"] + span["end"]) / 2
            (in_clip if any(a <= mid <= b for a, b in covered)
             else in_gap).append(span)
        fp = audio_fingerprint(out_mp4, master, total_s, work)
        agree = sum(1 for r in gate_rows if r["agree"])
        report = {
            "proof": "SwiftRender pipeline proof segment: Rosewood "
                     "music video lines 1-16. NOT the Gate 5 "
                     "master (lines 17-46 and the wordless beats "
                     "are not in this segment; gaps are black fill).",
            "job_id": jid,
            "master_md5_verified": "f8a26ca20f409265ae3f3585f978090f",
            "duration_math": {
                "needed_span_s_total": totals["needed_span_s_total"],
                "right_sized_request_s_total":
                    totals["requested_duration_s_total"],
                "manual_flat_10s_total": totals[
                    "manual_flat_default_s_total"],
                "generation_seconds_saved":
                    totals["generation_seconds_saved"],
                "generation_seconds_saved_pct":
                    totals["generation_seconds_saved_pct"],
                "rule": "ceil(span + 1.0s handle), min 3, max 10, "
                        "computed in code per line from the real "
                        "timing map",
            },
            "gate_comparison": {
                "lines": gate_rows,
                "agreement": "%d/%d verdicts identical"
                             % (agree, len(gate_rows)),
                "disagreements": [r for r in gate_rows
                                  if not r["agree"]],
            },
            "assembly": rep,
            "verification": {
                "timeline_total_s": total_s,
                "output_duration_s": rep["output_duration_s"],
                "duration_delta_s": rep["duration_delta_s"],
                "duration_within_tolerance_1s":
                    abs(rep["duration_delta_s"] or 99) <= 1.0,
                "decode_clean": rep["decode_clean"],
                "frozen_spans_in_clip_regions": in_clip,
                "frozen_spans_in_gap_fill": in_gap,
                "loudness_lufs_integrated":
                    rep["loudness_lufs_integrated"],
                "audio_fingerprint": fp,
            },
        }
        with open(os.path.join(
                HERE, "proof-rosewood-2026-10-31.json"), "w") as f:
            json.dump(report, f, indent=1)
        print(json.dumps(report["verification"], indent=1))
        print("agreement:", report["gate_comparison"]["agreement"])
        return report
    finally:
        proc.terminate()


if __name__ == "__main__":
    main()
