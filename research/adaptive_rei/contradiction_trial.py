"""Compare single-fact verdicts with and without a separate contradiction check."""
import json
from urllib.request import urlopen

from adaptive_rei_benchmark import single_fact_verdict
from revision_pairs_trial import ROOT, URL


def main():
    saved = json.loads((ROOT / "results/schema_single_fact.json").read_text())
    model = saved["model"]
    with urlopen(URL + "/api/tags", timeout=30) as response:
        if not any(m["name"] == model and m["digest"] == saved["digest"]
                   for m in json.load(response)["models"]):
            raise ValueError("Model digest mismatch")
    cases = [("previous", x["claim"], x["question"], x["expected"]) for x in saved["results"]]
    controls = json.loads((ROOT / "contradiction_controls.json").read_text())
    for claim, *passages in controls:
        for expected, passage in zip(("yes", "no", "uncertain"), passages, strict=True):
            cases.append(("new", claim, f'Is this claim true: "{claim}"? {passage}', expected))
    rows = []
    for suite, claim, question, expected in cases:
        base = single_fact_verdict(URL, model, question)
        checked = single_fact_verdict(URL, model, question, check_contradiction=True)
        rows.append(dict(suite=suite, claim=claim, question=question, expected=expected,
                         base=base, checked=checked))
    print(json.dumps(dict(model=model, digest=saved["digest"], rows=rows), indent=2))


if __name__ == "__main__":
    main()
