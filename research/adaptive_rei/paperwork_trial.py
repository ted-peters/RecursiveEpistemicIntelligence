"""Paired audit experiment. Reference labels and evidence are fixed before inference."""
import json
from pathlib import Path
from urllib.request import urlopen

from adaptive_rei_benchmark import predict, SINGLE_PASS
from boolq_trial import MODEL
from selective_review import decide

ROOT = Path(__file__).parent
URL = "http://localhost:11434"
GUIDANCE = ("Distinguish evidence of paperwork from evidence of the event. Missing or "
            "incomplete documentation alone leaves actual performance uncertain. "
            "Use direct evidence of completion or omission when available.")


def main():
    with urlopen(URL + "/api/tags", timeout=30) as response:
        digest = next(x["digest"] for x in json.load(response)["models"] if x["name"] == MODEL)
    cases = []
    for p in json.loads((ROOT / "maintenance_audit_cases.json").read_text()):
        cases.extend(("pilot", q, " ".join(p["evidence"]), label) for q, label, _ in p["claims"])
    for q, gap, done, missed in json.loads((ROOT / "paperwork_controls.json").read_text()):
        for evidence, label in [(gap, "uncertain"), (gap + " " + done, "yes"), (gap + " " + missed, "no")]:
            cases.append(("fresh", q, evidence, label))
    rows = []
    for suite, question, evidence, expected in cases:
        passage = question + " " + evidence
        direct, direct_cost = predict(URL, MODEL, SINGLE_PASS, passage)
        current, cost = decide(URL, MODEL, passage, skip_gaps=True)
        if current["answer"] == "no":
            # Recheck a denial once. A positive reversal needs a different policy.
            check, extra = predict(URL, MODEL, SINGLE_PASS + " " + GUIDANCE, passage)
            candidate = "uncertain" if check.get("answer") == "uncertain" else "no"
        else:
            candidate, extra = current["answer"], 0
        row = dict(suite=suite, question=question, evidence=evidence, expected=expected,
                   conventional=direct.get("answer"), conventional_tokens=direct_cost,
                   current=current["answer"], current_tokens=cost, candidate=candidate,
                   candidate_tokens=cost + extra)
        rows.append(row)
    print(json.dumps(dict(model=MODEL, digest=digest, rows=rows), indent=2))


if __name__ == "__main__":
    main()
