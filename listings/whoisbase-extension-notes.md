# WhoisBase extension: Studio update notes (for the browser-lane session)

Prepared 2026-11-01. WhoisBase is ALREADY LIVE (Hub:
https://rapidapi.com/YamilLittle/api/whoisbase, Studio API ID
api_d929ebc1-41a9-4113-8fab-59602753880f). The DomainBase
extension (spec-domainbase.md) added four endpoints to the same
service; the service has been redeployed from the same repo, and
its existing RAPIDAPI_PROXY_SECRET is unchanged - no secret work
is needed for this update.

## What to change in Studio (small chunks)

1. Endpoints: add the four new GET endpoints from
   listings/whoisbase-openapi.json (updated in this build):
   - GET /availability?domain=
   - GET /availability/bulk?domains=
   - GET /dns?domain=&type=
   - GET /suggest?keywords=&limit=
2. Overview/description: add the domain-availability section:
   "Now with domain availability built in: /availability promotes
   the unregistered answer to a first-class result with the
   registry source named and the same cache block; /availability
   /bulk checks up to 50 domains in one call (each domain counts
   as one request); /dns returns live DNS records via
   DNS-over-HTTPS with TTLs as returned; /suggest returns only
   name variants verified available against the registry - an
   unverified suggestion is never listed. Premium status is
   reported only when a registry itself publishes it, never
   guessed."
3. Plans: UNCHANGED (BASIC $0/250mo, PRO $0/10,000mo, ULTRA
   $20/100,000mo, MEGA $70/500,000mo hard). The bulk metering
   line ("each domain checked counts as one request") belongs in
   the endpoint description, not the plan grid.
4. Gateway test after saving: GET /availability?domain=
   google.com through the Hub - expect 200, available: false,
   registry_source rdap.verisign.com, cache block present. Then
   GET /availability/bulk with two domains - expect per-domain
   records and the metering line.
5. Spotlight: the existing Spotlight stays; if Studio allows an
   edit, the proof doc docs/whoisbase-freshness.md gained the
   bulk-check case in this build (same GitHub blob URL).

## Honesty notes

- Availability is only as final as the registry's answer at that
  second; the cache block rides on every availability response
  and fresh=true bypasses - keep that wording.
- .co lookups route through the same engine; where a TLD has no
  RDAP or port-43 route the structured 422 answers, same as
  /lookup. Do not claim universal TLD coverage.
