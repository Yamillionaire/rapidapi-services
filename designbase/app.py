"""DesignBase - design intelligence for creators (the user's own
product, 2026-10-31; RapidAPI lane build #15).

Design help, not image generation: structured color palettes,
structured design briefs, production-ready image-generation
prompts, and structured critiques of uploaded designs. It is NOT
an image generator and never returns one.

What is computed in code vs judged by the model, kept separate on
purpose:
- Code (deterministic): every hex value the model returns is
  validated against the hex grammar and invalid values are
  DROPPED, never repaired by guessing; WCAG contrast ratios are
  computed from the validated hex values; the /image-prompt
  endpoint assembles its prompt from a written prompt-grammar
  table (subject, composition, lighting, era lock, negative
  constraints) and needs no model at all; uploaded image format
  and dimensions are read from the file header in code.
- Model (the owner's Gemini API): palette selection for a brief,
  brief writing, and the critique's scored design judgments.
  Those scores are labeled as model judgments in the response.
  If the reasoning engine fails, the endpoint answers an
  explicit structured error, never an invented design judgment.

Engine states, reported honestly in /health:
- live: GEMINI_API_KEY is set; /palette, /design-brief and
  /critique run.
- awaiting_key: no key yet; those three endpoints answer an
  explicit 503 engine_not_configured (the lane's standing key
  step: the owner adds the same Gemini key the other Gemini
  services use). /image-prompt is code-assembled and keeps
  working in this state; /health says so.

The server keeps the lane scaffold's exact conventions (shared
with FactBase, XBase and DriftCheck): stdlib only, the RapidAPI
proxy-secret gate (401 JSON without the X-RapidAPI-Proxy-Secret
header, /health always open), and explicit structured JSON
errors for every failure.

Endpoints:
  POST /palette      {brief, count? (default 3, cap 5)}
                     -> validated palettes with computed contrast
  POST /design-brief {product, audience, vibe}
                     -> structured design brief
  POST /image-prompt {subject, style, era?, product?}
                     -> production-ready generation prompt
  POST /critique     multipart image upload -> scored critique
  GET  /health       -> service status, engine states, limits
Run: python3 app.py (PORT env, default 8116). No dependencies.
"""
import base64
import json
import os
import re
import time
import urllib.request
import urllib.error
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SERVICE = "designbase"
VERSION = "1.0.0"
BUILD = "2026-10-31-v1"
RECENT = []                       # last request outcomes (see /health)

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
# Per-model quotas on the owner's key are separate buckets: when the
# primary model answers 429, the same request is retried against the
# fallback model instead of failing the call. Fallback choice,
# measured on the owner's key during the FactBase build (2026-10-31):
# gemini-2.5-flash is retired for new users (404), gemini-3.7-flash
# and gemini-3.8-flash answered in ~77-84s (too slow),
# gemini-3.1-flash-lite answered in ~3s with clean JSON.
GEMINI_FALLBACK_MODEL = os.environ.get("GEMINI_FALLBACK_MODEL",
                                       "gemini-3.1-flash-lite")
GEMINI_BASE = os.environ.get(
    "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"
).rstrip("/")

MAX_BRIEF_CHARS = 2000
MAX_FIELD_CHARS = 500
MAX_BODY = 1_000_000              # JSON endpoints
MAX_IMAGE_BODY = 11_000_000       # /critique multipart envelope
MAX_IMAGE_BYTES = 8_000_000       # the image file itself
DEFAULT_PALETTE_COUNT = 3
MAX_PALETTE_COUNT = 5
GEMINI_TIMEOUT = 60
CRITIQUE_TIMEOUT = 120
UA = "DesignBase/1.0 (+https://rapidapi.com/YamilLittle/api/designbase)"

PALETTE_ROLES = ("primary", "secondary", "accent", "background", "text")
IMAGE_MIMES = ("image/png", "image/jpeg", "image/gif", "image/webp")


def engine_state():
    return "live" if GEMINI_KEY else "awaiting_key"


# --------------------------------------------------------------------------
# Gemini client (palette selection, brief writing, critique).
# One retry on transient upstream errors; a 429 on the primary model
# falls back to GEMINI_FALLBACK_MODEL (the FactBase/SwiftTranslate
# pattern, per-model quota buckets). One extension over FactBase,
# added after the build battery's critique call met a persistent
# primary-model 503: a persistent 500/503 on the primary also falls
# back instead of failing the call.
# --------------------------------------------------------------------------
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
                if exc.code in (500, 503) and model != models[-1]:
                    break  # primary persistently unavailable; the
                           # fallback model is a separate deployment
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
    outermost bracket span."""
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


# --------------------------------------------------------------------------
# Color math, computed in code. Hex values are validated against the
# hex grammar; invalid values are dropped, never repaired. Contrast
# ratios are the WCAG 2.x ratios computed from relative luminance.
# --------------------------------------------------------------------------
_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})$")


def normalize_hex(value):
    """Return the canonical #RRGGBB form of a valid hex string, or
    None when the value is not a hex color."""
    if not isinstance(value, str):
        return None
    v = value.strip()
    if not _HEX_RE.match(v):
        return None
    digits = v[1:]
    if len(digits) == 3:
        digits = "".join(ch * 2 for ch in digits)
    return "#" + digits.upper()


def _luminance(hex6):
    def channel(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r = channel(int(hex6[1:3], 16))
    g = channel(int(hex6[3:5], 16))
    b = channel(int(hex6[5:7], 16))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(hex_a, hex_b):
    la, lb = _luminance(hex_a), _luminance(hex_b)
    light, dark = max(la, lb), min(la, lb)
    return round((light + 0.05) / (dark + 0.05), 2)


def palette_contrast(colors):
    """Contrast block for one validated palette. Ratios are computed
    against the palette's background-role color(s); when the model
    returned no background role, ratios are computed against white
    and black and the block says so."""
    backgrounds = [c for c in colors if c["role"] == "background"]
    foregrounds = [c for c in colors if c["role"] != "background"]
    if not backgrounds:
        pairs = []
        for fg in foregrounds:
            pairs.append({
                "hex": fg["hex"], "role": fg["role"],
                "vs_white": contrast_ratio(fg["hex"], "#FFFFFF"),
                "vs_black": contrast_ratio(fg["hex"], "#000000")})
        return {"basis": "no background role in this palette; ratios "
                         "computed against #FFFFFF and #000000",
                "pairs": pairs}
    pairs = []
    for fg in foregrounds:
        entry = {"hex": fg["hex"], "role": fg["role"], "ratios": []}
        for bg in backgrounds:
            ratio = contrast_ratio(fg["hex"], bg["hex"])
            entry["ratios"].append({
                "background": bg["hex"], "ratio": ratio,
                "aa_normal_text": ratio >= 4.5,
                "aa_large_text": ratio >= 3.0})
        pairs.append(entry)
    return {"basis": "WCAG 2.x contrast ratios computed in code "
                     "against the palette's background color(s)",
            "pairs": pairs}


def clean_palette(raw_palette):
    """Validate one model palette. Returns (palette, dropped_count)
    or (None, dropped_count) when too few valid colors survive."""
    if not isinstance(raw_palette, dict):
        return None, 0
    colors, dropped = [], 0
    for raw_color in raw_palette.get("colors") or []:
        if not isinstance(raw_color, dict):
            dropped += 1
            continue
        hexval = normalize_hex(raw_color.get("hex"))
        if hexval is None:
            dropped += 1
            continue
        role = str(raw_color.get("role") or "").strip().lower()
        if role not in PALETTE_ROLES:
            role = "accent"
        colors.append({"hex": hexval,
                       "name": str(raw_color.get("name") or "").strip()
                               [:60],
                       "role": role})
    if len(colors) < 3:
        return None, dropped
    palette = {"name": str(raw_palette.get("name") or "").strip()[:80],
               "mood": str(raw_palette.get("mood") or "").strip()[:200],
               "colors": colors,
               "contrast": palette_contrast(colors)}
    return palette, dropped


def palette_pipeline(brief, count):
    prompt = (
        "You are the palette step of a design-intelligence service. "
        f"Propose {count} distinct color palettes suited to this "
        "design brief. Each palette needs 4 to 6 colors, each with: "
        "hex (a #RRGGBB value), name (a short evocative color name), "
        "and role (exactly one of: primary, secondary, accent, "
        "background, text). Every palette must include at least one "
        "background color and at least one primary color. Palettes "
        "must differ from each other in mood or hue family, not just "
        "in shade. Return JSON only: {\"palettes\": [{\"name\": "
        "\"...\", \"mood\": \"...\", \"colors\": [{\"hex\": "
        "\"#RRGGBB\", \"name\": \"...\", \"role\": \"...\"}]}]}\n\n"
        "BRIEF:\n" + brief)
    raw = gemini_generate([{"text": prompt}], json_mode=True)
    parsed = _parse_json(raw)
    raw_palettes = parsed.get("palettes") if isinstance(parsed, dict) \
        else parsed
    if not isinstance(raw_palettes, list):
        raise ValueError("model returned no palette list")
    palettes, dropped_total = [], 0
    for raw_palette in raw_palettes:
        palette, dropped = clean_palette(raw_palette)
        dropped_total += dropped
        if palette is not None:
            palettes.append(palette)
        if len(palettes) >= count:
            break
    if not palettes:
        raise ValueError("model returned no palette with at least "
                         "three valid hex colors")
    return {"brief": brief, "palette_count": len(palettes),
            "palettes": palettes,
            "validation": {"invalid_hex_dropped": dropped_total,
                           "note": "Hex values are validated in code; "
                                   "invalid values are dropped, never "
                                   "repaired. Contrast ratios are "
                                   "computed in code (WCAG 2.x)."}}


# --------------------------------------------------------------------------
# Design brief.
# --------------------------------------------------------------------------
def _clean_str(value, cap=600):
    return str(value or "").strip()[:cap]


def _clean_list(value, cap_items=8, cap_chars=300):
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item.strip()[:cap_chars])
        if len(out) >= cap_items:
            break
    return out


def design_brief_pipeline(product, audience, vibe):
    prompt = (
        "You are the design-brief step of a design-intelligence "
        "service. Write a structured design brief a working designer "
        "or image generator can execute without further questions. "
        "Be specific: name composition moves, type character, and "
        "color behavior, not adjectives alone. Return JSON only: "
        "{\"concept_direction\": \"...\", \"composition\": \"...\", "
        "\"typography\": {\"direction\": \"...\", \"headline\": "
        "\"...\", \"body\": \"...\"}, \"color_direction\": "
        "{\"direction\": \"...\", \"notes\": \"...\"}, \"dos\": "
        "[\"...\"], \"donts\": [\"...\"]}. Give 4 to 6 dos and 4 to "
        "6 donts, each one concrete and checkable.\n\n"
        f"PRODUCT: {product}\nAUDIENCE: {audience}\nVIBE: {vibe}")
    raw = gemini_generate([{"text": prompt}], json_mode=True)
    parsed = _parse_json(raw)
    if not isinstance(parsed, dict):
        raise ValueError("model returned no brief object")
    typography = parsed.get("typography") or {}
    color = parsed.get("color_direction") or {}
    brief = {
        "concept_direction": _clean_str(parsed.get("concept_direction")),
        "composition": _clean_str(parsed.get("composition")),
        "typography": {
            "direction": _clean_str(
                typography.get("direction") if isinstance(typography, dict)
                else typography),
            "headline": _clean_str(
                typography.get("headline") if isinstance(typography, dict)
                else ""),
            "body": _clean_str(
                typography.get("body") if isinstance(typography, dict)
                else "")},
        "color_direction": {
            "direction": _clean_str(
                color.get("direction") if isinstance(color, dict) else color),
            "notes": _clean_str(
                color.get("notes") if isinstance(color, dict) else "")},
        "dos": _clean_list(parsed.get("dos")),
        "donts": _clean_list(parsed.get("donts")),
    }
    if not brief["concept_direction"]:
        raise ValueError("model returned a brief with no concept "
                         "direction")
    return {"product": product, "audience": audience, "vibe": vibe,
            "brief": brief}


# --------------------------------------------------------------------------
# Image prompt builder. Pure code: a written prompt-grammar table.
# The same discipline as the owner's merch and character work:
# subject first, then medium/style, composition, lighting, an era
# lock when an era is given, product framing when a product is
# given, and explicit negative constraints (no text unless the
# caller's subject itself is lettering, no watermark, no modern
# objects in a locked era).
# --------------------------------------------------------------------------
STYLE_GRAMMAR = [
    # (needles, medium phrase, composition phrase, lighting phrase)
    (("die-cut sticker", "die cut sticker", "sticker"),
     "flat vector sticker illustration with a bold die-cut outline",
     "single centered subject, generous margin on all sides, plain "
     "contrasting backdrop",
     "flat even lighting, no shadows on the backdrop"),
    (("product photo", "product photography", "product shot"),
     "professional product photography",
     "subject centered on a clean studio backdrop, shot straight-on "
     "at product height, full product in frame with margin",
     "soft diffused studio lighting, controlled reflections, true "
     "color"),
    (("mockup",),
     "photorealistic product mockup photograph",
     "the product shown in real use, worn or held by a real-looking "
     "person where the product is wearable, environment kept simple "
     "so the product stays the subject",
     "natural light matched to the environment, realistic shadows"),
    (("photoreal", "photo", "photograph"),
     "photorealistic photograph, shot on a 35mm lens",
     "subject placed on a rule-of-thirds intersection, environment "
     "in soft focus behind the subject",
     "natural directional light, realistic shadows and skin texture"),
    (("comic", "graphic novel"),
     "bold comic-book illustration, strong ink outlines, halftone "
     "shading",
     "dynamic diagonal composition, subject large in frame, action "
     "reading left to right",
     "dramatic high-contrast lighting with a clear key light"),
    (("poster", "vintage"),
     "vintage screen-printed poster illustration, limited ink colors",
     "strong central emblem composition, layered foreground and "
     "background shapes, generous negative space for the title area",
     "flat graphic shading, no photographic gradients"),
    (("watercolor",),
     "hand-painted watercolor illustration, visible paper texture",
     "subject centered with breathing room, soft edge bleed into the "
     "paper",
     "soft luminous washes, light from the upper left"),
    (("3d render", "3d", "pixar", "render"),
     "high-quality 3D render, physically based materials",
     "subject centered, camera at a slight three-quarter angle, "
     "clean environment",
     "three-point studio lighting, soft shadows, subtle rim light"),
    (("vector", "flat", "logo", "emblem", "icon"),
     "flat vector illustration, clean shapes, no gradients except "
     "where the style demands them",
     "single centered subject, symmetrical where the subject allows, "
     "plain backdrop",
     "flat even illumination, no cast shadows"),
]

GENERIC_GRAMMAR = ("illustration in the named style",
                   "subject large and centered, clear silhouette, "
                   "environment kept secondary",
                   "clear directional lighting that models the "
                   "subject, no flat wash")


def match_style(style_text):
    low = style_text.lower()
    for needles, medium, composition, lighting in STYLE_GRAMMAR:
        if any(n in low for n in needles):
            return medium, composition, lighting, True
    return (f"illustration in this style: {style_text}",
            GENERIC_GRAMMAR[1], GENERIC_GRAMMAR[2], False)


def image_prompt_pipeline(subject, style, era, product):
    medium, composition, lighting, preset_hit = match_style(style)
    parts = [subject, medium, composition, lighting]
    components = {"subject": subject, "style": style,
                  "medium": medium, "composition": composition,
                  "lighting": lighting}
    negatives = ["no text", "no lettering", "no words",
                 "no watermark", "no signature",
                 "no distorted hands", "no extra limbs",
                 "no blurry or duplicated subject"]
    notes = ["Assembled in code from the prompt grammar; no model "
             "call was made."]
    if era:
        era_lock = (f"Era lock: the scene is set in {era}. All "
                    "clothing, hairstyles, props, vehicles, signage "
                    f"and architecture must be period-accurate for "
                    f"{era}; nothing introduced after that period may "
                    "appear.")
        parts.append(era_lock)
        components["era_lock"] = era_lock
        negatives += ["no modern objects", "no anachronisms",
                      "no contemporary clothing or devices"]
    if product:
        product_note = (f"Intended for {product}: keep the subject "
                        "centered with clear margins on every side, "
                        "and keep colors strong enough to survive "
                        "print reproduction.")
        parts.append(product_note)
        components["product"] = product_note
        notes.append("Product framing applied; verify print margins "
                     "on the target product before production.")
    if not preset_hit:
        notes.append("Style did not match a built-in grammar preset; "
                     "generic composition and lighting were used. "
                     "Preset styles: sticker, product photo, mockup, "
                     "photoreal, comic, poster/vintage, watercolor, "
                     "3d render, vector/emblem.")
    prompt = ". ".join(p.strip().rstrip(".") for p in parts if p.strip())
    return {"prompt": prompt,
            "negative_prompt": ", ".join(negatives),
            "components": components, "notes": notes}


# --------------------------------------------------------------------------
# Critique. The scored judgments are the model's (labeled as such);
# the file's format and dimensions are read from its header in code,
# and every returned score is validated and clamped in code.
# --------------------------------------------------------------------------
def image_info(data):
    """Format and dimensions from the file header, in code. Returns
    (mime, width, height); width/height are None when the header
    variant does not carry them at a fixed offset."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        width = int.from_bytes(data[16:20], "big")
        height = int.from_bytes(data[20:24], "big")
        return "image/png", width, height
    if data[:3] == b"\xff\xd8\xff":
        width = height = None
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                break
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2):
                height = int.from_bytes(data[i + 5:i + 7], "big")
                width = int.from_bytes(data[i + 7:i + 9], "big")
                break
            if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            length = int.from_bytes(data[i + 2:i + 4], "big")
            if length < 2:
                break
            i += 2 + length
        return "image/jpeg", width, height
    if data[:6] in (b"GIF87a", b"GIF89a"):
        width = int.from_bytes(data[6:8], "little")
        height = int.from_bytes(data[8:10], "little")
        return "image/gif", width, height
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        width = height = None
        if data[12:16] == b"VP8X" and len(data) >= 30:
            width = int.from_bytes(data[24:27], "little") + 1
            height = int.from_bytes(data[27:30], "little") + 1
        return "image/webp", width, height
    return None, None, None


def _clean_score(value):
    """A model score, validated in code: numeric, clamped to
    0-10, one decimal. Anything else becomes None (not scored),
    never a guessed number."""
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    return round(max(0.0, min(10.0, score)), 1)


def critique_pipeline(image_bytes, mime, context):
    b64 = base64.b64encode(image_bytes).decode()
    focus = (f" The design is intended as: {context}." if context
             else "")
    prompt = (
        "You are the critique step of a design-intelligence service. "
        "Critique the uploaded design on four dimensions, each scored "
        "0 to 10 (10 is professional-grade): composition (balance, "
        "hierarchy, use of space), color_harmony (palette cohesion, "
        "contrast, mood fit), legibility (any text and key shapes "
        "readable at a glance and at small size), focal_point (one "
        "clear place the eye lands first). Ground every judgment in "
        "what is actually visible in the image. Fixes must be "
        "specific and executable (name the element and the change), "
        "never generic advice. Return JSON only: {\"summary\": "
        "\"...\", \"scores\": {\"composition\": {\"score\": 0, "
        "\"note\": \"...\"}, \"color_harmony\": {\"score\": 0, "
        "\"note\": \"...\"}, \"legibility\": {\"score\": 0, \"note\": "
        "\"...\"}, \"focal_point\": {\"score\": 0, \"note\": \"...\"}}, "
        "\"strengths\": [\"...\"], \"fixes\": [{\"issue\": \"...\", "
        "\"fix\": \"...\", \"priority\": \"high|medium|low\"}]}. "
        "Give 3 to 6 fixes, ordered by impact." + focus)
    raw = gemini_generate(
        [{"text": prompt},
         {"inlineData": {"mimeType": mime, "data": b64}}],
        json_mode=True, timeout=CRITIQUE_TIMEOUT)
    parsed = _parse_json(raw)
    if not isinstance(parsed, dict):
        raise ValueError("model returned no critique object")
    raw_scores = parsed.get("scores") or {}
    scores = {}
    for dimension in ("composition", "color_harmony", "legibility",
                      "focal_point"):
        entry = raw_scores.get(dimension) or {}
        if not isinstance(entry, dict):
            entry = {"score": entry}
        score = _clean_score(entry.get("score"))
        scores[dimension] = {
            "score": score,
            "note": _clean_str(entry.get("note"), 400)
                    if score is not None else
                    "Not scored: the engine returned no usable score "
                    "for this dimension."}
    fixes = []
    for raw_fix in parsed.get("fixes") or []:
        if not isinstance(raw_fix, dict):
            continue
        issue = _clean_str(raw_fix.get("issue"), 300)
        fix = _clean_str(raw_fix.get("fix"), 300)
        if not issue or not fix:
            continue
        priority = str(raw_fix.get("priority") or "").strip().lower()
        if priority not in ("high", "medium", "low"):
            priority = "medium"
        fixes.append({"issue": issue, "fix": fix,
                      "priority": priority})
        if len(fixes) >= 10:
            break
    scored = [s["score"] for s in scores.values()
              if s["score"] is not None]
    overall = round(sum(scored) / len(scored), 1) if scored else None
    return {"summary": _clean_str(parsed.get("summary"), 800),
            "scores": scores, "overall_score": overall,
            "strengths": _clean_list(parsed.get("strengths"), 6, 300),
            "fixes": fixes,
            "judgment_source": "Scores and fixes are model judgments "
                               "(Gemini vision) grounded in the "
                               "uploaded image; format and dimensions "
                               "in this response are read from the "
                               "file header in code."}


# --------------------------------------------------------------------------
# Health.
# --------------------------------------------------------------------------
def health():
    state = engine_state()
    return 200, {
        "status": "ok", "service": SERVICE, "version": VERSION,
        "build": BUILD,
        "engines": {
            "reasoning": {"state": state, "model": GEMINI_MODEL,
                          "fallback_model": GEMINI_FALLBACK_MODEL,
                          "role": "palette selection, design-brief "
                                  "writing, and critique judgments "
                                  "(/palette, /design-brief, "
                                  "/critique)"},
            "prompt_builder": {"state": "live",
                               "engine": "code (deterministic "
                                         "prompt-grammar assembly)",
                               "role": "/image-prompt; needs no "
                                       "model and works while the "
                                       "reasoning engine awaits its "
                                       "key"},
            "color_math": {"state": "live", "engine": "code",
                           "role": "hex validation (invalid values "
                                   "dropped, never repaired) and "
                                   "WCAG 2.x contrast ratios for "
                                   "/palette"}},
        "limits": {"max_brief_chars": MAX_BRIEF_CHARS,
                   "max_field_chars": MAX_FIELD_CHARS,
                   "default_palette_count": DEFAULT_PALETTE_COUNT,
                   "max_palette_count": MAX_PALETTE_COUNT,
                   "max_image_bytes": MAX_IMAGE_BYTES,
                   "image_formats": ["png", "jpeg", "gif", "webp"]},
        "endpoints": ["POST /palette", "POST /design-brief",
                      "POST /image-prompt", "POST /critique",
                      "GET /health"],
        "recent_requests": RECENT[-5:],
        "note": "DesignBase returns design intelligence (palettes, "
                "briefs, image-generation prompts, critiques); it "
                "does not generate images. Critique scores are "
                "labeled model judgments; hex values and contrast "
                "ratios are computed in code."}


# --------------------------------------------------------------------------
# Server: scaffold conventions (gate + structured errors).
# --------------------------------------------------------------------------
def _not_configured():
    return 503, {"error": "engine_not_configured",
                 "detail": "No Gemini API key is configured on this "
                           "deployment yet, so this endpoint is not "
                           "available. The service owner must add "
                           "GEMINI_API_KEY to enable it. "
                           "/image-prompt is code-assembled and "
                           "remains available."}


def _parse_multipart(body, content_type):
    """Minimal multipart/form-data parser: returns {field_name:
    (filename, bytes)} for file parts and {field_name: str} for
    plain fields (the FactBase pattern)."""
    m = re.search(r"boundary=(.+)$", content_type or "")
    if not m:
        return None
    boundary = m.group(1).strip().strip('"').encode()
    parts = {}
    for chunk in body.split(b"--" + boundary):
        if b"\r\n\r\n" not in chunk:
            continue
        head, data = chunk.split(b"\r\n\r\n", 1)
        if data.endswith(b"\r\n"):
            data = data[:-2]
        if data.endswith(b"--"):
            data = data[:-2]
        name_m = re.search(rb'name="([^"]+)"', head)
        if not name_m:
            continue
        name = name_m.group(1).decode("utf-8", "replace")
        file_m = re.search(rb'filename="([^"]*)"', head)
        if file_m:
            parts[name] = (file_m.group(1).decode("utf-8", "replace"),
                           data)
        else:
            parts[name] = data.decode("utf-8", "replace")
    return parts


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

        def _read_body(self, cap):
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = 0
            if length <= 0 or length > cap:
                return None
            return self.rfile.read(length)

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
            if path not in ("/palette", "/design-brief",
                            "/image-prompt", "/critique"):
                return self._json(404, {"error": "not_found",
                                        "detail": f"No endpoint at {path}. See /health for service info."})
            started = time.time()
            if path == "/critique":
                return self._critique(started)
            return self._json_endpoint(path, started)

        # -- JSON endpoints -------------------------------------------
        def _json_endpoint(self, path, started):
            raw = self._read_body(MAX_BODY)
            if raw is None:
                return self._json(422, {"error": "invalid_body",
                                        "detail": f"Send a JSON body of at most {MAX_BODY} bytes."})
            try:
                body = json.loads(raw.decode("utf-8"))
                if not isinstance(body, dict):
                    raise ValueError("body must be a JSON object")
            except Exception:
                return self._json(422, {"error": "invalid_body",
                                        "detail": "Request body must be a JSON object."})

            if path == "/image-prompt":
                return self._image_prompt(body, started)
            if engine_state() != "live":
                return self._record(path, *_not_configured(), started)
            if path == "/palette":
                return self._palette(body, started)
            return self._design_brief(body, started)

        def _field(self, body, name, required=True):
            value = body.get(name)
            if not isinstance(value, str) or not value.strip():
                return None
            return value.strip()

        def _palette(self, body, started):
            brief = self._field(body, "brief")
            if brief is None:
                return self._record("/palette", *(422, {
                    "error": "missing_parameter",
                    "detail": "Provide a non-empty 'brief'."}), started)
            if len(brief) > MAX_BRIEF_CHARS:
                return self._record("/palette", *(422, {
                    "error": "text_too_long",
                    "detail": f"Brief is {len(brief)} characters; the maximum is {MAX_BRIEF_CHARS}."}), started)
            count = body.get("count", DEFAULT_PALETTE_COUNT)
            try:
                count = max(1, min(int(count), MAX_PALETTE_COUNT))
            except (TypeError, ValueError):
                count = DEFAULT_PALETTE_COUNT
            try:
                result = palette_pipeline(brief, count)
            except Exception as exc:
                return self._record("/palette", *(502, {
                    "error": "engine_upstream_error",
                    "detail": f"{type(exc).__name__}: {exc}"}), started)
            payload = dict(result)
            payload["_meta"] = {"service": SERVICE, "version": VERSION,
                                "engine": engine_state(),
                                "latency_ms": round((time.time() - started) * 1000)}
            return self._record("/palette", 200, payload, started,
                                {"count": result["palette_count"]})

        def _design_brief(self, body, started):
            fields = {}
            for name in ("product", "audience", "vibe"):
                value = self._field(body, name)
                if value is None:
                    return self._record("/design-brief", *(422, {
                        "error": "missing_parameter",
                        "detail": f"Provide a non-empty '{name}'."}),
                        started)
                if len(value) > MAX_FIELD_CHARS:
                    return self._record("/design-brief", *(422, {
                        "error": "text_too_long",
                        "detail": f"'{name}' is {len(value)} characters; the maximum is {MAX_FIELD_CHARS}."}), started)
                fields[name] = value
            try:
                result = design_brief_pipeline(**fields)
            except Exception as exc:
                return self._record("/design-brief", *(502, {
                    "error": "engine_upstream_error",
                    "detail": f"{type(exc).__name__}: {exc}"}), started)
            payload = dict(result)
            payload["_meta"] = {"service": SERVICE, "version": VERSION,
                                "engine": engine_state(),
                                "latency_ms": round((time.time() - started) * 1000)}
            return self._record("/design-brief", 200, payload, started)

        def _image_prompt(self, body, started):
            subject = self._field(body, "subject")
            if subject is None:
                return self._record("/image-prompt", *(422, {
                    "error": "missing_parameter",
                    "detail": "Provide a non-empty 'subject'."}), started)
            style = self._field(body, "style")
            if style is None:
                return self._record("/image-prompt", *(422, {
                    "error": "missing_parameter",
                    "detail": "Provide a non-empty 'style'."}), started)
            for name, value in (("subject", subject), ("style", style)):
                if len(value) > MAX_FIELD_CHARS:
                    return self._record("/image-prompt", *(422, {
                        "error": "text_too_long",
                        "detail": f"'{name}' is {len(value)} characters; the maximum is {MAX_FIELD_CHARS}."}), started)
            era = self._field(body, "era", required=False)
            product = self._field(body, "product", required=False)
            result = image_prompt_pipeline(subject, style, era, product)
            payload = dict(result)
            payload["_meta"] = {"service": SERVICE, "version": VERSION,
                                "engine": "code",
                                "latency_ms": round((time.time() - started) * 1000)}
            return self._record("/image-prompt", 200, payload, started)

        # -- Critique (multipart image upload) -------------------------
        def _critique(self, started):
            if engine_state() != "live":
                return self._record("/critique", *_not_configured(),
                                    started)
            raw = self._read_body(MAX_IMAGE_BODY)
            if raw is None:
                return self._json(422, {"error": "invalid_body",
                                        "detail": f"Send a multipart image upload of at most {MAX_IMAGE_BODY} bytes."})
            parts = _parse_multipart(
                raw, self.headers.get("Content-Type") or "")
            if not parts:
                return self._record("/critique", *(422, {
                    "error": "invalid_body",
                    "detail": "Request must be multipart/form-data with an image file part."}), started)
            upload = None
            context = ""
            for name, value in parts.items():
                if isinstance(value, tuple) and upload is None:
                    upload = value
                elif name == "context" and isinstance(value, str):
                    context = value.strip()[:MAX_FIELD_CHARS]
            if upload is None:
                return self._record("/critique", *(422, {
                    "error": "missing_parameter",
                    "detail": "No file part found in the multipart body."}), started)
            filename, data = upload
            if not data:
                return self._record("/critique", *(422, {
                    "error": "missing_parameter",
                    "detail": "The uploaded image file is empty."}),
                    started)
            if len(data) > MAX_IMAGE_BYTES:
                return self._record("/critique", *(422, {
                    "error": "image_too_large",
                    "detail": f"Image is {len(data)} bytes; the maximum is {MAX_IMAGE_BYTES}."}), started)
            mime, width, height = image_info(data)
            if mime is None:
                return self._record("/critique", *(422, {
                    "error": "unsupported_format",
                    "detail": "The uploaded file is not a PNG, JPEG, GIF or WebP image (checked from the file header, not the filename)."}), started)
            try:
                result = critique_pipeline(data, mime, context)
            except Exception as exc:
                return self._record("/critique", *(502, {
                    "error": "engine_upstream_error",
                    "detail": f"{type(exc).__name__}: {exc}"}), started)
            payload = dict(result)
            payload["image"] = {"filename": filename, "format": mime,
                                "bytes": len(data), "width": width,
                                "height": height}
            if context:
                payload["context"] = context
            payload["_meta"] = {"service": SERVICE, "version": VERSION,
                                "engine": engine_state(),
                                "latency_ms": round((time.time() - started) * 1000)}
            return self._record("/critique", 200, payload, started,
                                {"overall": result["overall_score"]})

    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    run_server(int(os.environ.get("PORT", "8116")))
