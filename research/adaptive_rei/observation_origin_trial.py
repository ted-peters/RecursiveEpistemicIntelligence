"""Score new relevant observation selection and downstream verdicts on blinded passages."""
import json
import random
from urllib.request import Request, urlopen

from paperwork_trial import ROOT, MODEL, URL, SINGLE_PASS, predict, decide
from plain_verdict import decide as plain


def select_line(question, lines):
    numbered = "\n".join(f"{i}. {line}" for i, line in enumerate(lines, 1))
    prompt = ("Which sentence supplies a firsthand observation or test of the item and time asked about? "
              "Ignore copied descriptions, forecasts and observations of other items. "
              "Return its number, or 0 if none.\n" + question + "\n" + numbered)
    payload = dict(model=MODEL, prompt=prompt, stream=False, format={"type": "integer", "enum": [0, 1, 2, 3]},
                   options=dict(temperature=0, seed=42, num_predict=8))
    req = Request(URL + "/api/generate", json.dumps(payload).encode(), {"Content-Type": "application/json"})
    with urlopen(req, timeout=90) as res:
        output = json.load(res)
    try:
        index = json.loads(output["response"])
    except ValueError:
        index = None
    if type(index) is not int or not 0 <= index <= len(lines):
        index = None
    return index, output["prompt_eval_count"] + output["eval_count"]


def main():
    with urlopen(URL + "/api/tags", timeout=30) as res:
        digest = next(m["digest"] for m in json.load(res)["models"] if m["name"] == MODEL)
    rows = []
    rng = random.Random(48)
    for question, entry, copy, echo, yes, no, wrong in json.loads((ROOT / "observation_origin_cases.json").read_text()):
        for kind, extra, label in [("copy", echo, "uncertain"), ("wrong_item", wrong, "uncertain"),
                                   ("supports", yes, "yes"), ("contradicts", no, "no")]:
            lines = [entry, copy, extra]
            rng.shuffle(lines)
            key = 0 if label == "uncertain" else lines.index(extra) + 1
            passage = question + " " + " ".join(lines)
            base, bt = predict(URL, MODEL, SINGLE_PASS, passage)
            current, ct = decide(URL, MODEL, passage, skip_gaps=True)
            index, cost = select_line(question, lines)
            answer = "uncertain" if index == 0 else None
            extra_cost = 0
            if index:
                result, extra_cost = plain(URL, MODEL, question + " " + lines[index-1])
                answer = result["answer"]
            rows.append(dict(question=question, kind=kind, lines=lines, expected=label, expected_line=key,
                             selected=index, answer=answer, tokens=cost+extra_cost, selection_tokens=cost,
                             conventional=base.get("answer"), conventional_tokens=bt,
                             current=current["answer"], current_tokens=ct))
    print(json.dumps(dict(model=MODEL, digest=digest, rows=rows), indent=2))


if __name__ == "__main__":
    main()
