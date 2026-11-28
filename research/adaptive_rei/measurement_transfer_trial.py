"""Run frozen pairs of equivalent phrasings through the supplied REI checkout."""
import json
from pathlib import Path
import sys
from urllib.request import urlopen

from unit_trial import ROOT, URL


def main():
    sys.path.insert(0, str(Path(sys.argv[1]).resolve() / "research/adaptive_rei"))
    from adaptive_rei_benchmark import single_fact_verdict

    previous = json.loads((ROOT / "results/unit_current.json").read_text())
    model = previous["model"]
    with urlopen(URL + "/api/tags", timeout=30) as response:
        if not any(m["name"] == model and m["digest"] == previous["digest"]
                   for m in json.load(response)["models"]):
            raise ValueError("Model digest mismatch")
    kinds = [("support", "yes"), ("contradiction", "no"), ("other_object", "uncertain"),
             ("other_property", "uncertain")]
    rows = []
    for claim, *variants in json.loads((ROOT / "measurement_transfer_cases.json").read_text()):
        for (kind, expected), pair in zip(kinds, variants, strict=True):
            for style, passage in zip(("standard", "paraphrase"), pair, strict=True):
                question = f'Is this claim true: "{claim}"? {passage}'
                result = single_fact_verdict(URL, model, question)
                rows.append(dict(claim=claim, kind=kind, expected=expected, style=style,
                                 question=question, result=result))
    print(json.dumps(dict(model=model, digest=previous["digest"], rows=rows), indent=2))


if __name__ == "__main__":
    main()
