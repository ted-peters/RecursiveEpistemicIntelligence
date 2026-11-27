"""Replay the PR 68 questions with schema-constrained graph extraction."""
import json
from urllib.request import urlopen

from adaptive_rei_benchmark import benchmark_rei
from revision_pairs_trial import ROOT, URL


def main():
    control = json.loads((ROOT / "results/revision_new.json").read_text())
    model = control["model"]
    with urlopen(URL + "/api/tags", timeout=30) as response:
        if not any(m["name"] == model and m["digest"] == control["digest"]
                   for m in json.load(response)["models"]):
            raise ValueError("Model digest mismatch")
    cases = [(r["question"], r["expected"]) for r in control["rows"]]
    report = benchmark_rei(URL, model, cases, schema_extraction=True)
    for result, original in zip(report["results"], control["rows"], strict=True):
        result.update(claim=original["claim"], question=original["question"])
    print(json.dumps(dict(**report, digest=control["digest"]), indent=2))


if __name__ == "__main__":
    main()
