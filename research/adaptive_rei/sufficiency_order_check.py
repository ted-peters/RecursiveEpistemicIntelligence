"""Post-hoc check of enum ordering using the same fresh passages and prompts."""
import json
from sufficiency_trial import ROOT, GATE, DIRECTION, choose

if __name__ == "__main__":
    report = json.loads((ROOT / "results/sufficiency_trial.json").read_text())
    rows = []
    for row in report["rows"]:
        if row["suite"] != "fresh":
            continue
        text = f'Is this claim true: "{row["claim"]}"? Passage: {row["evidence"]}'
        gate, gt = choose(GATE, text, ["settled", "open"])
        direction, dt = choose(DIRECTION, text, ["no", "yes"])
        rows.append(dict(claim=row["claim"], expected=row["expected"], gate=gate,
                         direction=direction, gate_tokens=gt, direction_tokens=dt))
    print(json.dumps(dict(model=report["model"], digest=report["digest"], rows=rows), indent=2))
