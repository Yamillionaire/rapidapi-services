"""SpotBase - brief-to-streaming-TV-ad-package API (the user's own product, 2026-11-01).

Reverse engineered from Vibe.co's prompt-to-streaming-TV product
(see docs/vibe-teardown-2026-11-01.md): Vibe fuses an AI creative
step with a licensed media step. This service is the creative step
as an API. Submit a brief (brand, product, audience, offer, call
to action, tone, 15 or 30 seconds) and it returns the complete ad
package: a timed script with word budgets enforced in code, a
shot-by-shot list with ready-to-paste Higgsfield generation
prompts, the voiceover text with a ready payload for our own
SwiftRead API, end-card copy, the CTV delivery spec and a
compliance checklist, plus a spec checker for the finished file.

It does NOT place ads on TV and never claims to: placement needs
the advertiser's own funded account on Vibe or another DSP, which
is a user tap. It does not render video or synthesize audio
either; generation happens in the caller's lane from the package.

Engines, following the fleet's SwiftRewrite pattern:
- Built-in template engine: always live, zero dependency, zero
  marginal cost. Tone-keyed segment templates filled from the
  brief, timing and word budgets computed in code.
- Gemini engine: when GEMINI_API_KEY is set (the same key
  SwiftRewrite and SwiftTranslate use), Gemini Flash drafts the
  script and shot visuals under a strict JSON contract; the same
  in-code budget enforcement then validates the result. Any
  failure falls back to the built-in engine and the response
  labels which engine actually produced the package.

The server follows the fleet's exact conventions (SwiftRead's):
the RapidAPI proxy-secret gate (401 JSON without the
X-RapidAPI-Proxy-Secret header, /health always open) and explicit
structured JSON errors. Stdlib only.

Endpoints:
  POST /ad-package   {brief}                 -> the full package
  POST /script       {brief}                 -> the timed script
  POST /shots        {brief}                 -> the shot list
  POST /check-spec   {measured file specs}   -> verdicts + fixes
  GET  /delivery-spec                        -> spec + checklist
  GET  /tones                                -> tones + voices
  GET  /health                               -> service status
Run: python3 app.py (PORT env, default 8118). No dependencies.
"""
import json
import os
import re
import time
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

SERVICE = "spotbase"
BUILD = "2026-11-01-v1"
MAX_BODY = 60_000           # request body byte cap
WORDS_PER_SECOND = 2.5      # natural voiceover pace, 150 wpm
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

# ---------------------------------------------------------------- tones

TONES = {
    "warm": {
        "voice": "en-US-AriaNeural", "voice_name": "Aria",
        "voice_style": "Warm, natural newsreader",
        "music": "Warm acoustic bed, gentle piano and soft strings, 90-110 BPM, hopeful and human, low under voiceover.",
        "visual_mood": "warm natural light, golden tones, real homes and real faces, gentle camera movement",
    },
    "bold": {
        "voice": "en-US-GuyNeural", "voice_name": "Guy",
        "voice_style": "Steady, broadcast",
        "music": "Confident modern beat, punchy drums and bass, 110-125 BPM, energetic but clean, low under voiceover.",
        "visual_mood": "high contrast light, strong color, dynamic camera moves, confident subjects",
    },
    "playful": {
        "voice": "en-US-JennyNeural", "voice_name": "Jenny",
        "voice_style": "Friendly, conversational",
        "music": "Light playful pop bed, ukulele or marimba touches, 100-120 BPM, smiling energy, low under voiceover.",
        "visual_mood": "bright daylight, saturated friendly color, quick playful cuts, people laughing naturally",
    },
    "premium": {
        "voice": "en-US-MichelleNeural", "voice_name": "Michelle",
        "voice_style": "Clear, professional",
        "music": "Minimal premium score, sparse piano and ambient pads, 80-95 BPM, quiet confidence, low under voiceover.",
        "visual_mood": "soft cinematic light, muted elegant palette, slow deliberate camera moves, uncluttered frames",
    },
    "urgent": {
        "voice": "en-US-EricNeural", "voice_name": "Eric",
        "voice_style": "Measured, articulate",
        "music": "Driving pulse bed, ticking percussion feel, 120-130 BPM, momentum without panic, low under voiceover.",
        "visual_mood": "crisp light, fast purposeful movement, close-ups on hands and product in action",
    },
    "trustworthy": {
        "voice": "en-US-ChristopherNeural", "voice_name": "Christopher",
        "voice_style": "Calm, documentary",
        "music": "Calm documentary bed, soft guitar and piano, 85-100 BPM, steady and sincere, low under voiceover.",
        "visual_mood": "honest natural light, documentary realism, steady camera, real locations",
    },
}

# ------------------------------------------------------- script structure

# role, start_s, end_s, word target. Budgets: 30s spot max 75 words,
# 15s spot max 38 words, end-card read inside the same budget.
PLANS = {
    30: [("hook", 0.0, 5.0, 12), ("problem", 5.0, 11.0, 15),
         ("product", 11.0, 19.0, 20), ("offer", 19.0, 25.0, 14),
         ("end_card", 25.0, 30.0, 10)],
    15: [("hook", 0.0, 4.0, 10), ("pitch", 4.0, 11.0, 16),
         ("end_card", 11.0, 15.0, 9)],
}
WORD_BUDGET = {30: 72, 15: 36}   # under the raw 75/38 maxima, leaving air at the tail

# Segment voiceover templates per role, keyed lightly by tone where
# the tone changes the register; {b}=brand {p}=product {a}=audience
# {o}=offer {c}=call to action {w}=website.
VO_TEMPLATES = {
    "hook": {
        "warm": "For {a}, life runs better with a little help.",
        "bold": "{a_cap}: this one is for you.",
        "playful": "Hey {a}, watch this.",
        "premium": "Some things are simply done better.",
        "urgent": "{a_cap}, this cannot wait much longer.",
        "trustworthy": "For {a}, trust is earned one day at a time.",
    },
    "problem": {
        "_": "The old way takes too long, costs too much, and still leaves the job half done.",
    },
    "product": {
        "_": "Meet {p} from {b}: made for {a}, simple to start, and built to do the job right.",
    },
    "offer": {
        "_": "Right now, {o}.",
    },
    "pitch": {
        "_": "Meet {p} from {b}, made for {a}. And right now, {o}.",
    },
    "end_card": {
        "_": "{b}. {c}. {w}",
    },
}

SHOT_VISUALS = {
    "hook": "Opening beat: a relatable {a} moment, mid-action, the need visible on their face before any product appears.",
    "problem": "The friction: the old, slow way of doing the job, close on the frustration, then a breath before the turn.",
    "product": "The product in real use: {p} in the hands of {a}, the job visibly getting done, one clear hero angle.",
    "offer": "The payoff: the finished result and the relief on the customer's face, offer energy without any text in frame.",
    "pitch": "The product in real use: {p} in the hands of {a}, the job visibly getting done, energy building toward the close.",
    "end_card": "Clean end-card background plate: the product setting at rest, calm frame with open space in the center for text added in edit.",
}

CAMERA = {
    "hook": "slow push-in from medium shot to close-up",
    "problem": "handheld-feel close-ups, slight movement, then a held beat",
    "product": "smooth tracking shot following the action, ending on a hero angle",
    "offer": "gentle crane-up reveal of the finished result",
    "pitch": "smooth tracking shot following the action, ending on a hero angle",
    "end_card": "locked-off static frame, no camera movement",
}

NEGATIVE_PROMPT = ("text, words, letters, numbers, captions, watermark, logo, "
                   "distorted hands, extra fingers, deformed faces, cartoon, "
                   "low resolution, blurry, oversaturated")

# ------------------------------------------------------------ CTV spec

DELIVERY_SPEC = {
    "summary": "Streaming TV (CTV) delivery spec: Vibe.co's published upload requirements plus the industry common denominator (Simulmedia 2026 CTV specs, Google DV360 creative guidelines). A file that passes every item is accepted by Vibe and matches what major publishers ask for.",
    "video": {
        "aspect_ratio": "16:9",
        "resolution_recommended": "1920x1080",
        "resolution_minimum": "1280x720",
        "format": "mp4 (H.264); mov accepted by many publishers, Vibe requires mp4",
        "duration_seconds": "15 or 30 standard; Vibe accepts 5 to 90 and rejects anything over 90",
        "frame_rate": "constant; one of 23.976, 24, 25, 29.97, 30",
        "bitrate_kbps_minimum_vibe": 2500,
        "bitrate_mbps_recommended_source": "15-30",
        "file_size_mb_maximum_vibe": 100,
    },
    "audio": {
        "channels": "stereo (2.0)",
        "codec": "AAC or PCM",
        "sample_rate_hz": 48000,
        "bitrate_kbps_minimum": 192,
        "loudness_lkfs": "-24 integrated, plus or minus 2 (CALM Act / ATSC A/85)",
        "true_peak_dbtp_maximum": -2.0,
        "duration_match": "audio and video durations match within about 500 ms",
    },
    "frame_and_content": [
        "No slates, countdowns, color bars or black leader at head or tail",
        "No decorative letterboxing or pillarboxing",
        "All burned-in text added in edit, never baked into generated footage",
        "Headline, logo and call to action inside title-safe margins (center 90 percent of frame)",
        "QR code, if used, large, high contrast, held at least 5 seconds, clear of platform UI zones",
        "Nothing essential in the outer 5 percent of the frame",
    ],
    "captions": "Some publishers require closed captions with the creative; prepare a caption file for the voiceover text either way.",
    "delivery_note": "Direct upload to Vibe takes the mp4 itself. Programmatic delivery through other DSPs runs on VAST tags; VPAID is not supported on CTV devices.",
}

COMPLIANCE_CHECKLIST = [
    {"step": "Duration", "check": "Spot is exactly the booked length (15 or 30 s) and under Vibe's 90 s ceiling."},
    {"step": "Picture", "check": "1920x1080 (or at least 1280x720), 16:9, constant frame rate, progressive, no letterbox decoration."},
    {"step": "File", "check": "mp4 container, H.264 video, at or under 100 MB for Vibe, bitrate at or above 2,500 kbps."},
    {"step": "Loudness", "check": "Integrated loudness measured at -24 LKFS plus or minus 2 with a real loudness meter (not RMS); true peak at or below -2 dBTP."},
    {"step": "Audio", "check": "Stereo, 48 kHz, 192 kbps or better, voiceover clear over the music bed, audio and video durations matching."},
    {"step": "Text and safe zones", "check": "Every word on screen was added in edit; headline, logo and CTA sit inside the center 90 percent; nothing essential touches the edges."},
    {"step": "Claims", "check": "Every claim in the script and on the end card is true of the product and substantiated; prices and offers match the landing page; required disclosures are legible for their full hold."},
    {"step": "Music and rights", "check": "Music is licensed for commercial TV use or original and cleared; no uncleared samples; talent and likeness releases on file for anyone recognizable."},
    {"step": "Captions", "check": "Caption file prepared from the final voiceover text, timed to the finished cut."},
    {"step": "End card", "check": "Brand, call to action and destination held for the final 4-5 seconds; QR code (if any) scans from a TV distance in a real test."},
    {"step": "Placement boundary", "check": "A passing file is placement-ready, not placed. Going live still needs the advertiser's own funded account on Vibe or another DSP, its compliance review, targeting and budget. SpotBase does not place ads."},
]

# ---------------------------------------------------------------- input

def _clean(value, cap=300):
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value).strip()[:cap]


def parse_brief(body):
    """Returns (brief, error) where error is a (status, payload) tuple."""
    if not isinstance(body, dict):
        return None, (422, {"error": "invalid_body",
                            "detail": "Request body must be a JSON object."})
    brief = {
        "brand_name": _clean(body.get("brand_name"), 80),
        "product": _clean(body.get("product"), 160),
        "audience": _clean(body.get("audience"), 160) or "busy people",
        "offer": _clean(body.get("offer"), 200),
        "call_to_action": _clean(body.get("call_to_action"), 80) or "Learn more",
        "website": _clean(body.get("website"), 120),
        "tone": _clean(body.get("tone"), 30).lower() or "warm",
        "duration_seconds": body.get("duration_seconds", 30),
    }
    if not brief["brand_name"]:
        return None, (422, {"error": "missing_field",
                            "detail": "brand_name is required."})
    if not brief["product"]:
        return None, (422, {"error": "missing_field",
                            "detail": "product is required."})
    if brief["tone"] not in TONES:
        return None, (422, {"error": "invalid_parameter",
                            "detail": f"tone must be one of: {', '.join(TONES)}."})
    dur = brief["duration_seconds"]
    if isinstance(dur, str) and dur.isdigit():
        dur = int(dur)
    if dur not in (15, 30):
        return None, (422, {"error": "invalid_parameter",
                            "detail": "duration_seconds must be 15 or 30, the standard streaming TV spot lengths."})
    brief["duration_seconds"] = dur
    if not brief["offer"]:
        brief["offer"] = f"discover what {brief['product']} can do for you"
        brief["_offer_defaulted"] = True
    return brief, None


def word_count(text):
    return len([w for w in re.split(r"\s+", text.strip()) if w])


def fill(template, brief):
    a = brief["audience"]
    return (template.replace("{a_cap}", a[:1].upper() + a[1:])
            .replace("{a}", a)
            .replace("{b}", brief["brand_name"])
            .replace("{p}", brief["product"])
            .replace("{o}", brief["offer"].rstrip("."))
            .replace("{c}", brief["call_to_action"].rstrip("."))
            .replace("{w}", brief["website"]))


def builtin_script(brief):
    """Tone-keyed templates filled from the brief; budgets enforced by caller."""
    tone = brief["tone"]
    segments = []
    for role, start, end, target in PLANS[brief["duration_seconds"]]:
        table = VO_TEMPLATES[role]
        text = fill(table.get(tone) or table["_"], brief)
        segments.append({"role": role, "start_s": start, "end_s": end,
                         "voiceover": text, "words": word_count(text),
                         "word_target": target})
    return segments


def builtin_visuals(brief):
    visuals = {}
    for role in SHOT_VISUALS:
        visuals[role] = {"visual": fill(SHOT_VISUALS[role], brief),
                         "camera": CAMERA[role]}
    return visuals


def enforce_budget(segments, duration):
    """Bring the script inside its word budget, trimming in code.

    Long caller fields (a full-sentence audience, a descriptive
    product name) can push the filled templates over budget, so
    enforcement is layered: first sentence only for the
    offer-bearing segment, then trailing clauses dropped from the
    longest segments, then a hard trim to each segment's word
    target. The end card is exempt (it carries the brand, the call
    to action and the destination). Every trim is flagged, never
    silent. Returns (segments, flags, total_words).
    """
    budget = WORD_BUDGET[duration]
    flags = []

    def total():
        return sum(s["words"] for s in segments)

    if total() > budget:
        for role in ("offer", "pitch"):
            seg = next((s for s in segments if s["role"] == role), None)
            if seg is None:
                continue
            first = re.split(r"(?<=[.!?])\s+", seg["voiceover"])[0]
            if word_count(first) < seg["words"]:
                seg["voiceover"] = first
                seg["words"] = word_count(first)
                flags.append(f"trimmed_{role}_to_first_sentence")
            if total() <= budget:
                break
    while total() > budget:
        candidates = [s for s in segments if s["role"] != "end_card"
                      and s["words"] > max(4, s["word_target"] // 2)]
        if not candidates:
            break
        seg = max(candidates, key=lambda s: s["words"])
        text = seg["voiceover"]
        if ", " in text:
            trimmed = text.rsplit(", ", 1)[0].rstrip(",") + "."
        else:
            trimmed = " ".join(text.split()[:seg["word_target"]]).rstrip(",;:") + "."
        if word_count(trimmed) >= seg["words"]:
            break
        seg["voiceover"] = trimmed
        seg["words"] = word_count(trimmed)
        flag = f"trimmed_{seg['role']}_clauses"
        if flag not in flags:
            flags.append(flag)
    if total() > budget:
        flags.append("over_budget_after_trim")
    return segments, flags, total()


def gemini_draft(brief):
    """Draft script segments and shot visuals with Gemini Flash.

    Strict JSON contract; raises on any deviation so the caller can
    fall back to the built-in engine and label the result.
    """
    plan = PLANS[brief["duration_seconds"]]
    plan_text = "; ".join(f"{r} {s}-{e}s about {t} words" for r, s, e, t in plan)
    prompt = (
        "You are a television commercial copywriter. Write a "
        f"{brief['duration_seconds']} second streaming TV ad script and shot plan "
        f"for this brief. Brand: {brief['brand_name']}. Product: {brief['product']}. "
        f"Audience: {brief['audience']}. Offer: {brief['offer']}. "
        f"Call to action: {brief['call_to_action']}. Website: {brief['website'] or 'none'}. "
        f"Tone: {brief['tone']}. Segments: {plan_text}. Keep every claim generic to the "
        "brief: invent no prices, statistics, awards or facts that are not in the brief. "
        "Return ONLY a JSON object of the form "
        "{\"segments\": [{\"role\": \"hook\", \"voiceover\": \"...\"}], "
        "\"visuals\": {\"hook\": {\"visual\": \"...\", \"camera\": \"...\"}}} "
        "with one segment per listed role and one visual per role.")
    payload = {"contents": [{"parts": [{"text": prompt}]}],
               "generationConfig": {"temperature": 0.7, "maxOutputTokens": 2048}}
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": GEMINI_KEY},
        method="POST")
    with urllib.request.urlopen(req, timeout=40) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    draft = json.loads(text)
    segments = []
    by_role = {s["role"]: s["voiceover"] for s in draft["segments"]}
    for role, start, end, target in plan:
        vo = _clean(by_role[role], 600)
        if not vo:
            raise ValueError(f"missing segment {role}")
        segments.append({"role": role, "start_s": start, "end_s": end,
                         "voiceover": vo, "words": word_count(vo),
                         "word_target": target})
    visuals = {}
    for role, _s, _e, _t in plan:
        v = draft["visuals"][role]
        visuals[role] = {"visual": _clean(v["visual"], 500),
                         "camera": _clean(v["camera"], 160)}
    return segments, visuals


# ------------------------------------------------------------- package

def build_package(brief):
    engine = "builtin"
    engine_note = ("AI engine key not configured on this deployment yet; "
                   "answered with the built-in engine.")
    segments = visuals = None
    if GEMINI_KEY:
        try:
            segments, visuals = gemini_draft(brief)
            engine = "gemini"
            engine_note = None
        except Exception as exc:
            segments = visuals = None
            engine = "builtin-fallback"
            engine_note = (f"Model engine unavailable ({type(exc).__name__}); "
                           "answered with the built-in engine.")
    if segments is None:
        segments = builtin_script(brief)
        visuals = builtin_visuals(brief)
    segments, flags, total_words = enforce_budget(segments, brief["duration_seconds"])
    tone = TONES[brief["tone"]]
    duration = brief["duration_seconds"]

    shots = []
    for i, seg in enumerate(segments, 1):
        v = visuals[seg["role"]]
        dur = round(seg["end_s"] - seg["start_s"], 1)
        if seg["role"] == "end_card":
            prompt = (f"Clean end-card background plate for a television commercial, "
                      f"16:9, {tone['visual_mood']}, the product setting at rest, "
                      f"calm uncluttered center of frame left open for text added in edit, "
                      f"photorealistic, broadcast quality")
            model = "Kling 3.0 (still plate or slow 5 s hold)"
        else:
            prompt = (f"Cinematic 16:9 television commercial shot, {tone['visual_mood']}. "
                      f"{v['visual']} Camera: {v['camera']}. Photorealistic, real people "
                      f"and real locations, natural expressions, broadcast quality, "
                      f"no text anywhere in frame")
            model = "Kling 3.0 or Seedance 2.0"
        shots.append({
            "shot": i, "role": seg["role"],
            "start_s": seg["start_s"], "end_s": seg["end_s"], "duration_s": dur,
            "visual": v["visual"], "camera": v["camera"],
            "voiceover": seg["voiceover"],
            "higgsfield_prompt": prompt,
            "negative_prompt": NEGATIVE_PROMPT,
            "model_suggestion": model,
            "aspect_ratio": "16:9", "resolution": "1920x1080",
        })

    vo_text = " ".join(s["voiceover"] for s in segments)
    end_card = {
        "headline": brief["product"],
        "subline": brief["offer"].rstrip(".") + ".",
        "call_to_action": brief["call_to_action"],
        "website": brief["website"] or "(supply the destination URL before production)",
        "logo": "Brand logo, supplied by the advertiser, placed upper center or center, supplied as a file; never generated.",
        "qr_code": "Optional: a QR code resolving to the call to action destination, large and high contrast, held for the full end card, test-scanned from TV distance.",
        "background": "Shot %d plate (the end-card shot in this package); all card text is typeset in edit over the plate." % len(shots),
        "hold_s": duration - segments[-1]["start_s"],
        "layout": "All text and logo inside title-safe margins (center 90 percent of frame).",
    }

    script = {
        "duration_seconds": duration,
        "segments": segments,
        "total_words": total_words,
        "word_budget": WORD_BUDGET[duration],
        "planning_pace": "150 words per minute (2.5 words per second)",
        "estimated_read_seconds": round(total_words / WORDS_PER_SECOND, 1),
        "flags": flags,
    }

    package = {
        "service": SERVICE,
        "engine": engine,
        "engine_note": engine_note,
        "brief": {k: v for k, v in brief.items() if not k.startswith("_")},
        "script": script,
        "shots": shots,
        "voiceover": {
            "text": vo_text,
            "suggested_voice": tone["voice"],
            "voice_name": tone["voice_name"],
            "voice_style": tone["voice_style"],
            "swiftread_payload": {
                "endpoint": "POST /speak (SwiftRead API)",
                "body": {"text": vo_text, "voice": tone["voice"]},
                "note": "Synthesize at natural pace, then mix to -24 LKFS integrated with the music bed under the voice; the read must land inside the spot length, so re-time against the assembled picture.",
            },
            "music_direction": tone["music"] + " Licensed library or original cleared music only.",
        },
        "end_card": end_card,
        "delivery_spec": DELIVERY_SPEC,
        "compliance_checklist": COMPLIANCE_CHECKLIST,
        "production_steps": [
            "1. Generate one clip per shot in Higgsfield using each shot's higgsfield_prompt (16:9, 1920x1080).",
            "2. Synthesize the voiceover from voiceover.swiftread_payload on SwiftRead.",
            "3. Assemble picture, voiceover and the music bed in an editor (or a pipeline such as SwiftRender), end-card text typeset over the final plate.",
            "4. Mix and master to the delivery spec: -24 LKFS plus or minus 2, true peak at or below -2 dBTP.",
            "5. Run the finished file through POST /check-spec with its measured values before paying for any placement.",
            "6. Place it through your own advertiser account (Vibe or another DSP): SpotBase does not place ads.",
        ],
        "honesty": ("SpotBase writes the production package; it does not render video, "
                    "synthesize the voiceover, or place ads on TV. Placement requires the "
                    "advertiser's own funded platform account and its compliance review."),
    }
    if brief.get("_offer_defaulted"):
        package["brief_notes"] = ["offer was not supplied; a generic offer line was drafted from the product field. Replace it with the real offer before production."]
    return package


# ------------------------------------------------------------ endpoints

def health(params):
    return 200, {"status": "ok", "service": SERVICE, "build": BUILD,
                 "creative_engine": "gemini" if GEMINI_KEY else "awaiting key (built-in engine active)",
                 "proxy_gate": "on" if os.environ.get("RAPIDAPI_PROXY_SECRET") else "off until the listing step sets RAPIDAPI_PROXY_SECRET",
                 "endpoints": ["POST /ad-package", "POST /script", "POST /shots",
                               "POST /check-spec", "GET /delivery-spec", "GET /tones",
                               "GET /health"],
                 "scope": "Brief-to-ad-package only. No video rendering, no voice synthesis, no ad placement."}


def tones(params):
    return 200, {"tones": {name: {"voice": t["voice"], "voice_name": t["voice_name"],
                                  "voice_style": t["voice_style"],
                                  "music_direction": t["music"],
                                  "visual_mood": t["visual_mood"]}
                           for name, t in TONES.items()}}


def delivery_spec(params):
    return 200, {"delivery_spec": DELIVERY_SPEC,
                 "compliance_checklist": COMPLIANCE_CHECKLIST}


def _brief_package(body):
    brief, err = parse_brief(body)
    if err:
        return None, err
    return build_package(brief), None


def ad_package(body):
    package, err = _brief_package(body)
    if err:
        return err
    return 200, package


def script_only(body):
    package, err = _brief_package(body)
    if err:
        return err
    return 200, {"service": SERVICE, "engine": package["engine"],
                 "engine_note": package["engine_note"],
                 "brief": package["brief"], "script": package["script"],
                 "voiceover_text": package["voiceover"]["text"]}


def shots_only(body):
    package, err = _brief_package(body)
    if err:
        return err
    return 200, {"service": SERVICE, "engine": package["engine"],
                 "engine_note": package["engine_note"],
                 "brief": package["brief"], "shots": package["shots"],
                 "end_card": package["end_card"]}


def _num(body, key):
    v = body.get(key)
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def check_spec(body):
    if not isinstance(body, dict):
        return 422, {"error": "invalid_body",
                     "detail": "Request body must be a JSON object of measured file specs."}
    items = []

    def add(field, verdict, detail):
        items.append({"field": field, "verdict": verdict, "detail": detail})

    dur = _num(body, "duration_seconds")
    if dur is None:
        add("duration_seconds", "not_checked", "Not supplied.")
    elif dur > 90:
        add("duration_seconds", "fail", f"{dur} s exceeds Vibe's 90 s upload ceiling.")
    elif dur in (15, 30) or abs(dur - round(dur)) < 0.05 and dur >= 5:
        add("duration_seconds", "pass", f"{dur} s is an accepted streaming TV length.")
    else:
        add("duration_seconds", "warn", f"{dur} s is inside Vibe's 5-90 s range but not a standard 15 or 30 s spot.")

    w, h = _num(body, "width"), _num(body, "height")
    if w is None or h is None:
        add("resolution", "not_checked", "width and height not supplied.")
    elif w >= 1920 and h >= 1080:
        add("resolution", "pass", f"{int(w)}x{int(h)} meets the recommended 1920x1080.")
    elif w >= 1280 and h >= 720:
        add("resolution", "warn", f"{int(w)}x{int(h)} meets the 1280x720 minimum but not the 1920x1080 recommendation.")
    else:
        add("resolution", "fail", f"{int(w)}x{int(h)} is below the 1280x720 minimum.")
    if w and h:
        ratio = w / h
        add("aspect_ratio", "pass" if abs(ratio - 16 / 9) < 0.02 else "fail",
            f"Aspect ratio computes to {ratio:.3f}; 16:9 is {16/9:.3f}.")

    fmt = _clean(body.get("format"), 20).lower()
    if not fmt:
        add("format", "not_checked", "Not supplied.")
    elif fmt in ("mp4", "mpeg-4", "mpeg4"):
        add("format", "pass", "mp4 is the required container.")
    elif fmt in ("mov", "quicktime"):
        add("format", "warn", "mov is accepted by many publishers but Vibe requires mp4.")
    else:
        add("format", "fail", f"{fmt} is not an accepted CTV container; deliver mp4.")

    fps = _num(body, "frame_rate")
    if fps is None:
        add("frame_rate", "not_checked", "Not supplied.")
    elif any(abs(fps - ok) < 0.02 for ok in (23.976, 24, 25, 29.97, 30)):
        add("frame_rate", "pass", f"{fps} fps is an accepted constant rate.")
    else:
        add("frame_rate", "fail", f"{fps} fps is not in the accepted set (23.976, 24, 25, 29.97, 30).")
    cfr = body.get("constant_frame_rate")
    if isinstance(cfr, bool):
        add("constant_frame_rate", "pass" if cfr else "fail",
            "Constant frame rate confirmed." if cfr else "Variable frame rate is rejected; re-encode constant.")

    br = _num(body, "bitrate_kbps")
    if br is None:
        add("bitrate_kbps", "not_checked", "Not supplied.")
    elif br >= 15000:
        add("bitrate_kbps", "pass", f"{int(br)} kbps is in the recommended 15-30 Mbps source band.")
    elif br >= 2500:
        add("bitrate_kbps", "warn", f"{int(br)} kbps passes Vibe's 2,500 kbps floor but is under the 15 Mbps source recommendation.")
    else:
        add("bitrate_kbps", "fail", f"{int(br)} kbps is under Vibe's 2,500 kbps minimum.")

    size = _num(body, "file_size_mb")
    if size is None:
        add("file_size_mb", "not_checked", "Not supplied.")
    elif size <= 100:
        add("file_size_mb", "pass", f"{size} MB is within Vibe's 100 MB cap.")
    else:
        add("file_size_mb", "fail", f"{size} MB exceeds Vibe's 100 MB cap.")

    ch = _num(body, "audio_channels")
    if ch is None:
        add("audio_channels", "not_checked", "Not supplied.")
    else:
        add("audio_channels", "pass" if ch == 2 else "fail",
            "Stereo as required." if ch == 2 else f"{int(ch)} channels; CTV delivery is stereo (2).")

    sr = _num(body, "sample_rate_hz")
    if sr is None:
        add("sample_rate_hz", "not_checked", "Not supplied.")
    else:
        add("sample_rate_hz", "pass" if sr == 48000 else "fail",
            "48 kHz as required." if sr == 48000 else f"{int(sr)} Hz; deliver 48 kHz.")

    abr = _num(body, "audio_bitrate_kbps")
    if abr is None:
        add("audio_bitrate_kbps", "not_checked", "Not supplied.")
    else:
        add("audio_bitrate_kbps", "pass" if abr >= 192 else "fail",
            f"{int(abr)} kbps meets the 192 kbps floor." if abr >= 192 else f"{int(abr)} kbps is under the 192 kbps floor.")

    lufs = _num(body, "loudness_lufs")
    if lufs is None:
        add("loudness_lufs", "not_checked", "Not supplied. Measure integrated loudness with a BS.1770 meter before delivery.")
    elif -26 <= lufs <= -22:
        add("loudness_lufs", "pass", f"{lufs} LUFS is inside -24 plus or minus 2 (CALM Act / ATSC A/85).")
    else:
        add("loudness_lufs", "fail", f"{lufs} LUFS is outside -24 plus or minus 2; re-mix to target -24.")

    tp = _num(body, "true_peak_dbtp")
    if tp is None:
        add("true_peak_dbtp", "not_checked", "Not supplied.")
    else:
        add("true_peak_dbtp", "pass" if tp <= -2.0 else "fail",
            f"{tp} dBTP is at or under the -2 ceiling." if tp <= -2.0 else f"{tp} dBTP exceeds the -2 dBTP ceiling; limit and re-measure.")

    verdicts = [i["verdict"] for i in items]
    overall = "fail" if "fail" in verdicts else ("warn" if "warn" in verdicts else "pass")
    if overall == "pass" and "not_checked" in verdicts:
        overall = "pass_with_unchecked_items"
    fixes = [f"{i['field']}: {i['detail']}" for i in items if i["verdict"] in ("fail", "warn")]
    return 200, {"service": SERVICE, "overall_verdict": overall, "items": items,
                 "fixes": fixes,
                 "note": "Verdicts score only the values supplied. not_checked items were not measured by this call and are never assumed to pass."}


POST_ROUTES = {"/ad-package": ad_package, "/script": script_only,
               "/shots": shots_only, "/check-spec": check_spec}
GET_ROUTES = {"/health": health, "/tones": tones, "/delivery-spec": delivery_spec}


def run_server(port):
    proxy_secret = os.environ.get("RAPIDAPI_PROXY_SECRET", "")

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
            handler = GET_ROUTES.get(path)
            if handler is None:
                return self._json(404, {"error": "not_found",
                                        "detail": f"No endpoint at {path}. See /health for service info."})
            try:
                status, payload = handler({})
            except Exception as exc:
                return self._json(500, {"error": "internal",
                                        "detail": f"{type(exc).__name__}: {exc}"})
            self._json(status, payload)

        def do_POST(self):
            path = urlparse(self.path).path.rstrip("/") or "/"
            if not self._gate_ok(path):
                return
            handler = POST_ROUTES.get(path)
            if handler is None:
                return self._json(404, {"error": "not_found",
                                        "detail": f"No endpoint at {path}. See /health for service info."})
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
            started = time.time()
            try:
                status, payload = handler(body)
            except Exception as exc:
                return self._json(500, {"error": "internal",
                                        "detail": f"{type(exc).__name__}: {exc}"})
            payload.setdefault("_meta", {"seconds": round(time.time() - started, 3)})
            self._json(status, payload)

    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    run_server(int(os.environ.get("PORT", "8118")))
