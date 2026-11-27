"""Run the published transfer set plus frozen alias controls against one checkout."""
import json
from pathlib import Path
import sys
from urllib.request import urlopen

from unit_trial import ROOT, URL


def main():
    sys.path.insert(0, str(Path(sys.argv[1]).resolve() / "research/adaptive_rei"))
    from adaptive_rei_benchmark import single_fact_verdict

    old = json.loads((ROOT / "results/measurement_transfer_current.json").read_text())
    with urlopen(URL + "/api/tags", timeout=30) as response:
        if not any(m["name"] == old["model"] and m["digest"] == old["digest"]
                   for m in json.load(response)["models"]):
            raise ValueError("Model digest mismatch")
    rows = [{k: v for k, v in x.items() if k != "result"} for x in old["rows"]]
    for claim, *passages in json.loads((ROOT / "measurement_alias_controls.json").read_text()):
        for expected, passage in zip(("yes", "no", "uncertain"), passages, strict=True):
            rows.append(dict(style="alias", expected=expected, claim=claim,
                             question=f'Is this claim true: "{claim}"? {passage}'))
    for row in rows:
        row["result"] = single_fact_verdict(URL, old["model"], row["question"])
    print(json.dumps(dict(model=old["model"], digest=old["digest"], rows=rows), indent=2))


if __name__ == "__main__":
    main()
