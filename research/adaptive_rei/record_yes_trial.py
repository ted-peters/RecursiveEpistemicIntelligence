"""Test record-based yes review; require fewer false yeses without losing valid answers."""
import json
import re
from urllib.request import urlopen

from counterexample_diagnostic import probe
from paperwork_trial import ROOT, MODEL, URL, SINGLE_PASS, predict, decide

RECORD = re.compile(r"\b(?:register|ledger|form|sheet|checklist|card|label|manifest|catalogue|inventory|ticket|log|report|schedule|certificate|notice|file|entry|roster)\b", re.I)


def eligible(question, evidence, verdict):
    if verdict["answer"] != "yes" or RECORD.search(question):
        return False
    # Uncited first-pass yes: only infer a documentary basis from a single record sentence.
    basis = verdict.get("citation")
    if not basis and len(re.split(r"(?<=[.!?])\s+|\n+", evidence.strip())) == 1:
        basis = evidence
    return bool(basis and RECORD.search(basis))


def main():
    with urlopen(URL + "/api/tags", timeout=30) as response:
        digest = next(m["digest"] for m in json.load(response)["models"] if m["name"] == MODEL)
    cases = []
    for name, q, record_q, record, witnessed, contradicted in json.loads((ROOT / "record_yes_cases.json").read_text()):
        cases.extend([(name, "unchecked", q, record, "uncertain"),
                      (name, "corroborated", q, record + " " + witnessed, "yes"),
                      (name, "contradicted", q, record + " " + contradicted, "no"),
                      (name, "record content", record_q, record, "yes")])
    for evidence, *claims in json.loads((ROOT / "source_selection_cases.json").read_text()):
        for q, expected, _ in claims:
            cases.append(("prior", "prior", q, evidence, expected))
    rows = []
    for name, kind, question, evidence, expected in cases:
        passage = question + " " + evidence
        direct, dt = predict(URL, MODEL, SINGLE_PASS, passage)
        current, tokens = decide(URL, MODEL, passage, skip_gaps=True)
        answer = current["answer"]
        review = probe(question, evidence, 40, constrained=True) if eligible(question, evidence, current) else None
        if review and review["answer"] is not None:
            answer = review["answer"]
        rows.append(dict(name=name, kind=kind, question=question, expected=expected,
                         direct=direct.get("answer"), direct_tokens=dt, current=current["answer"],
                         citation=current.get("citation"), current_tokens=tokens, candidate=answer,
                         review=review, candidate_tokens=tokens + (review["tokens"] if review else 0)))
    print(json.dumps(dict(model=MODEL, digest=digest, rows=rows), indent=2))


if __name__ == "__main__":
    main()
