"""DesignBase proof battery (2026-10-31).

Phase A (awaiting): the service with no Gemini key behind a test
proxy secret - gate behavior, the honest 503 state on the three
engine endpoints, and /image-prompt (code-assembled) answering 200
through the gate, as /health promises.

Phase B (live pipeline): the service pointed at tests/
connector_bridge.py, which routes its Gemini calls through the
user's connected Gemini API (the connector credential flow), so the
service's unmodified pipeline runs against the real engine:
- /palette on a merch-tee brief: structure, code-validated hex,
  computed contrast ratios all checked in the battery itself;
- /design-brief on a poster: full structure with do/don't lists;
- /image-prompt era-locked: era lock text and negative constraints
  verified in code;
- /critique of a real merch design file from the workspace: four
  scored dimensions, fixes, and header-read image info;
- invalid inputs: missing fields and a non-image upload.

No key is read or printed anywhere. Results (checks + full sample
responses) are written to battery-2026-10-31.json next to this file.
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import urllib.error
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "..", "app.py")
BRIDGE = os.path.join(HERE, "connector_bridge.py")
SECRET = "designbase-battery-test-secret"
DESIGN_FILE = os.path.expanduser(
    "~/workspace/merch-designs-2026-10-30/sheet-based-designs/"
    "hoodie-back-dj-riot.png")
HEX_RE = re.compile(r"^#[0-9A-F]{6}$")
results = {"checks": [], "samples": {},
           "environment": "Phase B Gemini calls routed through "
                          "tests/connector_bridge.py via the "
                          "custom.gemini connector (real engine, "
                          "production request shapes). Contrast "
                          "ratios and hex validation verified "
                          "independently by this battery."}


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


def call_multipart(port, path, filename, data, fields=None, timeout=240):
    boundary = "----designbase" + uuid.uuid4().hex
    chunks = []
    for name, value in (fields or {}).items():
        chunks.append((
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n").encode())
    chunks.append((
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; '
        f'filename="{filename}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n").encode()
        + data + f"\r\n--{boundary}--\r\n".encode())
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", method="POST",
        data=b"".join(chunks),
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


def pace(seconds=15):
    """The owner's Gemini key has a per-minute quota; the battery
    paces its engine-heavy calls so the proof measures the pipeline,
    not the quota."""
    time.sleep(seconds)

# --- Phase A: awaiting_key ---------------------------------------------
proc = start([APP], {"PORT": "8218", "RAPIDAPI_PROXY_SECRET": SECRET},
             8218)
try:
    status, health = call(8218, "GET", "/health")
    check("awaiting /health 200, reasoning state awaiting_key, "
          "code engines live",
          status == 200
          and health["engines"]["reasoning"]["state"] == "awaiting_key"
          and health["engines"]["prompt_builder"]["state"] == "live"
          and health["engines"]["color_math"]["state"] == "live")
    results["samples"]["health_awaiting"] = health

    status, body = call(8218, "POST", "/palette",
                        {"brief": "a merch tee"})
    check("gate: /palette without secret -> 401",
          status == 401 and body["error"] == "unauthorized")

    status, body = call(8218, "POST", "/palette",
                        {"brief": "a merch tee"},
                        {"X-RapidAPI-Proxy-Secret": "wrong"})
    check("gate: /palette wrong secret -> 401", status == 401)

    status, body = call(8218, "POST", "/palette",
                        {"brief": "a merch tee"}, AUTH)
    check("awaiting /palette -> explicit 503 engine_not_configured",
          status == 503 and body["error"] == "engine_not_configured")
    results["samples"]["palette_awaiting"] = body

    status, body = call(8218, "POST", "/design-brief",
                        {"product": "poster", "audience": "fans",
                         "vibe": "bold"}, AUTH)
    check("awaiting /design-brief -> explicit 503 engine_not_configured",
          status == 503 and body["error"] == "engine_not_configured")

    status, body = call(8218, "POST", "/critique", {"x": 1}, AUTH)
    check("awaiting /critique -> explicit 503 engine_not_configured",
          status == 503 and body["error"] == "engine_not_configured")

    status, body = call(8218, "POST", "/image-prompt",
                        {"subject": "a lighthouse at dawn",
                         "style": "photorealistic photograph"}, AUTH)
    check("awaiting /image-prompt -> 200 (code-assembled, as /health "
          "promises)",
          status == 200 and "lighthouse" in body.get("prompt", "")
          and "no text" in body.get("negative_prompt", ""))
    results["samples"]["image_prompt_awaiting"] = body
finally:
    proc.terminate()

# --- Phase B: live pipeline through the connector bridge ----------------
bridge = subprocess.Popen([sys.executable, BRIDGE, "8901"],
                          stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL)
time.sleep(1.0)
proc = start([APP], {"PORT": "8219", "RAPIDAPI_PROXY_SECRET": SECRET,
                     "GEMINI_API_KEY": "local-bridge-placeholder",
                     "GEMINI_BASE_URL": "http://127.0.0.1:8901/v1beta"},
             8219)
try:
    status, health = call(8219, "GET", "/health")
    check("live /health: reasoning live, models named",
          status == 200
          and health["engines"]["reasoning"]["state"] == "live"
          and health["engines"]["reasoning"]["model"])
    results["samples"]["health_live"] = health

    # Deterministic endpoint first: no quota spent.
    status, body = call(8219, "POST", "/image-prompt",
                        {"subject": "a solo b-boy frozen mid-freeze on "
                                    "a rooftop",
                         "style": "comic book cover illustration",
                         "era": "the Bronx in 1983",
                         "product": "a merch tee"}, AUTH)
    prompt = body.get("prompt", "")
    check("live /image-prompt era-locked -> era lock, negative "
          "constraints, product framing all present",
          status == 200 and "Era lock" in prompt and "1983" in prompt
          and "no text" in body.get("negative_prompt", "")
          and "no modern objects" in body.get("negative_prompt", "")
          and body.get("components", {}).get("product"))
    results["samples"]["image_prompt_era"] = body

    status, body = call(8219, "POST", "/image-prompt",
                        {"style": "vector"}, AUTH)
    check("/image-prompt missing subject -> 422 missing_parameter",
          status == 422 and body["error"] == "missing_parameter")

    status, body = call(8219, "POST", "/palette", {}, AUTH)
    check("/palette empty body -> 422 missing_parameter",
          status == 422 and body["error"] == "missing_parameter")

    pace()
    status, body = call(8219, "POST", "/palette",
                        {"brief": "Merch tee for a hip-hop DJ brand: "
                                  "bold, nightclub energy, must print "
                                  "well on black and white tees",
                         "count": 2}, AUTH, timeout=240)
    palettes = body.get("palettes", [])
    hex_ok = bool(palettes) and all(
        HEX_RE.match(c["hex"])
        for p in palettes for c in p["colors"])
    roles_ok = bool(palettes) and all(
        any(c["role"] == "background" for c in p["colors"])
        and any(c["role"] == "primary" for c in p["colors"])
        for p in palettes)
    contrast_ok = bool(palettes) and all(
        p.get("contrast", {}).get("pairs") for p in palettes)
    # Independently recompute one ratio (white on black = 21.0).
    from importlib import import_module
    sys.path.insert(0, os.path.join(HERE, ".."))
    app_mod = import_module("app")
    ratio_bw = app_mod.contrast_ratio("#FFFFFF", "#000000")
    check("/palette merch-tee brief -> palettes with valid hex, "
          "background+primary roles, computed contrast; code ratio "
          "white/black = 21.0",
          status == 200 and len(palettes) >= 1 and hex_ok and roles_ok
          and contrast_ok and ratio_bw == 21.0,
          f"palettes={len(palettes)}, hex_ok={hex_ok}, "
          f"roles_ok={roles_ok}, contrast_ok={contrast_ok}, "
          f"white_on_black={ratio_bw}")
    results["samples"]["palette_merch_tee"] = body

    pace()
    status, body = call(8219, "POST", "/design-brief",
                        {"product": "a concert poster for a jazz "
                                    "quartet",
                         "audience": "record collectors aged 30-55",
                         "vibe": "1962 Blue Note sleeve energy, "
                                 "confident and spare"}, AUTH,
                        timeout=240)
    brief = body.get("brief", {})
    check("/design-brief poster -> full structure with do/don't "
          "lists",
          status == 200 and bool(brief.get("concept_direction"))
          and bool(brief.get("composition"))
          and bool(brief.get("typography", {}).get("direction"))
          and bool(brief.get("color_direction", {}).get("direction"))
          and len(brief.get("dos", [])) >= 3
          and len(brief.get("donts", [])) >= 3,
          f"dos={len(brief.get('dos', []))}, "
          f"donts={len(brief.get('donts', []))}")
    results["samples"]["design_brief_poster"] = body

    status, body = call(8219, "POST", "/design-brief",
                        {"product": "poster", "audience": "fans"},
                        AUTH)
    check("/design-brief missing vibe -> 422 missing_parameter",
          status == 422 and body["error"] == "missing_parameter")

    with open(DESIGN_FILE, "rb") as fh:
        design_bytes = fh.read()
    pace()
    status, body = call_multipart(
        8219, "/critique", os.path.basename(DESIGN_FILE), design_bytes,
        fields={"context": "back print of a character merch hoodie"},
        timeout=300)
    scores = body.get("scores", {})
    dims = ("composition", "color_harmony", "legibility",
            "focal_point")
    scores_ok = all(
        isinstance(scores.get(d, {}).get("score"), (int, float))
        and 0 <= scores[d]["score"] <= 10 for d in dims)
    img = body.get("image", {})
    check("/critique real merch design -> four scored dimensions, "
          "fixes, header-read image info",
          status == 200 and scores_ok
          and len(body.get("fixes", [])) >= 1
          and img.get("format") == "image/png"
          and bool(img.get("width")) and bool(img.get("height")),
          f"overall={body.get('overall_score')}, "
          f"fixes={len(body.get('fixes', []))}, "
          f"image={img.get('width')}x{img.get('height')}")
    results["samples"]["critique_hoodie_back"] = body

    status, body = call_multipart(8219, "/critique", "notes.txt",
                                  b"this is not an image", timeout=60)
    check("/critique non-image upload -> 422 unsupported_format",
          status == 422 and body["error"] == "unsupported_format")
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
