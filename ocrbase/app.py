"""OCRBase - print-first OCR (RapidAPI lane, wave 5).

Spec: ~/workspace/rapidapi-competitors/docs/spec-ocrbase.md

Honest scope: print and typed documents plus clean scans only.
Handwriting is NOT supported and is never implied. The engine is
Tesseract 5 (Apache 2.0) run as a subprocess; no key, no per-call
cost, no third-party data leaves this server.

Endpoints:
  POST /extract    image upload (multipart field "file"), or JSON
                   {"url": "..."} or {"image_base64": "..."};
                   optional "lang" (default "eng") and reserved
                   "pdf_page" (ignored at launch except page 1).
                   Formats: PNG, JPEG, TIFF, WEBP; PDF first page.
  GET  /languages  tessdata packs actually installed on this host.
  GET  /health     status, engine + version, languages, limits.

Server conventions follow the fleet scaffold (driftcheck pattern):
stdlib http.server only, RAPIDAPI_PROXY_SECRET gate (401 JSON
without the X-RapidAPI-Proxy-Secret header, /health always open),
structured JSON errors for every failure, never a bare 500.

Run: python3 app.py (PORT env, default 8118).
Needs: tesseract binary on PATH; pdftoppm (poppler-utils) for PDF.
"""
import base64
import csv
import io
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

SERVICE = "ocrbase"
VERSION = "1.0.0"
BUILD = "2026-11-01-v1"
RECENT = []

MAX_FILE_BYTES = 10_000_000       # 10 MB cap (spec)
MAX_BODY = 20_000_000             # whole request body cap (base64 headroom)
FETCH_TIMEOUT = 15                # seconds (spec)
FETCH_CAP = MAX_FILE_BYTES
LOW_CONF_THRESHOLD = 60.0
UA = "Mozilla/5.0 (compatible; OCRBaseBot/1.0; +https://rapidapi.com/YamilLittle/api/ocrbase)"

SUPPORTED_IMAGE_FORMATS = ("png", "jpeg", "tiff", "webp")

# ---------------------------------------------------------------------------
# Engine discovery (cached at startup)
# ---------------------------------------------------------------------------

def _detect_engine_version():
    exe = shutil.which("tesseract")
    if not exe:
        return None, None
    try:
        out = subprocess.run([exe, "--version"], capture_output=True,
                             text=True, timeout=15)
        first = (out.stdout or out.stderr or "").splitlines()[0].strip()
        m = re.search(r"(\d+\.\d+(?:\.\d+)?)", first)
        return exe, (m.group(1) if m else first)
    except Exception:
        return exe, None


def _detect_languages(exe):
    if not exe:
        return []
    try:
        out = subprocess.run([exe, "--list-langs"], capture_output=True,
                             text=True, timeout=15)
        langs = []
        for line in (out.stdout or "").splitlines():
            line = line.strip()
            # First line is "List of available languages ..." header.
            if line and re.fullmatch(r"[a-zA-Z0-9_]+", line):
                langs.append(line)
        return sorted(langs)
    except Exception:
        return []


TESSERACT_EXE, ENGINE_VERSION = _detect_engine_version()
INSTALLED_LANGUAGES = _detect_languages(TESSERACT_EXE)
PDFTOPPM_EXE = shutil.which("pdftoppm")

# ---------------------------------------------------------------------------
# Fetching (SSRF-hardened; mirrors cleanextract's explicit CIDR approach).
#
# Deliberately NOT Python's ipaddress is_private flag, which also rejects
# the RFC 2544 benchmarking range (198.18.0.0/15) that some sandboxed
# resolvers legitimately return for public hosts. Explicit nets only.
# ---------------------------------------------------------------------------
_BLOCKED_NETS = [ipaddress.ip_network(n) for n in (
    "0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8",
    "169.254.0.0/16", "172.16.0.0/12", "192.168.0.0/16", "224.0.0.0/4",
    "::1/128", "fc00::/7", "fe80::/10", "ff00::/8")]


class SSRFBlocked(ValueError):
    pass


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
            raise SSRFBlocked("redirect to a non-http(s) address refused")
        if not _host_is_public(parsed.hostname):
            raise SSRFBlocked("redirect to a non-public address refused")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_GuardedRedirect)


def fetch_bytes(url):
    """Returns raw bytes, or raises SSRFBlocked / ValueError / Exception."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("url must be an absolute http or https URL")
    if not _host_is_public(parsed.hostname):
        raise SSRFBlocked("only public web addresses can be fetched")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with _OPENER.open(req, timeout=FETCH_TIMEOUT) as resp:
        raw = resp.read(FETCH_CAP + 1)
    if len(raw) > FETCH_CAP:
        raise ValueError(f"remote file exceeds the {FETCH_CAP} byte cap")
    return raw


# ---------------------------------------------------------------------------
# Format detection (magic bytes; filename/Content-Type are not trusted)
# ---------------------------------------------------------------------------

def detect_format(raw):
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if raw[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if raw[:4] in (b"II*\x00", b"MM\x00*"):
        return "tiff"
    if len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "webp"
    if raw[:5] == b"%PDF-":
        return "pdf"
    return None


_EXT = {"png": ".png", "jpeg": ".jpg", "tiff": ".tiff", "webp": ".webp",
        "pdf": ".pdf"}


# ---------------------------------------------------------------------------
# OCR core
# ---------------------------------------------------------------------------

def _pdf_first_page_to_png(pdf_path, workdir):
    """Returns png path or an error tuple (status, payload)."""
    if not PDFTOPPM_EXE:
        return None, (422, {"error": "pdf_support_unavailable",
                            "detail": "PDF input was received but pdftoppm "
                                      "(poppler-utils) is not available on "
                                      "this deployment, so PDF cannot be "
                                      "processed. Send a PNG/JPEG/TIFF/WEBP "
                                      "image instead."})
    prefix = os.path.join(workdir, "page")
    try:
        proc = subprocess.run(
            [PDFTOPPM_EXE, "-png", "-r", "300", "-f", "1", "-l", "1",
             "-singlefile", pdf_path, prefix],
            capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return None, (422, {"error": "pdf_support_unavailable",
                            "detail": "pdftoppm timed out rendering the PDF first page."})
    png_path = prefix + ".png"
    if proc.returncode != 0 or not os.path.exists(png_path):
        return None, (422, {"error": "unreadable_file",
                            "detail": "pdftoppm could not render the PDF first page: "
                                      + (proc.stderr or "").strip()[:300]})
    return png_path, None


def run_tesseract(image_path, lang):
    """Run tesseract with TSV output. Returns (words, blocks) or raises."""
    env = dict(os.environ)
    env["OMP_THREAD_LIMIT"] = "1"
    with tempfile.TemporaryDirectory() as td:
        outbase = os.path.join(td, "ocr")
        proc = subprocess.run(
            [TESSERACT_EXE, image_path, outbase, "--psm", "1",
             "-l", lang, "tsv"],
            capture_output=True, text=True, timeout=120, env=env)
        tsv_path = outbase + ".tsv"
        if proc.returncode != 0 or not os.path.exists(tsv_path):
            raise RuntimeError(
                "tesseract failed: " + (proc.stderr or "").strip()[:300])
        with open(tsv_path, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh, delimiter="\t", quoting=csv.QUOTE_NONE))
    words = []
    for row in rows:
        try:
            level = int(row.get("level") or 0)
        except ValueError:
            continue
        if level != 5:
            continue
        text = (row.get("text") or "").strip()
        if not text:
            continue
        try:
            conf = float(row.get("conf"))
        except (TypeError, ValueError):
            conf = -1.0
        try:
            bbox = {"left": int(float(row.get("left") or 0)),
                    "top": int(float(row.get("top") or 0)),
                    "width": int(float(row.get("width") or 0)),
                    "height": int(float(row.get("height") or 0))}
            block_num = int(float(row.get("block_num") or 0))
            line_num = int(float(row.get("line_num") or 0))
            par_num = int(float(row.get("par_num") or 0))
        except ValueError:
            continue
        words.append({"text": text, "conf": round(conf, 2), "bbox": bbox,
                      "block_num": block_num, "line_num": line_num,
                      "_par_num": par_num})
    return words


def words_to_text_and_blocks(words):
    """Rebuild plain text in reading order + a blocks summary."""
    lines = {}   # (block, par, line) -> [word texts]
    order = []
    blocks_map = {}
    for w in words:
        key = (w["block_num"], w["_par_num"], w["line_num"])
        if key not in lines:
            lines[key] = []
            order.append(key)
        lines[key].append(w["text"])
        b = blocks_map.setdefault(w["block_num"],
                                  {"block_num": w["block_num"], "lines": 0,
                                   "words": 0, "text": ""})
        b["words"] += 1
    block_texts = {}
    for key in order:
        line_text = " ".join(lines[key])
        bnum = key[0]
        blocks_map[bnum]["lines"] += 1
        block_texts.setdefault(bnum, []).append(line_text)
    for bnum, lts in block_texts.items():
        blocks_map[bnum]["text"] = "\n".join(lts)
    blocks = [blocks_map[k] for k in sorted(blocks_map)]
    text = "\n\n".join(b["text"] for b in blocks)
    return text, blocks


def extract_ocr(raw, lang):
    """Returns (status, payload)."""
    if not TESSERACT_EXE:
        return 503, {"error": "engine_not_configured",
                     "detail": "tesseract is not installed on this deployment."}
    if lang not in INSTALLED_LANGUAGES:
        return 422, {"error": "unsupported_language",
                     "detail": f"Language '{lang}' is not installed. "
                               f"Installed: {', '.join(INSTALLED_LANGUAGES)}. "
                               "See GET /languages."}
    if len(raw) == 0:
        return 422, {"error": "missing_parameter",
                     "detail": "The supplied file is empty."}
    if len(raw) > MAX_FILE_BYTES:
        return 413, {"error": "file_too_large",
                     "detail": f"File is {len(raw)} bytes; the cap is {MAX_FILE_BYTES} bytes (10 MB)."}
    fmt = detect_format(raw)
    if fmt is None:
        return 415, {"error": "unsupported_format",
                     "detail": "Unrecognized file format. Supported: PNG, JPEG, TIFF, WEBP images and PDF (first page)."}
    started = time.time()
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "input" + _EXT[fmt])
        with open(src, "wb") as fh:
            fh.write(raw)
        image_path = src
        if fmt == "pdf":
            image_path, err = _pdf_first_page_to_png(src, td)
            if err:
                return err
        try:
            words_internal = run_tesseract(image_path, lang)
        except subprocess.TimeoutExpired:
            return 422, {"error": "ocr_timeout",
                         "detail": "tesseract exceeded the 120s processing limit for this page."}
        except Exception as exc:
            return 422, {"error": "ocr_failed",
                         "detail": f"{type(exc).__name__}: {exc}"}
    processing_ms = round((time.time() - started) * 1000)
    if not words_internal:
        return 422, {"error": "no_text_detected",
                     "detail": "No printed text was detected in the image. "
                               "OCRBase covers print/typed documents and clean "
                               "scans only; handwriting is not supported.",
                     "language": lang, "engine": "tesseract",
                     "engine_version": ENGINE_VERSION,
                     "processing_ms": processing_ms}
    confs = [w["conf"] for w in words_internal if w["conf"] >= 0]
    mean_conf = round(sum(confs) / len(confs), 2) if confs else 0.0
    text, blocks = words_to_text_and_blocks(words_internal)
    words = [{k: w[k] for k in ("text", "conf", "bbox", "block_num", "line_num")}
             for w in words_internal]
    return 200, {
        "text": text,
        "words": words,
        "blocks": blocks,
        "word_count": len(words),
        "mean_confidence": mean_conf,
        "low_confidence_warning": bool(mean_conf < LOW_CONF_THRESHOLD),
        "low_confidence_threshold": LOW_CONF_THRESHOLD,
        "language": lang,
        "engine": "tesseract",
        "engine_version": ENGINE_VERSION,
        "format": fmt,
        "processing_ms": processing_ms,
    }


# ---------------------------------------------------------------------------
# Request input handling: multipart uploads, or JSON with URL / base64.
# ---------------------------------------------------------------------------

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
        head, sep, data = part.partition(b"\r\n\r\n")
        if not sep:
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


def gather_input(fields, files):
    """Returns (raw_bytes, error_tuple_or_None)."""
    if files.get("file"):
        return files["file"], None
    url = (fields.get("url") or "").strip()
    if url:
        try:
            return fetch_bytes(url), None
        except SSRFBlocked as exc:
            return None, (422, {"error": "ssrf_blocked", "detail": str(exc)})
        except ValueError as exc:
            # Size cap / bad URL scheme from fetch_bytes.
            msg = str(exc)
            code = "file_too_large" if "exceeds" in msg else "url_fetch_failed"
            status = 413 if code == "file_too_large" else 422
            return None, (status, {"error": code, "detail": msg})
        except Exception as exc:
            return None, (502, {"error": "url_fetch_failed",
                                "detail": f"Could not fetch url: {type(exc).__name__}: {exc}"})
    b64 = fields.get("image_base64") or fields.get("file_base64")
    if b64:
        candidate = b64.strip()
        if candidate.startswith("data:") and "," in candidate:
            candidate = candidate.split(",", 1)[1]
        try:
            return base64.b64decode(candidate, validate=False), None
        except Exception:
            return None, (422, {"error": "invalid_body",
                                "detail": "image_base64 is not valid base64."})
    return None, (422, {"error": "missing_parameter",
                        "detail": "Provide a multipart file upload (field 'file'), "
                                  "or JSON {\"url\": \"...\"}, or JSON {\"image_base64\": \"...\"}."})


# ---------------------------------------------------------------------------
# Health / languages
# ---------------------------------------------------------------------------

def health():
    return 200, {"status": "ok", "service": SERVICE, "version": VERSION,
                 "build": BUILD,
                 "engine": "tesseract",
                 "engine_version": ENGINE_VERSION,
                 "engine_available": bool(TESSERACT_EXE),
                 "pdf_support": "available (pdftoppm)" if PDFTOPPM_EXE
                                else "unavailable (pdftoppm not installed); PDF inputs return pdf_support_unavailable",
                 "languages": INSTALLED_LANGUAGES,
                 "limits": {"max_file_bytes": MAX_FILE_BYTES,
                            "max_body_bytes": MAX_BODY,
                            "fetch_timeout_seconds": FETCH_TIMEOUT,
                            "low_confidence_threshold": LOW_CONF_THRESHOLD,
                            "pdf_scope": "first page only at launch"},
                 "supported_formats": list(SUPPORTED_IMAGE_FORMATS) + ["pdf (first page)"],
                 "endpoints": ["POST /extract", "GET /languages", "GET /health"],
                 "recent_requests": RECENT[-5:],
                 "note": "Print and typed documents plus clean scans only. "
                         "Handwriting is NOT supported. Accuracy on degraded "
                         "scans and complex multi-column layouts is limited; "
                         "per-word confidence fields say so."}


def languages():
    return 200, {"service": SERVICE, "engine": "tesseract",
                 "engine_version": ENGINE_VERSION,
                 "languages": INSTALLED_LANGUAGES,
                 "default": "eng",
                 "note": "Only tessdata packs actually installed on this host are listed."}


# ---------------------------------------------------------------------------
# Server (driftcheck pattern: own run_server, gate + structured errors)
# ---------------------------------------------------------------------------

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

        def _record(self, path, err, started):
            status, payload = err
            RECENT.append({"endpoint": path, "status": status,
                           "seconds": round(time.time() - started, 3),
                           "error": payload.get("error")})
            del RECENT[:-10]
            return self._json(status, payload)

        def do_GET(self):
            path = urlparse(self.path).path.rstrip("/") or "/"
            if not self._gate_ok(path):
                return
            if path == "/health":
                status, payload = health()
                return self._json(status, payload)
            if path == "/languages":
                status, payload = languages()
                return self._json(status, payload)
            return self._json(404, {"error": "not_found",
                                    "detail": f"No endpoint at {path}. See /health for service info."})

        def do_POST(self):
            path = urlparse(self.path).path.rstrip("/") or "/"
            if not self._gate_ok(path):
                return
            if path != "/extract":
                return self._json(404, {"error": "not_found",
                                        "detail": f"No endpoint at {path}. See /health for service info."})
            started = time.time()
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = 0
            if length <= 0 or length > MAX_BODY:
                return self._record(path, (422, {"error": "invalid_body",
                    "detail": f"Send a multipart or JSON body of at most {MAX_BODY} bytes."}), started)
            raw_body = self.rfile.read(length)
            ctype = self.headers.get("Content-Type", "")
            try:
                if ctype.startswith("multipart/form-data"):
                    fields, files = parse_multipart(raw_body, ctype)
                elif "json" in ctype:
                    body = json.loads(raw_body.decode("utf-8"))
                    if not isinstance(body, dict):
                        raise ValueError("body must be a JSON object")
                    fields = {k: (v if isinstance(v, str) else json.dumps(v))
                              for k, v in body.items()}
                    files = {}
                else:
                    return self._record(path, (422, {"error": "invalid_body",
                        "detail": "Content-Type must be multipart/form-data or application/json."}), started)
            except ValueError as exc:
                return self._record(path, (422, {"error": "invalid_body",
                                                 "detail": str(exc)}), started)
            except Exception:
                return self._record(path, (422, {"error": "invalid_body",
                    "detail": "Request body could not be parsed."}), started)

            lang = (fields.get("lang") or "eng").strip() or "eng"
            # "pdf_page" is a reserved field at launch: accepted and
            # ignored; only the first PDF page is processed.
            _pdf_page_reserved = fields.get("pdf_page")  # noqa: F841

            raw, err = gather_input(fields, files)
            if err:
                return self._record(path, err, started)
            status, payload = extract_ocr(raw, lang)
            if status != 200:
                return self._record(path, (status, payload), started)
            RECENT.append({"endpoint": path, "status": 200,
                           "seconds": round(time.time() - started, 3),
                           "mean_confidence": payload.get("mean_confidence"),
                           "word_count": payload.get("word_count")})
            del RECENT[:-10]
            payload = dict(payload)
            payload["_meta"] = {"service": SERVICE, "version": VERSION,
                                "latency_ms": round((time.time() - started) * 1000)}
            return self._json(200, payload)

    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    run_server(int(os.environ.get("PORT", "8118")))
