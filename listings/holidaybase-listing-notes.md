# HolidayBase: Studio listing notes (for the browser-lane listing session)

Prepared 2026-11-01 at build time. The listing itself (Studio
create/PRIVATE, plans, proxy-secret wiring, publish, gateway test,
Spotlight) runs in the parent's browser lane, in SMALL CHUNKED
TASKS (basics, then endpoints, then pricing plus proxy secret).
Service is live on Render first; see the registry's sweep-derived
originals section for the service id and URL.

## Basics

- Name: HolidayBase
- Base URL: confirm the exact subdomain from the Render service
  record before saving (Render suffixes the name when the bare one
  is taken globally)
- Short description: Public holidays for 250 countries plus the
  working-day math payroll actually calls, cross-checked against
  a second data library, with the data vintage on every response.
- Category: Calendar / Date and Time (provider's pick in Studio)

## Endpoints (6)

- GET /holidays?country=US&year=2027&subdiv=CA - holidays with
  name, local name, library-computed observed date when one
  exists, and a cross_check block against the second library.
- GET /is-working-day?country=FR&date=2027-05-01 - boolean plus
  the reason (weekend / named holiday) when false.
- GET /working-days?country=DE&from=&to= - count in a range
  (5-year cap).
- GET /add-working-days?country=JP&date=&days=10 - both
  directions (negative days step back).
- GET /countries - coverage as actually loaded (250 countries).
- GET /health - status, engine versions, honest limits (open).

Every non-health response carries data_vintage with the library
versions behind the answer.

Full machine-readable spec: listings/holidaybase-openapi.json.

## Plans (hard limits, monthly quotas)

BASIC $0 / 5,000; PRO $0 / 100,000 (Calendarific's $10 tier made
free - the hook); ULTRA $20 / 500,000 (vs their $30 unlimited);
MEGA $45 / 2,000,000.

## Proxy secret wiring (before publish)

1. In Studio, copy the API's proxy secret.
2. Set it on the Render service as RAPIDAPI_PROXY_SECRET
   (render_api.py set-env), then trigger a deploy.
3. VERIFY THE GATE AT THE SERVICE: GET /holidays?country=US
   &year=2027 without the header must return 401
   {"error": "unauthorized"}; with the header, 200 with the
   holiday list; GET /health stays open. If the gate is not
   active after the first deploy, deploy once more and re-verify
   (env race, learned 2026-10-28). NOTE: the service was
   gate-tested at build time with a temporary secret that was NOT
   retained, so the origin currently sits GATED under that
   unrecorded value. Setting the Studio secret overwrites it;
   re-verify right after, before publishing.
4. Publish, then run the Hub gateway test (subscribe the owner's
   test account to BASIC first): GET /add-working-days
   country=JP, date=2027-01-04, days=5 - expect result_date
   2027-01-12. Retry once on a cold-start timeout.

## Spotlight (after publish, same session)

Description must stay UNDER 280 characters. Draft (about 240):
"Holidays plus the working-day math payroll actually calls:
counts, add-working-days in both directions, two data libraries
cross-checked, and the data vintage printed on every response.
250 countries. Proof inside."
Post via the URL tab with the GitHub blob URL of
docs/holidaybase-reliability.md on
github.com/Yamillionaire/rapidapi-services.

## Honesty notes for the overview copy (do not oversell)

- Financial-market holidays are NOT included; do not claim them.
- Coverage is national public holidays in 250 countries; regional
  and religious calendars are thinner - say so.
- The category's incumbents are healthy; sell reliability, the
  working-day engine, and the vintage label - not rescued pain.
