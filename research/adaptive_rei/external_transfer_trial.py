"""Frozen MultiNLI sample: two examples per genre and label, five genres."""
import json
from urllib.request import urlopen

from decisive_fact_trial import ROOT, URL, SINGLE_PASS, RULE, predict, decide

DATA = ("https://datasets-server.huggingface.co/rows?dataset=nyu-mll%2Fmulti_nli"
        "&config=default&split=validation_matched&offset=0&length=100")
LABELS = {"entailment": "yes", "neutral": "uncertain", "contradiction": "no"}


def run():
    with urlopen(DATA, timeout=60) as response:
        dataset = json.load(response)
    names = next(f["type"]["names"] for f in dataset["features"] if f["name"] == "label")
    pairs = {r["row"]["pairID"]: r["row"] for r in dataset["rows"]}
    ids = json.loads((ROOT / "external_transfer_ids.json").read_text())
    digests = json.loads((ROOT / "results/mixed_model_trial.json").read_text())["digests"]
    with urlopen(URL + "/api/tags", timeout=30) as response:
        installed = {m["name"]: m["digest"] for m in json.load(response)["models"]}
    rows = []
    for model, digest in digests.items():
        if installed.get(model) != digest:
            raise ValueError(f"Model digest mismatch for {model}")
        for pair_id in ids:
            pair = pairs[pair_id]
            text = 'Is this claim true: "' + pair["hypothesis"] + '"? Passage: ' + pair["premise"]
            direct, dt = predict(URL, model, SINGLE_PASS, text)
            current, ct = decide(URL, model, text, skip_gaps=True)
            fact, ft = predict(URL, model, RULE, text, max_tokens=96)
            rows.append(dict(model=model, pair_id=pair_id, genre=pair["genre"],
                             expected=LABELS[names[pair["label"]]], direct=direct.get("answer"),
                             direct_tokens=dt, current=current["answer"], current_tokens=ct,
                             fact=fact.get("fact"), candidate=fact.get("answer"), candidate_tokens=ft))
    print(json.dumps(dict(data=DATA, digests=digests, rows=rows), indent=2))


if __name__ == "__main__":
    run()
