"""Replay development questions and a separately authored capacity holdout."""
import json
from pathlib import Path
import sys
from urllib.request import urlopen

from unit_trial import ROOT, URL


def main():
    sys.path.insert(0, str(Path(sys.argv[1]).resolve() / "research/adaptive_rei"))
    from adaptive_rei_benchmark import single_fact_verdict

    old = json.loads((ROOT / "results/blind_measurement_trial.json").read_text())
    with urlopen(URL + "/api/tags", timeout=30) as response:
        if not any(m["name"] == old["model"] and m["digest"] == old["digest"]
                   for m in json.load(response)["models"]):
            raise ValueError("Model digest mismatch")
    rows = [dict(suite="development", question=x["question"], expected=x["expected"])
            for x in old["rows"]]
    for group in json.loads((ROOT / "capacity_holdout.json").read_text()):
        for label in ("yes", "no", "uncertain"):
            question = f'Is this claim true: "{group["claim"]}"? {group[label]}'
            rows.append(dict(suite="holdout", question=question, expected=label))
    for row in rows:
        row["result"] = single_fact_verdict(URL, old["model"], row["question"])
    print(json.dumps(dict(model=old["model"], digest=old["digest"], rows=rows), indent=2))


if __name__ == "__main__":
    main()
