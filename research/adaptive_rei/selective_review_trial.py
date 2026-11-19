"""Matched live comparison on disjoint BoolQ items and uncertainty controls."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

from adaptive_rei_benchmark import SINGLE_PASS, predict
from boolq_trial import DIGEST, MODEL, URL, passage, sample_indices, ORIGINAL, FOCUS, IMPLIED
from selective_review import decide

SEED = 20261123
SIZE = 240


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path)
    parser.add_argument("--url", default="http://127.0.0.1:11434")
    args = parser.parse_args()
    if args.data:
        raw = args.data.read_bytes()
    else:
        with urlopen(URL, timeout=60) as response:
            raw = response.read()
    if hashlib.sha256(raw).hexdigest() != DIGEST:
        raise ValueError("Unrecognized dataset")
    data = [json.loads(line) for line in raw.splitlines()]
    indices = sample_indices(data, SEED, SIZE, (ORIGINAL, FOCUS, IMPLIED, "boolq_plain_verdict.json"))
    cases = [("boolq", i, passage(data[i]), "yes" if data[i]["answer"] else "no") for i in indices]
    for file in ("selective_review_controls.json", "aside_cases.json", "evidence_budget_cases.json"):
        controls = json.loads(Path(__file__).with_name(file).read_text())
        cases.extend((file, i, q, a) for i, (q, a) in enumerate(controls))
    with urlopen(args.url + "/api/tags", timeout=30) as response:
        digest = next(m["digest"] for m in json.load(response)["models"] if m["name"] == MODEL)
    rows = []
    for n, (suite, i, text, expected) in enumerate(cases):
        row = {"suite": suite, "index": i, "expected": expected}
        for arm in (("baseline", "candidate") if n % 2 == 0 else ("candidate", "baseline")):
            if arm == "baseline":
                answer, tokens = predict(args.url, MODEL, SINGLE_PASS, text)
            else:
                answer, tokens = decide(args.url, MODEL, text)
            row[arm] = {**answer, "tokens": tokens}
        rows.append(row)
    print(json.dumps({"seed": SEED, "model": MODEL, "digest": digest, "data_sha256": DIGEST, "rows": rows}))


if __name__ == "__main__":
    main()
