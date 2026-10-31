"""DriftCheck - drift / quality check for generated images and video
(the user's own product, 2026-10-31; RapidAPI lane build #12).

Born from the user's own production pain: generated character art and
motion shots drift from their references (emblems change size, faces
wander, proportions slip), and every undetected miss costs regeneration
credits. DriftCheck is the cheap gate in front of the spend: send a
candidate image (or a video) plus the reference it was supposed to
match, get back a drift report BEFORE the next credit is burned.

What v1 measures, with lightweight methods only (Pillow + numpy, no
model downloads, deployable on the free tier):
- Visual similarity vs the reference, computed on the subject art
  (both images cropped to their foreground bounding box first, so
  margins do not dominate): difference hash, perceptual hash (DCT),
  global SSIM, and a color-histogram intersection. Reported per method
  AND as a composite; the reference is also searched in overlapping
  regions (a model sheet holds many panels; the best-matching region
  is reported by name), because a whole-sheet comparison alone would
  grade the sheet's layout, not the candidate's fidelity.
- Proportion report: the subject art's bounding-box share of frame
  (width %, height %, area %) for candidate and reference, with a flag
  when the scale diverges materially (default > 20 percentage points).
  This is the check that catches an emblem rendered at the wrong size.
- Emblem / text check: OCR of the candidate when a tesseract binary is
  present on the host (it is NOT on the current deployment; the
  component then reports itself unavailable instead of guessing), plus
  the caller-supplied expected_text compared against whatever OCR
  found. The geometry half of the emblem check (scale vs reference)
  is the proportion report above.
- Video: frames sampled across the full duration with ffmpeg, each
  graded against the reference; the worst frames are returned with
  timestamps, and frozen spans (consecutive near-identical sampled
  frames) are flagged.

What v1 deliberately does NOT claim: there is no anatomy/pose check
(no lightweight pose estimator deploys cleanly on this tier, so the
component is omitted rather than faked), and the similarity scores are
classical image metrics, not a learned embedding: they are honest
triage numbers for catching gross drift, proportion slips, and wrong
assets early, not a substitute for the final human zoom audit.

The server keeps the lane scaffold's exact conventions (shared with
SwiftRead): the RapidAPI proxy-secret gate (401 JSON without the
X-RapidAPI-Proxy-Secret header, /health always open) and explicit
structured JSON errors for every failure.

Endpoints:
  POST /check-image   candidate + reference (upload, URL, or base64)
  POST /check-video   video + reference (upload or URL)
  GET  /health        -> service status, limits, method inventory
Run: python3 app.py (PORT env, default 8113).
Needs: pip install Pillow numpy; ffmpeg/ffprobe on PATH for /check-video.
"""
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import numpy as np
from PIL import Image

SERVICE = "driftcheck"
VERSION = "1.0.0"
BUILD = "2026-10-31-v1"
RECENT = []                       # last request outcomes (see /health)

MAX_IMAGE_BYTES = 15_000_000      # per image upload / fetch
MAX_VIDEO_BYTES = 60_000_000      # per video upload / fetch
MAX_BODY = 90_000_000             # whole request body cap
MAX_VIDEO_SECONDS = 300           # longer videos are refused, not truncated silently
DEFAULT_FRAMES = 10               # sampled frames per video check
MAX_FRAMES = 24
FETCH_TIMEOUT = 30
UA = "Mozilla/5.0 (compatible; DriftCheckBot/1.0; +https://rapidapi.com/YamilLittle/api/driftcheck)"

# Verdict bands on the 0..100 headline drift score (100 = reject).
# The headline blends the two measurements that proved discriminating
# in calibration on the user's own production files (2026-10-31):
# headline = 0.7 x similarity drift + 0.3 x proportion penalty, where
# the proportion penalty is min(100, 2 x the largest bbox-share
# divergence in points). Measured anchors: identical image 0.0; an
# approved design vs its own model sheet 42.2 (similarity 58.6,
# proportion divergence 0.3/1.9 points); the oversized-emblem reject
# 68.9 (similarity 56.2, divergence 49.2/36.5 - the proportion term is
# what separates it, which is the failure this service exists to
# catch). Bands: pass <= 50, warn <= 65, fail above.
# Honest limit, measured not assumed: the classical similarity core
# cannot verify character IDENTITY against a multi-panel model sheet
# (a wrong character graded 57.2 similarity drift vs the right one's
# 58.6). Against same-class references (an approved comp, a start
# still) the similarity grade is meaningful - a real motion clip's
# frames graded 11-39 against their own start still.
DRIFT_PASS_MAX = 50.0
DRIFT_WARN_MAX = 65.0
PROP_FLAG_POINTS = 20.0           # bbox-share divergence that raises the flag
FROZEN_SIM = 0.97                 # dhash similarity at/above this = same frame


# --------------------------------------------------------------------------
# Fetching (SSRF-hardened, the CleanExtract/SwiftRead stack).
# --------------------------------------------------------------------------
_BLOCKED_NETS = [ipaddress.ip_network(n) for n in (
    "0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8",
    "169.254.0.0/16", "172.16.0.0/12", "192.168.0.0/16", "224.0.0.0/4",
    "::1/128", "fc00::/7", "fe80::/10", "ff00::/8")]


def _host_is_public(host):
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception:
        return False
    if not infos:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if any(ip in net for net in _BLOCKED_NETS):
            return False
    return True


class _GuardedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlparse(newurl)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return None
        if not _host_is_public(parsed.hostname):
            raise ValueError("redirect to a non-public address refused")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_GuardedRedirect)


def fetch_bytes(url, cap):
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("url must be an absolute http or https URL")
    if not _host_is_public(parsed.hostname):
        raise ValueError("only public web addresses can be fetched")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with _OPENER.open(req, timeout=FETCH_TIMEOUT) as resp:
        raw = resp.read(cap + 1)
    if len(raw) > cap:
        raise ValueError(f"remote file exceeds the {cap} byte cap")
    return raw


# --------------------------------------------------------------------------
# Image metrics (Pillow + numpy only).
# --------------------------------------------------------------------------
def foreground_mask(im):
    """Boolean mask of the subject art. The alpha channel when the image
    actually uses transparency; otherwise distance from the background
    color estimated from the frame corners."""
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        alpha = np.asarray(im.convert("RGBA"))[:, :, 3]
        if float((alpha < 250).mean()) > 0.01:
            return alpha > 16
    rgb = np.asarray(im.convert("RGB")).astype(np.int32)
    h, w, _ = rgb.shape
    p = max(4, min(h, w) // 32)
    corners = np.concatenate([
        rgb[:p, :p].reshape(-1, 3), rgb[:p, -p:].reshape(-1, 3),
        rgb[-p:, :p].reshape(-1, 3), rgb[-p:, -p:].reshape(-1, 3)])
    bg = np.median(corners, axis=0)
    return np.abs(rgb - bg).sum(axis=2) > 60


def bbox_share(im):
    """Subject art bounding-box share of frame, with a percentile trim
    so stray specks do not stretch the box."""
    mask = foreground_mask(im)
    h, w = mask.shape
    if int(mask.sum()) < 0.001 * mask.size:
        return None
    ys, xs = np.nonzero(mask)
    x0, x1 = np.percentile(xs, [0.05, 99.95])
    y0, y1 = np.percentile(ys, [0.05, 99.95])
    bw, bh = (x1 - x0 + 1) / w, (y1 - y0 + 1) / h
    return {"width_pct": round(float(bw) * 100, 1),
            "height_pct": round(float(bh) * 100, 1),
            "area_pct": round(float(bw * bh) * 100, 1),
            "bbox_px": [int(x0), int(y0), int(x1), int(y1)]}


def subject_crop(im):
    mask = foreground_mask(im)
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return im.convert("RGB")
    x0, x1 = np.percentile(xs, [0.05, 99.95]).astype(int)
    y0, y1 = np.percentile(ys, [0.05, 99.95]).astype(int)
    return im.convert("RGB").crop((int(x0), int(y0), int(x1) + 1, int(y1) + 1))


def _dhash(gray):
    small = np.asarray(Image.fromarray(gray).resize((9, 8), Image.BILINEAR))
    return (small[:, 1:] > small[:, :-1]).flatten()


def _phash(gray):
    small = np.asarray(Image.fromarray(gray).resize((32, 32), Image.BILINEAR),
                       dtype=np.float64)
    n = 32
    k = np.arange(n)
    dct = np.cos((2 * k[:, None] + 1) * k[None, :] * np.pi / (2 * n))
    dct[0, :] *= 1.0 / np.sqrt(2)
    coeff = dct @ small @ dct.T
    low = coeff[:8, :8]
    med = np.median(low[1:, :])
    return (low > med).flatten()


def _hamming_sim(a, b):
    return 1.0 - float(np.mean(a != b))


def _global_ssim(a, b):
    a = a.astype(np.float64)
    b = b.astype(np.float64)
    mua, mub = a.mean(), b.mean()
    va, vb = a.var(), b.var()
    cov = float(((a - mua) * (b - mub)).mean())
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    val = ((2 * mua * mub + c1) * (2 * cov + c2)) / \
          ((mua ** 2 + mub ** 2 + c1) * (va + vb + c2))
    return max(0.0, min(1.0, float(val)))


def _hist_sim(a_rgb, b_rgb):
    def hist(arr):
        h = np.zeros(64)
        q = (arr // 64).astype(np.int32)
        idx = q[:, :, 0] * 16 + q[:, :, 1] * 4 + q[:, :, 2]
        np.add.at(h, idx.flatten(), 1)
        return h / h.sum()
    ha, hb = hist(a_rgb), hist(b_rgb)
    return float(np.minimum(ha, hb).sum())


def pair_similarity(cand_im, ref_im):
    """Similarity of two images' subject art (bbox-cropped, 256px).
    Returns (parts dict, composite 0..1, drift 0..100)."""
    c = subject_crop(cand_im).resize((256, 256), Image.BILINEAR)
    r = subject_crop(ref_im).resize((256, 256), Image.BILINEAR)
    ca, ra = np.asarray(c), np.asarray(r)
    cg, rg = ca.mean(axis=2), ra.mean(axis=2)
    parts = {
        "dhash": _hamming_sim(_dhash(cg), _dhash(rg)),
        "phash": _hamming_sim(_phash(cg), _phash(rg)),
        "ssim_global": _global_ssim(cg, rg),
        "color_histogram": _hist_sim(ca, ra),
    }
    composite = float(np.mean(list(parts.values())))
    return ({k: round(v, 3) for k, v in parts.items()},
            round(composite, 3), round((1 - composite) * 100, 1))


def reference_regions(im):
    """The full reference plus overlapping regions, so a candidate can
    match the panel of a sheet it actually came from."""
    im = im.convert("RGB")
    w, h = im.size
    out = {"full": im,
           "center": im.crop((int(w * .2), int(h * .2), int(w * .8), int(h * .8))),
           "left": im.crop((0, 0, int(w * .55), h)),
           "right": im.crop((int(w * .45), 0, w, h)),
           "top": im.crop((0, 0, w, int(h * .55))),
           "bottom": im.crop((0, int(h * .45), w, h))}
    for i, (fx, fy) in enumerate([(0, 0), (.45, 0), (0, .45), (.45, .45)]):
        out[f"quadrant_{i + 1}"] = im.crop(
            (int(w * fx), int(h * fy), int(w * (fx + .55)), int(h * (fy + .55))))
    return out


def best_region_similarity(cand_im, ref_im):
    full_parts, full_comp, full_drift = pair_similarity(cand_im, ref_im)
    best = {"region": "full", "parts": full_parts,
            "composite": full_comp, "drift_score": full_drift}
    for name, crop in reference_regions(ref_im).items():
        if name == "full":
            continue
        parts, comp, drift = pair_similarity(cand_im, crop)
        if comp > best["composite"]:
            best = {"region": name, "parts": parts,
                    "composite": comp, "drift_score": drift}
    return {"full_frame": {"parts": full_parts, "composite": full_comp,
                           "drift_score": full_drift},
            "best_region": best}


def frame_dhash(im):
    gray = np.asarray(im.convert("RGB")).mean(axis=2)
    return _dhash(gray)


# --------------------------------------------------------------------------
# OCR (optional; honest about its absence).
# --------------------------------------------------------------------------
def ocr_status():
    cmd = os.environ.get("DRIFTCHECK_OCR_CMD") or shutil.which("tesseract")
    return cmd


def run_ocr(im):
    cmd = ocr_status()
    if not cmd:
        return {"status": "unavailable",
                "detail": "No OCR engine on this host (tesseract not installed). "
                          "Text in the candidate is NOT verified by this component; "
                          "the emblem's geometry is covered by the proportion report."}
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
            subject_crop(im).save(tf.name)
            path = tf.name
        out = subprocess.run([cmd, path, "stdout", "--psm", "11"],
                             capture_output=True, text=True, timeout=60)
        text = re.sub(r"\s+", " ", out.stdout or "").strip()
        return {"status": "ok", "engine": os.path.basename(cmd),
                "text_found": text[:500]}
    except Exception as exc:
        return {"status": "error",
                "detail": f"OCR failed: {type(exc).__name__}: {exc}"}
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass


# --------------------------------------------------------------------------
# Check logic.
# --------------------------------------------------------------------------
def verdict_for(drift):
    if drift <= DRIFT_PASS_MAX:
        return "pass"
    if drift <= DRIFT_WARN_MAX:
        return "warn"
    return "fail"


_VERDICT_RANK = {"pass": 0, "warn": 1, "fail": 2}


def check_image(cand_im, ref_im, expected_text=None):
    sim = best_region_similarity(cand_im, ref_im)
    sim_drift = sim["best_region"]["drift_score"]

    cand_share = bbox_share(cand_im)
    ref_share = bbox_share(ref_im)
    prop = {"candidate": cand_share, "reference": ref_share}
    prop_flag = False
    prop_penalty = None
    if cand_share and ref_share:
        dw = abs(cand_share["width_pct"] - ref_share["width_pct"])
        dh = abs(cand_share["height_pct"] - ref_share["height_pct"])
        prop["divergence_points"] = {"width": round(dw, 1), "height": round(dh, 1)}
        prop_flag = dw > PROP_FLAG_POINTS or dh > PROP_FLAG_POINTS
        prop["flag"] = ("subject scale diverges from the reference by more than "
                        f"{PROP_FLAG_POINTS:.0f} points (width {dw:.1f}, height {dh:.1f})"
                        if prop_flag else None)
        prop_penalty = min(100.0, 2.0 * max(dw, dh))
        prop["penalty"] = round(prop_penalty, 1)
    else:
        prop["flag"] = None
        prop["detail"] = "Foreground could not be isolated on one of the images; share comparison skipped."
    if prop_penalty is not None:
        drift = round(0.7 * sim_drift + 0.3 * prop_penalty, 1)
    else:
        drift = sim_drift
    verdict = verdict_for(drift)
    if prop_flag:
        verdict = max(verdict, "warn", key=lambda v: _VERDICT_RANK[v])

    ocr = run_ocr(cand_im)
    text_check = {"ocr": ocr}
    if expected_text:
        text_check["expected_text"] = expected_text
        if ocr.get("status") == "ok":
            found = ocr.get("text_found", "")
            hit = expected_text.lower() in found.lower()
            text_check["expected_found"] = hit
            if not hit:
                text_check["flag"] = "expected text not found in the candidate"
                verdict = max(verdict, "warn", key=lambda v: _VERDICT_RANK[v])
        else:
            text_check["expected_found"] = None
            text_check["flag"] = None

    notes = [
        "Headline drift_score = 0.7 x similarity drift + 0.3 x proportion penalty "
        "(penalty = min(100, 2 x the largest bounding-box share divergence in points)); "
        "both inputs are reported separately, and the verdict also escalates on a "
        "proportion flag or a missing expected text.",
        "Similarity grades the subject art (bounding-box cropped) with classical "
        "metrics (dhash, phash, global SSIM, color histogram) - no learned embedding.",
        "A model sheet is a collage of panels: the best-matching reference region "
        "is reported alongside the full-frame score, and the similarity grade uses the best region.",
        "Identity limit, measured in calibration: against a multi-panel model sheet "
        "these metrics cannot confirm WHICH character is drawn (a wrong character "
        "graded about the same as the right one). For identity-grade gating, pass the "
        "approved same-class comp (the locked design or start still) as the reference; "
        "against a sheet, the discriminating evidence is the proportion report, the "
        "color_histogram part, and the text check.",
        "Proportion compares bounding-box share of frame; it assumes candidate and "
        "reference are the same framing class (sticker vs sticker, scene vs scene). "
        "Against a model sheet, whose foreground saturates the frame, it reads as "
        "'how much smaller is the candidate's art than the sheet's coverage' - which "
        "is exactly the oversized/undersized emblem signal it was built to catch.",
    ]
    if ocr.get("status") != "ok":
        notes.append("OCR is unavailable on this deployment, so lettering inside the "
                     "art is not machine-read here; run the native-resolution zoom "
                     "audit before shipping anything the OCR component could not read.")
    return {"drift_score": drift, "verdict": verdict,
            "score_composition": {
                "similarity_drift": sim_drift,
                "proportion_penalty": (round(prop_penalty, 1)
                                       if prop_penalty is not None else None),
                "formula": "0.7 x similarity drift + 0.3 x proportion penalty "
                           "(similarity alone when no share could be measured)"},
            "similarity": sim, "proportion": prop, "text_check": text_check,
            "notes": notes}


def probe_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", path],
        capture_output=True, text=True, timeout=30)
    return float(out.stdout.strip())


def extract_frame(video_path, at_seconds, out_path):
    subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{at_seconds:.2f}", "-i", video_path,
         "-frames:v", "1", "-vf", "scale='min(512,iw)':-2", "-y", out_path],
        capture_output=True, text=True, timeout=60, check=True)


def check_video(video_path, ref_im, n_frames=DEFAULT_FRAMES):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        return None, (503, {"error": "engine_not_configured",
                            "detail": "ffmpeg/ffprobe are not installed on this deployment, so /check-video cannot run."})
    try:
        duration = probe_duration(video_path)
    except Exception as exc:
        return None, (422, {"error": "unreadable_video",
                            "detail": f"ffprobe could not read the video: {type(exc).__name__}: {exc}"})
    if duration <= 0:
        return None, (422, {"error": "unreadable_video",
                            "detail": "The video reports a zero duration."})
    if duration > MAX_VIDEO_SECONDS:
        return None, (422, {"error": "video_too_long",
                            "detail": f"Video is {duration:.0f}s; the per-request maximum is {MAX_VIDEO_SECONDS}s."})
    n = max(3, min(int(n_frames or DEFAULT_FRAMES), MAX_FRAMES))
    times = [duration * (i + 0.5) / n for i in range(n)]
    frames = []
    prev_hash = None
    frozen_run = 0
    frozen_spans = []
    run_start = None
    with tempfile.TemporaryDirectory() as td:
        for i, t in enumerate(times):
            fp = os.path.join(td, f"f{i}.png")
            try:
                extract_frame(video_path, t, fp)
                im = Image.open(fp).copy()
            except Exception as exc:
                return None, (422, {"error": "unreadable_video",
                                    "detail": f"ffmpeg could not extract a frame at {t:.1f}s: {type(exc).__name__}"})
            parts, comp, drift = pair_similarity(im, ref_im)
            h = frame_dhash(im)
            frozen_with_prev = None
            if prev_hash is not None:
                frozen_with_prev = _hamming_sim(h, prev_hash) >= FROZEN_SIM
            if frozen_with_prev:
                if frozen_run == 0:
                    run_start = times[i - 1]
                frozen_run += 1
            else:
                if frozen_run >= 2:
                    frozen_spans.append({"from_s": round(run_start, 2),
                                         "to_s": round(times[i - 1], 2)})
                frozen_run = 0
                run_start = None
            prev_hash = h
            frames.append({"index": i, "at_s": round(t, 2), "drift_score": drift,
                           "similarity": comp, "parts": parts,
                           "near_identical_to_previous": frozen_with_prev})
        if frozen_run >= 2 and run_start is not None:
            frozen_spans.append({"from_s": round(run_start, 2),
                                 "to_s": round(times[-1], 2)})
    drifts = [f["drift_score"] for f in frames]
    worst = sorted(frames, key=lambda f: f["drift_score"], reverse=True)[:3]
    mean_drift = round(float(np.mean(drifts)), 1)
    max_drift = round(float(np.max(drifts)), 1)
    verdict = verdict_for(max_drift)
    if frozen_spans:
        verdict = max(verdict, "warn", key=lambda v: _VERDICT_RANK[v])
    result = {"duration_s": round(duration, 2), "frames_sampled": n,
              "drift_score": max_drift, "mean_drift_score": mean_drift,
              "verdict": verdict,
              "frames": frames,
              "worst_frames": [{"index": f["index"], "at_s": f["at_s"],
                                "drift_score": f["drift_score"]} for f in worst],
              "frozen_spans": frozen_spans,
              "frozen_flag": ("near-identical consecutive sampled frames over "
                              f"{len(frozen_spans)} span(s): the clip holds a still "
                              "instead of staying in motion" if frozen_spans else None),
              "notes": [
                  "Video drift_score is the worst sampled frame's similarity drift "
                  "(no proportion term: frames and the reference still are the same "
                  "framing class by construction).",
                  "Each sampled frame is graded against the reference with the same "
                  "subject-crop metrics as /check-image; the verdict rides on the worst frame.",
                  f"Frozen detection compares difference hashes of consecutive sampled "
                  f"frames (similarity >= {FROZEN_SIM}); fine motion smaller than the "
                  "sampling interval can be missed - sample more frames for short clips.",
              ]}
    return result, None


# --------------------------------------------------------------------------
# Request input handling: multipart uploads, or JSON with URLs / base64.
# --------------------------------------------------------------------------
def parse_multipart(body, content_type):
    m = re.search(r"boundary=(.+)", content_type or "")
    if not m:
        raise ValueError("multipart boundary missing")
    boundary = m.group(1).strip().strip('"').encode()
    fields, files = {}, {}
    for part in body.split(b"--" + boundary):
        part = part.strip(b"\r\n")
        if not part or part == b"--":
            continue
        if part.endswith(b"--"):
            part = part[:-2].rstrip(b"\r\n")
        head, _, data = part.partition(b"\r\n\r\n")
        if not _:
            continue
        head_text = head.decode("utf-8", "replace")
        name_m = re.search(r'name="([^"]+)"', head_text)
        if not name_m:
            continue
        name = name_m.group(1)
        if 'filename="' in head_text:
            files[name] = data
        else:
            fields[name] = data.decode("utf-8", "replace")
    return fields, files


def _decode_image(raw, label):
    if raw is None or len(raw) == 0:
        return None, (422, {"error": "missing_parameter",
                            "detail": f"Provide the {label} image (upload, URL, or base64)."})
    if len(raw) > MAX_IMAGE_BYTES:
        return None, (422, {"error": "file_too_large",
                            "detail": f"The {label} image is {len(raw)} bytes; the cap is {MAX_IMAGE_BYTES}."})
    try:
        import io
        im = Image.open(io.BytesIO(raw))
        im.load()
        return im, None
    except Exception:
        return None, (422, {"error": "unreadable_image",
                            "detail": f"The {label} file is not a readable image."})


def _gather(fields, files, kind):
    """kind: 'candidate' | 'reference' | 'video'. Returns raw bytes or an error."""
    import base64
    if kind in files and files[kind]:
        return files[kind], None
    url = (fields.get(f"{kind}_url") or "").strip()
    if url:
        try:
            cap = MAX_VIDEO_BYTES if kind == "video" else MAX_IMAGE_BYTES
            return fetch_bytes(url, cap), None
        except ValueError as exc:
            return None, (422, {"error": "fetch_refused", "detail": str(exc)})
        except Exception as exc:
            return None, (502, {"error": "fetch_failed",
                                "detail": f"Could not fetch {kind}_url: {type(exc).__name__}: {exc}"})
    b64 = fields.get(f"{kind}_base64")
    if b64:
        try:
            return base64.b64decode(b64, validate=False), None
        except Exception:
            return None, (422, {"error": "invalid_body",
                                "detail": f"{kind}_base64 is not valid base64."})
    return None, (422, {"error": "missing_parameter",
                        "detail": f"Provide the {kind} as an upload, {kind}_url, or {kind}_base64."})


# --------------------------------------------------------------------------
# Health.
# --------------------------------------------------------------------------
def health():
    return 200, {"status": "ok", "service": SERVICE, "version": VERSION,
                 "build": BUILD,
                 "methods": {
                     "similarity": "subject-crop dhash + phash (DCT) + global SSIM + color histogram, full-frame and best reference region",
                     "proportion": "foreground bounding-box share of frame (alpha channel, or corner-background distance)",
                     "ocr": "available" if ocr_status() else "unavailable on this deployment (no tesseract binary); reported honestly per response",
                     "video": "ffmpeg frame sampling" if shutil.which("ffmpeg") else "unavailable (no ffmpeg)",
                     "anatomy": "not included in v1: no lightweight pose estimator deploys on this tier, so the check is omitted rather than approximated",
                 },
                 "limits": {"max_image_bytes": MAX_IMAGE_BYTES,
                            "max_video_bytes": MAX_VIDEO_BYTES,
                            "max_video_seconds": MAX_VIDEO_SECONDS,
                            "max_frames_per_video": MAX_FRAMES,
                            "drift_bands": {"pass_at_or_below": DRIFT_PASS_MAX,
                                            "warn_at_or_below": DRIFT_WARN_MAX},
                            "proportion_flag_points": PROP_FLAG_POINTS},
                 "endpoints": ["POST /check-image", "POST /check-video", "GET /health"],
                 "recent_requests": RECENT[-5:],
                 "note": "Classical-metric triage for generated-media drift: catch the wrong emblem, the wrong scale, and the frozen clip before the next regeneration credit is spent. Not a substitute for a final human review."}


# --------------------------------------------------------------------------
# Server: scaffold conventions (gate + structured errors), POST bodies.
# --------------------------------------------------------------------------
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
            if path not in ("/check-image", "/check-video"):
                return self._json(404, {"error": "not_found",
                                        "detail": f"No endpoint at {path}. See /health for service info."})
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = 0
            if length <= 0 or length > MAX_BODY:
                return self._json(422, {"error": "invalid_body",
                                        "detail": f"Send a multipart or JSON body of at most {MAX_BODY} bytes."})
            raw = self.rfile.read(length)
            ctype = self.headers.get("Content-Type", "")
            started = time.time()
            try:
                if ctype.startswith("multipart/form-data"):
                    fields, files = parse_multipart(raw, ctype)
                elif "json" in ctype:
                    body = json.loads(raw.decode("utf-8"))
                    if not isinstance(body, dict):
                        raise ValueError("body must be a JSON object")
                    fields = {k: (v if isinstance(v, str) else json.dumps(v))
                              for k, v in body.items()}
                    files = {}
                else:
                    return self._json(422, {"error": "invalid_body",
                                            "detail": "Content-Type must be multipart/form-data or application/json."})
            except ValueError as exc:
                return self._json(422, {"error": "invalid_body", "detail": str(exc)})
            except Exception:
                return self._json(422, {"error": "invalid_body",
                                        "detail": "Request body could not be parsed."})

            ref_raw, err = _gather(fields, files, "reference")
            if err:
                return self._record(path, err, started)
            ref_im, err = _decode_image(ref_raw, "reference")
            if err:
                return self._record(path, err, started)

            if path == "/check-image":
                cand_raw, err = _gather(fields, files, "candidate")
                if err:
                    return self._record(path, err, started)
                cand_im, err = _decode_image(cand_raw, "candidate")
                if err:
                    return self._record(path, err, started)
                try:
                    result = check_image(cand_im, ref_im,
                                         expected_text=(fields.get("expected_text") or None))
                except Exception as exc:
                    return self._record(path, (502, {"error": "check_failed",
                                                     "detail": f"{type(exc).__name__}: {exc}"}), started)
                return self._ok(path, result, started)

            # /check-video
            vid_raw, err = _gather(fields, files, "video")
            if err:
                return self._record(path, err, started)
            if len(vid_raw) > MAX_VIDEO_BYTES:
                return self._record(path, (422, {"error": "file_too_large",
                                                 "detail": f"The video is {len(vid_raw)} bytes; the cap is {MAX_VIDEO_BYTES}."}), started)
            try:
                n_frames = int(fields.get("frames") or DEFAULT_FRAMES)
            except ValueError:
                n_frames = DEFAULT_FRAMES
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
                tf.write(vid_raw)
                vpath = tf.name
            try:
                result, err = check_video(vpath, ref_im, n_frames)
            finally:
                try:
                    os.unlink(vpath)
                except Exception:
                    pass
            if err:
                return self._record(path, err, started)
            return self._ok(path, result, started)

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
                           "verdict": result.get("verdict"),
                           "drift_score": result.get("drift_score")})
            del RECENT[:-10]
            result = dict(result)
            result["_meta"] = {"service": SERVICE, "version": VERSION,
                               "latency_ms": round((time.time() - started) * 1000)}
            return self._json(200, result)

    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    run_server(int(os.environ.get("PORT", "8113")))
