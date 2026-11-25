"""Compare three verdict modes. Primary score: all three wordings correct per fresh claim."""
import json
from urllib.request import urlopen

from paperwork_trial import ROOT, URL, MODEL, SINGLE_PASS, predict, decide
from plain_verdict import decide as plain


def main():
    with urlopen(URL + "/api/tags", timeout=30) as response:
        digest = next(m["digest"] for m in json.load(response)["models"] if m["name"] == MODEL)
    rows = []
    for name, evidence, expected, questions in json.loads((ROOT / "paraphrase_cases.json").read_text()):
        for question in questions:
            passage = question + " " + evidence
            baseline, bt = predict(URL, MODEL, SINGLE_PASS, passage)
            current, ct = decide(URL, MODEL, passage, skip_gaps=True)
            candidate, et = plain(URL, MODEL, passage, separate_reports=True)
            rows.append(dict(case=name, question=question, expected=expected,
                             conventional=baseline.get("answer"), conventional_tokens=bt,
                             current=current["answer"], current_tokens=ct,
                             candidate=candidate["answer"], candidate_tokens=et))
    print(json.dumps(dict(model=MODEL, digest=digest, rows=rows), indent=2))


if __name__ == "__main__":
    main()
