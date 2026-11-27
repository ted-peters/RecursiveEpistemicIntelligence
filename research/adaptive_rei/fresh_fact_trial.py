"""Score both independently prompted verdicts for each one-word evidence change."""
import json
from urllib.request import urlopen

from quote_first_trial import MODEL, ROOT, URL, VERDICT, generate


def main():
    digest = json.loads((ROOT / "results/unlabeled_repeat_trial.json").read_text())["digest"]
    with urlopen(URL + "/api/tags", timeout=30) as response:
        if not any(m["name"] == MODEL and m["digest"] == digest
                   for m in json.load(response)["models"]):
            raise ValueError("Model digest mismatch")
    cases = json.loads((ROOT / "fresh_fact_pairs.json").read_text())
    labels = dict(type="string", enum=["yes", "no", "uncertain"])
    rows = []
    for index, (claim, template, supporting, contradicting) in enumerate(cases):
        variants = [("yes", supporting), ("no", contradicting)]
        if index % 2:
            variants.reverse()
        for expected, word in variants:
            passage = template.format(word)
            prompt = VERDICT + f'\nClaim: {claim}\nPassage: {passage}'
            result = generate(prompt, labels, 12)
            rows.append(dict(claim=claim, passage=passage, expected=expected, result=result))
    print(json.dumps(dict(model=MODEL, digest=digest, rows=rows), indent=2))


if __name__ == "__main__":
    main()
