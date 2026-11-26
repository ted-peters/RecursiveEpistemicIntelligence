"""Post-hoc constrained review, retaining the original first-pass answers and costs."""
import json
from urllib.request import Request, urlopen
from verdict_consistency_trial import CHECK, ROOT, URL


def main():
    trial = json.loads((ROOT / "results/verdict_consistency_trial.json").read_text())
    schema = {"type": "object", "properties": {"answer": {"type": "string", "enum": ["keep", "uncertain"]}},
              "required": ["answer"], "additionalProperties": False}
    for row in trial["rows"]:
        if row["review"] is None:
            continue
        prompt = CHECK + "\n\n" + row["question"] + "\nProposed reason: " + row["fact"]
        payload = dict(model=row["model"], prompt=prompt, stream=False, format=schema,
                       options=dict(temperature=0, seed=42, num_predict=32))
        req = Request(URL + "/api/generate", json.dumps(payload).encode(), {"Content-Type": "application/json"})
        with urlopen(req, timeout=90) as response:
            output = json.load(response)
        row["review"] = json.loads(output["response"])
        row["checked"] = "uncertain" if row["review"]["answer"] == "uncertain" else row["original"]
        row["checked_tokens"] = row["original_tokens"] + output["prompt_eval_count"] + output["eval_count"]
    print(json.dumps(trial, indent=2))


if __name__ == "__main__":
    main()
