#!/usr/bin/env python3
"""SwiftRender - a video production pipeline API (RapidAPI lane, queue #17).

Honest scope: SwiftRender accelerates the production pipeline AROUND
video generation. It cannot speed up any generation model's own
rendering or inference, and it does not claim to. What it removes is
the waiting and rework around generation:

- Right-sized generation durations, computed in code from the job's
  timing map (needed span + a stated handle, capped) instead of the
  flat 10 s default the manual workflow used.
- Parallel submission bookkeeping: every line of a job is created,
  gated and re-queued independently, so clips can be generated in
  parallel through any lane and dropped in through the import
  adapter.
- Instant automatic gating on arrival: the DriftCheck engine
  (worst-frame drift vs the clip's own first frame, frozen spans)
  plus ffmpeg freezedetect, run the moment a clip lands.
- An automatic retry queue: a failed clip returns a corrected-prompt
  draft built in code from its failure class (the same corrections
  that worked manually on the owner's Rosewood lines 9, 12 and 13)
  and is re-queued as awaiting generation. A failed clip is never
  silently installed.
- Automatic assembly: when every line has a passing clip, each
  clip's approved span is cut per the timing map, laid on the job
  timeline against the job's audio track, and returned as one MP4
  with a measured assembly report.

Provider adapters: the import adapter (clips generated anywhere,
including Muse's built-in generator) is live. A Replicate adapter
(Seedance) is coded but parked on REPLICATE_API_TOKEN and answers a
clean provider_not_configured until the owner provides the token
through the Secure Vault. No account was created, no credit bought,
no paid generation run for this build.

Gate rule (the lane's standard): every non-health endpoint requires
the x-rapidapi-proxy-secret header to match RAPIDAPI_PROXY_SECRET.
Storage is a filesystem job store under SWIFTRENDER_DATA_DIR
(default ./data next to this file). Render's free disk is
ephemeral; job records survive restarts of the process, not
necessarily a full disk wipe, and the service does not claim
otherwise.
"""

import hashlib
import importlib.util
import json
import math
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

PORT = int(os.environ.get("PORT", "8117"))
PROXY_SECRET = os.environ.get("RAPIDAPI_PROXY_SECRET", "")
REPLICATE_TOKEN = os.environ.get("REPLICATE_API_TOKEN", "")
REPLICATE_MODEL = os.environ.get("REPLICATE_MODEL", "bytedance/seedance-1-pro")
DATA_DIR = os.environ.get(
    "SWIFTRENDER_DATA_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))

HANDLE_S = 1.0          # stated handle added to each needed span
MIN_REQUEST_S = 3       # shortest generation request the service books
MAX_REQUEST_S = 10      # cap: the manual workflow's flat default
MAX_CLIP_BYTES = 200 * 1024 * 1024
MAX_AUDIO_BYTES = 200 * 1024 * 1024
OUT_W, OUT_H, OUT_FPS = 1280, 720, 30

RECENT = []
JOBS = {}
LOCK = threading.RLock()
_ENCODER = {"name": None}

# ---------------------------------------------------------------- engine load

def _load_drift_engine():
    """Load the DriftCheck engine in-process from the sibling service.

    The engine is reused, not copied: driftcheck/app.py exports
    check_video, probe_duration, fetch_bytes and the verdict bands.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "..", "driftcheck", "app.py"),
        os.path.join(os.getcwd(), "driftcheck", "app.py"),
    ]
    for path in candidates:
        path = os.path.normpath(path)
        if os.path.exists(path):
            spec = importlib.util.spec_from_file_location(
                "driftcheck_engine", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod, path
    return None, None


DRIFT, DRIFT_PATH = _load_drift_engine()


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ------------------------------------------------------------ duration math

def requested_duration(span_s):
    """The right-sizing rule, in code: needed span + HANDLE_S,
    ceilinged, floored at MIN_REQUEST_S, capped at MAX_REQUEST_S."""
    return max(MIN_REQUEST_S,
               min(MAX_REQUEST_S, int(math.ceil(span_s + HANDLE_S))))


# ------------------------------------------------------------- ffmpeg utils

def _run(cmd, timeout=600):
    return subprocess.run(cmd, capture_output=True, text=True,
                          timeout=timeout)


def ffmpeg_version():
    try:
        out = _run(["ffmpeg", "-version"], timeout=15)
        if out.returncode == 0:
            return out.stdout.splitlines()[0].strip()
    except Exception:
        pass
    return None


def video_encoder():
    """libx264 when the host's ffmpeg has it, else mpeg4 (native)."""
    if _ENCODER["name"]:
        return _ENCODER["name"]
    for enc in ("libx264", "mpeg4"):
        try:
            out = _run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                        "color=c=black:s=64x64:d=0.1", "-c:v", enc,
                        "-f", "null", "-"], timeout=30)
            if out.returncode == 0:
                _ENCODER["name"] = enc
                return enc
        except Exception:
            continue
    _ENCODER["name"] = "mpeg4"
    return "mpeg4"


def freezedetect_spans(path):
    """ffmpeg freezedetect (n=0.003:d=2, the manual QA settings).
    Returns a list of {start, end, duration_s} frozen spans."""
    try:
        out = _run(["ffmpeg", "-v", "info", "-i", path, "-vf",
                    "freezedetect=n=0.003:d=2", "-map", "0:v:0",
                    "-f", "null", "-"], timeout=300)
        log = out.stderr or ""
    except Exception as exc:
        return [], "freezedetect_failed: %s" % exc
    spans = []
    cur = None
    for line in log.splitlines():
        m = re.search(r"freeze_start:\s*([0-9.]+)", line)
        if m:
            cur = float(m.group(1))
            continue
        m = re.search(r"freeze_end:\s*([0-9.]+)", line)
        if m and cur is not None:
            end = float(m.group(1))
            spans.append({"start": round(cur, 2), "end": round(end, 2),
                          "duration_s": round(end - cur, 2)})
            cur = None
    if cur is not None:
        dur = None
        if DRIFT is not None:
            dur = DRIFT.probe_duration(path)
        if dur:
            spans.append({"start": round(cur, 2), "end": round(dur, 2),
                          "duration_s": round(dur - cur, 2)})
    return spans, None


def decode_clean(path):
    try:
        out = _run(["ffmpeg", "-v", "error", "-i", path, "-f", "null",
                    "-"], timeout=600)
        return out.returncode == 0 and not (out.stderr or "").strip()
    except Exception:
        return False


def measure_loudness(path):
    """Integrated loudness via ffmpeg loudnorm analysis pass."""
    try:
        out = _run(["ffmpeg", "-i", path, "-af",
                    "loudnorm=print_format=json", "-f", "null", "-"],
                   timeout=600)
        m = re.search(r'"input_i"\s*:\s*"(-?[0-9.]+)"', out.stderr or "")
        if m:
            return float(m.group(1))
    except Exception:
        pass
    return None


# -------------------------------------------------------------- gate logic

CORRECTIONS = {
    "frozen": (
        " Keep the camera and the subject in continuous visible "
        "motion for the entire clip; no held frames, no still-image "
        "holds, no freeze at the head or the tail."),
    "composition_replacement": (
        " Hold ONE stable composition from the first frame to the "
        "last: no tilt, no pan reveal, no zoom reveal, no change of "
        "subject or framing; all motion happens inside the frame "
        "only (wind, light, small subject movement)."),
    "text_artifact": (
        " No text-bearing surfaces anywhere in frame: no books, "
        "ledgers, signs, plaques, engraved stones, labels or "
        "printed pages; every surface blank, smooth and unmarked."),
    "general_drift": (
        " Keep the subject, framing, palette and era identical to "
        "the first frame for the whole clip; slow, minimal camera "
        "movement only."),
}


def corrected_prompt(base_prompt, failure_class):
    suffix = CORRECTIONS.get(failure_class, CORRECTIONS["general_drift"])
    base = (base_prompt or "").strip()
    if suffix.strip() in base:
        return base
    return (base + suffix).strip()


def run_gate(video_path, duration_s):
    """DriftCheck engine + freezedetect. Returns (gate_dict, error)."""
    if DRIFT is None:
        return None, "drift_engine_unavailable"
    from PIL import Image
    frames_dir = os.path.join(os.path.dirname(video_path), "_gate")
    os.makedirs(frames_dir, exist_ok=True)
    first = os.path.join(frames_dir, "first.jpg")
    try:
        DRIFT.extract_frame(video_path, 0.05, first)
    except Exception as exc:
        return None, "first_frame_failed: %s" % exc
    ref_im = Image.open(first).convert("RGB")
    result, err = DRIFT.check_video(video_path, ref_im, n_frames=10)
    if err:
        if isinstance(err, tuple) and len(err) == 2 \
                and isinstance(err[1], dict):
            err = err[1].get("detail") or err[1].get("error") or str(err)
        return None, str(err)
    spans, ferr = freezedetect_spans(video_path)
    verdict = result["verdict"]
    engine_verdict = verdict
    dur = result["duration_s"] or duration_s or 0
    frozen_s = round(sum(s["duration_s"] for s in spans), 2)
    coverage = round(frozen_s / dur, 3) if dur else 0
    escalation = None
    if coverage >= 0.5:
        # A motion clip must stay in motion (the owner's standing
        # motion-integrity rule): half or more of the runtime
        # frozen is a failure, not a warning.
        verdict = "fail"
        escalation = ("frozen coverage %.0f%% of runtime >= 50%%: "
                      "escalated to fail" % (100 * coverage))
    elif spans and verdict == "pass":
        verdict = "warn"
        escalation = "frozen span(s) present: escalated pass to warn"
    gate = {
        "engine": "driftcheck (worst frame vs own first frame, "
                  "10 sampled frames) + ffmpeg freezedetect "
                  "n=0.003:d=2",
        "drift_score": result["drift_score"],
        "mean_drift_score": result["mean_drift_score"],
        "duration_s": result["duration_s"],
        "frames_sampled": result["frames_sampled"],
        "worst_frames": result["worst_frames"],
        "frozen_spans_engine": result.get("frozen_spans") or [],
        "frozen_spans_freezedetect": spans,
        "frozen_coverage": coverage,
        "freezedetect_error": ferr,
        "engine_verdict": engine_verdict,
        "escalation": escalation,
        "verdict": verdict,
    }
    return gate, None


def classify_failure(gate):
    """Failure class for the retry queue, from the gate record."""
    spans = (gate.get("frozen_spans_freezedetect") or
             gate.get("frozen_spans_engine") or [])
    drift = gate.get("drift_score") or 0
    if spans and drift <= 65:
        return "frozen"
    worst = gate.get("worst_frames") or []
    dur = gate.get("duration_s") or 0
    late = any((w.get("at_s") or 0) >= 0.5 * max(dur, 0.01)
               for w in worst[:1])
    if drift > 65 and late:
        return "composition_replacement"
    return "general_drift"


# --------------------------------------------------------------- job store

def job_dir(job_id):
    return os.path.join(DATA_DIR, job_id)


def save_job(job):
    d = job_dir(job["id"])
    os.makedirs(d, exist_ok=True)
    tmp = os.path.join(d, "job.json.tmp")
    with open(tmp, "w") as f:
        json.dump(job, f, indent=1)
    os.replace(tmp, os.path.join(d, "job.json"))


def load_jobs():
    if not os.path.isdir(DATA_DIR):
        return
    for name in sorted(os.listdir(DATA_DIR)):
        p = os.path.join(DATA_DIR, name, "job.json")
        if os.path.exists(p):
            try:
                with open(p) as f:
                    job = json.load(f)
                JOBS[job["id"]] = job
            except Exception:
                continue


def public_job(job):
    out = json.loads(json.dumps(job))
    for clip in out["clips"].values():
        for imp in clip.get("imports", []):
            imp.pop("file", None)
    return out


def clip_passing(clip):
    """A line passes when its current import's verdict is pass or
    warn. Warn lines carry their reason into the assembly report;
    assembly is allowed, exactly as the manual workflow installed
    warn clips only with the reason recorded."""
    cur = clip.get("current_import")
    if cur is None:
        return False
    imp = clip["imports"][cur]
    return imp.get("verdict") in ("pass", "warn")


def missing_lines(job):
    return [lid for lid, c in job["clips"].items()
            if not clip_passing(c)]


# ------------------------------------------------------- provider adapters

class ImportAdapter:
    """Clips generated anywhere are dropped in via /import and flow
    through the same gate and assembly. Live."""
    name = "import"
    state = "live"


class ReplicateAdapter:
    """Seedance through Replicate. Coded, parked on
    REPLICATE_API_TOKEN: without the token every call answers
    provider_not_configured. With a token it submits a prediction
    for the model named by REPLICATE_MODEL, polls to completion,
    downloads the output and returns its bytes for the normal
    import/gate path. This path is unverified until the owner
    provides the token (no paid generation was run for this
    build)."""
    name = "replicate"

    @property
    def state(self):
        return "live" if REPLICATE_TOKEN else "provider_not_configured"

    def generate(self, prompt, duration_s):
        if not REPLICATE_TOKEN:
            return None, "provider_not_configured"
        body = json.dumps({
            "input": {"prompt": prompt, "duration": duration_s,
                      "aspect_ratio": "16:9"},
        }).encode()
        url = ("https://api.replicate.com/v1/models/%s/predictions"
               % REPLICATE_MODEL)
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={"Authorization": "Bearer " + REPLICATE_TOKEN,
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                pred = json.loads(r.read().decode())
        except Exception as exc:
            return None, "replicate_submit_failed: %s" % exc
        get_url = (pred.get("urls") or {}).get("get")
        deadline = time.time() + 900
        while get_url and time.time() < deadline:
            time.sleep(5)
            req = urllib.request.Request(
                get_url, headers={
                    "Authorization": "Bearer " + REPLICATE_TOKEN})
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    pred = json.loads(r.read().decode())
            except Exception as exc:
                return None, "replicate_poll_failed: %s" % exc
            status = pred.get("status")
            if status == "succeeded":
                out = pred.get("output")
                if isinstance(out, list):
                    out = out[0] if out else None
                if not out:
                    return None, "replicate_empty_output"
                try:
                    with urllib.request.urlopen(out, timeout=300) as r:
                        return r.read(), None
                except Exception as exc:
                    return None, "replicate_download_failed: %s" % exc
            if status in ("failed", "canceled"):
                return None, "replicate_%s: %s" % (
                    status, pred.get("error"))
        return None, "replicate_timeout"


ADAPTERS = {"import": ImportAdapter(), "replicate": ReplicateAdapter()}


# ------------------------------------------------------------ job creation

def build_clip_entries(timing_map, clips_in):
    """Timing math in code: per-line span from the timing map and
    the right-sized generation request, shown in the record."""
    prompts = {}
    for c in clips_in or []:
        lid = str(c.get("line_id"))
        prompts[lid] = {"prompt": c.get("prompt") or "",
                        "reference": c.get("reference")}
    clips = {}
    manual_total = 0
    sized_total = 0
    for t in timing_map:
        lid = str(t["line_id"])
        start, end = float(t["start"]), float(t["end"])
        span = round(end - start, 3)
        req = requested_duration(span)
        manual_total += MAX_REQUEST_S
        sized_total += req
        meta = prompts.get(lid, {"prompt": "", "reference": None})
        clips[lid] = {
            "line_id": lid,
            "prompt": meta["prompt"],
            "reference": meta["reference"],
            "timing": {"start": start, "end": end, "span_s": span},
            "generation": {
                "needed_span_s": span,
                "handle_s": HANDLE_S,
                "requested_duration_s": req,
                "rule": "ceil(span + handle), min %d, max %d"
                        % (MIN_REQUEST_S, MAX_REQUEST_S),
                "manual_flat_default_s": MAX_REQUEST_S,
            },
            "status": "awaiting_generation",
            "imports": [],
            "current_import": None,
        }
    totals = {
        "lines": len(clips),
        "needed_span_s_total": round(
            sum(c["timing"]["span_s"] for c in clips.values()), 3),
        "requested_duration_s_total": sized_total,
        "manual_flat_default_s_total": manual_total,
        "generation_seconds_saved": manual_total - sized_total,
        "generation_seconds_saved_pct": round(
            100.0 * (manual_total - sized_total) / manual_total, 1)
        if manual_total else 0,
    }
    return clips, totals


def register_import(job, clip, data, filename, approved_in_s,
                    visual_failure):
    """Save an imported clip, gate it, set the line's state and the
    retry queue. A failed clip is never installed as current."""
    cdir = os.path.join(job_dir(job["id"]), "clips")
    os.makedirs(cdir, exist_ok=True)
    idx = len(clip["imports"])
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", filename or "clip.mp4")
    fname = "%s_%02d_%s" % (clip["line_id"], idx, safe)
    fpath = os.path.join(cdir, fname)
    with open(fpath, "wb") as f:
        f.write(data)
    duration_s = DRIFT.probe_duration(fpath) if DRIFT else None
    imp = {
        "index": idx,
        "file": fname,
        "bytes": len(data),
        "sha256": sha256_bytes(data),
        "duration_s": duration_s,
        "approved_in_s": approved_in_s or 0,
        "imported_at": now_iso(),
        "gate": None,
        "verdict": None,
        "failure_class": None,
        "corrected_prompt": None,
    }
    if visual_failure:
        # Caller-attested visual QA failure (for example lettering
        # the drift metrics cannot read; OCR is unavailable on this
        # host, exactly as DriftCheck reports). Recorded as a gate
        # failure of the named class, never hidden.
        imp["verdict"] = "fail"
        imp["failure_class"] = visual_failure
        imp["gate"] = {"engine": "caller visual QA attestation",
                       "note": "visual_failure=%s supplied at import; "
                               "drift metrics do not read text"
                               % visual_failure}
        imp["corrected_prompt"] = corrected_prompt(
            clip["prompt"], visual_failure)
        clip["imports"].append(imp)
        clip["status"] = "gate_failed"
        return imp
    gate, err = run_gate(fpath, duration_s)
    if err:
        imp["verdict"] = "gate_error"
        imp["gate"] = {"error": err}
        clip["imports"].append(imp)
        clip["status"] = "gate_error"
        return imp
    imp["gate"] = gate
    imp["verdict"] = gate["verdict"]
    if gate["verdict"] == "fail":
        imp["failure_class"] = classify_failure(gate)
        imp["corrected_prompt"] = corrected_prompt(
            clip["prompt"], imp["failure_class"])
        clip["status"] = "gate_failed"
    else:
        clip["current_import"] = idx
        clip["status"] = ("gated_warn" if gate["verdict"] == "warn"
                          else "gated_pass")
    clip["imports"].append(imp)
    return imp


def retry_queue(job):
    queue = []
    for lid, clip in job["clips"].items():
        if clip["status"] in ("gate_failed", "awaiting_generation"):
            last = clip["imports"][-1] if clip["imports"] else None
            queue.append({
                "line_id": lid,
                "status": clip["status"],
                "failure_class": (last or {}).get("failure_class"),
                "corrected_prompt": (last or {}).get(
                    "corrected_prompt") or clip["prompt"],
                "requested_duration_s":
                    clip["generation"]["requested_duration_s"],
            })
    return queue


# ---------------------------------------------------------------- assembly

def _enc_args():
    enc = video_encoder()
    if enc == "libx264":
        return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18"]
    return ["-c:v", "mpeg4", "-q:v", "3"]


def assemble(job):
    """Cut each passing clip's approved span per the timing map and
    lay the pieces on the job timeline against the job's audio.
    Refuses, listing the lines, when any line lacks a passing clip
    or the job has no audio track."""
    miss = missing_lines(job)
    if miss:
        return None, {"error": "missing_passing_clips",
                      "missing_lines": miss}
    if not job.get("audio") or not job["audio"].get("file"):
        return None, {"error": "audio_missing",
                      "detail": "the job was created without an "
                                "audio track; assembly lays clips "
                                "against the job's audio"}
    jdir = job_dir(job["id"])
    work = os.path.join(jdir, "assembly")
    os.makedirs(work, exist_ok=True)
    enc = _enc_args()
    vf = ("scale=%d:%d:force_original_aspect_ratio=decrease,"
          "pad=%d:%d:(ow-iw)/2:(oh-ih)/2,fps=%d,format=yuv420p"
          % (OUT_W, OUT_H, OUT_W, OUT_H, OUT_FPS))
    lines = sorted(job["clips"].values(),
                   key=lambda c: c["timing"]["start"])
    total = max(c["timing"]["end"] for c in lines)
    pieces, used, cursor = [], [], 0.0
    n = 0
    for clip in lines:
        start, end = clip["timing"]["start"], clip["timing"]["end"]
        span = end - start
        if start > cursor + 0.01:
            gap = start - cursor
            gp = os.path.join(work, "piece_%03d_gap.mp4" % n)
            out = _run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                        "color=c=black:s=%dx%d:r=%d"
                        % (OUT_W, OUT_H, OUT_FPS),
                        "-t", "%.3f" % gap, "-vf",
                        "format=yuv420p"] + enc + [gp], timeout=300)
            if out.returncode != 0:
                return None, {"error": "gap_encode_failed",
                              "detail": (out.stderr or "")[-400:]}
            pieces.append(gp)
            n += 1
        imp = clip["imports"][clip["current_import"]]
        src = os.path.join(jdir, "clips", imp["file"])
        src_in = float(imp.get("approved_in_s") or 0)
        sp = os.path.join(work, "piece_%03d_%s.mp4" % (n, clip["line_id"]))
        out = _run(["ffmpeg", "-y", "-ss", "%.3f" % src_in, "-i", src,
                    "-t", "%.3f" % span, "-vf", vf, "-an"] + enc + [sp],
                   timeout=600)
        if out.returncode != 0:
            return None, {"error": "segment_encode_failed",
                          "line_id": clip["line_id"],
                          "detail": (out.stderr or "")[-400:]}
        pieces.append(sp)
        used.append({"line_id": clip["line_id"],
                     "timeline_start_s": start,
                     "timeline_end_s": end,
                     "source_in_s": src_in,
                     "span_s": round(span, 3),
                     "verdict": imp["verdict"],
                     "gate_drift_score":
                         (imp.get("gate") or {}).get("drift_score")})
        cursor = end
        n += 1
    if total > cursor + 0.01:
        gp = os.path.join(work, "piece_%03d_tailgap.mp4" % n)
        out = _run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                    "color=c=black:s=%dx%d:r=%d" % (OUT_W, OUT_H, OUT_FPS),
                    "-t", "%.3f" % (total - cursor), "-vf",
                    "format=yuv420p"] + enc + [gp], timeout=300)
        if out.returncode != 0:
            return None, {"error": "gap_encode_failed",
                          "detail": (out.stderr or "")[-400:]}
        pieces.append(gp)
    listfile = os.path.join(work, "concat.txt")
    with open(listfile, "w") as f:
        for p in pieces:
            f.write("file '%s'\n" % p)
    video_only = os.path.join(work, "video.mp4")
    out = _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i",
                listfile, "-c", "copy", video_only], timeout=600)
    if out.returncode != 0:
        return None, {"error": "concat_failed",
                      "detail": (out.stderr or "")[-400:]}
    audio_path = os.path.join(jdir, job["audio"]["file"])
    output = os.path.join(jdir, "output.mp4")
    out = _run(["ffmpeg", "-y", "-i", video_only, "-i", audio_path,
                "-t", "%.3f" % total, "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart", output], timeout=600)
    if out.returncode != 0:
        return None, {"error": "mux_failed",
                      "detail": (out.stderr or "")[-400:]}
    probed = DRIFT.probe_duration(output) if DRIFT else None
    spans, _ = freezedetect_spans(output)
    report = {
        "assembled_at": now_iso(),
        "output_file": "output.mp4",
        "encoder": video_encoder(),
        "lines_used": used,
        "warn_lines": [u["line_id"] for u in used
                       if u["verdict"] == "warn"],
        "timeline_total_s": round(total, 3),
        "output_duration_s": probed,
        "duration_delta_s": (round(probed - total, 3)
                             if probed else None),
        "audio_duration_s": job["audio"].get("duration_s"),
        "audio_sha256": job["audio"].get("sha256"),
        "loudness_lufs_integrated": measure_loudness(output),
        "frozen_spans": spans,
        "decode_clean": decode_clean(output),
    }
    return report, None


# ------------------------------------------------------------------- HTTP

def parse_multipart(body, content_type):
    m = re.search(r"boundary=([^;]+)", content_type or "")
    if not m:
        return {}, {}
    boundary = m.group(1).strip().strip('"').encode()
    fields, files = {}, {}
    for part in body.split(b"--" + boundary):
        part = part.strip(b"\r\n")
        if not part or part == b"--":
            continue
        if part.endswith(b"--"):
            part = part[:-2].rstrip(b"\r\n")
        head, _, payload = part.partition(b"\r\n\r\n")
        head = head.decode("utf-8", "replace")
        nm = re.search(r'name="([^"]+)"', head)
        if not nm:
            continue
        fn = re.search(r'filename="([^"]*)"', head)
        if fn:
            files[nm.group(1)] = (fn.group(1), payload)
        else:
            fields[nm.group(1)] = payload.decode("utf-8", "replace")
    return fields, files


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, obj, ctype="application/json"):
        if isinstance(obj, (bytes, bytearray)):
            body = bytes(obj)
        else:
            body = json.dumps(obj, indent=1).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _gate_ok(self):
        if not PROXY_SECRET:
            return True
        return self.headers.get("x-rapidapi-proxy-secret") == PROXY_SECRET

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def _json_body(self):
        try:
            return json.loads(self._body().decode() or "{}")
        except Exception:
            return None

    def _note(self, what):
        RECENT.append({"at": now_iso(), "event": what})
        del RECENT[:-20]

    # -- GET ------------------------------------------------------
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            return self._send(200, {
                "service": "SwiftRender",
                "version": "1.0.0",
                "honesty": "accelerates the production pipeline "
                           "around generation, never a model's own "
                           "rendering",
                "engines": {
                    "drift_gate": ("live" if DRIFT else "unavailable"),
                    "drift_engine_path": DRIFT_PATH,
                    "ffmpeg": ffmpeg_version(),
                    "assembly": ("live" if ffmpeg_version()
                                 else "unavailable"),
                    "adapters": {k: v.state
                                 for k, v in ADAPTERS.items()},
                },
                "gate": ("proxy-secret enforced"
                         if PROXY_SECRET else
                         "proxy-secret NOT set on origin (test mode)"),
                "storage": DATA_DIR,
                "storage_note": "filesystem job store; on Render's "
                                "free tier the disk is ephemeral",
                "limits": {"handle_s": HANDLE_S,
                           "min_request_s": MIN_REQUEST_S,
                           "max_request_s": MAX_REQUEST_S,
                           "max_clip_bytes": MAX_CLIP_BYTES},
                "jobs_on_disk": len(JOBS),
                "recent": RECENT[-5:],
            })
        if not self._gate_ok():
            return self._send(401, {"error": "unauthorized",
                                    "detail": "missing or wrong "
                                              "x-rapidapi-proxy-secret"})
        m = re.match(r"^/jobs/([^/]+)$", path)
        if m:
            job = JOBS.get(m.group(1))
            if not job:
                return self._send(404, {"error": "job_not_found"})
            out = public_job(job)
            out["retry_queue"] = retry_queue(job)
            out["missing_lines"] = missing_lines(job)
            return self._send(200, out)
        m = re.match(r"^/jobs/([^/]+)/output$", path)
        if m:
            job = JOBS.get(m.group(1))
            if not job or not job.get("assembly"):
                return self._send(404, {"error": "output_not_found"})
            p = os.path.join(job_dir(job["id"]), "output.mp4")
            if not os.path.exists(p):
                return self._send(404, {"error": "output_not_found"})
            with open(p, "rb") as f:
                return self._send(200, f.read(), "video/mp4")
        return self._send(404, {"error": "not_found", "path": path})

    # -- POST -----------------------------------------------------
    def do_POST(self):
        path = urlparse(self.path).path
        if not self._gate_ok():
            return self._send(401, {"error": "unauthorized",
                                    "detail": "missing or wrong "
                                              "x-rapidapi-proxy-secret"})
        if path == "/jobs":
            return self._create_job()
        m = re.match(r"^/jobs/([^/]+)/clips/([^/]+)/import$", path)
        if m:
            return self._import_clip(m.group(1), m.group(2))
        m = re.match(r"^/jobs/([^/]+)/clips/([^/]+)/generate$", path)
        if m:
            return self._generate_clip(m.group(1), m.group(2))
        m = re.match(r"^/jobs/([^/]+)/assemble$", path)
        if m:
            return self._assemble(m.group(1))
        return self._send(404, {"error": "not_found", "path": path})

    def _create_job(self):
        ctype = self.headers.get("Content-Type") or ""
        audio_file = None
        if "multipart/form-data" in ctype:
            fields, files = parse_multipart(self._body(), ctype)
            try:
                payload = {
                    "title": fields.get("title", "untitled"),
                    "timing_map": json.loads(fields["timing_map"]),
                    "clips": json.loads(fields.get("clips") or "[]"),
                    "audio_url": fields.get("audio_url"),
                }
            except Exception as exc:
                return self._send(422, {"error": "bad_multipart",
                                        "detail": str(exc)})
            if "audio" in files:
                audio_file = files["audio"]
        else:
            payload = self._json_body()
            if payload is None:
                return self._send(422, {"error": "bad_json"})
        timing = payload.get("timing_map")
        if not timing or not isinstance(timing, list):
            return self._send(422, {"error": "timing_map_required",
                                    "detail": "timing_map: "
                                              "[{line_id, start, end}]"})
        for t in timing:
            if ("line_id" not in t or "start" not in t
                    or "end" not in t or float(t["end"]) <= float(t["start"])):
                return self._send(422, {"error": "bad_timing_entry",
                                        "entry": t})
        job_id = "job-" + uuid.uuid4().hex[:10]
        clips, totals = build_clip_entries(timing,
                                           payload.get("clips"))
        job = {
            "id": job_id,
            "title": payload.get("title") or "untitled",
            "created_at": now_iso(),
            "audio": None,
            "clips": clips,
            "totals": totals,
            "assembly": None,
        }
        jdir = job_dir(job_id)
        os.makedirs(jdir, exist_ok=True)
        audio_bytes, audio_name, audio_source = None, None, None
        if audio_file:
            audio_name, audio_bytes = audio_file
            audio_source = "upload"
        elif payload.get("audio_url"):
            if DRIFT is None:
                return self._send(503, {"error": "fetch_unavailable"})
            audio_bytes, err = DRIFT.fetch_bytes(
                payload["audio_url"], MAX_AUDIO_BYTES)
            if err:
                return self._send(422, {"error": "audio_fetch_failed",
                                        "detail": err})
            audio_name = "audio" + (
                os.path.splitext(urlparse(payload["audio_url"]).path)[1]
                or ".bin")
            audio_source = "url"
        if audio_bytes:
            ext = os.path.splitext(audio_name or "audio.bin")[1] or ".bin"
            fname = "audio" + ext
            apath = os.path.join(jdir, fname)
            with open(apath, "wb") as f:
                f.write(audio_bytes)
            job["audio"] = {
                "source": audio_source,
                "file": fname,
                "bytes": len(audio_bytes),
                "sha256": sha256_bytes(audio_bytes),
                "duration_s": (DRIFT.probe_duration(apath)
                               if DRIFT else None),
            }
        with LOCK:
            JOBS[job_id] = job
            save_job(job)
        self._note("job created %s" % job_id)
        return self._send(201, public_job(job))

    def _import_clip(self, job_id, line_id):
        job = JOBS.get(job_id)
        if not job:
            return self._send(404, {"error": "job_not_found"})
        clip = job["clips"].get(line_id)
        if not clip:
            return self._send(404, {"error": "line_not_found",
                                    "line_id": line_id})
        ctype = self.headers.get("Content-Type") or ""
        if "multipart/form-data" not in ctype:
            return self._send(422, {"error": "multipart_required",
                                    "detail": "send the video as a "
                                              "multipart file part "
                                              "named 'video'"})
        fields, files = parse_multipart(self._body(), ctype)
        if "video" not in files:
            return self._send(422, {"error": "video_part_required"})
        filename, data = files["video"]
        if len(data) > MAX_CLIP_BYTES:
            return self._send(422, {"error": "clip_too_large"})
        try:
            approved_in = float(fields.get("approved_in_s") or 0)
        except Exception:
            approved_in = 0
        visual_failure = fields.get("visual_failure") or None
        if visual_failure and visual_failure not in CORRECTIONS:
            return self._send(422, {"error": "bad_visual_failure",
                                    "allowed": sorted(CORRECTIONS)})
        with LOCK:
            imp = register_import(job, clip, data, filename,
                                  approved_in, visual_failure)
            save_job(job)
        self._note("import %s/%s -> %s" % (job_id, line_id,
                                           imp["verdict"]))
        return self._send(200, {
            "job_id": job_id, "line_id": line_id,
            "import": {k: v for k, v in imp.items() if k != "file"},
            "line_status": clip["status"],
            "current_import": clip["current_import"],
        })

    def _generate_clip(self, job_id, line_id):
        job = JOBS.get(job_id)
        if not job:
            return self._send(404, {"error": "job_not_found"})
        clip = job["clips"].get(line_id)
        if not clip:
            return self._send(404, {"error": "line_not_found",
                                    "line_id": line_id})
        payload = self._json_body() or {}
        provider = payload.get("provider") or "replicate"
        adapter = ADAPTERS.get(provider)
        if adapter is None:
            return self._send(422, {"error": "unknown_provider",
                                    "providers": sorted(ADAPTERS)})
        if provider == "import":
            return self._send(422, {
                "error": "import_is_an_upload",
                "detail": "the import adapter takes clips through "
                          "POST /jobs/{id}/clips/{line_id}/import"})
        last = clip["imports"][-1] if clip["imports"] else None
        prompt = (payload.get("prompt")
                  or (last or {}).get("corrected_prompt")
                  or clip["prompt"])
        data, err = adapter.generate(
            prompt, clip["generation"]["requested_duration_s"])
        if err == "provider_not_configured":
            return self._send(503, {
                "error": "provider_not_configured",
                "provider": provider,
                "detail": "the Replicate adapter is coded but parked "
                          "on REPLICATE_API_TOKEN, which the owner "
                          "provides through the Secure Vault; clips "
                          "can be generated in any lane meanwhile "
                          "and dropped in through the import adapter",
                "line_id": line_id,
                "prompt_that_would_be_submitted": prompt,
                "requested_duration_s":
                    clip["generation"]["requested_duration_s"]})
        if err:
            return self._send(502, {"error": "generation_failed",
                                    "provider": provider,
                                    "detail": err})
        with LOCK:
            imp = register_import(job, clip, data,
                                  "%s-replicate.mp4" % line_id, 0, None)
            save_job(job)
        return self._send(200, {
            "job_id": job_id, "line_id": line_id,
            "provider": provider,
            "import": {k: v for k, v in imp.items() if k != "file"},
            "line_status": clip["status"]})

    def _assemble(self, job_id):
        job = JOBS.get(job_id)
        if not job:
            return self._send(404, {"error": "job_not_found"})
        self._json_body()  # drain any body
        with LOCK:
            report, err = assemble(job)
            if err:
                code = 409 if err["error"] == "missing_passing_clips" \
                    else 422
                return self._send(code, err)
            job["assembly"] = report
            for clip in job["clips"].values():
                if clip_passing(clip):
                    clip["status"] = "assembled"
            save_job(job)
        self._note("assembled %s" % job_id)
        return self._send(200, {"job_id": job_id, "assembly": report,
                                "output_url": "/jobs/%s/output"
                                              % job_id})


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    load_jobs()
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print("SwiftRender listening on %d (data %s, drift %s)"
          % (PORT, DATA_DIR, "live" if DRIFT else "UNAVAILABLE"),
          flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
