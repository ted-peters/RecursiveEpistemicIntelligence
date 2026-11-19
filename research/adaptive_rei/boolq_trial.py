"""Independent BoolQ routing audit and a seeded, matched live Qwen comparison."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
from urllib.request import urlopen

from adaptive_rei_benchmark import SINGLE_PASS, predict
from evidence_register import decide, evidence_passage, register_answer
from report_chain import report_chain_answer

# Byte-identical mirror of the original Google release, verified below.
URL = ("https://raw.githubusercontent.com/svinkapeppa/boolq/"
       "65cad7c96c62f80b37394434fc4bf5a6148ccafc/dev.jsonl")
DIGEST = "ebc29ea3808c5c611672384b3de56e83349fe38fc1fe876fd29b674d81d0a80a"
MODEL = "qwen3:4b-instruct"
SEED = 20261119
SAMPLE = 40


def passage(row):
    return row["question"].strip().rstrip("?") + "? " + row["passage"]


def route(text):
    if register_answer(text) is not None:
        return "register"
    if report_chain_answer(text) is not None:
        return "report_chain"
    if evidence_passage(text) != text:
        return "aside_filter"
    return "unchanged_prompt"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, help="Optional local copy of the official dev.jsonl")
    parser.add_argument("--url", default="http://127.0.0.1:11434")
    args = parser.parse_args()
    if args.data:
        raw = args.data.read_bytes()
    else:
        with urlopen(URL, timeout=60) as response:
            raw = response.read()
    if hashlib.sha256(raw).hexdigest() != DIGEST:
        raise ValueError("BoolQ development file failed SHA-256 verification")
    data = [json.loads(line) for line in raw.splitlines()]
    texts = [passage(row) for row in data]
    coverage = Counter(map(route, texts))
    with urlopen(args.url + "/api/tags", timeout=30) as response:
        models = json.load(response)["models"]
    digest = next(m["digest"] for m in models if m["name"] == MODEL)
    rows = []
    for order, index in enumerate(random.Random(SEED).sample(range(len(data)), SAMPLE)):
        text = texts[index]
        expected = "yes" if data[index]["answer"] else "no"
        result = {"index": index, "route": route(text), "expected": expected}
        for arm in (("baseline", "rei") if order % 2 == 0 else ("rei", "baseline")):
            if arm == "rei":
                answer, tokens = decide(args.url, MODEL, text)
            else:
                answer, tokens = predict(args.url, MODEL, SINGLE_PASS, text)
            result[arm] = {"answer": answer.get("answer"), "tokens": tokens}
        rows.append(result)
    totals = {arm: {"correct": sum(r[arm]["answer"] == r["expected"] for r in rows),
                    "tokens": sum(r[arm]["tokens"] for r in rows)} for arm in ("baseline", "rei")}
    print(json.dumps({"data_url": URL, "sha256": DIGEST, "seed": SEED, "model": MODEL,
                      "model_digest": digest, "full_split_routes": coverage,
                      "sample_totals": totals, "rows": rows}))


if __name__ == "__main__":
    main()
