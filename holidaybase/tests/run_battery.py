"""HolidayBase local battery (2026-11-01).

Starts holidaybase/app.py on a throwaway port (18220, to avoid the
8120 default which GateCheck uses on this VM), runs the checks from
the build task, restarts it with RAPIDAPI_PROXY_SECRET set for the
gate checks, and writes battery-2026-11-01.md next to this script.

Run: /tmp/hb-venv/bin/python tests/run_battery.py
(the venv must have holidays==0.107 and holidata==2026.9.0)
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "..", "app.py")
PORT = 18220
BASE = f"http://127.0.0.1:{PORT}"
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")


def get(path, headers=None):
    req = urllib.request.Request(BASE + path, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


def start_server(env_extra=None):
    env = dict(os.environ, PORT=str(PORT))
    env.pop("RAPIDAPI_PROXY_SECRET", None)
    if env_extra:
        env.update(env_extra)
    proc = subprocess.Popen([sys.executable, APP], env=env,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            status, _ = get("/health")
            if status == 200:
                return proc
        except Exception:
            pass
        time.sleep(0.5)
    proc.kill()
    raise RuntimeError("server did not come up")


def main():
    proc = start_server()
    try:
        # /health
        status, health = get("/health")
        check("health 200, service + versions",
              status == 200 and health["service"] == "holidaybase"
              and health["engine"]["holidays"] == "0.107"
              and health["engine"]["holidata"] == "2026.9.0",
              json.dumps(health["engine"]))

        # US 2027 holidays
        status, us = get("/holidays?country=US&year=2027")
        by_date = {h["date"]: h for h in us.get("holidays", [])}
        check("US 2027 200 + count", status == 200 and us["count"] == 15,
              f"count={us.get('count')}")
        check("US 2027-01-01 New Year's Day",
              by_date.get("2027-01-01", {}).get("name") == "New Year's Day",
              str(by_date.get("2027-01-01")))
        check("US 2027-07-04 Independence Day present",
              by_date.get("2027-07-04", {}).get("name") == "Independence Day",
              str(by_date.get("2027-07-04")))
        check("US Independence Day observed = 2027-07-05 (library's own)",
              by_date.get("2027-07-04", {}).get("observed") == "2027-07-05",
              f"observed={by_date.get('2027-07-04', {}).get('observed')}")
        check("US 2027-07-05 is the observed entry itself",
              by_date.get("2027-07-05", {}).get("is_observed_entry") is True,
              str(by_date.get("2027-07-05")))
        check("US types == ['public'] (only category the loaded calendar exposes)",
              all(h["types"] == ["public"] for h in us["holidays"]))
        check("US data_vintage present",
              us.get("data_vintage") == {"holidays": "0.107",
                                         "holidata": "2026.9.0"},
              str(us.get("data_vintage")))
        cc = us.get("cross_check", {})
        check("US cross_check present, compared",
              cc.get("status") == "compared" and "holidata_count" in cc
              and "disagreements" in cc,
              f"holidata_count={cc.get('holidata_count')} "
              f"disagreements={json.dumps(cc.get('disagreements'))}")
        check("US cross_check flags 2027-11-26 as holidata_only "
              "(day after Thanksgiving: holidata has it, python-holidays does not)",
              any(d["date"] == "2027-11-26" and d["source"] == "holidata_only"
                  for d in cc.get("disagreements", [])))

        # US subdiv CA
        status, ca = get("/holidays?country=US&year=2027&subdiv=CA")
        ca_names = " | ".join(h["name"] for h in ca.get("holidays", []))
        check("US-CA 2027 includes Cesar Chavez Day (subdiv works)",
              status == 200 and "Cesar Chavez Day" in ca_names,
              f"count={ca.get('count')}")

        # FR local names: name English, local_name French
        status, fr = get("/holidays?country=FR&year=2027")
        fr_by = {h["date"]: h for h in fr.get("holidays", [])}
        jan1 = fr_by.get("2027-01-01", {})
        check("FR 2027-01-01 name English / local_name French",
              jan1.get("name") == "New Year's Day"
              and jan1.get("local_name") == "Jour de l'an",
              str(jan1))

        # JP cross-check unavailable (holidata covers 34 countries, not JP)
        status, jp = get("/holidays?country=JP&year=2027")
        check("JP cross_check = holidata_unavailable_for_country",
              jp.get("cross_check") == {"status": "holidata_unavailable_for_country"},
              str(jp.get("cross_check")))

        # is-working-day FR 2027-05-01: a Saturday AND May Day.
        # Precedence stated in app.py: holiday is reported first.
        status, wd = get("/is-working-day?country=FR&date=2027-05-01")
        check("FR 2027-05-01 (Sat + May Day) not working, reason holiday first",
              status == 200 and wd["working_day"] is False
              and str(wd["reason"]).startswith("holiday:"),
              str(wd))
        # Plain Tuesday: 2027-05-04 (May 4, 2027 is a Tuesday, no FR holiday)
        status, wd2 = get("/is-working-day?country=FR&date=2027-05-04")
        check("FR 2027-05-04 (plain Tuesday) working, reason null",
              status == 200 and wd2["working_day"] is True
              and wd2["reason"] is None, str(wd2))
        # A plain Sunday for the weekend reason
        status, wd3 = get("/is-working-day?country=FR&date=2027-05-02")
        check("FR 2027-05-02 (Sunday) not working, reason weekend",
              status == 200 and wd3["working_day"] is False
              and wd3["reason"] == "weekend", str(wd3))

        # working-days DE, hand-checked span: Mon 2027-01-04 .. Sun 2027-01-17
        # is exactly two Mon-Sun weeks. Weekdays: Jan 4-8 and Jan 11-15 = 10.
        # DE national holidays in that span: none (only Jan 1 that month).
        # Hand count = 10.
        status, span = get("/working-days?country=DE&from=2027-01-04&to=2027-01-17")
        check("DE 2027-01-04..2027-01-17 working days == 10 (hand-checked)",
              status == 200 and span["count"] == 10, str(span))
        # Range cap: >5 years -> 422
        status, big = get("/working-days?country=DE&from=2020-01-01&to=2027-01-01")
        check("DE range over 5 years -> 422 range_too_large",
              status == 422 and big["error"] == "range_too_large", str(big))

        # add-working-days round trip, JP from Mon 2027-01-04.
        # Hand expectation for +5: Jan 5,6,7,8 are working (4); Jan 9-10
        # weekend; Jan 11 is Coming of Age Day (JP holiday); Jan 12 = 5th.
        status, fwd = get("/add-working-days?country=JP&date=2027-01-04&days=5")
        check("JP 2027-01-04 +5 working days == 2027-01-12 (hand-checked)",
              status == 200 and fwd["result_date"] == "2027-01-12", str(fwd))
        status, back = get("/add-working-days?country=JP&date=2027-01-12&days=-5")
        check("JP 2027-01-12 -5 working days == 2027-01-04 (round trip)",
              status == 200 and back["result_date"] == "2027-01-04", str(back))

        # /countries
        status, countries = get("/countries")
        check("/countries count > 100 (canonical, aliases not double-counted)",
              status == 200 and countries["count"] > 100,
              f"count={countries.get('count')}")
        us_entry = [c for c in countries["countries"] if c["code"] == "US"]
        check("/countries US entry carries subdivisions incl. CA",
              bool(us_entry) and "CA" in us_entry[0]["subdivisions"])

        # Errors
        status, bad = get("/holidays?country=XX&year=2027")
        check("unknown country XX -> 422 unsupported_country",
              status == 422 and bad["error"] == "unsupported_country", str(bad))
        status, bad2 = get("/is-working-day?country=FR&date=2027-13-40")
        check("bad date 2027-13-40 -> 422 invalid_date",
              status == 422 and bad2["error"] == "invalid_date", str(bad2))
        status, bad3 = get("/holidays?country=US&year=2027&subdiv=XX")
        check("bad subdiv XX -> 422 unsupported_subdivision",
              status == 422 and bad3["error"] == "unsupported_subdivision",
              str(bad3))
    finally:
        proc.terminate()

    # Gate: RAPIDAPI_PROXY_SECRET set
    proc = start_server({"RAPIDAPI_PROXY_SECRET": "battery-secret"})
    try:
        status, denied = get("/holidays?country=US&year=2027")
        check("gate: no secret header -> 401 unauthorized",
              status == 401 and denied["error"] == "unauthorized", str(denied))
        status, allowed = get("/holidays?country=US&year=2027",
                              {"X-RapidAPI-Proxy-Secret": "battery-secret"})
        check("gate: correct secret header -> 200",
              status == 200 and allowed.get("count") == 15,
              f"status={status}")
        status, open_health = get("/health")
        check("gate: /health stays open without secret",
              status == 200 and open_health["service"] == "holidaybase")
    finally:
        proc.terminate()

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    lines = [f"# HolidayBase local battery - 2026-11-01",
             "",
             f"Server: app.py on port {PORT} (throwaway port; the 8120 "
             "default is GateCheck's on this VM). Engines: holidays "
             "0.107, holidata 2026.9.0 (the pinned requirements.txt).",
             "",
             f"Result: {passed}/{len(RESULTS)} checks passed.",
             "",
             "| # | Check | Result | Detail |",
             "|---|-------|--------|--------|"]
    for i, (name, ok, detail) in enumerate(RESULTS, 1):
        detail = detail.replace("|", "/")[:300]
        lines.append(f"| {i} | {name} | {'PASS' if ok else 'FAIL'} | {detail} |")
    lines += ["",
              "Notes:",
              "- FR 2027-05-01 is both a Saturday and May Day. Reason "
              "precedence in app.py: holiday is checked (and reported) "
              "before weekend, so the reason is the holiday name.",
              "- DE hand-check: 2027-01-04..2027-01-17 is two full "
              "Mon-Sun weeks (10 weekdays) with no German national "
              "holiday in the span (January's only one is Jan 1), so "
              "the hand count is 10.",
              "- JP hand-check: from Mon 2027-01-04, working days are "
              "Jan 5, 6, 7, 8, then Jan 12 (Jan 9-10 weekend, Jan 11 "
              "Coming of Age Day), so +5 lands on 2027-01-12 and -5 "
              "from there returns to 2027-01-04.",
              "- Observed dates come only from python-holidays itself "
              "(entries it names '(observed)', with observed=True); "
              "the service invents no shifts.",
              ""]
    out = os.path.join(HERE, "battery-2026-11-01.md")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print(f"\n{passed}/{len(RESULTS)} passed; wrote {out}")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
