"""Trial on isolated time fields in same-item observations; fall back on unsupported expressions."""
import json
from urllib.request import urlopen

from clock_normalization import clock_minutes
from time_before_relation_trial import URL, MODEL, RELATION, TIME, DIRECTION, FRESH, predict

CASES = [
    ("the lantern", "burning", "extinguished", "quarter past eight in the evening", "20:15", "08:15"),
    ("the hatch", "fastened", "unfastened", "quarter to nine in the morning", "08:45", "09:15"),
    ("the dial", "stationary", "moving", "half past two in the afternoon", "14:30", "02:30"),
    ("the booth", "occupied", "vacant", "12:09 a.m.", "00:09", "12:09 p.m."),
    ("the hopper", "empty", "full", "ten to four in the afternoon", "15:50", "16:10"),
    ("the panel", "lit", "dark", "five past seven in the morning", "07:05", "07:50"),
]
# No fallback row may be resolved solely by comparing clock readings.
CONTEXT = [
    ("Monday at noon", "Tuesday at noon", "irrelevant"),
    ("Tuesday at 08:00", "Monday at 08:00", "irrelevant"),
    ("08:00 UTC", "08:00 UTC+02:00", "irrelevant"),
    ("8 p.m.", "eight", "irrelevant"),
    ("Friday at noon", "Friday at midday", "supports"),
    ("around noon", "noon", "supports"),
]


def run():
    with urlopen(URL + "/api/tags", timeout=30) as res:
        digest = next(m["digest"] for m in json.load(res)["models"] if m["name"] == MODEL)
    cases = []
    for suite, scenarios in (("fresh", CASES), ("prior", FRESH)):
        for item, state, opposite, exact, alias, different in scenarios:
            for when in (alias, different):
                for observation, label in ((state, "supports"), (opposite, "contradicts")):
                    cases.append((suite, item, state, observation, exact, when,
                                  "irrelevant" if when == different else label))
    cases.extend(("context", "the shutter", "closed", "closed", exact, when, label)
                 for exact, when, label in CONTEXT)
    rows = []
    for suite, item, state, observation, exact, when, expected in cases:
        passage = f"Was {item} {state} at {exact}?\nQuoted sentence: At {when} a clerk found {item} {observation}."
        single, bt = predict(URL, MODEL, RELATION, passage, max_tokens=32)
        gate, gt = predict(URL, MODEL, TIME, passage, max_tokens=32)
        a, b = clock_minutes(exact), clock_minutes(when)
        covered = a is not None and b is not None
        gate_answer = gate.get("answer")
        routed = ("same" if a == b else "different") if covered else gate_answer
        direction = None
        dt = 0
        if "same" in (gate_answer, routed):
            output, dt = predict(URL, MODEL, DIRECTION, passage, max_tokens=32)
            direction = output.get("answer")
        def verdict(choice):
            return direction if choice == "same" else "irrelevant" if choice == "different" else None
        rows.append(dict(suite=suite, passage=passage, expected=expected, covered=covered, minutes=[a,b],
                         single=single.get("answer"), single_tokens=bt, gate=gate_answer,
                         staged=verdict(gate_answer), staged_tokens=gt + (dt if gate_answer=="same" else 0),
                         normalized=verdict(routed), normalized_tokens=(0 if covered else gt) + (dt if routed=="same" else 0)))
    print(json.dumps(dict(model=MODEL, digest=digest, rows=rows), indent=2))


if __name__ == "__main__":
    run()
