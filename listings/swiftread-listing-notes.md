# SwiftRead: Studio listing notes (for the browser-lane listing session)

Prepared 2026-10-30 with the fix pass. The listing itself
(Studio create/PRIVATE, plans, publish, gateway test, Spotlight) runs
in the parent's browser lane; this file carries the fixlist's three
listing actions so nothing from the fix research gets lost.

## Plans: bill PER REQUEST, never per character (fixlist item 9)

Configure the four plans exactly as quotas of REQUESTS:
BASIC $0 / 100 requests per month, PRO $5 / 1,000, ULTRA $20 / 10,000,
MEGA $60 / 50,000. Do NOT enable any per-character or per-1,000-char
metering if Studio offers it: the structural complaint against Large
Text to Speech is that one 15,000-character article costs 15 quotas
there. On SwiftRead one article, any length up to the cap, is 1
request. Confirm the plan unit reads "requests" before publishing.

## Documentation: binary MP3 handling snippets (fixlist item 10)

VoiceRSS users publicly asked how to handle the binary response.
Put these in the listing documentation/overview verbatim:

JavaScript (browser, fetch to Blob and play):

```js
const res = await fetch("https://swiftread.p.rapidapi.com/read-url", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-RapidAPI-Key": YOUR_KEY,
    "X-RapidAPI-Host": "swiftread.p.rapidapi.com"
  },
  body: JSON.stringify({ url: "https://example.com/some-article", voice: "en-US-AriaNeural" })
});
const blob = await res.blob();              // the MP3 itself, no expiring URL
const audio = new Audio(URL.createObjectURL(blob));
audio.play();
```

Python (requests, save and play):

```python
import requests

r = requests.post(
    "https://swiftread.p.rapidapi.com/speak",
    headers={"X-RapidAPI-Key": YOUR_KEY, "X-RapidAPI-Host": "swiftread.p.rapidapi.com"},
    json={"text": "The text you want to hear.", "voice": "sw-KE-ZuriNeural"},
    timeout=300,  # long articles take a while to synthesize
)
r.raise_for_status()
open("listen.mp3", "wb").write(r.content)   # standard audio/mpeg
```

Mobile note for the docs: the response IS the MP3 file (audio/mpeg);
save it or hand it to the platform audio player. There is no download
URL to expire.

## Voice samples (fixlist items 5 and 8)

If the listing flow supports playable samples or rich overview media,
generate one short sample per language group from the deployed
service (POST /speak, a two-sentence sample line in that language)
and attach/link them in the overview. Suggested voices: Aria
(en-US), Sonia (en-GB), Ezinne (en-NG), Elvira (es-ES), Denise
(fr-FR), Katja (de-DE), Francisca (pt-BR), Elsa (it-IT), Nanami
(ja-JP), Xiaoxiao (zh-CN), Zuri (sw-KE), Mekdes (am-ET), Ubax
(so-SO), Thando (zu-ZA), Adri (af-ZA). If Studio cannot host audio,
link the samples from the Spotlight proof doc instead
(docs/swiftread-reliability.md lists the /voices roster).

## Spotlight (after publish)

Description must stay UNDER 280 characters. Draft (211 chars):
"SwiftRead turns any article URL into natural spoken audio: 322 neural
voices in 75 languages, paragraph pauses, a 15,000-character cap billed
per request, and the MP3 returned directly. Live test results inside."
Post via the URL tab with the GitHub blob URL of
docs/swiftread-reliability.md (the File tab rejects markdown).

## Presentation order (owner directive)

Where the listing or docs present voices or languages, lead with the
most-spoken languages: English, Chinese (Mandarin), Hindi, Spanish,
French, Arabic, Bengali, Portuguese, Russian, Japanese, German,
Indonesian, Urdu - then the featured African set (Swahili, Amharic,
Somali, Zulu, Afrikaans, and the African English variants grouped
with English) - then the rest. GET /voices already returns this
order; the featured 45 (featured: true in the data) are the picks to
highlight in the overview.
