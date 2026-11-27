"""Paired response-format ablation on all 48 earlier passages. Score invalid labels as misses."""
import json
import re
from urllib.request import Request, urlopen

from sufficiency_trial import ROOT, MODEL, URL, GATE, DIRECTION


def probe(prompt, text, choices, constrained):
    payload = dict(model=MODEL, prompt=prompt + "\n\n" + text, stream=False,
                   options=dict(temperature=0, seed=42, num_predict=12))
    if constrained:
        payload["format"] = {"type": "string", "enum": choices}
    req = Request(URL + "/api/generate", json.dumps(payload).encode(), {"Content-Type": "application/json"})
    with urlopen(req, timeout=90) as response:
        result = json.load(response)
    raw = result["response"]
    value = raw.strip().strip('"').lower()
    strict = value if value in choices else None
    # Diagnostic only: accept an explicit leading label followed by punctuation or whitespace.
    match = re.match(r'^\s*["*]*(\w+)\b', raw.lower())
    leading = match[1] if match and match[1] in choices else None
    return dict(raw=raw, strict=strict, leading=leading, stop=result.get("done_reason"),
                tokens=result["prompt_eval_count"] + result["eval_count"])


def main():
    prior = json.loads((ROOT / "results/sufficiency_trial.json").read_text())
    with urlopen(URL + "/api/tags", timeout=30) as response:
        if not any(m["name"] == MODEL and m["digest"] == prior["digest"] for m in json.load(response)["models"]):
            raise ValueError("Model digest mismatch")
    rows = []
    for case in prior["rows"]:
        text = f'Is this claim true: "{case["claim"]}"? Passage: {case["evidence"]}'
        row = {k: case[k] for k in ("suite", "claim", "evidence", "expected")}
        for mode in ("constrained", "plain"):
            gate = probe(GATE, text, ["open", "settled"], mode == "constrained")
            # Also probe direction on a rejected case to isolate the effect at each stage.
            direction = probe(DIRECTION, text, ["yes", "no"], mode == "constrained")
            row[mode] = dict(gate=gate, direction=direction)
        rows.append(row)
    print(json.dumps(dict(model=MODEL, digest=prior["digest"], rows=rows), indent=2))


if __name__ == "__main__":
    main()
