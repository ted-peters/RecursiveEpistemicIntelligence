"""Score all three evidence variants per claim and misses on neutral passages."""
import json
from urllib.request import urlopen
from decisive_fact_trial import ROOT, URL, SINGLE_PASS, RULE, predict, decide


def main():
    cases = json.loads((ROOT / "evidence_flip_cases.json").read_text())
    models = json.loads((ROOT / "results/mixed_model_trial.json").read_text())["digests"]
    with urlopen(URL + "/api/tags", timeout=30) as response:
        installed = {m["name"]: m["digest"] for m in json.load(response)["models"]}
    rows = []
    for model, digest in models.items():
        if installed.get(model) != digest:
            raise ValueError(f"Model digest mismatch for {model}")
        for claim, *variants in cases:
            for evidence, expected in zip(variants, ("yes", "no", "uncertain"), strict=True):
                text = f'Is this claim true: "{claim}"? Passage: {evidence}'
                direct, dt = predict(URL, model, SINGLE_PASS, text)
                current, ct = decide(URL, model, text, skip_gaps=True)
                fact, ft = predict(URL, model, RULE, text, max_tokens=96)
                rows.append(dict(model=model, claim=claim, evidence=evidence, expected=expected,
                                 direct=direct.get("answer"), direct_tokens=dt, current=current["answer"],
                                 current_tokens=ct, candidate=fact.get("answer"), fact=fact.get("fact"),
                                 candidate_tokens=ft))
    print(json.dumps(dict(digests=models, rows=rows), indent=2))


if __name__ == "__main__":
    main()
