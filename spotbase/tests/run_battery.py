"""SpotBase proof battery: boots the real server and calls every
endpoint over HTTP, saving the raw outputs as proof JSON.

Usage: python3 run_battery.py <base_url> <out_file> [proxy_secret]
The server itself is started by the caller (local) or already
running (deployed). With a proxy_secret argument, gated calls
carry the header and one call without it is recorded (expect 401).
"""
import json
import sys
import urllib.request
import urllib.error

BASE = sys.argv[1].rstrip("/")
OUT = sys.argv[2]
SECRET = sys.argv[3] if len(sys.argv) > 3 else ""

BRIEF_30 = {
    "brand_name": "Peak Roast Coffee",
    "product": "Peak Roast cold brew coffee, ready to drink",
    "audience": "commuters who need real energy without the coffee shop line",
    "offer": "your first case ships free this month",
    "call_to_action": "Order yours today",
    "website": "peakroast.example.com",
    "tone": "bold",
    "duration_seconds": 30,
}
BRIEF_15 = {
    "brand_name": "Brightpath Tutoring",
    "product": "Brightpath one-on-one online math tutoring for grades 6 to 12",
    "audience": "parents who want their kids confident in math",
    "offer": "the first session is free",
    "call_to_action": "Book the free session",
    "website": "brightpath.example.com",
    "tone": "trustworthy",
    "duration_seconds": 15,
}
SPEC_PASS = {
    "duration_seconds": 30, "width": 1920, "height": 1080, "format": "mp4",
    "frame_rate": 29.97, "constant_frame_rate": True, "bitrate_kbps": 20000,
    "file_size_mb": 62, "audio_channels": 2, "sample_rate_hz": 48000,
    "audio_bitrate_kbps": 256, "loudness_lufs": -24.1, "true_peak_dbtp": -2.4,
}
SPEC_FAIL = {
    "duration_seconds": 34, "width": 854, "height": 480, "format": "webm",
    "frame_rate": 24, "constant_frame_rate": False, "bitrate_kbps": 900,
    "file_size_mb": 140, "audio_channels": 1, "sample_rate_hz": 44100,
    "audio_bitrate_kbps": 96, "loudness_lufs": -15.5, "true_peak_dbtp": -0.4,
}


def call(method, path, body=None, secret=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    if secret:
        req.add_header("X-RapidAPI-Proxy-Secret", secret)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def main():
    results = {}
    results["health"] = call("GET", "/health")
    results["tones"] = call("GET", "/tones", secret=SECRET or None)
    results["delivery_spec"] = call("GET", "/delivery-spec", secret=SECRET or None)
    results["ad_package_30s"] = call("POST", "/ad-package", BRIEF_30, SECRET or None)
    results["ad_package_15s"] = call("POST", "/ad-package", BRIEF_15, SECRET or None)
    results["script_only"] = call("POST", "/script", BRIEF_30, SECRET or None)
    results["shots_only"] = call("POST", "/shots", BRIEF_15, SECRET or None)
    results["check_spec_pass"] = call("POST", "/check-spec", SPEC_PASS, SECRET or None)
    results["check_spec_fail"] = call("POST", "/check-spec", SPEC_FAIL, SECRET or None)
    results["check_spec_partial"] = call("POST", "/check-spec",
                                         {"duration_seconds": 15, "width": 1280, "height": 720},
                                         SECRET or None)
    results["error_missing_brand"] = call("POST", "/ad-package",
                                          {"product": "x"}, SECRET or None)
    results["error_bad_duration"] = call("POST", "/ad-package",
                                         {"brand_name": "x", "product": "y",
                                          "duration_seconds": 45}, SECRET or None)
    results["error_bad_tone"] = call("POST", "/ad-package",
                                     {"brand_name": "x", "product": "y", "tone": "loud"},
                                     SECRET or None)
    results["not_found"] = call("GET", "/nope", secret=SECRET or None)
    if SECRET:
        results["gate_without_secret"] = call("GET", "/tones")
    summary = {k: v[0] for k, v in results.items()}
    with open(OUT, "w") as f:
        json.dump({"base_url": BASE, "status_summary": summary, "results":
                   {k: {"status": v[0], "body": v[1]} for k, v in results.items()}},
                  f, indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
