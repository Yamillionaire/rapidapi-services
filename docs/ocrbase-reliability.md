# OCRBase: the proof page, run before you pay

Most OCR APIs ask you to trust the demo. OCRBase publishes its own
test battery instead: the same generated 300-DPI test page, run
through the live engine, with every word's confidence shown.

## The launch battery (2026-11-01, Tesseract 5.3.4)

| Test | Result |
| --- | --- |
| English page, 2550x3300 at 300 DPI, 202 words | 200, all 202 words, mean word confidence 96.46 |
| Spanish page (lang=spa), 88 words | 200, mean word confidence 96.49 |
| Same Spanish page via base64 JSON | 200 |
| PDF of the page (first page, rendered at 300 DPI) | 200, 202 words |
| Blank image | 422 `no_text_detected` - a named error, not an empty 200 |
| Unsupported file | 415 `unsupported_format`, stating what was received |
| Unknown language | 422 `unsupported_language`, listing what is installed |
| URL pointing at 127.0.0.1 / link-local | 422 `ssrf_blocked` on every hop |

## Memory and speed, measured, not promised

Peak memory of the whole service during a full-page extraction:
176.5 MB, inside a hard 512 MB limit, verified under a memory
cgroup with swapping disabled. A dense 300-DPI page takes about
5 seconds of engine time on an unloaded host; OCRBase reports
`processing_ms` on every response so you can hold it to that.

## What OCRBase does not do

Handwriting. It is labeled "not supported" in the listing, in
/health, and here. Print and typed documents are the product;
degraded scans and complex multi-column layouts return lower
per-word confidence, and the confidence fields say so per word
instead of hiding it behind one average.

## Pricing honesty

The print incumbent charges $10.94 / $24.94 / $56.94. OCRBase:
PRO $5, ULTRA $14.94, MEGA $46.94, same hard-limit shape, with a
free BASIC tier of 100 pages a month.
