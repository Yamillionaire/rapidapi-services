# OCRBase proof gate: memory + timing (2026-11-01)

Spec: `docs/spec-ocrbase.md`. This is the spec's first gate: peak RSS
and per-page seconds for a typical page inside the Render free-tier
512 MB envelope, before any deployment decision.

## Verdict

- **Memory: PASS.** Peak RSS of the whole server process tree during
  a full-page request was **176.5 MB** (run 1) and **173.2 MB**
  (run 2), against a 512 MB limit. Confirmed a second way: the server
  ran to completion inside a hard cgroup cap
  (`systemd-run --scope -p MemoryMax=512M -p MemorySwapMax=0`) and
  returned a full 200 result with no OOM kill.
- **Timing: FAIL against the ~5 s server-side criterion as measured
  on this VM today, with a stated cause.** Server `processing_ms`
  was 7,880 to 10,016 ms across runs. The tesseract CLI alone, same
  page and flags, measured 4.49 and 4.68 s in an earlier, quieter
  window, but 5.99 to 9.0 s in the same loaded window as the server
  runs (load average 9 to 14 on a 4-vCPU VM shared with the rest of
  the fleet and other agents' work). So the engine itself can meet
  ~5 s on an unloaded host; the end-to-end server number on this
  shared VM today did not. The spec's aspirational target of under
  1.5 s for a typical 300-DPI page is **not met** in any measurement
  here and is not claimed.
- **Overall gate: NOT a clean pass.** Memory passes decisively.
  Timing needs a re-measure on an unloaded host (or a dedicated
  instance) before the "under ~5 s typical page" claim is made
  anywhere. Per the spec, if the proof fails the build returns to
  the queue rather than shipping on a false number; the code is
  built and functionally proven (below), and this timing caveat is
  the open item for the parent decision.

## Method (honest)

- Host: this VM, 4 vCPU, tesseract 5.3.4 (Leptonica 1.82.0),
  tessdata eng/spa/fra/deu/por plus osd. Python stdlib server from
  `ocrbase/app.py`, run with `PORT` set to a free local port
  (18240 to 18243; the spec default 8118 is occupied on this VM by
  the home-hosted CaptionBase service, so it was not used locally).
- Test page: generated with PIL at 300 DPI, 2550x3300 PNG
  (238,931 bytes), Liberation Serif, a title plus four realistic
  paragraphs of printed English prose (202 words). A two-paragraph
  Spanish page was generated the same way.
- RSS: sampled from `/proc/<pid>/status` VmRSS for the server PID
  plus its child processes (the tesseract subprocess) every 20 ms
  (run 1, full `/proc` scan) and every 50 ms (run 2, cheap
  `/proc/<pid>/task/*/children` walk), spanning the full request.
  Baseline server-only RSS before the request: 23.5 MB.
  `/usr/bin/time -v` is not installed on this VM, so it was not
  used; the cgroup run above is the independent memory check.
- Timing: `processing_ms` is measured inside the server around the
  PDF-render (when applicable) plus tesseract work; wall times from
  the client are also reported. Direct-CLI comparison runs used the
  identical command the server runs
  (`OMP_THREAD_LIMIT=1 tesseract in.png out --psm 1 -l eng tsv`).
  PSM note: `--psm 1` was also compared with `--psm 3` on this page;
  PSM 1 measured 4.49/4.68 s vs PSM 3 at 17.86/18.90 s, so the app
  uses PSM 1 as the spec allows.

## Numbers

| Measurement | Result |
|---|---|
| Peak tree RSS, run 1 (20 ms sampling) | 176.5 MB |
| Peak tree RSS, run 2 (50 ms sampling) | 173.2 MB |
| Server baseline RSS (idle) | 23.5 MB |
| Hard cgroup cap test (512M, no swap) | Completed, HTTP 200, 202 words |
| Server processing_ms, run 1 | 9,292 ms |
| Server processing_ms, warm run | 7,880 ms |
| Server processing_ms, measured run 2 | 10,016 ms |
| Server processing_ms, cgroup run | 9,180 ms |
| Tesseract CLI alone, quieter window | 4.49 s, 4.68 s |
| Tesseract CLI alone, loaded window | 5.99 s, 9.0 s |
| VM load average during server runs | 9 to 14 (4 vCPU) |
| English page result | 202 words, mean_confidence 96.46, low_confidence_warning false, 5 blocks |

## Functional tests (all against the running server)

| Test | Result |
|---|---|
| GET /health | 200: status ok, service ocrbase, engine tesseract 5.3.4, languages listed, limits shown, handwriting NOT supported note present |
| GET /languages | 200: `["deu", "eng", "fra", "osd", "por", "spa"]` - the packs actually installed (osd is tesseract's orientation pack, reported honestly as installed) |
| POST /extract, English PNG (multipart) | 200: 202 words, mean_confidence 96.46, words carry text/conf/bbox/block_num/line_num, text in reading order |
| POST /extract, Spanish PNG (`lang=spa`) | 200: 88 words, mean_confidence 96.49, correct Spanish text |
| POST /extract, Spanish via JSON `image_base64` | 200: 88 words |
| POST /extract, PDF of the English page | 200: 202 words, format `pdf`, mean_confidence 96.5 (pdftoppm path works locally) |
| Blank (no-text) image | 422 `no_text_detected` with detail |
| Unsupported file (`.xyz` text bytes) | 415 `unsupported_format` with detail |
| Uninstalled language (`lang=jpn`) | 422 `unsupported_language`, installed list in detail |
| URL to 127.0.0.1 / localhost / 169.254.169.254 | 422 `ssrf_blocked` for all three |
| URL with ftp scheme | 422 `url_fetch_failed` (http/https only) |
| URL to unresolvable public host | 502 `url_fetch_failed` |
| Proxy-secret gate (separate instance, `RAPIDAPI_PROXY_SECRET` set) | /languages without header: 401 `unauthorized`; with header: 200; /health without header: 200 (always open) |

Not tested locally: `file_too_large` (10 MB cap is enforced in code
on upload, base64, and URL paths but no >10 MB fixture was sent),
JPEG/TIFF/WEBP fixtures (format detection is magic-byte based and
the PNG/PDF paths exercise the shared pipeline), and a live public
URL fetch success (only its failure and SSRF paths were exercised;
the sandbox resolver returns benchmarking-range addresses for
public hosts, which the explicit-CIDR blocklist deliberately
allows, per the cleanextract approach).

## Deviations / notes

- Local proof used ports 18240+ because 8118 is taken on this VM;
  the app default remains 8118 per spec.
- `GET /languages` includes `osd` because `tesseract --list-langs`
  reports it; the list is the honest installed list, not curated.
- No deployment was made and nothing outside `ocrbase/` was touched.
