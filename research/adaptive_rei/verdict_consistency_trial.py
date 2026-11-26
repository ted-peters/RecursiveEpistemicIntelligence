"""Review first-pass denials against their own stated basis, sharing the first pass."""
import json
from urllib.request import urlopen
from decisive_fact_trial import ROOT, URL, RULE, predict

CHECK = ("The proposed answer is no. Given the question, original evidence and proposed reason, "
         "does the evidence actually establish the opposite of the claim? If it only leaves "
         "the claim unresolved, return uncertain. Otherwise return keep. "
         "Output JSON with one field, answer.")


def label(value):
    return value.strip().lower() if isinstance(value, str) else None


def main():
    models = json.loads((ROOT / "results/mixed_model_trial.json").read_text())["digests"]
    with urlopen(URL + "/api/tags", timeout=30) as response:
        installed = {m["name"]: m["digest"] for m in json.load(response)["models"]}
    if any(installed.get(m) != digest for m, digest in models.items()):
        raise ValueError("Model digest mismatch")
    cases = []
    for q, gap, no, yes in json.loads((ROOT / "verdict_consistency_cases.json").read_text()):
        cases.extend(("fresh", q + " " + evidence, expected)
                     for evidence, expected in [(gap, "uncertain"), (no, "no"), (yes, "yes")])
    prior = json.loads((ROOT / "mixed_model_confirmation.json").read_text())
    cases.extend(("prior", text, expected) for _, text, expected in prior)
    rows = []
    for model in models:
        for suite, text, expected in cases:
            out, cost = predict(URL, model, RULE, text, max_tokens=96)
            first, fact = label(out.get("answer")), out.get("fact")
            final, review, extra = first, None, 0
            if first == "no" and isinstance(fact, str) and fact.strip():
                review, extra = predict(URL, model, CHECK, text + "\nProposed reason: " + fact, max_tokens=32)
                if label(review.get("answer")) == "uncertain":
                    final = "uncertain"
            rows.append(dict(model=model, suite=suite, question=text, expected=expected, original=first,
                             fact=fact, review=review, checked=final, original_tokens=cost, checked_tokens=cost+extra))
    print(json.dumps(dict(digests=models, rows=rows), indent=2))


if __name__ == "__main__":
    main()
