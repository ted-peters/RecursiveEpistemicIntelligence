"""Measure the hybrid policy on matched record pairs and a separate prose stratum."""
import argparse
import json
import random
from urllib.request import urlopen

from adaptive_rei_benchmark import SINGLE_PASS, predict
from evidence_register import RULES, decide

MODEL = "qwen3:4b-instruct"


def register_cases():
    # Paired interventions reverse one root observation. The expected answer is
    # specified by construction, independently of the parser and graph engine.
    rng = random.Random(78623)
    for pair in range(12):
        length = 3 + pair % 4
        ids = sorted(rng.sample(range(1, 41), length + 2))
        chain, independent, target = ids[:length], ids[-2], ids[-1]
        first = rng.choice(("yes", "no"))
        previous = first
        reports = []
        for before, after in zip(chain, chain[1:]):
            following = rng.choice(("yes", "no"))
            reports.append(f"Claim {after}: {following} if claim {before} is {previous}.")
            previous = following
        direction = "yes" if pair % 2 == 0 else "no"
        opposite = "no" if direction == "yes" else "yes"
        reports += [f"Claim {independent}: yes.",
                    f"Claim {target}: {direction} if claim {chain[-1]} is {previous} and claim {independent} is yes."]
        if pair % 3 == 1:
            reports.append(f"Claim {target}: {opposite}.")
        if pair % 3 == 2:
            reports.append(f"Claim {target}: {direction}.")
        for active in (True, False):
            root = first if active else ("no" if first == "yes" else "yes")
            lines = [f"Claim {chain[0]}: {root}.", *reports]
            # Same report order within each pair; change only the root value.
            random.Random(pair + 120).shuffle(lines)
            expected = [(direction if active else "uncertain"),
                        ("uncertain" if active else opposite), direction][pair % 3]
            yield "register", "\n".join([f"What is the answer for claim {target}?", RULES, *lines]), expected


PROSE = [
    ("Did the quartet play an encore? The recording covers the entire concert and ends with an encore by all four players.", "yes"),
    ("Was the copper disk magnetic? The label was missing. The case beside it contained a magnet, but no one tested the disk.", "uncertain"),
    ("Was booth five occupied at noon? The noon panorama shows its whole interior empty.", "no"),
    ("Was the last page signed? The legal assistant inspected the original and saw the signature on its last page.", "yes"),
    ("Did sanding cause the variation in gloss? Both the coating and sanding technique changed, and only the finished pieces were compared.", "uncertain"),
    ("Did the clock chime at ten? The bell was disconnected all morning. The hands showed ten without any sound.", "no"),
]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:11434")
    args = parser.parse_args()
    rows = []
    with urlopen(args.url + "/api/tags", timeout=30) as response:
        models = json.load(response)["models"]
    digest = next(m["digest"] for m in models if m["name"] == MODEL)
    cases = list(register_cases()) + [("prose", q, a) for q, a in PROSE]
    for i, (kind, q, expected) in enumerate(cases):
        row = {"kind": kind, "question": q, "expected": expected}
        for arm in (("single", "candidate") if i % 2 == 0 else ("candidate", "single")):
            output, tokens = predict(args.url, MODEL, SINGLE_PASS, q) if arm == "single" else decide(args.url, MODEL, q)
            row[arm] = {"answer": output.get("answer"), "tokens": tokens}
        rows.append(row)
    print(json.dumps({"model": MODEL, "model_digest": digest, "rows": rows}))
