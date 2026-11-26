"""Score exact relation and token cost on fresh questions, with prior cases reported separately."""
import json
from urllib.request import urlopen

from polarity_time_trial import CASES, MODEL, RELATION, URL, predict

TIME = ("Compare only the times in the question and observation. Ignore the observed state. "
        "Return JSON with answer same if the two times denote the same instant, "
        "different if they are distinct, or unknown if you cannot tell.")
DIRECTION = ("The observation passed the time check. Decide whether its stated condition supports "
             "or contradicts the question's proposed condition. Return JSON with field answer "
             "set to supports or contradicts.")
FRESH = [
    ("the kiln", "warm", "cold", "nine thirty in the morning", "09:30", "09:13"),
    ("the canopy", "extended", "retracted", "three quarters past one in the afternoon", "13:45", "13:15"),
    ("the basin", "dry", "wet", "eight in the evening", "20:00", "08:00"),
    ("the platform", "occupied", "vacant", "eleven fifty in the morning", "ten minutes before noon", "ten minutes after noon"),
    ("the fan", "stationary", "spinning", "half past seven in the evening", "19:30", "19:03"),
    ("the counter", "staffed", "unattended", "five past ten in the morning", "10:05 a.m.", "10:50 a.m."),
    ("the awning", "raised", "lowered", "quarter to six in the evening", "17:45", "18:15"),
    ("the chest", "sealed", "unsealed", "one minute past midnight", "00:01", "12:01 p.m."),
]


def main():
    with urlopen(URL + "/api/tags", timeout=30) as response:
        digest = next(m["digest"] for m in json.load(response)["models"] if m["name"] == MODEL)
    rows = []
    for suite, scenarios in (("fresh", FRESH), ("prior", CASES)):
        for item, state, opposite, exact, alias, other in scenarios:
            question = f"Was {item} {state} at {exact}?"
            for timing, when in (("exact", exact), ("equivalent", alias), ("different", other)):
                for direction, observed in (("supports", state), ("contradicts", opposite)):
                    quote = f"At {when} a clerk found {item} {observed}."
                    passage = question + "\nQuoted sentence: " + quote
                    single, single_tokens = predict(URL, MODEL, RELATION, passage, max_tokens=32)
                    gate, cost = predict(URL, MODEL, TIME, passage, max_tokens=32)
                    time_answer = gate.get("answer")
                    final = "irrelevant" if time_answer == "different" else None
                    second_cost = 0
                    if time_answer == "same":
                        result, second_cost = predict(URL, MODEL, DIRECTION, passage, max_tokens=32)
                        final = result.get("answer")
                    rows.append(dict(suite=suite, question=question, quote=quote, timing=timing,
                                     expected=direction if timing != "different" else "irrelevant",
                                     single=single.get("answer"), single_tokens=single_tokens, gate=time_answer,
                                     gate_tokens=cost, staged=final, staged_tokens=cost + second_cost))
    print(json.dumps(dict(model=MODEL, digest=digest, rows=rows), indent=2))


if __name__ == "__main__":
    main()
