"""Compare review gates on shared verdicts, charging each arm for its own calls."""
import json
import re
from urllib.request import urlopen

from paperwork_trial import ROOT, URL, MODEL, GUIDANCE, SINGLE_PASS, predict, decide

DOCUMENT = re.compile(r"\b(?:entries|entry|cards?|records?|certificates?|logs?|reports?|sheets?|slips?|forms?|receipts?|files?|checklists?|register|documentation|paperwork)\b", re.I)
GAP = re.compile(r"\b(?:only|missing|blank|unavailable|incomplete|no|absent|unaccounted|unrecorded|could not|cannot)\b", re.I)


def run_case(question, evidence, expected, suite):
    passage = question + " " + evidence
    conventional, direct_cost = predict(URL, MODEL, SINGLE_PASS, passage)
    current, cost = decide(URL, MODEL, passage, skip_gaps=True)
    answer = current["answer"]
    citation = current["citation"] or ""
    eligible = bool(answer == "no" and DOCUMENT.search(citation) and GAP.search(citation))
    broad, extra = answer, 0
    if answer == "no":
        review, extra = predict(URL, MODEL, SINGLE_PASS + " " + GUIDANCE, passage)
        if review.get("answer") == "uncertain":
            broad = "uncertain"
    return dict(suite=suite, question=question, evidence=evidence, expected=expected,
                conventional=conventional.get("answer"), conventional_tokens=direct_cost,
                current=answer, current_tokens=cost, citation=citation, eligible=eligible,
                broad=broad, broad_tokens=cost+extra, narrow=broad if eligible else answer,
                narrow_tokens=cost+(extra if eligible else 0))


def main():
    with urlopen(URL + "/api/tags", timeout=30) as response:
        digest = next(x["digest"] for x in json.load(response)["models"] if x["name"] == MODEL)
    rows = []
    for p in json.loads((ROOT / "maintenance_audit_cases.json").read_text()):
        for question, label, _ in p["claims"]:
            rows.append(run_case(question, " ".join(p["evidence"]), label, "pilot"))
    for q, gap, yes, no in json.loads((ROOT / "cited_gap_controls.json").read_text()):
        for extra, label in [("", "uncertain"), (" " + yes, "yes"), (" " + no, "no")]:
            rows.append(run_case(q, gap + extra, label, "fresh"))
    print(json.dumps(dict(model=MODEL, digest=digest, rows=rows), indent=2))


if __name__ == "__main__":
    main()
