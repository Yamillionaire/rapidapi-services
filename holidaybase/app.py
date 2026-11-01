"""HolidayBase - holidays and working-day arithmetic (spec: docs/spec-holidaybase.md).

Holiday data plus the working-day engine the holiday incumbents
underserve, from two MIT, fully offline data libraries:

- python-holidays (the served data): 250 canonical country calendars
  with subdivisions, per-country weekend definitions, and observed
  shifts computed by the library itself (its country calendars are
  built with observed=True, so entries named "... (observed)" are the
  library's own shifted dates - this service never invents a shift
  the library does not provide).
- holidata (the cross-check): every /holidays response recomputes the
  same country/year with holidata and reports date-level disagreements
  between the two libraries, so data QA is a visible part of the
  product instead of a private hope.

Honest limits (also stated in /health): national PUBLIC holidays only,
following the default calendars both libraries ship. Financial-market
holidays are NOT included. Regional/religious calendars are thinner
and holidata's regional entries are excluded from the cross-check
(scope: national entries, region == ""). Cross-checks are date-level:
the libraries name some shared holidays differently (python-holidays
"(observed)" vs holidata "(in lieu of)"), so names are shown for
context but only dates are compared.

Names: "name" is the English name where python-holidays exposes an
en_US localization for the country; "local_name" is the name in the
country calendar's default language. Where no en_US localization
exists, name falls back to the local name and the two are equal -
the library does not provide an English name and none is invented.

Types: python-holidays does not expose a per-holiday category for
individual entries in a loaded calendar; a loaded calendar exposes
only the categories it was built with, which for the default
calendars is {"public"}. Every item therefore carries
types == ["public"], derived from the loaded calendar's categories,
not asserted per holiday.

Weekends: python-holidays exposes per-country weekend days (for
example Fri/Sat for Egypt), and this service uses them. The fallback
where a calendar exposed none would be Sat/Sun; every calendar
checked in the pinned version does expose them.

Zero marginal cost, no key, no scraping. Shared scaffold server
(RapidAPI proxy-secret gate, structured JSON errors). Run:
python3 app.py (PORT env, default 8120). Needs:
pip install -r requirements.txt (holidays, holidata).
"""
import datetime
import os
import re
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))
from rapidapi_server import run

import holidays as holidays_lib
import holidata as holidata_lib
import importlib.metadata as _md

SERVICE = "holidaybase"
HOLIDAYS_VERSION = _md.version("holidays")
HOLIDATA_VERSION = _md.version("holidata")
DATA_VINTAGE = {"holidays": HOLIDAYS_VERSION, "holidata": HOLIDATA_VERSION}

# Canonical coverage: include_aliases=False, so alpha-3 aliases (USA
# for US, etc.) do not double-count countries. Aliases are still
# accepted as input (see _ALIASES below); they are just not listed
# as separate countries.
_SUPPORTED = holidays_lib.list_supported_countries(include_aliases=False)
_SUPPORTED_WITH_ALIASES = holidays_lib.list_supported_countries()
MAX_RANGE_DAYS = 1830          # working-days range cap: ~5 years, 422 beyond
MAX_ADD_DAYS = 3660            # add-working-days magnitude cap
_OBSERVED_RE = re.compile(r"\(observed\)", re.IGNORECASE)
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_cal_cache = {}
_cal_lock = threading.Lock()


def _err(status, code, detail):
    return status, {"error": code, "detail": detail}


def _vintage(payload):
    payload["data_vintage"] = dict(DATA_VINTAGE)
    return payload


# --------------------------------------------------------------------------
# Validation helpers.
# --------------------------------------------------------------------------
def _resolve_country(params):
    """Returns (country_code, error). Country codes are validated
    against the supported list (aliases like USA accepted and passed
    through to the library, which resolves them); anything else is a
    422 unsupported_country pointing at /countries, per spec."""
    raw = (params.get("country") or "").strip().upper()
    if not raw:
        return None, _err(422, "missing_parameter",
                          "Provide country= with an ISO country code, "
                          "for example country=US. See /countries.")
    if raw not in _SUPPORTED_WITH_ALIASES:
        return None, _err(422, "unsupported_country",
                          f"Country '{raw}' is not supported. "
                          "See /countries for the coverage list.")
    return raw, None


def _resolve_subdiv(country, params):
    """Returns (subdiv_or_None, error). Validated against the
    canonical subdivision list for the country when one exists;
    the library remains the final arbiter (its NotImplementedError
    for an unknown subdivision becomes a 422, never a 502)."""
    raw = (params.get("subdiv") or "").strip().upper()
    if not raw:
        return None, None
    canonical = country if country in _SUPPORTED else None
    known = _SUPPORTED.get(canonical, []) if canonical else []
    if known and raw not in known:
        return None, _err(422, "unsupported_subdivision",
                          f"Subdivision '{raw}' is not supported for "
                          f"{country}. See /countries for its list.")
    return raw, None


def _parse_date(raw, field):
    if raw is None or not _DATE_RE.match(raw.strip()):
        return None, _err(422, "invalid_date",
                          f"{field} must be a date as YYYY-MM-DD.")
    try:
        return datetime.date.fromisoformat(raw.strip()), None
    except ValueError:
        return None, _err(422, "invalid_date",
                          f"{field}='{raw}' is not a real calendar date.")


def _parse_year(params):
    raw = (params.get("year") or "").strip()
    if not raw:
        return datetime.date.today().year, None
    try:
        year = int(raw)
    except ValueError:
        return None, _err(422, "invalid_date",
                          "year must be an integer, for example year=2027.")
    if year < 1900 or year > 2200:
        return None, _err(422, "invalid_date",
                          "year must be between 1900 and 2200.")
    return year, None


# --------------------------------------------------------------------------
# Calendar construction (lazy, cached per country/subdiv/year-set/
# language so import and startup stay light).
# --------------------------------------------------------------------------
def _calendar(country, subdiv, years, language=None):
    """language=None builds the calendar in its default (local)
    language; language='en_US' builds the English localization."""
    key = (country, subdiv, tuple(sorted(years)), language)
    with _cal_lock:
        cal = _cal_cache.get(key)
    if cal is not None:
        return cal
    kwargs = {"years": sorted(years), "observed": True}
    if subdiv:
        kwargs["subdiv"] = subdiv
    if language:
        kwargs["language"] = language
    cal = holidays_lib.country_holidays(country, **kwargs)
    with _cal_lock:
        _cal_cache[key] = cal
    return cal


def _calendars(country, subdiv, years):
    """Returns (english_cal, local_cal). English uses the en_US
    localization when the country calendar supports it; otherwise
    the two are the same object and names equal local names."""
    local = _calendar(country, subdiv, years)
    if "en_US" in (local.supported_languages or ()) \
            and local.default_language != "en_US":
        english = _calendar(country, subdiv, years, language="en_US")
    else:
        english = local
    return english, local


def _weekend_days(cal):
    """Weekday numbers (Mon=0) the library says are weekend days for
    this country; Sat/Sun if a calendar ever exposes none."""
    weekend = getattr(cal, "weekend", None)
    if weekend:
        return set(weekend)
    return {5, 6}


def _is_working_day(d, country, subdiv):
    english, _local = _calendars(country, subdiv, [d.year])
    name = english.get(d)
    if name is not None:
        return False, f"holiday: {name}"
    if d.weekday() in _weekend_days(english):
        return False, "weekend"
    return True, None


# --------------------------------------------------------------------------
# holidata cross-check (national scope: entries with region == "").
# --------------------------------------------------------------------------
def _holidata_national(country, year):
    """Returns {date_iso: description} for holidata's national
    entries, or None when holidata has no usable calendar for the
    country (unknown country, or no default language and no English
    fallback, e.g. it covers only 34 countries)."""
    try:
        locale = holidata_lib.for_locale(country)
    except Exception:
        try:
            locale = holidata_lib.for_locale(country, "en")
        except Exception:
            return None
    try:
        entries = list(locale.get_holidays_of(year))
    except Exception:
        return None
    out = {}
    for entry in entries:
        if getattr(entry, "region", ""):
            continue  # regional entry: outside the national scope
        d = entry.date
        iso = d.date().isoformat() if hasattr(d, "date") else str(d)[:10]
        out[iso] = entry.description
    return out


def _cross_check(country, year, english_cal):
    holidata_dates = _holidata_national(country, year)
    if holidata_dates is None:
        return {"status": "holidata_unavailable_for_country"}
    served = {d.isoformat(): name for d, name in english_cal.items()}
    disagreements = []
    for iso in sorted(set(served) | set(holidata_dates)):
        in_served = iso in served
        in_holidata = iso in holidata_dates
        if in_served and in_holidata:
            continue
        disagreements.append({
            "date": iso,
            "source": "holidays_only" if in_served else "holidata_only",
            "holidays_name": served.get(iso),
            "holidata_name": holidata_dates.get(iso),
        })
    return {"status": "compared",
            "scope": "national (holidata entries with region == ''), "
                     "dates compared, names shown for context only",
            "holidays_count": len(served),
            "holidata_count": len(holidata_dates),
            "disagreements": disagreements}


# --------------------------------------------------------------------------
# Endpoints.
# --------------------------------------------------------------------------
def holidays_endpoint(params):
    country, err = _resolve_country(params)
    if err:
        return err
    subdiv, err = _resolve_subdiv(country, params)
    if err:
        return err
    year, err = _parse_year(params)
    if err:
        return err
    try:
        english, local = _calendars(country, subdiv, [year])
    except NotImplementedError as exc:
        return _err(422, "unsupported_subdivision", str(exc))
    types = sorted(getattr(english, "categories", None) or {"public"})

    # Observed entries the library itself computed: an entry whose
    # name carries "(observed)". Its base holiday gets this date as
    # its "observed" field only when a same-named base entry sits
    # within 7 days (observed shifts are weekend-adjacent; a Dec 31
    # "(observed)" entry belongs to next Jan 1, which is not in this
    # year's set, and must not be attached to this Jan 1).
    raw = sorted(english.items())
    observed_by_base = {}
    for d, name in raw:
        if _OBSERVED_RE.search(name):
            base = _OBSERVED_RE.sub("", name).strip().rstrip(";").strip()
            observed_by_base.setdefault(base, []).append(d)

    items = []
    for d, name in raw:
        iso = d.isoformat()
        local_name = local.get(d, name)
        is_observed_entry = bool(_OBSERVED_RE.search(name))
        if is_observed_entry:
            observed = iso
        else:
            observed = None
            for cand in observed_by_base.get(name, []):
                if abs((cand - d).days) <= 7:
                    observed = cand.isoformat()
                    break
        items.append({"date": iso, "name": name,
                      "local_name": local_name,
                      "types": types,
                      "observed": observed,
                      "is_observed_entry": is_observed_entry})
    payload = {"country": country, "subdiv": subdiv, "year": year,
               "count": len(items), "holidays": items,
               "cross_check": _cross_check(country, year, english)}
    return 200, _vintage(payload)


def is_working_day_endpoint(params):
    country, err = _resolve_country(params)
    if err:
        return err
    subdiv, err = _resolve_subdiv(country, params)
    if err:
        return err
    d, err = _parse_date(params.get("date"), "date")
    if err:
        return err
    try:
        working, reason = _is_working_day(d, country, subdiv)
    except NotImplementedError as exc:
        return _err(422, "unsupported_subdivision", str(exc))
    # Reason precedence: a holiday is reported even when the date is
    # also a weekend day (checked first in _is_working_day).
    payload = {"country": country, "subdiv": subdiv,
               "date": d.isoformat(), "working_day": working,
               "reason": None if working else reason}
    return 200, _vintage(payload)


def working_days_endpoint(params):
    country, err = _resolve_country(params)
    if err:
        return err
    subdiv, err = _resolve_subdiv(country, params)
    if err:
        return err
    start, err = _parse_date(params.get("from"), "from")
    if err:
        return err
    end, err = _parse_date(params.get("to"), "to")
    if err:
        return err
    if end < start:
        return _err(422, "invalid_date", "to must not be before from.")
    span = (end - start).days + 1
    if span - 1 > MAX_RANGE_DAYS:
        return _err(422, "range_too_large",
                    f"Range spans {span} days; the maximum is about "
                    f"5 years ({MAX_RANGE_DAYS} days between from and to).")
    count = 0
    d = start
    one = datetime.timedelta(days=1)
    try:
        while d <= end:  # inclusive of both endpoints, stated in /health
            working, _reason = _is_working_day(d, country, subdiv)
            if working:
                count += 1
            d += one
    except NotImplementedError as exc:
        return _err(422, "unsupported_subdivision", str(exc))
    payload = {"country": country, "subdiv": subdiv,
               "from": start.isoformat(), "to": end.isoformat(),
               "count": count}
    return 200, _vintage(payload)


def add_working_days_endpoint(params):
    country, err = _resolve_country(params)
    if err:
        return err
    subdiv, err = _resolve_subdiv(country, params)
    if err:
        return err
    start, err = _parse_date(params.get("date"), "date")
    if err:
        return err
    raw_days = (params.get("days") or "").strip()
    try:
        days = int(raw_days)
    except (TypeError, ValueError):
        return _err(422, "invalid_parameter",
                    "days must be an integer (negative steps backwards), "
                    "for example days=10 or days=-5.")
    if abs(days) > MAX_ADD_DAYS:
        return _err(422, "invalid_parameter",
                    f"days magnitude is capped at {MAX_ADD_DAYS}.")
    # Step day by day in code: move one calendar day in the requested
    # direction; each landing on a working day consumes one of the
    # requested days. days=0 returns the start date unchanged, even
    # if it is not itself a working day.
    step = 1 if days >= 0 else -1
    remaining = abs(days)
    d = start
    one = datetime.timedelta(days=step)
    try:
        while remaining:
            d += one
            working, _reason = _is_working_day(d, country, subdiv)
            if working:
                remaining -= 1
    except NotImplementedError as exc:
        return _err(422, "unsupported_subdivision", str(exc))
    payload = {"country": country, "subdiv": subdiv,
               "start_date": start.isoformat(), "days_added": days,
               "result_date": d.isoformat()}
    return 200, _vintage(payload)


def countries_endpoint(params):
    countries = [{"code": code, "subdivisions": subdivs}
                 for code, subdivs in sorted(_SUPPORTED.items())]
    payload = {"countries": countries, "count": len(countries),
               "note": "Canonical ISO codes as loaded from "
                       "python-holidays list_supported_countries"
                       "(include_aliases=False); alpha-3 aliases "
                       "(e.g. USA) are accepted as input but not "
                       "double-counted here."}
    return 200, _vintage(payload)


def health(params):
    return 200, {
        "status": "ok", "service": SERVICE,
        "engine": {"holidays": HOLIDAYS_VERSION,
                   "holidata": HOLIDATA_VERSION},
        "data_vintage": {"holidays_version": HOLIDAYS_VERSION,
                         "holidata_version": HOLIDATA_VERSION,
                         "release_dates": "not available from the "
                         "installed package metadata; versions only"},
        "countries_loaded": len(_SUPPORTED),
        "limits": {
            "scope": "National public holidays only, from the default "
                     "calendars of python-holidays (served) cross-checked "
                     "against holidata (national entries only).",
            "financial_market_holidays": "NOT included (a different "
                     "dataset; claiming them would be a silent gap).",
            "types": "Loaded default calendars expose only the 'public' "
                     "category, so every holiday carries types=['public']; "
                     "python-holidays exposes no per-holiday category for "
                     "individual entries in these calendars.",
            "observed": "Observed dates are included only where "
                        "python-holidays itself computes them (entries "
                        "named '(observed)'); no shift is invented.",
            "local_name": "English names use the library's en_US "
                          "localization where it exists; where it does "
                          "not, name equals local_name.",
            "weekend": "Per-country weekend days from python-holidays "
                       "where exposed (e.g. Fri/Sat in some countries); "
                       "Sat/Sun is the fallback if a calendar exposes none.",
            "working_days_range": "Inclusive of both endpoints; ranges "
                                  "over about 5 years are refused (422).",
            "future_years": "Future-year dates depend on legislated "
                            "calendars and carry the data_vintage label.",
        },
        "endpoints": ["GET /holidays?country=&year=&subdiv=",
                      "GET /is-working-day?country=&date=&subdiv=",
                      "GET /working-days?country=&from=&to=&subdiv=",
                      "GET /add-working-days?country=&date=&days=&subdiv=",
                      "GET /countries", "GET /health"],
        "note": "Every non-health response carries data_vintage. "
                "Every failure is a structured JSON error."}


if __name__ == "__main__":
    run({"/holidays": holidays_endpoint,
         "/is-working-day": is_working_day_endpoint,
         "/working-days": working_days_endpoint,
         "/add-working-days": add_working_days_endpoint,
         "/countries": countries_endpoint,
         "/health": health},
        int(os.environ.get("PORT", "8120")), SERVICE)
