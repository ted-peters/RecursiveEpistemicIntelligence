"""Paired prompt ablation; primary endpoint is all three verdicts correct per fresh passage."""
import json
from urllib.request import urlopen

from paperwork_trial import ROOT, URL, MODEL, SINGLE_PASS, predict, decide
from source_selection import decide as select


def main():
    with urlopen(URL + "/api/tags", timeout=30) as response:
        digest = next(m["digest"] for m in json.load(response)["models"] if m["name"] == MODEL)
    rows = []
    for suite, filename in [("fresh", "counterexample_cases.json"), ("prior", "source_selection_cases.json")]:
        cases = json.loads((ROOT / filename).read_text())
        for packet, (evidence, *claims) in enumerate(cases):
            for question, expected, *_ in claims:
                passage = question + " " + evidence
                baseline, bt = predict(URL, MODEL, SINGLE_PASS, passage)
                current, ct = decide(URL, MODEL, passage, skip_gaps=True)
                original, ot = select(URL, MODEL, passage)
                candidate, et = select(URL, MODEL, passage, check_opposite=True)
                rows.append(dict(suite=suite, packet=packet, question=question, expected=expected,
                                 baseline=baseline.get("answer"), baseline_tokens=bt,
                                 current=current["answer"], current_tokens=ct,
                                 original=original["answer"], original_tokens=ot,
                                 candidate=candidate["answer"], candidate_tokens=et,
                                 original_line=original["line"], candidate_line=candidate["line"]))
    print(json.dumps(dict(model=MODEL, digest=digest, rows=rows), indent=2))


if __name__ == "__main__":
    main()
