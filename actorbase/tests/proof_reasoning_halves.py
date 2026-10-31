"""ActorBase supplementary proof (2026-10-31): the reasoning
halves of /three-reads and directed /table-read.

Why this exists: in the build sandbox the Edge speech websocket
stalls through the egress proxy, so the local battery's
/three-reads and directed /table-read checks cannot complete
(they fail at synthesis, after the reasoning succeeds - the
endpoint correctly returns the synthesis error and discards the
reads). The DEPLOYED battery proves the synthesis half end to
end (deployed /perform and /table-read: real audio, measured
timings). This proof covers the other half against the REAL
Gemini engine (via tests/connector_bridge.py): it imports the
service module, replaces ONLY the synthesis function in this
test process with a stand-in that returns the service's own
measured silence (production code untouched), and calls the
real endpoint functions, so the Gemini tactics/subtext, the
direction interpretation, the delivery planning and the
response shaping are all the production code paths.

Results: proof-reasoning-halves-2026-10-31.json next to this
file. Run with the venv interpreter (edge-tts importable):
  /tmp/actorbase-venv/bin/python proof_reasoning_halves.py
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

results = {"checks": [], "samples": {},
           "environment": "Real Gemini via tests/connector_bridge.py; "
                          "synthesis replaced in this test process "
                          "only, by measured silence, because the "
                          "sandbox egress stalls the speech "
                          "websocket (deployed battery proves real "
                          "audio on the same code paths)."}


def check(name, cond, detail=""):
    results["checks"].append(
        {"name": name, "pass": bool(cond), "detail": detail})
    print(("PASS " if cond else "FAIL ") + name
          + (f" - {detail}" if detail else ""))


bridge = subprocess.Popen(
    [sys.executable, os.path.join(HERE, "connector_bridge.py"), "8898"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1.0)
os.environ["GEMINI_API_KEY"] = "local-bridge-placeholder"
os.environ["GEMINI_BASE_URL"] = "http://127.0.0.1:8898/v1beta"
try:
    import app

    def fake_synth(jobs):
        # One second of the service's own measured silence per
        # segment: enough for real MP3 frame measurement.
        return [app.silence_ms(1000) for _ in jobs], None

    app.synthesize_segments = fake_synth

    payload, err = app.do_three_reads({
        "line": "I never loved you.",
        "context": "Final scene. She has rehearsed this lie all "
                   "act; saying it is the only way to make him "
                   "leave town and live.",
        "persona": "leading-lady"})
    reads = (payload or {}).get("reads", [])
    tactics = [r["tactic"].strip().lower() for r in reads]
    params = {(r["emotion"], r["intensity"]) for r in reads}
    check("/three-reads reasoning: 3 reads, distinct tactics, "
          "differing delivery params, notes present",
          err is None and len(reads) == 3
          and len(set(tactics)) == 3 and len(params) >= 2
          and all(r["subtext"] and r["delivery_note"] for r in reads),
          f"tactics={tactics}, params={sorted(params)}")
    if payload:
        results["samples"]["three_reads"] = {
            "line": payload["line"],
            "reads": [{k: r[k] for k in ("read", "tactic", "subtext",
                                         "emotion", "intensity",
                                         "emphasis", "delivery_note")}
                      for r in reads]}

    time.sleep(20)  # quota pacing, as in the main battery
    payload, err = app.do_table_read({
        "cast": {"KING": {"persona": "patriarch"},
                 "FOOL": {"persona": "trickster"}},
        "lines": [
            {"speaker": "KING", "line": "Speak plainly, fool.",
             "direction": "barely contained fury, each word "
                          "weighed like a stone"},
            {"speaker": "FOOL",
             "line": "Plainly, then: the crown is heavy because "
                     "the head is empty."}]})
    tm = (payload or {}).get("timing_map", [])
    check("/table-read direction: interpreted into the delivery "
          "vocabulary (anger) for the directed line",
          err is None and len(tm) == 2
          and tm[0]["direction_interpreted"] is True
          and tm[0]["emotion"] == "anger",
          f"map={[(t['emotion'], t['direction_interpreted']) for t in tm]}")
    if payload:
        results["samples"]["table_read_directed"] = {
            "timing_map": tm, "warnings": payload["warnings"]}
finally:
    bridge.terminate()

failed = [c for c in results["checks"] if not c["pass"]]
out = os.path.join(HERE, "proof-reasoning-halves-2026-10-31.json")
with open(out, "w") as fh:
    json.dump(results, fh, indent=2)
print(f"\n{len(results['checks']) - len(failed)}/{len(results['checks'])} "
      f"checks passed; proof at {out}")
sys.exit(1 if failed else 0)
