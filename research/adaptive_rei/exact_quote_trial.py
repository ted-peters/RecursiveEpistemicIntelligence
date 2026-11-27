"""Replace the generated quote with the full source sentence in a paired replay."""
import json
from urllib.request import urlopen

from quote_first_trial import MODEL, ROOT, URL, VERDICT, generate


def main():
    previous = json.loads((ROOT / "results/quote_first_trial.json").read_text())
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
        excerpt = case["quote"]["value"]
        generated_quote = excerpt if isinstance(excerpt, str) else ""
        row["direct"] = generate(prompt, labels, 12)
        row["guided"] = generate(prompt + "\nSelected quote: " + generated_quote, labels, 12)
        row["exact"] = generate(prompt + "\nSelected quote: " + passage, labels, 12)
        rows.append(row)
    print(json.dumps(dict(model=MODEL, digest=previous["digest"], rows=rows), indent=2))


if __name__ == "__main__":
    main()
