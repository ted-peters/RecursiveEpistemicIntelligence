"""Test one evidence-first call on fresh controls with identical baseline and REI arms."""
import json
from urllib.request import urlopen
from paperwork_trial import ROOT, URL, SINGLE_PASS, predict, decide

RULE = ("Use the supplied facts only. First give the decisive calculation, logical implication, "
        "or observation in at most twelve words. Check units, direction and scope. "
        "If both outcomes fit, answer uncertain. Return JSON fields in order: fact, answer "
        "(yes, no, or uncertain).")


def main():
    models = json.loads((ROOT / "results/mixed_model_trial.json").read_text())["digests"]
    with urlopen(URL + "/api/tags", timeout=30) as response:
        installed = {m["name"]: m["digest"] for m in json.load(response)["models"]}
    rows = []
    for model, digest in models.items():
        if installed.get(model) != digest:
            raise ValueError(f"Unexpected model digest for {model}")
        for domain, question, expected in json.loads((ROOT / "mixed_model_confirmation.json").read_text()):
            baseline, bt = predict(URL, model, SINGLE_PASS, question)
            current, ct = decide(URL, model, question, skip_gaps=True)
            candidate, et = predict(URL, model, RULE, question, max_tokens=96)
            rows.append(dict(model=model, domain=domain, question=question, expected=expected,
                             direct=baseline.get("answer"), direct_tokens=bt, rei=current["answer"],
                             rei_tokens=ct, candidate=candidate.get("answer"), fact=candidate.get("fact"),
                             candidate_tokens=et))
    print(json.dumps(dict(digests=models, rows=rows), indent=2))


if __name__ == "__main__":
    main()
