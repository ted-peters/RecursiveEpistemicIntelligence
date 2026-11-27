"""Compare a single passage with an unlabeled verbatim repetition."""
import json
from urllib.request import urlopen

from quote_first_trial import MODEL, ROOT, URL, VERDICT, generate


def main():
    previous = json.loads((ROOT / "results/repeated_label_trial.json").read_text())
    with urlopen(URL + "/api/tags", timeout=30) as response:
        if not any(m["name"] == MODEL and m["digest"] == previous["digest"]
                   for m in json.load(response)["models"]):
            raise ValueError("Model digest mismatch")

    labels = dict(type="string", enum=["yes", "no", "uncertain"])
    rows = []
    for case in previous["rows"]:
        row = {key: case[key] for key in ("suite", "claim", "evidence", "expected")}
        passage = case["evidence"]
        prompt = VERDICT + f'\nClaim: {case["claim"]}\nPassage: {passage}'
        row["direct"] = generate(prompt, labels, 12)
        row["unlabeled"] = generate(prompt + "\n" + passage, labels, 12)
        rows.append(row)
    print(json.dumps(dict(model=MODEL, digest=previous["digest"], rows=rows), indent=2))


if __name__ == "__main__":
    main()
