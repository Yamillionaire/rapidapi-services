# WhoisBase DomainBase extension - test battery, 2026-11-01

Scope: local tests only, no deploy. Server run from the edited
`whoisbase/app.py` on scratch port 8199 (`PORT=8199 python3 app.py`),
tested with curl, then shut down. Sandbox note: port 43 is blocked
here (connections reset), so port-43 TLD paths cannot succeed in this
environment; all RDAP paths were exercised live. The IANA bootstrap
loaded live: rdap_tld_count 1203, bootstrap_publication
2026-10-28T22:00:04Z.

## Reference note

The task pointed at `cleanlist/app.py` for the DNS-over-HTTPS pattern;
no such file exists in the tree. The fleet's DoH pattern actually
lives in `emailcheck/app.py` (`fetch_json` with an
`Accept: application/dns-json` header). `/dns` follows that pattern
against `https://dns.google/resolve?name=&type=` exactly as tasked.

## Results

### GET /health (updated note)
HTTP 200. Note now ends: "...DomainBase extension: /availability and
/availability/bulk (cap 50; each domain checked counts as one
request), /dns via DNS-over-HTTPS, and /suggest with
availability-verified candidates only. Premium is reported only when
a registry publishes it, never guessed."

### GET /availability?domain=zxqw-domainbase-test-20261101.com (unregistered .com)
HTTP 200:
{"domain": "zxqw-domainbase-test-20261101.com", "available": true,
"registered": false, "registry_source": "rdap.verisign.com",
"source": "rdap", "premium": null, "premium_note": "Premium status is
reported only when a registry publishes it in its record; this
registry did not publish a premium flag for this domain, so premium
is null rather than guessed or estimated.", "cache": {"cached": true,
"age_seconds": 14, "ttl_seconds": 60, "fresh_fetch": false,
"served_stale": false}, "checked_at": "2026-11-01T21:42:46Z"}
(One earlier attempt returned a structured 502 upstream_error -
"Remote end closed connection without response" from
rdap.verisign.com; Verisign RDAP intermittently drops connections
from this sandbox. The stock /lookup path shows the identical
behavior, and a retry with fresh=true returned the 200 above.)

### GET /availability?domain=google.com (registered)
HTTP 200: available false, registered true, registry_source
rdap.verisign.com, source rdap, premium null (same premium_note),
cache ttl_seconds 300.

### GET /availability?domain=example.zzznottld (unsupported TLD)
HTTP 422, identical shape to /lookup:
{"error": "unsupported_tld", "detail": "The .zzznottld registry
publishes no RDAP endpoint and we have no port-43 route for it. See
/tlds for the coverage map.", "domain": "example.zzznottld"}

### GET /availability?domain=example.io (port-43 TLD, sandbox-blocked)
HTTP 502 structured (converted by the new endpoints' guard, see
Findings): {"error": "upstream_error", "detail": "Lookup for
example.io failed: ConnectionResetError: [Errno 104] Connection
reset by peer", "domain": "example.io"}

### GET /availability/bulk?domains=google.com,zxqw-domainbase-test-20261101.com,not a domain!!,example.org
HTTP 200. count 4, available_count 1, registered_count 2,
error_count 1, metering "Each domain checked counts as one request."
Results in request order: google.com (registered, served from shared
cache: cached true, age_seconds 6), zxqw-domainbase-test-20261101.com
(available true), the invalid entry in place as
{"domain": "not a domain!!", "available": null, "error":
"invalid_domain", "detail": "'not a domain!!' is not a valid domain
name. ..."}, example.org (registered, registry_source
rdap.publicinterestregistry.org). The batch never fails on a bad
entry.

### Bulk cap
51 domains -> HTTP 422 {"error": "too_many_domains", "detail": "Bulk
availability is capped at 50 domains per request; this request
listed 51. Split it into smaller batches."}

### GET /dns?domain=example.com (no type: all seven)
HTTP 200. types [A, AAAA, MX, NS, TXT, CNAME, SOA], status_by_type
all 0. Records with TTLs as returned, e.g. A: 104.20.23.154 and
172.66.147.243 (ttl 300); MX: "0 ." (ttl 205, the null-MX record,
reported verbatim); NS: elliott.ns.cloudflare.com. and
hera.ns.cloudflare.com. (ttl 21600); SOA ttl 1800; CNAME empty list.

### GET /dns?domain=example.com&type=MX
HTTP 200: {"domain": "example.com", "type": "MX", "status": 0,
"records": [{"name": "example.com.", "type": "MX", "ttl": 179,
"data": "0 ."}], "resolver": "dns.google (DNS-over-HTTPS)"}

### GET /dns?domain=example.com&type=BOGUS
HTTP 422 {"error": "invalid_dns_type", "detail": "'BOGUS' is not a
supported DNS record type. Supported types: A, AAAA, MX, NS, TXT,
CNAME, SOA."}

### GET /suggest?keywords=zqxbrew&limit=5 (one keyword)
HTTP 200 in 5.5s. checked_count 7 (one base x 7 TLDs), count 4:
zqxbrew.com, zqxbrew.org, zqxbrew.app, zqxbrew.dev, each
{"available": true, "source": "rdap", "registry_source": ...}.
Note field: "Only candidates verified available through the live
registry availability path are listed; unverified names are never
listed as available." Non-listings this run: .co (unsupported_tld in
this engine: no RDAP bootstrap entry and no port-43 route), .io
(port-43 blocked in sandbox), .net (check did not verify this run;
an earlier in-process probe returned registered: false for
zqxbrew.net, so the omission was a failed check applying the
verified-only rule, not a registered verdict).

### GET /suggest?keywords=zqx,brew&limit=3 (join patterns)
HTTP 200 in 9.2s. checked_count 15, count 3: zqx.app, zqx.dev, and
zqxbrew.com (a keyword-join candidate), all verified available.

### GET /suggest (missing keywords)
HTTP 422 {"error": "missing_parameter", ...}

## Regression (existing endpoints, same server build)

### GET /lookup?domain=google.com
HTTP 200, unchanged shape: keys _meta, cache, created, dnssec,
domain, events, expires, nameservers, registered, registrant,
registrar, registry_server, source, status, tld, updated;
registered true, registrar "MarkMonitor Inc.", created
1997-09-15T04:00:00Z, cache block present.

### GET /tlds
HTTP 200: rdap_tld_count 1203, complaint_tld_coverage {dev: rdap,
at: whois-port43, rs: whois-port43, pl: rdap, eu: whois-port43,
fi: rdap} - unchanged.

## Findings

1. Pre-existing bug in the stock service (not introduced by this
   extension): `query_port43`'s recv loop catches only timeouts, so
   a ConnectionResetError mid-read escapes `do_lookup` as a raw
   exception and the scaffold turns it into a generic 502. The new
   endpoints guard against it (a `_safe_lookup` wrapper converts it
   to the structured error shape, per-domain inside bulk), so the
   extension never fails a batch or surfaces a bare exception.
   Stock /lookup behavior was left byte-identical; fixing
   query_port43 itself is a separate decision.
2. .co has no route in this engine (absent from the live IANA RDAP
   bootstrap, no port-43 server mapped), so /suggest .co candidates
   are checked, never verify, and are never listed. The candidate
   TLD set was kept as tasked (com, co, io, net, org, app, dev).
3. Verisign RDAP intermittently drops connections from this sandbox
   (RemoteDisconnected / connection reset), roughly 1 attempt in
   several during the battery. Every occurrence surfaced as the
   service's structured 502 (or a per-domain error in bulk), and
   retries succeeded. No code change made for this; it matches the
   deployed service's existing upstream behavior.
