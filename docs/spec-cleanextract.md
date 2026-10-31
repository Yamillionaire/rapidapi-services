# Spec E: CleanExtract

Approved by the user 2026-10-28 ("Proceed with the next one"). Score 82.

## The comparable listing

Article Extractor and Summarizer by restyler: 11,784 subscribers,
rated 3/5 (17 votes), service level 74%, latency 1,421ms. Pricing:
Basic free / 50 per month, Pro $15 / 500, Ultra $95 / 5,000,
Mega $195 / 25,000 (monthly quotas). Complaints: years of unanswered
503 service-unavailable, 403 and 401 threads, 500s on localhost URLs,
503s on failed HTML retrieval.

## The fix

Everything runs on our own server: stdlib article extraction plus an
extractive summarizer (frequency-scored sentence selection). There is no
external AI call and no third-party extractor to fail, which is the whole
reliability pitch. Errors are structured objects (source HTTP errors,
fetch refusals, no-article-text), never a bare 503. Fetches are
SSRF-hardened: http/https only, explicit blocklist for loopback, RFC1918,
link-local and cloud-metadata ranges, checked again on every redirect
hop, with size and time caps.

Endpoints: GET /extract?url=, GET /summarize?url=&sentences=,
GET /summarize-text?text=&sentences=, GET /health.

Honest labeling: summaries are extractive (the article's own key
sentences), and the response says so. Abstractive AI summaries are a
possible v2 if revenue justifies a model budget.

## Pricing (RapidAPI, hard limits, monthly quotas)

BASIC $0 / 250 per month (five times the incumbent's free 50),
PRO $5 / 5,000 (the incumbent charges $15 for 500),
ULTRA $85 / 50,000, MEGA $185 / 250,000. Net after the 25% fee:
$3.75 / $63.75 / $138.75. The pitch is reliability plus ten times the
Pro quota at a third of the Pro price.

## Costs and risks

$0 end to end. Fifth Render service: the keep-warm window shrinks to
09:00-13:00 ET (4h x 5 x 31 = 620h inside the 750h cap). Paywalled or
bot-walled source pages return the source's HTTP status as a structured
error; that is the source's wall, not an outage, and the listing says so.
