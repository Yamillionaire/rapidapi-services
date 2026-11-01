# HolidayBase: holidays, working days, and a data vintage on every answer

Holiday data goes stale quietly: legislatures add public holidays,
and an API that never says which data it is serving leaves you to
find out in production. Every HolidayBase response carries
`data_vintage` with the exact library versions behind it
(holidays 0.107, holidata 2026.9.0 at launch), and every /holidays
answer is cross-checked against a second, independent library.

## The launch battery (2026-11-01, 28/28 checks)

- US 2027: 15 holidays including New Year's Day and Independence
  Day with its library-computed observed date (2027-07-05).
  No observed shift is ever invented: an observed date appears
  only when the source library itself computes one.
- The cross-check earns its keep on day one: for the US in 2027
  the two libraries disagree on exactly one date - the Day after
  Thanksgiving, present in holidata only - and the response says
  so instead of hiding it.
- Working-day math, hand-verified: Germany, 2027-01-04 to
  2027-01-17 = 10 working days. Japan: 2027-01-04 plus 5 working
  days = 2027-01-12 (skipping the weekend and Coming of Age Day),
  and minus 5 returns exactly to the start.
- Country weekends come from the library, not an assumption:
  Egypt's Friday/Saturday weekend is honored.
- Coverage is reported as loaded: 250 countries at launch, and an
  unknown country is a named 422, never a silent empty list.

## What is not included, on purpose

Financial-market holidays are a different dataset and are not
claimed. Regional and religious calendars are thinner than
national public holidays, and the listing says so. The category's
incumbents are mostly healthy and silent; HolidayBase is sold on
the working-day engine, the cross-check, and the vintage label -
reliability, not rescued pain.
