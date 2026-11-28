"""Run against a supplied research checkout so each arm uses its own production code."""
import json
from pathlib import Path
import sys
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
URL = "http://127.0.0.1:11434"


def main():
    source = Path(sys.argv[1]).resolve() / "research/adaptive_rei"
    sys.path.insert(0, str(source))
    from adaptive_rei_benchmark import single_fact_verdict
    from quantity_comparison import quantity_verdict

    old = json.loads((ROOT / "results/quantity_trial.json").read_text())
    with urlopen(URL + "/api/tags", timeout=30) as response:
        if not any(m["name"] == old["model"] and m["digest"] == old["digest"]
                   for m in json.load(response)["models"]):
            raise ValueError("Model digest mismatch")
    controls = json.loads((ROOT / "unit_controls.json").read_text())
    rows = []
    for claim, *passages in controls:
        for label, passage in zip(("yes", "no", "uncertain"), passages, strict=True):
            question = f'Is this claim true: "{claim}"? {passage}'
            result = single_fact_verdict(URL, old["model"], question)
            rows.append(dict(claim=claim, question=question, expected=label, result=result))
    prior_routes = [quantity_verdict(x["question"]) for x in old["rows"]]
    print(json.dumps(dict(model=old["model"], digest=old["digest"], rows=rows,
                          prior_routes=prior_routes), indent=2))


if __name__ == "__main__":
    main()
