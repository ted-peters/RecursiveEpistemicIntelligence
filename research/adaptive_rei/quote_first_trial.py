"""Paired verdicts with and without a model-selected quote on frozen passages."""
import json
from urllib.request import Request, urlopen

from sufficiency_trial import MODEL, ROOT, URL

VERDICT = ("Does the passage establish the claim? Choose yes if it establishes the claim, "
           "no if it contradicts it, or uncertain if it does neither.")
QUOTE = ("Quote the exact words from the passage most relevant to deciding the claim. "
         "If the evidence is inconclusive, quote what the passage actually says. "
         "Return only a verbatim excerpt.")


def generate(prompt, schema, limit):
    payload = dict(model=MODEL, prompt=prompt, format=schema, stream=False,
                   options=dict(temperature=0, seed=42, num_predict=limit))
    req = Request(URL + "/api/generate", json.dumps(payload).encode(),
                  {"Content-Type": "application/json"})
    with urlopen(req, timeout=90) as response:
        data = json.load(response)
    raw = data["response"]
    try:
        value = json.loads(raw)
    except ValueError:
        value = None
    return dict(raw=raw, value=value, stop=data["done_reason"],
                tokens=data["prompt_eval_count"] + data["eval_count"])


def main():
    source = json.loads((ROOT / "results/sufficiency_format_trial.json").read_text())
    with urlopen(URL + "/api/tags", timeout=30) as response:
        if not any(m["name"] == MODEL and m["digest"] == source["digest"]
                   for m in json.load(response)["models"]):
            raise ValueError("Model digest mismatch")
    labels = dict(type="string", enum=["yes", "no", "uncertain"])
    rows = []
    for case in source["rows"]:
        row = {key: case[key] for key in ("claim", "evidence", "suite", "expected")}
        passage = row["evidence"]
        context = f'\nClaim: {row["claim"]}\nPassage: {passage}'
        direct = generate(VERDICT + context, labels, 12)
        quote = generate(QUOTE + context, dict(type="string"), 96)
        excerpt = quote["value"] if isinstance(quote["value"], str) else ""
        guided = generate(VERDICT + context + "\nSelected quote: " + excerpt, labels, 12)
        rows.append(dict(**row, direct=direct, quote=quote, guided=guided,
                         verbatim=bool(excerpt.strip()) and excerpt in passage,
                         full_passage=excerpt == passage))
    print(json.dumps(dict(model=MODEL, digest=source["digest"], rows=rows), indent=2))


if __name__ == "__main__":
    main()
