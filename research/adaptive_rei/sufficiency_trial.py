"""Llama comparison on frozen fresh and previous claim triplets."""
import json
from urllib.request import Request, urlopen

from decisive_fact_trial import ROOT, URL, SINGLE_PASS, RULE, predict

MODEL = "llama3.2:1b"
GATE = ("Does the passage contain enough evidence to establish either that the claim is true "
        "or that it is false? If both are possible choose open. Otherwise choose settled.")
DIRECTION = "Given the passage, is the claim true? Choose yes or no."


def choose(prompt, text, choices):
    payload = dict(model=MODEL, prompt=prompt + "\n\n" + text, stream=False,
                   format={"type": "string", "enum": choices},
                   options=dict(temperature=0, seed=42, num_predict=12))
    req = Request(URL + "/api/generate", json.dumps(payload).encode(), {"Content-Type": "application/json"})
    with urlopen(req, timeout=90) as res:
        output = json.load(res)
    return json.loads(output["response"]), output["prompt_eval_count"] + output["eval_count"]


def main():
    digest = json.loads((ROOT / "results/mixed_model_trial.json").read_text())["digests"][MODEL]
    with urlopen(URL + "/api/tags", timeout=30) as res:
        if not any(m["name"] == MODEL and m["digest"] == digest for m in json.load(res)["models"]):
            raise ValueError("Model digest mismatch")
    rows = []
    for suite, file in (("fresh", "sufficiency_cases.json"), ("prior", "evidence_flip_cases.json")):
        for claim, *variants in json.loads((ROOT / file).read_text()):
            for evidence, expected in zip(variants, ("yes", "no", "uncertain"), strict=True):
                text = f'Is this claim true: "{claim}"? Passage: {evidence}'
                direct, dt = predict(URL, MODEL, SINGLE_PASS, text)
                fact, ft = predict(URL, MODEL, RULE, text, max_tokens=96)
                gate, gt = choose(GATE, text, ["open", "settled"])
                answer, extra = ("uncertain", 0) if gate == "open" else choose(DIRECTION, text, ["yes", "no"])
                rows.append(dict(suite=suite, claim=claim, evidence=evidence, expected=expected,
                                 direct=direct.get("answer"), direct_tokens=dt, first=fact.get("answer"),
                                 first_tokens=ft, gate=gate, gate_tokens=gt, staged=answer, staged_tokens=gt+extra))
    print(json.dumps(dict(model=MODEL, digest=digest, rows=rows), indent=2))


if __name__ == "__main__":
    main()
