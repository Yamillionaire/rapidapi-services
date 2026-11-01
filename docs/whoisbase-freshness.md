# Fresh records, and a force flag that actually forces

Whois Lookup by Zozor54 (3,811 subscribers, rated 3/5) carries three
recurring complaints across its 29 Discussion threads, every one of
them Unanswered: records that stay stale for hours even when callers
pass the provider's force-refresh flag, timeouts that arrive as bare
504s, and blank or null data for whole TLDs - users name .dev, .at,
.rs, .pl, .eu and .fi. WhoisBase was built so each failure mode has
nowhere to live. Lookups go live to the registry: RDAP resolved
through the IANA bootstrap, and a port-43 query to the registry's own
whois server for TLDs that run no RDAP endpoint. The cache holds a
record for at most 300 seconds, every response prints its cache state
and the record's age in seconds, and fresh=true (or force=1, the
incumbent's own flag name) bypasses the cache and re-asks the
registry before answering.

Spotlight description (211 characters): WhoisBase looks domains up
live at the registry: RDAP via the IANA bootstrap, port-43 where no
RDAP exists. Every answer shows its cache age, fresh=true truly
refetches, and the incumbent's $10 Pro tier is free.

Verified against the live WhoisBase service on 2026-10-29:

| Test | Result |
| --- | --- |
| .com (google.com) over RDAP | 200, registrar MarkMonitor Inc., created 1997-09-15, expires 2028-09-14, 4 nameservers, about 1.1s cold |
| .dev (web.dev) and .pl (allegro.pl) over RDAP | 200, full records - two of the TLDs users report blank on the incumbent |
| .fi (finnair.fi) over RDAP | 200, created 1991-01-01, 4 nameservers |
| .at (nic.at) over port-43 | 200, registered, created 2000-08-25, 5 nameservers - a TLD with no RDAP endpoint anywhere |
| .eu (eurid.eu) over port-43 | 200, registrar EURid vzw, 6 nameservers |
| .rs (rnids.rs) over port-43 | 200, registrar RNIDS, created 2008-03-10, statuses Active and Registry lock, 6 nameservers |
| .de (example.de) over port-43 | 200, status connect, with the registry's data restriction labeled in the response instead of padded fields |
| Cache honesty | A repeat call returns cached: true with the record's age and its 300-second TTL; ?fresh=true and ?force=1 both return cached: false, age_seconds: 0, straight from the registry |
| Unregistered .com | 200 with registered: false and the full schema (60-second negative TTL), never blank fields that make you guess |
| Missing parameter, garbage domain, an IP address, an unsupported TLD | A named 422 JSON error for each - no bare 504s, no empty 200s anywhere in the test set |
| Coverage map (/tlds) | 1,203 TLDs over RDAP from the live IANA bootstrap, plus the port-43 fallback map |

And the pricing answers too: the incumbent charges $10 a month for
its entry tier. WhoisBase Pro is free at 10,000 lookups a month,
Ultra is $20 against their $30, and Mega is $70 against their $80,
all hard limits.

## The availability extension (2026-11-01)

The bulk case from the extension battery, run against the live engine:

| Case | Result |
| --- | --- |
| Bulk check of 4 (google.com, an unregistered .com, one invalid entry, example.org) | 200 with per-domain records in request order: 2 registered, 1 available, and the invalid entry as its own named error in place - the batch never fails for one bad domain |
| Bulk over the cap (51 domains) | A named 422, not a silent truncation |
| Metering honesty | The response itself states each domain checked counts as one request - no hidden quota burn |
| Suggestions | Only names verified available through the same registry path are listed; checked_count is reported, and a TLD with no registry route is checked, never verified, and never listed |
| DNS | All seven record types for example.com via DNS-over-HTTPS, TTLs exactly as returned |
