# Spec D: GeoBase Cities (wave 3, queue #4)

Approved by the user 2026-10-28 ("Build GeoDB Cities next"). Score 86.

## The comparable listing

GeoDB Cities by wirefreethought: 50,222 subscribers (live-verified
2026-10-28), rated 3/5 (60 votes), pricing Basic $0 / 1,000 per day,
Pro $20, Ultra $40, Mega $80 (per-day quotas). Complaint themes from its
own Discussions:
1. Recurring outages ("The API is unreachable... again").
2. Cities wrong, missing, or deleted: Rome (wikiDataId Q220) deleted,
   Surrey BC missing, Cluj-Napoca deleted, Sao Paulo findable only by ID,
   Princeton Ontario missing, Sevastopol returned in the Buryatia region.
3. Provider silence: many threads unanswered.

## The fix

Same upstream data the incumbent uses (GeoNames, CC BY; Wikidata CC0
cross-check in v2), served on the scaffold that has never gone down for
our other three APIs, with the complained-about places in the launch test
set and correct in the shipped data (all verified against the GeoNames
snapshot of 2026-10-28):
- Rome, geonameid 3169070, capital of Italy: present.
- Surrey, BC (6159905, pop 568,322): present.
- Cluj-Napoca (681290, pop 286,598): present.
- Sao Paulo: findable by plain-ASCII name search (diacritic folding).
- Sevastopol: admin region is Sevastopol itself, not Buryatia.
- Sterling, VA (4787534): present.

## Scope v1

Dataset: GeoNames cities15000 (34,191 populated places, population 15,000+
or capitals) + admin1 regions (3,865) + country info (252). Honest limit,
stated in the listing: places under 15,000 population arrive in v2 with
the cities500 expansion. Endpoints mirror the incumbent's core REST
surface under /v1/geo: countries list/get, country regions list/get,
region cities, cities search (namePrefix, countryIds, minPopulation,
sort, limit/offset), city get, city dateTime, city time, city distance,
nearby cities by coordinates. Response envelope matches the incumbent's
{data, metadata{currentOffset,totalCount}} shape so switching costs a
base-URL change.

## Pricing (RapidAPI, hard limits)

BASIC $0 / 2,000 per day (double the incumbent free quota), PRO $10
(vs $20), ULTRA $30 (vs $40), MEGA $70 (vs $80). Net after the 25% fee:
$7.50 / $22.50 / $52.50.

## Costs and risks

$0 end to end: GeoNames is CC BY (attribution line ships in responses and
docs), Render free tier (adds a fourth service: the keep-warm window must
shrink to stay inside 750 workspace hours). Ongoing: dataset refresh is a
re-download, scripted; the correction pipeline (user-reported place fixes
reviewed against Wikidata) is the v2 differentiator.
