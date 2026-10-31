# Spec: WhoisBase (wave 4, queue #10)

Approved under the user's full-run queue authorization of 2026-10-29
(automate the queue; the Studio listing, publish, and Spotlight steps
run via the parent's browser lane). Score 63.

## The comparable listing

Whois Lookup by Zozor54: 3,811 subscribers, rated 3/5 (16 votes),
service level 99%, listed latency 1,371ms, pricing Pro $10, Ultra $30,
Mega $80. All 29 of its Discussion threads sit Unanswered. Complaint
themes from its own Discussions:
1. Stale cached results: records stay wrong for hours even when the
   caller passes the incumbent's force-refresh flag.
2. Timeouts and bare 504s with no structured error to handle.
3. Missing, blank, or null data for many TLDs - users name .dev, .at,
   .rs, .pl, .eu, .fi and more.
4. Double-subscription billing (a RapidAPI platform grievance; the fix
   on our side is a free Pro tier, so nobody pays to evaluate us).

## The fix

A live whois service on the shared scaffold, built on the free public
RDAP protocol (RFC 9083) instead of scraped or resold whois data.

- Live RDAP via the IANA bootstrap: the TLD's authoritative registry
  server is resolved from https://data.iana.org/rdap/dns.json (cached
  24h, with a built-in seed for the major TLDs if IANA is unreachable)
  and queried directly. RDAP answers are structured JSON at the
  source; we normalize them into one stable record schema.
- Port-43 fallback: TLDs with no RDAP endpoint in the bootstrap
  (notably .at, .rs, .eu, .de, .io, .ch) are queried live against the
  registry's own whois server (whois.nic.at, whois.rnids.rs, whois.eu,
  whois.denic.de, whois.identity.digital, whois.nic.ch) and the text
  record is parsed into the same schema. Fields a registry withholds
  (DENIC, for example, publishes almost nothing by design) are
  reported as withheld, never invented and never silently blank.
- Honest cache, the headline fix: records are cached for 300 seconds
  (60 for negative results). EVERY response carries a cache block:
  whether it was served from cache, the record's age in seconds, the
  TTL, and whether a fresh fetch was forced. The `fresh` parameter
  (alias `force`, the incumbent's own flag name) genuinely bypasses
  the cache and refetches from the registry before answering; the
  response then shows cached: false and age_seconds: 0. If a forced
  refetch fails, the last good record is served flagged served_stale
  with its true age instead of an error.
- Explicit errors only: timeouts, unreachable registries, and
  malformed upstream answers return the scaffold's structured JSON
  error objects (with a 502 and an error code that names the failure,
  e.g. upstream_timeout). No bare 504 pages, no empty 200s.
- Negative results are answers, not blanks: an unregistered domain
  returns 200 with registered: false and the full schema, so client
  code never has to guess whether blank fields mean "available" or
  "broken" - the incumbent's third complaint.

Endpoints: GET /lookup?domain= (fresh/force optional),
GET /domain/{domain} (same lookup, path form), GET /tlds (the live
coverage map: which TLDs answer over RDAP, which over port-43),
GET /health.

Record schema: domain, tld, registered, source (rdap | whois-port43),
registry server, registrar (name, IANA id, url), created / updated /
expires (ISO 8601), status list, nameservers, dnssec flag, registrant
organization and country when the registry publishes them, the raw
event list, and the cache block described above.

## Pricing (RapidAPI, hard limits, monthly quotas)

BASIC $0 / 250 per month, PRO $0 / 10,000 (the incumbent charges $10
for its entry tier; ours is free), ULTRA $20 / 100,000 (vs $30),
MEGA $70 / 500,000 (vs $80). Net after the 25% fee: $15 / $52.50.

## Costs and risks

$0 end to end: RDAP and port-43 whois are the registries' own public
protocols; no key, no license, no scraping. Tenth Render service: the
keep-warm fleet window stays 09:00-11:00 ET (2h x 10 services x 31
days = 620h worst month inside the 750h workspace cap).

Two honest limits. (1) Port-43 egress is blocked in the local build
sandbox by policy, so the fallback's parser and client are verified
locally against canned registry records and a local test server; its
live path is exercised on Render. If port 43 were blocked there too,
non-RDAP TLDs would return the explicit upstream error rather than
data - the spec accepts that risk because RDAP already covers the
large majority of TLDs (592 bootstrap entries) including .dev, .pl,
and .fi from the complaint list. (2) GDPR-era registries publish thin
records; where a field is withheld we say so in the response instead
of padding it.

## Local test log (2026-10-29, build sandbox, test proxy secret set)

Port-43 parser battery (canned registry records + a local fake whois
server for the socket path): 15/15 PASS - nic.at (.at), EURid (.eu,
next-line registrar and block nameservers), RNIDS (.rs, dd.mm.yyyy
dates), Verisign not-found text, and the socket client end to end.
The first run caught real bugs (plural "Name servers:" headers and a
missing dd.mm.yyyy-with-time date format); both fixed and re-verified.

Live HTTP battery against the locally running service: health open
without the secret and reporting 1,203 RDAP TLDs from the live IANA
bootstrap; /lookup returns 401 without the proxy secret. Lookups
returned full structured records for google.com (.com, MarkMonitor,
created 1997-09-15, 4 nameservers, ~1.1s cold), web.dev (.dev),
allegro.pl (.pl), finnair.fi (.fi), example.org and wikipedia.org
(.org). Cache behavior verified end to end: the repeat call served
cached: true with its age; ?fresh=true and the ?force=1 alias both
bypassed and refetched (cached: false, age 0); an unregistered .com
returned 200 with registered: false and the 60-second negative TTL.
Error shapes verified: missing parameter, garbage domain, an IP
address, and an unsupported TLD each return their named 422 JSON
error; URL-form input (https://www.google.com/search?q=x) normalizes
to google.com. .at/.eu/.rs in the sandbox return the explicit 502
upstream_error (port-43 egress is policy-blocked here), never a blank
record. Two checks were environment-limited rather than code
failures: Nominet (.uk) persistently rate-limits the shared sandbox
egress IP with HTTP 429, and Verisign dropped connections under burst
load; both surface as structured errors after one retry, and both
succeed when spaced (the unregistered .com case re-verified standalone:
registered: false, TTL 60).

Deployed verification (2026-10-29, https://whoisbase.onrender.com,
Render srv-dbhl8lbbc2fs73epsfp0, commits cc715442 and 929fd827):
/health live reporting 1,203 RDAP TLDs; RDAP records verified for
google.com, web.dev, allegro.pl, finnair.fi. Port-43, blocked in the
build sandbox, WORKS from Render: nic.at, eurid.eu, rnids.rs and
example.de all returned real structured records (the live .rs answer
exposed RNIDS's DNS-label nameserver format; the parser fix is commit
929fd827 and .rs now returns 6 nameservers with clean statuses).
Deployed cache behavior matches the local battery (repeat call
cached: true; fresh=true refetches; unregistered .com registered:
false at the 60s negative TTL). The proxy gate was verified locally
with a test-only secret (401 without the header, /health open); the
production secret is wired in the parent's Studio lane, so the
deployed service intentionally carries no secret yet.
