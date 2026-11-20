"""Paired live comparison; share the first verdict across the two review policies."""
import argparse
import hashlib
import json
from pathlib import Path
import random
from urllib.request import urlopen

from adaptive_rei_benchmark import SINGLE_PASS, predict
from boolq_trial import DIGEST, ORIGINAL, FOCUS, IMPLIED, MODEL, URL, passage, sample_indices
from plain_verdict import decide as plain_decide
from selective_review import review

SEED = 20261125
SIZE = 200
ROOT = Path(__file__).resolve().parent


def new_indices(data):
    prior_files = (ORIGINAL, FOCUS, IMPLIED, "boolq_plain_verdict.json")
    used = set(sample_indices(data, 20261123, 240, prior_files))
    for name in (*prior_files, "evidence_first_review.json"):
        report = json.loads((ROOT / "results" / name).read_text())
        used.update(r["index"] for r in report["rows"] if r.get("suite", "boolq") == "boolq")
    questions = {data[i]["question"] for i in used}
    passages = {data[i]["passage"] for i in used}
    pool = [i for i,r in enumerate(data) if r["question"] not in questions and r["passage"] not in passages]
    return random.Random(SEED).sample(pool, SIZE)


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
        raise ValueError("Unexpected BoolQ dataset checksum")
    data = list(map(json.loads, raw.splitlines()))
    cases = [("boolq", i, passage(data[i]), "yes" if data[i]["answer"] else "no") for i in new_indices(data)]
    for suite in ("compact_review_controls", "evidence_first_controls", "selective_review_controls"):
        cases.extend((suite, i, q, a) for i, (q, a) in enumerate(json.loads((ROOT / (suite + ".json")).read_text())))
    with urlopen(args.url + "/api/tags", timeout=30) as response:
        digest = next(m["digest"] for m in json.load(response)["models"] if m["name"] == MODEL)
    rows = []
    for n, (suite, index, text, expected) in enumerate(cases):
        row = {"suite": suite, "index": index, "expected": expected}
        for arm in (("json", "plain") if n % 2 == 0 else ("plain", "json")):
            output, tokens = (predict(args.url, MODEL, SINGLE_PASS, text) if arm == "json"
                              else plain_decide(args.url, MODEL, text))
            row[arm] = {"answer": output.get("answer"), "tokens": tokens}
        first = row["plain"]
        for arm in (("current", "compact") if n % 2 == 0 else ("compact", "current")):
            output, total = review(args.url, MODEL, text, first, first["tokens"], compact=arm == "compact")
            row[arm] = {"answer": output["answer"], "tokens": total, "citation": output["citation"]}
        rows.append(row)
    print(json.dumps({"model": MODEL, "digest": digest, "seed": SEED, "data_sha256": DIGEST, "rows": rows}))


if __name__ == "__main__":
    main()
