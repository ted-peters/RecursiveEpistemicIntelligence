"""Replay the independently written answer key against the two frozen methods."""
import json
from urllib.request import urlopen

from adaptive_rei_benchmark import single_fact_verdict
from quote_first_trial import MODEL, ROOT, URL, VERDICT, generate


def main():
    digest = json.loads((ROOT / "results/range_current.json").read_text())["digest"]
    with urlopen(URL + "/api/tags", timeout=30) as response:
        if not any(m["name"] == MODEL and m["digest"] == digest for m in json.load(response)["models"]):
            raise ValueError("Model digest mismatch")
    groups = json.loads((ROOT / "blind_measurement_cases.json").read_text())
    labels = ["yes", "no", "uncertain"]
    assert len(groups) == 5
    rows = []
    for group in groups:
        for expected in labels:
            assert len(group[expected]) == 2
            for style, passage in enumerate(group[expected], 1):
                question = f'Is this claim true: "{group["claim"]}"? {passage}'
                direct = generate(VERDICT + "\n\n" + question, dict(type="string", enum=labels), 12)
                rei = single_fact_verdict(URL, MODEL, question)
                rows.append(dict(claim=group["claim"], question=question, style=style,
                                 expected=expected, direct=direct, rei=rei))
    print(json.dumps(dict(model=MODEL, digest=digest, rows=rows), indent=2))


if __name__ == "__main__":
    main()
