"""ActorBase - an acting engine for drama writing and performance
(the user's own product, 2026-10-31; RapidAPI lane build #16).

An actor, as an API: it performs lines as acted speech, reads whole
scenes aloud with a cast of distinct voices, builds characters the
way working actors do (objectives, obstacles, tactics - verbs, not
adjectives), offers three genuinely different reads of the same
line so a writer can hear which one lands, and analyzes scenes for
beats, turns, subtext and power shifts. Stage, screen and voice
acting share the same craft underneath; the endpoints are that
craft, made callable.

Two engines, reported separately and honestly in /health:

- Performance: the SwiftRead synthesis path, reused - Microsoft
  Edge neural voices via the edge-tts package, zero marginal cost,
  no API key. A performance is planned in code from a FIXED
  delivery table (emotion x intensity -> rate / pitch / volume /
  beat pause, shipped in docs/spec-actorbase.md): the text is
  segmented into beats, emphasis spans (marked *like this* by the
  caller, or placed by the three-reads engine) become their own
  segments with a documented prosody lift, and the segments are
  synthesized with their own prosody and stitched with measured
  silence. The plan is returned with every performance as an
  SSML-style score, so a caller can see exactly what was done.
  Segment and total durations are MEASURED in code by parsing the
  MP3 frames of the actual audio, never estimated.
- Reasoning: the owner's Gemini API (same pattern as FactBase:
  primary gemini-3.6-flash, fallback gemini-3.1-flash-lite),
  used where acting judgment is the product: character builds,
  scene analysis, the three reads' tactics and subtext, and
  interpreting free-text line directions in a table read.
  Engine states: live when GEMINI_API_KEY is set, awaiting_key
  otherwise. In awaiting_key, /character, /scene-notes and
  /three-reads answer an explicit 503 engine_not_configured,
  while /perform and /table-read keep working on the performance
  engine alone (free-text directions are then carried through
  uninterpreted and the response says so). Engine failure returns
  an explicit structured error, never an invented performance or
  analysis. There is no mock mode.

Personas are generic craft archetypes (ingenue, leading-man,
villain, matriarch, trickster...), each mapped to a stock Edge
voice and a default emotional lean. No real actor's voice or
likeness is imitated, and no persona is named for a person.

The server keeps the lane scaffold's exact conventions (shared
with SwiftRead and FactBase): the RapidAPI proxy-secret gate
(401 JSON without the X-RapidAPI-Proxy-Secret header, /health
always open) and explicit structured JSON errors for every
failure. Performances return JSON with the MP3 base64-encoded,
because a performance is audio PLUS its delivery notes and
timing map, and the notes are half the product.

Endpoints:
  POST /perform      {text, emotion?, intensity?, voice?, persona?}
                     -> performed MP3 + delivery notes + plan
  POST /table-read   {lines: [{speaker, line, direction?,
                     emotion?, intensity?, pause_after_ms?}],
                     cast: {speaker: voice | persona |
                     {voice?, persona?, emotion?, intensity?}}}
                     -> one stitched MP3 + per-line timing map
  POST /character    {description, name?, play_context?}
                     -> the actor's character build
  POST /three-reads  {line, context?}
                     -> three different performed reads
  POST /scene-notes  {scene_text} -> beats, turns, subtext,
                     power shifts, per character
  GET  /health       -> engine states, limits, tables
Run: python3 app.py (PORT env, default 8116).
Needs: pip install edge-tts (see requirements.txt).
"""
import asyncio
import base64
import json
import os
import re
import threading
import time
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SERVICE = "actorbase"
VERSION = "1.0.0"
BUILD = "2026-10-31-v1"
RECENT = []                       # last request outcomes (see /health)

# --------------------------------------------------------------------------
# Reasoning engine (the owner's Gemini API): the FactBase client,
# including DesignBase's extension (a persistent 500/503 on the
# primary also falls back - per-model quota buckets are separate).
# --------------------------------------------------------------------------
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
GEMINI_FALLBACK_MODEL = os.environ.get("GEMINI_FALLBACK_MODEL",
                                       "gemini-3.1-flash-lite")
GEMINI_BASE = os.environ.get(
    "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"
).rstrip("/")
GEMINI_TIMEOUT = 90
UA = "ActorBase/1.0 (+https://rapidapi.com/YamilLittle/api/actorbase)"


def reasoning_state():
    return "live" if GEMINI_KEY else "awaiting_key"


def _gemini_once(model, parts, json_mode, timeout):
    payload = {"contents": [{"parts": parts}],
               "generationConfig": {"temperature": 0.4}}
    if json_mode:
        payload["generationConfig"]["responseMimeType"] = "application/json"
    req = urllib.request.Request(
        f"{GEMINI_BASE}/models/{model}:generateContent",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json",
                 "x-goog-api-key": GEMINI_KEY, "User-Agent": UA},
        method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    text = "".join(
        p.get("text", "")
        for cand in data.get("candidates", [])
        for p in cand.get("content", {}).get("parts", []))
    if not text.strip():
        raise ValueError("empty model response")
    return text


def gemini_generate(parts, json_mode=False, timeout=GEMINI_TIMEOUT):
    """One logical Gemini call: transient 5xx get one spaced retry;
    a 429 (the primary model's quota bucket is exhausted) retries
    once after a pause, then falls back to GEMINI_FALLBACK_MODEL,
    whose quota bucket is separate; a persistent 500/503 on the
    primary falls back the same way."""
    models = [GEMINI_MODEL]
    if GEMINI_FALLBACK_MODEL and GEMINI_FALLBACK_MODEL != GEMINI_MODEL:
        models.append(GEMINI_FALLBACK_MODEL)
    last_exc = None
    for model in models:
        for attempt in range(2):
            try:
                return _gemini_once(model, parts, json_mode, timeout)
            except urllib.error.HTTPError as exc:
                last_exc = exc
                if exc.code == 429 and attempt == 0:
                    time.sleep(8)
                    continue
                if exc.code == 429:
                    break  # quota bucket spent; try the fallback model
                if exc.code in (500, 503) and attempt == 0:
                    time.sleep(2)
                    continue
                if exc.code in (500, 503):
                    break  # persistent upstream error; fall back
                raise
            except Exception as exc:
                last_exc = exc
                if attempt == 0:
                    time.sleep(2)
                    continue
                raise
    raise last_exc


def _parse_json(text):
    """Defensive JSON parse: strip code fences, fall back to the
    outermost bracket span (the FactBase pattern)."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.IGNORECASE)
    try:
        return json.loads(t)
    except Exception:
        start = min([i for i in (t.find("["), t.find("{")) if i >= 0],
                    default=-1)
        end = max(t.rfind("]"), t.rfind("}"))
        if start >= 0 and end > start:
            return json.loads(t[start:end + 1])
        raise


def gemini_json(prompt):
    raw = gemini_generate([{"text": prompt}], json_mode=True)
    return _parse_json(raw)


# --------------------------------------------------------------------------
# Voice roster: the SwiftRead catalog (actorbase/voices.json, the
# live Edge list: 322 voices, 142 locales, 75 languages), with
# SwiftRead's curated list as the offline fallback.
# --------------------------------------------------------------------------
VOICES = [
    {"id": "en-US-AriaNeural",       "name": "Aria",       "locale": "en-US", "language": "English", "gender": "Female", "style": "Warm, natural newsreader"},
    {"id": "en-US-JennyNeural",      "name": "Jenny",      "locale": "en-US", "language": "English", "gender": "Female", "style": "Friendly, conversational"},
    {"id": "en-US-MichelleNeural",   "name": "Michelle",   "locale": "en-US", "language": "English", "gender": "Female", "style": "Clear, professional"},
    {"id": "en-US-GuyNeural",        "name": "Guy",        "locale": "en-US", "language": "English", "gender": "Male",   "style": "Steady, broadcast"},
    {"id": "en-US-ChristopherNeural","name": "Christopher","locale": "en-US", "language": "English", "gender": "Male",   "style": "Calm, documentary"},
    {"id": "en-US-EricNeural",       "name": "Eric",       "locale": "en-US", "language": "English", "gender": "Male",   "style": "Measured, articulate"},
    {"id": "en-GB-SoniaNeural",      "name": "Sonia",      "locale": "en-GB", "language": "English", "gender": "Female", "style": "Polished British newsreader"},
    {"id": "en-GB-LibbyNeural",      "name": "Libby",      "locale": "en-GB", "language": "English", "gender": "Female", "style": "Bright British"},
    {"id": "en-GB-RyanNeural",       "name": "Ryan",       "locale": "en-GB", "language": "English", "gender": "Male",   "style": "Warm British"},
    {"id": "en-GB-ThomasNeural",     "name": "Thomas",     "locale": "en-GB", "language": "English", "gender": "Male",   "style": "Formal British"},
]
_CATALOG = {"voices": len(VOICES),
            "locales": len({v["locale"] for v in VOICES}),
            "languages": len({v["locale"].split("-")[0] for v in VOICES})}
try:
    import pathlib
    _data = json.loads(pathlib.Path(__file__).with_name("voices.json")
                       .read_text(encoding="utf-8"))
    if _data.get("voices"):
        VOICES = _data["voices"]
        _CATALOG = _data["counts"]
except Exception:
    pass
_VOICE_IDS = {v["id"] for v in VOICES}
DEFAULT_VOICE = "en-US-ChristopherNeural"

# Personas: generic craft archetypes ONLY - a stock voice plus a
# default emotional lean. No real actor is imitated or named.
PERSONAS = {
    "ingenue":      {"voice": "en-US-AriaNeural",       "lean": "tenderness",
                     "note": "Young, open, sincere; the discovery is still new to her."},
    "leading-lady": {"voice": "en-GB-SoniaNeural",      "lean": "resolve",
                     "note": "Composed and commanding; carries the scene's spine."},
    "leading-man":  {"voice": "en-US-GuyNeural",        "lean": "resolve",
                     "note": "Steady, grounded, direct; says less than he means."},
    "young-hero":   {"voice": "en-US-EricNeural",       "lean": "joy",
                     "note": "Quick, earnest, still surprised by the world."},
    "matriarch":    {"voice": "en-US-MichelleNeural",   "lean": "resolve",
                     "note": "Clear authority; warmth rationed on purpose."},
    "patriarch":    {"voice": "en-GB-ThomasNeural",     "lean": "contempt",
                     "note": "Formal, weighty, accustomed to being obeyed."},
    "villain":      {"voice": "en-US-ChristopherNeural", "lean": "contempt",
                     "note": "Calm, cold, unhurried; the threat is in the quiet."},
    "trickster":    {"voice": "en-US-JennyNeural",      "lean": "joy",
                     "note": "Light, playful, always half a step ahead of the room."},
    "confidante":   {"voice": "en-GB-LibbyNeural",      "lean": "tenderness",
                     "note": "Bright and close; the keeper of everyone's secrets."},
    "narrator":     {"voice": "en-GB-RyanNeural",       "lean": "neutral",
                     "note": "Warm storyteller distance; outside the action, on its side."},
}

# --------------------------------------------------------------------------
# The delivery table (FIXED, in code; shipped verbatim in
# docs/spec-actorbase.md). Signature prosody at intensity 3, plus
# the per-intensity-point step; intensity 1..5 moves two steps
# either way. Every step deepens its signature (same sign), so a
# higher intensity always means MORE of the emotion, never less.
# Clamps keep every value inside the engine's range.
# --------------------------------------------------------------------------
DELIVERY_TABLE = {
    # emotion:      rate%  pitchHz  vol%   rate_step pitch_step vol_step  beat_pause_ms
    "neutral":    {"rate": 0,   "pitch": 0,  "volume": 0,  "rate_step": 0, "pitch_step": 0, "volume_step": 0, "beat_pause_ms": 250},
    "joy":        {"rate": 6,   "pitch": 6,  "volume": 4,  "rate_step": 2, "pitch_step": 2, "volume_step": 1, "beat_pause_ms": 200},
    "anger":      {"rate": 8,   "pitch": 2,  "volume": 10, "rate_step": 3, "pitch_step": 1, "volume_step": 3, "beat_pause_ms": 150},
    "grief":      {"rate": -12, "pitch": -6, "volume": -4, "rate_step": -3, "pitch_step": -2, "volume_step": -1, "beat_pause_ms": 450},
    "fear":       {"rate": 10,  "pitch": 8,  "volume": -2, "rate_step": 3, "pitch_step": 2, "volume_step": -1, "beat_pause_ms": 180},
    "tenderness": {"rate": -6,  "pitch": -2, "volume": -4, "rate_step": -2, "pitch_step": -1, "volume_step": -1, "beat_pause_ms": 350},
    "contempt":   {"rate": -4,  "pitch": -4, "volume": 2,  "rate_step": -1, "pitch_step": -1, "volume_step": 1, "beat_pause_ms": 300},
    "resolve":    {"rate": -2,  "pitch": -2, "volume": 6,  "rate_step": -1, "pitch_step": -1, "volume_step": 2, "beat_pause_ms": 300},
    "awe":        {"rate": -8,  "pitch": 2,  "volume": -2, "rate_step": -2, "pitch_step": 1, "volume_step": -1, "beat_pause_ms": 500},
    "guilt":      {"rate": -8,  "pitch": -5, "volume": -6, "rate_step": -2, "pitch_step": -2, "volume_step": -2, "beat_pause_ms": 400},
}
EMOTIONS = sorted(DELIVERY_TABLE)
# Emphasis realization (fixed, in code): an emphasized span is
# lifted +4 Hz and +6% volume, slowed 4%, and set off by a
# preceding beat of at least 120 ms.
EMPHASIS_LIFT = {"rate": -4, "pitch": 4, "volume": 6}
EMPHASIS_MIN_PAUSE_MS = 120


def delivery_params(emotion, intensity):
    """The one place emotion + intensity become engine prosody.
    Returns the table row as applied, with clamps."""
    row = DELIVERY_TABLE[emotion]
    steps = intensity - 3
    return {
        "rate": max(-50, min(100, row["rate"] + row["rate_step"] * steps)),
        "pitch": max(-30, min(30, row["pitch"] + row["pitch_step"] * steps)),
        "volume": max(-50, min(50, row["volume"] + row["volume_step"] * steps)),
        "beat_pause_ms": row["beat_pause_ms"],
    }


def _pct(v):
    return f"{v:+d}%"


def _hz(v):
    return f"{v:+d}Hz"


# --------------------------------------------------------------------------
# Performance planning (in code). Text is segmented into beats at
# sentence boundaries; caller emphasis markup (*span*) and any
# emphasis words supplied by the reasoning engine split spans out
# as their own segments. The plan is the performance score: it is
# returned as delivery_plan plus a rendered SSML-style string.
# --------------------------------------------------------------------------
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|(?<=[。！？।])\s*")
EMPHASIS_RE = re.compile(r"\*([^*]+)\*")


def split_beats(text):
    parts = SENT_SPLIT.split(text.replace("\n", " "))
    return [p.strip() for p in parts if p and p.strip()]


def parse_markup(text):
    """Split *emphasized* spans out. Returns (plain_text, spans)
    where spans are (start, end) offsets into plain_text."""
    spans, plain, pos = [], [], 0
    cursor = 0
    for m in EMPHASIS_RE.finditer(text):
        plain.append(text[pos:m.start()])
        cursor += m.start() - pos
        spans.append((cursor, cursor + len(m.group(1))))
        plain.append(m.group(1))
        cursor += len(m.group(1))
        pos = m.end()
    plain.append(text[pos:])
    return "".join(plain), spans


def plan_performance(text, emotion, intensity, emphasis_words=None):
    """Build the segment plan for one performed line. Returns
    (segments, plan_meta): each segment is {text, emphasis, rate,
    pitch, volume, pause_before_ms}; the caller stitches them."""
    base = delivery_params(emotion, intensity)
    plain, spans = parse_markup(text)
    wanted = []
    for w in (emphasis_words or []):
        for m in re.finditer(r"\b" + re.escape(w) + r"\b", plain,
                             flags=re.IGNORECASE):
            wanted.append((m.start(), m.end()))
    spans = sorted(set(spans + wanted))
    # Flatten to (text, emphasis) pieces at span boundaries.
    pieces, cursor = [], 0
    for start, end in spans:
        if start > cursor:
            pieces.append((plain[cursor:start], False))
        if end > start:
            pieces.append((plain[start:end], True))
        cursor = max(cursor, end)
    if cursor < len(plain):
        pieces.append((plain[cursor:], False))
    # Beat-split the non-emphasis pieces at sentence boundaries;
    # emphasis spans stay whole.
    beats = []
    for piece, emph in pieces:
        if emph:
            if piece.strip():
                beats.append((piece.strip(), True))
        else:
            for beat in split_beats(piece):
                beats.append((beat, False))
    segments = []
    for i, (beat, emph) in enumerate(beats):
        params = dict(base)
        if emph:
            params = {
                "rate": max(-50, min(100, base["rate"] + EMPHASIS_LIFT["rate"])),
                "pitch": max(-30, min(30, base["pitch"] + EMPHASIS_LIFT["pitch"])),
                "volume": max(-50, min(50, base["volume"] + EMPHASIS_LIFT["volume"])),
                "beat_pause_ms": base["beat_pause_ms"],
            }
        pause_before = 0
        if i > 0:
            pause_before = base["beat_pause_ms"]
            if emph:
                pause_before = max(EMPHASIS_MIN_PAUSE_MS, pause_before // 2)
        segments.append({"text": beat, "emphasis": emph,
                         "rate": params["rate"], "pitch": params["pitch"],
                         "volume": params["volume"],
                         "pause_before_ms": pause_before})
    meta = {"emotion": emotion, "intensity": intensity,
            "base_prosody": {"rate": base["rate"], "pitch": base["pitch"],
                             "volume": base["volume"],
                             "beat_pause_ms": base["beat_pause_ms"]},
            "emphasis_spans": len([s for s in segments if s["emphasis"]]),
            "plain_text": plain}
    return segments, meta


def render_score(segments):
    """The plan as an SSML-style score string (documentation of
    the performance; synthesis realizes it by segment prosody and
    stitched silence - see the spec for exactly how)."""
    out = ["<speak>"]
    for seg in segments:
        if seg["pause_before_ms"]:
            out.append(f'<break time="{seg["pause_before_ms"]}ms"/>')
        tag = (f'<prosody rate="{_pct(seg["rate"])}" '
               f'pitch="{_hz(seg["pitch"])}" '
               f'volume="{_pct(seg["volume"])}">')
        body = seg["text"]
        if seg["emphasis"]:
            body = f"<emphasis>{body}</emphasis>"
        out.append(tag + body + "</prosody>")
    out.append("</speak>")
    return "".join(out)


# --------------------------------------------------------------------------
# MP3 measurement (in code): frame-accurate durations by parsing
# MPEG audio frames - no estimation from byte counts.
# --------------------------------------------------------------------------
_BR_MPEG1_L3 = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0]
_BR_MPEG2_L3 = [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0]
_SR = {3: [44100, 48000, 32000], 2: [22050, 24000, 16000],
       0: [11025, 12000, 8000]}


def mp3_frames(data):
    """Yield (offset, length, duration_s) per MPEG Layer III frame."""
    i = 0
    if data[:3] == b"ID3" and len(data) > 10:
        size = 0
        for b in data[6:10]:
            size = (size << 7) | (b & 0x7F)
        i = 10 + size
    n = len(data)
    while i + 4 <= n:
        if data[i] != 0xFF or (data[i + 1] & 0xE0) != 0xE0:
            i += 1
            continue
        version = (data[i + 1] >> 3) & 0x03
        layer = (data[i + 1] >> 1) & 0x03
        if version == 1 or layer != 1:
            i += 1
            continue
        br_idx = (data[i + 2] >> 4) & 0x0F
        sr_idx = (data[i + 2] >> 2) & 0x03
        padding = (data[i + 2] >> 1) & 0x01
        if br_idx in (0, 15) or sr_idx == 3:
            i += 1
            continue
        if version == 3:
            bitrate = _BR_MPEG1_L3[br_idx]
            samples = 1152
            length = (144 * bitrate * 1000) // _SR[version][sr_idx] + padding
        else:
            bitrate = _BR_MPEG2_L3[br_idx]
            samples = 576
            length = (72 * bitrate * 1000) // _SR[version][sr_idx] + padding
        if length < 4 or i + length > n + 4:
            # Tolerate a truncated final frame: count it and stop.
            if i + 4 <= n:
                yield (i, max(0, n - i), samples / _SR[version][sr_idx])
            return
        yield (i, length, samples / _SR[version][sr_idx])
        i += length


def mp3_duration(data):
    return round(sum(d for _, _, d in mp3_frames(data)), 3)


# Silence in the exact format edge-tts emits (24 kHz, 48 kbps,
# mono), reused from the SwiftRead code path: 0.4 s of it ships as
# PARAGRAPH_PAUSE there; here it is frame-split to build pauses
# of any requested length, rounded to whole frames (24 ms).
SILENCE_BLOB = base64.b64decode("//OEwAAAAAAAAAAAAEluZm8AAAAPAAAAEwAAC3AAHR0dHR0pKSkpKTY2NjY2Q0NDQ0NDT09PT09cXFxcXGhoaGhodXV1dXV1goKCgoKOjo6Ojpubm5ubp6enp6entLS0tLTBwcHBwc3Nzc3N2tra2tra5ubm5ubz8/Pz8///////AAAAAExhdmM2Mi4yOAAAAAAAAAAAAAAAACQDAAAAAAAAAAtwBmwvuQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA//NkxAAAAANIAAAAAExBTUVVVVVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//NkxHwAAANIAAAAAFVVVVVVVVVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//NkxHwAAANIAAAAAFVVVVVVVVVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//NkxHwAAANIAAAAAFVVVVVVVVVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//NkxHwAAANIAAAAAFVVVVVVVVVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//NkxHwAAANIAAAAAFVVVVVVVVVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//NkxHwAAANIAAAAAFVVVVVVVVVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//NkxHwAAANIAAAAAFVVVVVVVVVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//NkxHwAAANIAAAAAFVVVVVVVVVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//NkxHwAAANIAAAAAFVVVVVVVVVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//NkxHwAAANIAAAAAFVVVVVVVVVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//NkxHwAAANIAAAAAFVVVVVVVVVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//NkxHwAAANIAAAAAFVVVVVVVVVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//NkxHwAAANIAAAAAFVVVVVVVVVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//NkxHwAAANIAAAAAFVVVVVVVVVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//NkxHwAAANIAAAAAFVVVVVVVVVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//NkxHwAAANIAAAAAFVVVVVVVVVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//NkxHwAAANIAAAAAFVVVVVVVVVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//NkxHwAAANIAAAAAFVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV")
_SILENCE_FRAMES = None


def silence_frames():
    global _SILENCE_FRAMES
    if _SILENCE_FRAMES is None:
        frames = [(o, l) for o, l, _ in mp3_frames(SILENCE_BLOB)]
        _SILENCE_FRAMES = [SILENCE_BLOB[o:o + l] for o, l in frames]
    return _SILENCE_FRAMES


def silence_ms(ms):
    if ms <= 0:
        return b""
    frames = silence_frames()
    if not frames:
        return b""
    frame_s = mp3_duration(SILENCE_BLOB) / len(frames)
    count = max(1, round(ms / 1000.0 / frame_s))
    return b"".join(frames[i % len(frames)] for i in range(count))


# --------------------------------------------------------------------------
# Synthesis: the SwiftRead engine path (lazy edge-tts import,
# env-proxy honored, system trust store for the engine websocket,
# per-segment retries, bounded concurrency, hard thread-join
# budget). A performance is short and every beat matters, so a
# segment that fails after its retries fails the performance with
# a structured 502 - beats are never silently dropped.
# --------------------------------------------------------------------------
SYNTH_CONCURRENCY = 4
REQUEST_BUDGET = 85


def performance_state():
    try:
        import edge_tts  # noqa: F401
        return "installed"
    except ImportError:
        return "not_installed"


async def _synth_segment(edge_tts, text, voice, rate, pitch, volume):
    proxy = (os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
             or os.environ.get("ALL_PROXY") or os.environ.get("all_proxy"))
    kwargs = {"proxy": proxy} if proxy else {}
    import ssl
    import edge_tts.communicate as _ec
    _ec._SSL_CTX = ssl.create_default_context()
    comm = edge_tts.Communicate(text, voice, rate=_pct(rate),
                                pitch=_hz(pitch), volume=_pct(volume),
                                **kwargs)
    buf = bytearray()
    async for part in comm.stream():
        if part["type"] == "audio":
            buf.extend(part["data"])
    return bytes(buf)


def synthesize_segments(jobs):
    """jobs: [{text, voice, rate, pitch, volume}]. Returns the list
    of MP3 byte strings in job order, or (None, error_tuple)."""
    try:
        import edge_tts
    except ImportError:
        return None, (503, {"error": "engine_not_configured",
                            "detail": "The performance engine package "
                                      "is not installed on this deployment."})
    results = [None] * len(jobs)

    async def job(sem, idx, spec):
        async with sem:
            for _attempt in range(2):
                try:
                    data = await _synth_segment(
                        edge_tts, spec["text"], spec["voice"],
                        spec["rate"], spec["pitch"], spec["volume"])
                except Exception:
                    continue
                if data:
                    results[idx] = data
                    return

    async def run_all():
        sem = asyncio.Semaphore(SYNTH_CONCURRENCY)
        await asyncio.gather(*[job(sem, i, s) for i, s in enumerate(jobs)])

    def runner():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(run_all())
        except Exception:
            pass
        finally:
            loop.close()

    worker = threading.Thread(target=runner, daemon=True)
    worker.start()
    worker.join(REQUEST_BUDGET)
    failed = [i for i, r in enumerate(results) if r is None]
    if failed:
        return None, (502, {"error": "synthesis_failed",
                            "detail": f"Performance synthesis failed "
                                      f"for segment(s) {failed} after "
                                      f"retries (engine errors, stalls, "
                                      f"or unspeakable text for the "
                                      f"chosen voice). No partial "
                                      f"performance is returned."})
    return results, None


def perform_segments(segments, voice):
    """Synthesize a planned performance and stitch it with the
    planned pauses. Returns (audio_bytes, segment_durations)."""
    jobs = [{"text": s["text"], "voice": voice, "rate": s["rate"],
             "pitch": s["pitch"], "volume": s["volume"]}
            for s in segments]
    results, err = synthesize_segments(jobs)
    if err:
        return None, None, err
    audio = bytearray()
    durations = []
    for seg, data in zip(segments, results):
        if seg["pause_before_ms"]:
            audio.extend(silence_ms(seg["pause_before_ms"]))
        audio.extend(data)
        durations.append(mp3_duration(data))
    return bytes(audio), durations, None


# --------------------------------------------------------------------------
# Casting: resolve voice / persona / emotion / intensity for one
# speaker. Explicit fields win; a persona fills the gaps (its
# voice, then its lean as the default emotion).
# --------------------------------------------------------------------------
def _err(status, code, detail):
    return status, {"error": code, "detail": detail}


def _check_intensity(value):
    if value is None:
        return None, None
    if isinstance(value, bool) or not isinstance(value, int):
        return None, _err(422, "invalid_parameter",
                          "intensity must be an integer from 1 to 5.")
    if value < 1 or value > 5:
        return None, _err(422, "invalid_parameter",
                          "intensity must be an integer from 1 to 5.")
    return value, None


def resolve_casting(spec):
    """spec: {voice?, persona?, emotion?, intensity?} (any subset).
    Returns (casting, error): casting is {voice, persona, emotion,
    intensity} fully resolved."""
    spec = spec or {}
    persona = spec.get("persona")
    if persona is not None and persona not in PERSONAS:
        return None, _err(422, "invalid_parameter",
                          f"persona must be one of: "
                          f"{', '.join(sorted(PERSONAS))}.")
    voice = spec.get("voice")
    if voice is not None and voice not in _VOICE_IDS:
        return None, _err(422, "invalid_parameter",
                          "voice must be a voice id from the Edge "
                          "catalog (322 voices; see /health).")
    if voice is None and persona:
        voice = PERSONAS[persona]["voice"]
    if voice is None:
        voice = DEFAULT_VOICE
    emotion = spec.get("emotion")
    if emotion is not None and emotion not in DELIVERY_TABLE:
        return None, _err(422, "invalid_parameter",
                          f"emotion must be one of: {', '.join(EMOTIONS)}.")
    if emotion is None and persona:
        emotion = PERSONAS[persona]["lean"]
    if emotion is None:
        emotion = "neutral"
    intensity, err = _check_intensity(spec.get("intensity"))
    if err:
        return None, err
    if intensity is None:
        intensity = 3
    return {"voice": voice, "persona": persona, "emotion": emotion,
            "intensity": intensity}, None


# --------------------------------------------------------------------------
# Endpoint pipelines.
# --------------------------------------------------------------------------
MAX_PERFORM_CHARS = 2000
MAX_LINE_CHARS = 600
MAX_SCENE_CHARS = 12000
MAX_LINES = 40
MAX_CAST = 12
MAX_TOTAL_READ_CHARS = 8000
MAX_BODY = 1_000_000

DIRECTION_VOCAB = (f"emotion must be one of {EMOTIONS}; intensity "
                   f"an integer 1 to 5")


def interpret_directions(directions):
    """One batched Gemini call mapping free-text line directions
    to the fixed delivery vocabulary. Returns {index: {emotion,
    intensity, emphasis[]}} for the directions it could read;
    raises on engine failure (the caller discloses and falls
    back, never invents)."""
    listing = "\n".join(f"{i}: {d}" for i, d in enumerate(directions))
    prompt = (
        "You are the direction interpreter for an acting engine. "
        "For each numbered actor direction below, choose the "
        "delivery that best serves it from this fixed vocabulary: "
        + DIRECTION_VOCAB + ". Also name up to three words from "
        "the direction's line that should carry emphasis ONLY if "
        "the direction clearly calls for stress on specific words; "
        "otherwise return an empty list. Return JSON only: an "
        "array of {\"index\": int, \"emotion\": \"...\", "
        "\"intensity\": int, \"emphasis\": [\"...\"]} with one "
        "object per direction.\n\nDIRECTIONS:\n" + listing)
    parsed = gemini_json(prompt)
    out = {}
    if isinstance(parsed, list):
        for item in parsed:
            if not isinstance(item, dict):
                continue
            idx = item.get("index")
            emotion = str(item.get("emotion", "")).lower()
            if not isinstance(idx, int) or emotion not in DELIVERY_TABLE:
                continue
            try:
                intensity = max(1, min(5, int(item.get("intensity", 3))))
            except (TypeError, ValueError):
                intensity = 3
            emphasis = [str(w) for w in item.get("emphasis", [])
                        if isinstance(w, str) and w.strip()][:3]
            out[idx] = {"emotion": emotion, "intensity": intensity,
                        "emphasis": emphasis}
    return out


def do_perform(body):
    text = (body.get("text") or "").strip()
    if not text:
        return None, _err(422, "missing_parameter",
                          "Provide text= with the line to perform.")
    if len(text) > MAX_PERFORM_CHARS:
        return None, _err(422, "text_too_long",
                          f"Text is {len(text)} characters; the "
                          f"per-performance maximum is {MAX_PERFORM_CHARS}.")
    casting, err = resolve_casting(body)
    if err:
        return None, err
    segments, meta = plan_performance(text, casting["emotion"],
                                      casting["intensity"])
    audio, durations, err = perform_segments(segments, casting["voice"])
    if err:
        return None, err
    for seg, dur in zip(segments, durations):
        seg["duration_s"] = dur
    payload = {
        "audio_base64": base64.b64encode(audio).decode(),
        "audio_format": "mp3",
        "duration_s": mp3_duration(audio),
        "voice": casting["voice"],
        "persona": casting["persona"],
        "emotion": casting["emotion"],
        "intensity": casting["intensity"],
        "delivery": meta["base_prosody"],
        "delivery_plan": segments,
        "score": render_score(segments),
        "characters": len(meta["plain_text"]),
        "note": "Emphasis spans are marked *like this* in the "
                "input text. Durations are measured from the audio "
                "frames. The voice is a stock synthesis voice "
                "under a generic archetype, not a human actor.",
    }
    return payload, None


def do_table_read(body):
    lines = body.get("lines")
    cast = body.get("cast")
    if not isinstance(lines, list) or not lines:
        return None, _err(422, "missing_parameter",
                          "Provide lines= as a non-empty array of "
                          "{speaker, line} objects.")
    if len(lines) > MAX_LINES:
        return None, _err(422, "too_many_lines",
                          f"{len(lines)} lines; the per-read maximum "
                          f"is {MAX_LINES}.")
    if not isinstance(cast, dict) or not cast:
        return None, _err(422, "missing_parameter",
                          "Provide cast= mapping each speaker to a "
                          "voice id, a persona name, or a casting "
                          "object {voice?, persona?, emotion?, "
                          "intensity?}.")
    if len(cast) > MAX_CAST:
        return None, _err(422, "too_many_speakers",
                          f"{len(cast)} cast entries; the maximum "
                          f"is {MAX_CAST}.")
    # Resolve the cast first: every speaker must be cast.
    castings = {}
    for speaker, spec in cast.items():
        if isinstance(spec, str):
            spec = ({"persona": spec} if spec in PERSONAS
                    else {"voice": spec})
        if not isinstance(spec, dict):
            return None, _err(422, "invalid_parameter",
                              f"cast[{speaker!r}] must be a voice id, "
                              f"a persona name, or a casting object.")
        casting, err = resolve_casting(spec)
        if err:
            return None, err
        castings[speaker] = casting
    total_chars = 0
    prepared = []
    for i, entry in enumerate(lines):
        if not isinstance(entry, dict):
            return None, _err(422, "invalid_parameter",
                              f"lines[{i}] must be an object.")
        speaker = entry.get("speaker")
        line = (entry.get("line") or "").strip()
        if not speaker or speaker not in castings:
            return None, _err(422, "missing_parameter",
                              f"lines[{i}].speaker {speaker!r} has no "
                              f"cast entry; cast every speaker.")
        if not line:
            return None, _err(422, "missing_parameter",
                              f"lines[{i}].line is empty.")
        if len(line) > MAX_LINE_CHARS:
            return None, _err(422, "text_too_long",
                              f"lines[{i}] is {len(line)} characters; "
                              f"the per-line maximum is {MAX_LINE_CHARS}.")
        total_chars += len(line)
        casting = dict(castings[speaker])
        if entry.get("emotion") is not None or entry.get("intensity") is not None:
            override, err = resolve_casting(
                {"voice": casting["voice"], "persona": casting["persona"],
                 "emotion": entry.get("emotion", casting["emotion"]),
                 "intensity": entry.get("intensity", casting["intensity"])})
            if err:
                return None, err
            casting = override
        pause_after = entry.get("pause_after_ms", 350)
        if (isinstance(pause_after, bool) or not isinstance(pause_after, int)
                or pause_after < 0 or pause_after > 5000):
            return None, _err(422, "invalid_parameter",
                              f"lines[{i}].pause_after_ms must be an "
                              f"integer from 0 to 5000.")
        prepared.append({"index": i, "speaker": speaker, "line": line,
                         "direction": entry.get("direction"),
                         "casting": casting,
                         "pause_after_ms": pause_after,
                         "emphasis_words": []})
    if total_chars > MAX_TOTAL_READ_CHARS:
        return None, _err(422, "text_too_long",
                          f"The read totals {total_chars} characters; "
                          f"the maximum is {MAX_TOTAL_READ_CHARS}.")
    # Free-text directions: interpreted in one batched call when
    # the reasoning engine is live; otherwise carried through
    # uninterpreted, and the response says so.
    warnings = []
    directed = [p for p in prepared if p["direction"]]
    interpreted = False
    if directed and reasoning_state() == "live":
        try:
            got = interpret_directions(
                [str(p["direction"]) for p in directed])
            for j, p in enumerate(directed):
                if j in got:
                    p["casting"] = {**p["casting"], **{
                        "emotion": got[j]["emotion"],
                        "intensity": got[j]["intensity"]}}
                    p["emphasis_words"] = got[j]["emphasis"]
                    interpreted = True
                else:
                    warnings.append(
                        f"lines[{p['index']}]: the direction could "
                        f"not be mapped to the delivery vocabulary; "
                        f"cast defaults were used.")
        except Exception as exc:
            warnings.append(
                f"Direction interpretation failed "
                f"({type(exc).__name__}); cast defaults were used "
                f"for every directed line.")
    elif directed:
        warnings.append(
            "Free-text directions were carried uninterpreted: the "
            "reasoning engine is not configured on this deployment, "
            "so cast defaults and explicit emotion/intensity fields "
            "govern the read.")
    # Plan, synthesize, stitch; the timing map is measured from
    # the actual segment audio.
    jobs = []
    for p in prepared:
        segments, meta = plan_performance(
            p["line"], p["casting"]["emotion"], p["casting"]["intensity"],
            emphasis_words=p["emphasis_words"])
        p["segments"] = segments
        p["plain_text"] = meta["plain_text"]
        for s in segments:
            jobs.append({"text": s["text"], "voice": p["casting"]["voice"],
                         "rate": s["rate"], "pitch": s["pitch"],
                         "volume": s["volume"]})
    results, err = synthesize_segments(jobs)
    if err:
        return None, err
    audio = bytearray()
    timing = []
    seg_iter = iter(results)
    cursor = 0.0
    for p in prepared:
        line_audio = bytearray()
        for seg in p["segments"]:
            data = next(seg_iter)
            if seg["pause_before_ms"]:
                line_audio.extend(silence_ms(seg["pause_before_ms"]))
            line_audio.extend(data)
        start = round(cursor, 3)
        cursor += mp3_duration(bytes(line_audio))
        end = round(cursor, 3)
        audio.extend(line_audio)
        if p is not prepared[-1] and p["pause_after_ms"]:
            pad = silence_ms(p["pause_after_ms"])
            audio.extend(pad)
            cursor += mp3_duration(pad)
        timing.append({
            "index": p["index"], "speaker": p["speaker"],
            "line": p["plain_text"],
            "voice": p["casting"]["voice"],
            "persona": p["casting"]["persona"],
            "emotion": p["casting"]["emotion"],
            "intensity": p["casting"]["intensity"],
            "direction": p["direction"],
            "direction_interpreted": bool(p["direction"]) and interpreted,
            "start_s": start, "end_s": end,
            "duration_s": round(end - start, 3),
            "pause_after_ms": p["pause_after_ms"]})
    payload = {
        "audio_base64": base64.b64encode(bytes(audio)).decode(),
        "audio_format": "mp3",
        "duration_s": mp3_duration(bytes(audio)),
        "timing_map": timing,
        "cast": {s: {"voice": c["voice"], "persona": c["persona"],
                     "emotion": c["emotion"], "intensity": c["intensity"]}
                 for s, c in castings.items()},
        "warnings": warnings,
        "note": "Timings are measured from the audio frames of "
                "the stitched performance. Voices are stock "
                "synthesis voices under generic archetypes, not "
                "human actors.",
    }
    return payload, None


def _require_live():
    if reasoning_state() != "live":
        return _err(503, "engine_not_configured",
                    "No Gemini API key is configured on this "
                    "deployment yet, so the reasoning engine is "
                    "not available. The service owner must add "
                    "GEMINI_API_KEY to enable it. The performance "
                    "endpoints (/perform, /table-read) do not need "
                    "it and keep working.")
    return None


def _str_list(value, cap=8):
    if not isinstance(value, list):
        return None
    out = [str(v).strip() for v in value if str(v).strip()]
    return out[:cap] if out else None


def do_character(body):
    err = _require_live()
    if err:
        return None, err
    description = (body.get("description") or "").strip()
    if not description:
        return None, _err(422, "missing_parameter",
                          "Provide description= of the character "
                          "to build.")
    if len(description) > 2000:
        return None, _err(422, "text_too_long",
                          f"Description is {len(description)} "
                          f"characters; the maximum is 2000.")
    name = (body.get("name") or "").strip()
    context = (body.get("play_context") or "").strip()
    prompt = (
        "You are a working actor preparing a role. Build the "
        "character below the way actors actually prepare: in "
        "actions and verbs, not adjectives. Ground every element "
        "in the description and context given; invent nothing "
        "that contradicts them, and where the material is silent, "
        "make the playable choice an actor would make and keep it "
        "specific. Return JSON only with exactly these keys:\n"
        "- \"name\": the character's name (use the given name; if "
        "none, use the description's own label for them)\n"
        "- \"objective\": what the character wants in the play, "
        "as an action sentence (\"I want to...\")\n"
        "- \"super_objective\": the want underneath everything "
        "they do across the whole play\n"
        "- \"obstacles\": array of 3-5 concrete obstacles, inner "
        "and outer\n"
        "- \"tactics\": array of 4-6 action verbs with a phrase "
        "each (e.g. \"to charm - ...\"), the ways they pursue "
        "the objective\n"
        "- \"backstory_beats\": array of 3-5 life beats that made "
        "them who they are at curtain\n"
        "- \"given_circumstances\": array of 3-5 facts of their "
        "world they cannot change\n"
        "- \"voice_notes\": how they speak (tempo, register, what "
        "they do with words) in 1-2 sentences\n"
        "- \"physicality_notes\": how they carry and move "
        "themselves in 1-2 sentences\n\n"
        + (f"NAME: {name}\n" if name else "")
        + f"DESCRIPTION: {description}\n"
        + (f"PLAY CONTEXT: {context}\n" if context else ""))
    try:
        parsed = gemini_json(prompt)
    except Exception as exc:
        return None, _err(502, "engine_upstream_error",
                          f"{type(exc).__name__}: {exc}")
    if not isinstance(parsed, dict):
        return None, _err(502, "engine_upstream_error",
                          "The reasoning engine returned an "
                          "unusable character build.")
    character = {}
    for key in ("name", "objective", "super_objective",
                "voice_notes", "physicality_notes"):
        value = parsed.get(key)
        if not isinstance(value, str) or not value.strip():
            return None, _err(502, "engine_upstream_error",
                              f"The reasoning engine's build is "
                              f"missing '{key}'; nothing was "
                              f"invented to fill it.")
        character[key] = value.strip()
    for key in ("obstacles", "tactics", "backstory_beats",
                "given_circumstances"):
        value = _str_list(parsed.get(key))
        if value is None:
            return None, _err(502, "engine_upstream_error",
                              f"The reasoning engine's build is "
                              f"missing '{key}'; nothing was "
                              "invented to fill it.")
        character[key] = value
    return {"character": character}, None


def do_three_reads(body):
    err = _require_live()
    if err:
        return None, err
    line = (body.get("line") or "").strip()
    if not line:
        return None, _err(422, "missing_parameter",
                          "Provide line= with the line to read "
                          "three ways.")
    if len(line) > 400:
        return None, _err(422, "text_too_long",
                          f"Line is {len(line)} characters; the "
                          f"maximum is 400.")
    context = (body.get("context") or "").strip()
    if len(context) > 1000:
        return None, _err(422, "text_too_long",
                          "context is over 1000 characters.")
    casting, err = resolve_casting(body)
    if err:
        return None, err
    prompt = (
        "You are an actor workshopping one line three ways for "
        "the writer. Give THREE genuinely different reads of the "
        "line: a different tactic (an action verb the speaker is "
        "playing on the other person) and a different subtext "
        "(what they mean underneath the words) each time - not "
        "three flavors of the same read. For each read also pick "
        "the delivery from this fixed vocabulary: emotion one of "
        + ", ".join(EMOTIONS) + "; intensity an integer 1 to 5; "
        "and up to two exact words from the line to stress "
        "(emphasis). Return JSON only: {\"reads\": [{\"tactic\": "
        "\"...\", \"subtext\": \"...\", \"emotion\": \"...\", "
        "\"intensity\": int, \"emphasis\": [\"...\"], "
        "\"delivery_note\": \"one sentence on how this read "
        "plays\"}]} with exactly three reads.\n\nLINE: " + line
        + (f"\nCONTEXT: {context}" if context else ""))
    try:
        parsed = gemini_json(prompt)
    except Exception as exc:
        return None, _err(502, "engine_upstream_error",
                          f"{type(exc).__name__}: {exc}")
    reads_in = parsed.get("reads") if isinstance(parsed, dict) else None
    if not isinstance(reads_in, list) or len(reads_in) != 3:
        return None, _err(502, "engine_upstream_error",
                          "The reasoning engine did not return "
                          "three reads; nothing was invented.")
    reads = []
    for i, item in enumerate(reads_in):
        if not isinstance(item, dict):
            return None, _err(502, "engine_upstream_error",
                              f"Read {i + 1} is malformed.")
        tactic = str(item.get("tactic", "")).strip()
        subtext = str(item.get("subtext", "")).strip()
        emotion = str(item.get("emotion", "")).lower()
        note = str(item.get("delivery_note", "")).strip()
        if not tactic or not subtext or emotion not in DELIVERY_TABLE:
            return None, _err(502, "engine_upstream_error",
                              f"Read {i + 1} is missing its tactic, "
                              f"subtext, or a usable emotion; nothing "
                              f"was invented.")
        try:
            intensity = max(1, min(5, int(item.get("intensity", 3))))
        except (TypeError, ValueError):
            intensity = 3
        emphasis = [str(w) for w in item.get("emphasis", [])
                    if isinstance(w, str) and w.strip()][:2]
        segments, meta = plan_performance(
            line, emotion, intensity, emphasis_words=emphasis)
        dropped = len(emphasis) - meta["emphasis_spans"] \
            if emphasis else 0
        audio, durations, serr = perform_segments(segments,
                                                  casting["voice"])
        if serr:
            return None, serr
        for seg, dur in zip(segments, durations):
            seg["duration_s"] = dur
        reads.append({
            "read": i + 1, "tactic": tactic, "subtext": subtext,
            "emotion": emotion, "intensity": intensity,
            "emphasis": emphasis,
            "emphasis_dropped": max(0, dropped),
            "delivery_note": note,
            "delivery": meta["base_prosody"],
            "delivery_plan": segments,
            "audio_base64": base64.b64encode(audio).decode(),
            "audio_format": "mp3",
            "duration_s": mp3_duration(audio)})
    return {"line": plan_performance(line, "neutral", 3)[1]["plain_text"],
            "context": context or None, "voice": casting["voice"],
            "persona": casting["persona"], "reads": reads}, None


def do_scene_notes(body):
    err = _require_live()
    if err:
        return None, err
    scene = (body.get("scene_text") or "").strip()
    if not scene:
        return None, _err(422, "missing_parameter",
                          "Provide scene_text= with the scene to "
                          "analyze.")
    if len(scene) > MAX_SCENE_CHARS:
        return None, _err(422, "text_too_long",
                          f"Scene is {len(scene)} characters; the "
                          f"maximum is {MAX_SCENE_CHARS}.")
    prompt = (
        "You are an actor and dramaturg analyzing a scene for "
        "the writer. Work in acting craft, not literary summary. "
        "Return JSON only with exactly these keys:\n"
        "- \"beats\": array of {\"beat\": what changes, \"turn\": "
        "the moment it turns, \"subtext\": what is meant "
        "underneath} - one object per beat, in scene order\n"
        "- \"power_shifts\": array of {\"where\": where in the "
        "scene, \"from\": who holds power before, \"to\": who "
        "holds it after}\n"
        "- \"characters\": object mapping each character's name "
        "to {\"wants\": their objective in this scene, \"hides\": "
        "what they are not saying, \"tactics\": array of action "
        "verbs they use}\n"
        "- \"summary\": 1-2 sentences on what the scene is "
        "really about underneath its subject\n\nSCENE:\n" + scene)
    try:
        parsed = gemini_json(prompt)
    except Exception as exc:
        return None, _err(502, "engine_upstream_error",
                          f"{type(exc).__name__}: {exc}")
    if not isinstance(parsed, dict):
        return None, _err(502, "engine_upstream_error",
                          "The reasoning engine returned an "
                          "unusable analysis.")
    beats = parsed.get("beats")
    if (not isinstance(beats, list) or not beats
            or any(not isinstance(b, dict) or not b.get("beat")
                   for b in beats)):
        return None, _err(502, "engine_upstream_error",
                          "The analysis is missing its beats; "
                          "nothing was invented.")
    shifts = parsed.get("power_shifts")
    if not isinstance(shifts, list):
        return None, _err(502, "engine_upstream_error",
                          "The analysis is missing its power "
                          "shifts; nothing was invented.")
    characters = parsed.get("characters")
    if not isinstance(characters, dict) or not characters:
        return None, _err(502, "engine_upstream_error",
                          "The analysis names no characters; "
                          "nothing was invented.")
    summary = parsed.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        return None, _err(502, "engine_upstream_error",
                          "The analysis is missing its summary; "
                          "nothing was invented.")
    return {"beats": beats, "power_shifts": shifts,
            "characters": characters, "summary": summary.strip()}, None


# --------------------------------------------------------------------------
# Health.
# --------------------------------------------------------------------------
def health():
    return 200, {
        "status": "ok", "service": SERVICE, "version": VERSION,
        "build": BUILD,
        "engines": {
            "reasoning": {"state": reasoning_state(),
                          "model": GEMINI_MODEL,
                          "fallback_model": GEMINI_FALLBACK_MODEL,
                          "role": "character builds, scene analysis, "
                                  "three-reads tactics and subtext, "
                                  "direction interpretation"},
            "performance": {"state": performance_state(),
                            "engine": "edge-tts (Microsoft Edge "
                                      "neural voices), the SwiftRead "
                                      "synthesis path",
                            "voices": _CATALOG["voices"],
                            "locales": _CATALOG["locales"],
                            "languages": _CATALOG["languages"],
                            "role": "acted speech for /perform, "
                                    "/table-read, /three-reads; "
                                    "zero marginal cost, no key"},
        },
        "delivery_table": {
            "emotions": EMOTIONS, "intensity_range": [1, 5],
            "note": "Fixed in code and shipped verbatim in the "
                    "spec: signature prosody at intensity 3 plus a "
                    "per-point step, clamped to the engine's range. "
                    "Emphasis spans lift pitch +4 Hz, volume +6%, "
                    "rate -4%, with a beat before them."},
        "personas": {name: {"voice": p["voice"], "lean": p["lean"]}
                     for name, p in PERSONAS.items()},
        "limits": {"max_perform_chars": MAX_PERFORM_CHARS,
                   "max_line_chars": MAX_LINE_CHARS,
                   "max_lines_per_read": MAX_LINES,
                   "max_cast": MAX_CAST,
                   "max_read_total_chars": MAX_TOTAL_READ_CHARS,
                   "max_scene_chars": MAX_SCENE_CHARS},
        "endpoints": ["POST /perform", "POST /table-read",
                      "POST /character", "POST /three-reads",
                      "POST /scene-notes", "GET /health"],
        "recent_requests": RECENT[-5:],
        "note": "Performances are synthesized speech under "
                "generic craft archetypes, not human actors and "
                "not imitations of any real performer. Delivery is "
                "bounded by the fixed delivery table; emotional "
                "range beyond it is not claimed."}


# --------------------------------------------------------------------------
# Server: scaffold conventions (gate + structured errors).
# --------------------------------------------------------------------------
def _not_configured_performance():
    return 503, {"error": "engine_not_configured",
                 "detail": "The performance engine package is not "
                           "installed on this deployment."}


def run_server(port):
    proxy_secret = os.environ.get("RAPIDAPI_PROXY_SECRET")
    routes = {"/perform": do_perform, "/table-read": do_table_read,
              "/character": do_character, "/three-reads": do_three_reads,
              "/scene-notes": do_scene_notes}

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

        def _record(self, path, status, payload, started, extra=None):
            entry = {"endpoint": path, "status": status,
                     "seconds": round(time.time() - started, 1)}
            if status == 200:
                entry.update(extra or {})
            else:
                entry["error"] = payload.get("error")
            RECENT.append(entry)
            del RECENT[:-10]
            return self._json(status, payload)

        def do_GET(self):
            path = urllib.parse.urlparse(self.path).path.rstrip("/") or "/"
            if not self._gate_ok(path):
                return
            if path == "/health":
                status, payload = health()
                return self._json(status, payload)
            return self._json(404, {"error": "not_found",
                                    "detail": f"No endpoint at {path}. See /health for service info."})

        def do_POST(self):
            path = urllib.parse.urlparse(self.path).path.rstrip("/") or "/"
            if not self._gate_ok(path):
                return
            if path not in routes:
                return self._json(404, {"error": "not_found",
                                        "detail": f"No endpoint at {path}. See /health for service info."})
            started = time.time()
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = 0
            if length <= 0 or length > MAX_BODY:
                return self._json(422, {"error": "invalid_body",
                                        "detail": f"Send a JSON body of at most {MAX_BODY} bytes."})
            raw = self.rfile.read(length)
            try:
                body = json.loads(raw.decode("utf-8"))
                if not isinstance(body, dict):
                    raise ValueError("body must be a JSON object")
            except Exception:
                return self._json(422, {"error": "invalid_body",
                                        "detail": "Request body must be a JSON object."})
            try:
                payload, err = routes[path](body)
            except Exception as exc:  # never a bare 500
                return self._record(path, 502, {
                    "error": "engine_upstream_error",
                    "detail": f"{type(exc).__name__}: {exc}"}, started)
            if err:
                return self._record(path, err[0], err[1], started)
            payload["_meta"] = {"service": SERVICE,
                                "version": VERSION,
                                "reasoning": reasoning_state(),
                                "latency_ms": round((time.time() - started) * 1000)}
            extra = {}
            if path in ("/perform", "/three-reads", "/table-read"):
                extra["duration_s"] = payload.get("duration_s")
            return self._record(path, 200, payload, started, extra)

    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    run_server(int(os.environ.get("PORT", "8116")))
