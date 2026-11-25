"""Primary score: both verdicts correct per fresh passage; diagnostic: selected evidence."""
import json
from urllib.request import urlopen

from paperwork_trial import ROOT, URL, MODEL, SINGLE_PASS, predict, decide
from plain_verdict import decide as plain
from source_selection import decide as select


def main():
    with urlopen(URL + "/api/tags", timeout=30) as response:
        digest = next(m["digest"] for m in json.load(response)["models"] if m["name"] == MODEL)
    cases = json.loads((ROOT / "source_selection_cases.json").read_text())
    prior = json.loads((ROOT / "paraphrase_cases.json").read_text())
    cases.extend([evidence, *[[q, label, line] for q in questions]]
                 for name, evidence, label, questions in prior if name in ("delivery", "prior-dispatch")
                 for line in [2 if name == "delivery" else 1])
    rows = []
    for packet, (evidence, *claims) in enumerate(cases):
        for question, expected, key in claims:
            passage = question + " " + evidence
            conventional, dt = predict(URL, MODEL, SINGLE_PASS, passage)
            current, ct = decide(URL, MODEL, passage, skip_gaps=True)
            previous, pt = plain(URL, MODEL, passage, separate_reports=True)
            candidate, st = select(URL, MODEL, passage)
            rows.append(dict(packet=packet, question=question, expected=expected, expected_line=key,
                             conventional=conventional.get("answer"), conventional_tokens=dt,
                             current=current["answer"], current_tokens=ct, previous=previous["answer"],
                             previous_tokens=pt, candidate=candidate["answer"], candidate_tokens=st,
                             selected_line=candidate["line"], citation=candidate["citation"]))
    print(json.dumps(dict(model=MODEL, digest=digest, fresh_packets=len(cases)-2, rows=rows), indent=2))


if __name__ == "__main__":
    main()
