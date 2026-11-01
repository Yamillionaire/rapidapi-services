#!/usr/bin/env python3
"""Proof battery for SwiftHumanize.

Runs against a live local instance (default http://127.0.0.1:8115).
For each sample: POST /score before, POST /humanize, POST /score on
the output, plus preservation and em-dash assertions. Writes a JSON
record and a human-readable markdown record into ../proofs/.

Usage: python3 run_proofs.py [base_url] [secret]
The secret, when given, is sent as X-SwiftHumanize-Secret and is
never written to the proof files.
"""
import json
import os
import sys
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8115"
SECRET = sys.argv[2] if len(sys.argv) > 2 else ""
HERE = os.path.dirname(os.path.abspath(__file__))
PROOFS = os.path.join(HERE, "..", "proofs")
EM_DASH = "\u2014"  # escape form, keeps the literal character out of project files

SAMPLES = [
    {
        "id": "sample-1-generic-ai-paragraph",
        "kind": "generic AI-sounding paragraph (composed for this test)",
        "tone": "keep",
        "strength": "standard",
        "text": (
            "In today's fast-paced world, effective communication plays a crucial role in "
            "achieving success. Moreover, it is important to note that successful teams "
            "leverage a comprehensive range of tools, strategies, and techniques to foster "
            "collaboration. Furthermore, by utilizing cutting-edge technology, organizations "
            "can streamline their workflows, enhance their productivity, and elevate their "
            "overall performance. This seamless integration serves as a testament to the "
            "transformative power of innovation in the modern workplace."
        ),
    },
    {
        "id": "sample-2-business-email",
        "kind": "short business email in stiff AI style",
        "tone": "professional",
        "strength": "standard",
        "text": (
            "Dear Team, I hope this email finds you well. I am writing to inform you that "
            "our quarterly meeting has been rescheduled to March 14 at 2:30 PM in Conference "
            "Room B. Additionally, please be advised that the deadline for the Harrison "
            "project report has been extended to March 21. It is important to note that "
            "attendance is mandatory, and all team members are required to review the "
            "attached documents, complete the assigned tasks, and prepare their updates "
            "prior to the meeting. Thank you for your continued dedication and commitment "
            "to excellence. Best regards, Dana Whitfield"
        ),
    },
    {
        "id": "sample-3-assistant-style",
        "kind": "paragraph in typical assistant style",
        "tone": "keep",
        "strength": "standard",
        "text": (
            "Here is a summary of the key points. The report covers three main areas: "
            "revenue growth, customer retention, and operational efficiency. Revenue grew "
            "by 12 percent in the fourth quarter, which is a strong result. Customer "
            "retention improved as well, rising to 94 percent. Operational efficiency also "
            "improved, with processing time reduced by 8 minutes per order. Overall, the "
            "results are positive across all three areas, and the outlook for the next "
            "quarter remains strong. Let me know if you would like me to expand on any "
            "of these points."
        ),
    },
]

STYLE_TEST = {
    "id": "style-sample-voice-match",
    "kind": "style_sample path: plain company note rewritten toward a blunt, short-sentence voice",
    "tone": "keep",
    "strength": "standard",
    "style_sample": (
        "Look, the numbers do not lie. We shipped late. Twice. Nobody is happy about it, "
        "least of all me. So we fix the schedule, we tell the client the truth, and we "
        "do not let it happen a third time. Simple as that."
    ),
    "text": (
        "It is important to note that the delivery timeline for the Patterson order has "
        "been adjusted. Moreover, the revised schedule indicates that the shipment will "
        "arrive on November 9 rather than November 4, and the client will be notified "
        "of this change through the appropriate channels in a timely manner."
    ),
}


def call(path, payload):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json",
                 **({"X-SwiftHumanize-Secret": SECRET} if SECRET else {})},
        method="POST")
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))


def run_case(case):
    before = call("/score", {"text": case["text"]})
    request = {"text": case["text"], "tone": case["tone"],
               "strength": case["strength"]}
    if case.get("style_sample"):
        request["style_sample"] = case["style_sample"]
    result = call("/humanize", request)
    after = call("/score", {"text": result["humanized"]})
    return {
        "id": case["id"],
        "kind": case["kind"],
        "tone": case["tone"],
        "strength": case["strength"],
        "style_sample": case.get("style_sample"),
        "original": case["text"],
        "score_before": before,
        "humanized": result["humanized"],
        "engine": result["engine"],
        "engine_note": result["engine_note"],
        "preserved": result["preserved"],
        "score_after": after,
        "checks": {
            "no_em_dash_in_output": EM_DASH not in result["humanized"],
            "score_improved": after["human_likeness_score"] > before["human_likeness_score"],
            "names_preserved": result["preserved"]["names_preserved"],
            "numbers_preserved": result["preserved"]["numbers_preserved"],
            "quotes_preserved": result["preserved"]["quotes_preserved"],
        },
    }


def main():
    cases = [run_case(c) for c in SAMPLES] + [run_case(STYLE_TEST)]
    os.makedirs(PROOFS, exist_ok=True)
    with open(os.path.join(PROOFS, "proof-results.json"), "w") as fh:
        json.dump({"base": BASE, "cases": cases}, fh, indent=2)
    lines = ["# SwiftHumanize proof results", "",
             f"Run against {BASE}. Engine results, preservation checks,",
             "and heuristic scores recorded exactly as returned.", ""]
    for c in cases:
        b, a = c["score_before"], c["score_after"]
        lines += [f"## {c['id']}", "", f"Kind: {c['kind']}. Tone: {c['tone']}. "
                  f"Strength: {c['strength']}. Engine: {c['engine']}.", ""]
        if c["style_sample"]:
            lines += ["Style sample:", "", c["style_sample"], ""]
        lines += ["Original:", "", c["original"], "",
                  f"Score before: {b['human_likeness_score']} ({b['assessment']}); "
                  f"tell phrases {b['ai_tell_phrases']['total']}; "
                  f"em-dashes {b['em_dash_count']}; sentence CV {b['sentences']['length_variation_cv']}.",
                  "", "Humanized:", "", c["humanized"], "",
                  f"Score after: {a['human_likeness_score']} ({a['assessment']}); "
                  f"tell phrases {a['ai_tell_phrases']['total']}; "
                  f"em-dashes {a['em_dash_count']}; sentence CV {a['sentences']['length_variation_cv']}.",
                  "", "Checks: " + json.dumps(c["checks"]), ""]
    with open(os.path.join(PROOFS, "proof-results.md"), "w") as fh:
        fh.write("\n".join(lines))
    for c in cases:
        print(c["id"], "engine:", c["engine"],
              "score:", c["score_before"]["human_likeness_score"], "->",
              c["score_after"]["human_likeness_score"], "checks:", c["checks"])


if __name__ == "__main__":
    main()
