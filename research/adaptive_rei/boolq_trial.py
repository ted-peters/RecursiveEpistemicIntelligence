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
from question_focus import decide as focused_decide, prose_prompt
from implied_evidence import decide as implied_decide

# Byte-identical mirror of the original Google release, verified below.
URL = ("https://raw.githubusercontent.com/svinkapeppa/boolq/"
       "65cad7c96c62f80b37394434fc4bf5a6148ccafc/dev.jsonl")
DIGEST = "ebc29ea3808c5c611672384b3de56e83349fe38fc1fe876fd29b674d81d0a80a"
MODEL = "qwen3:4b-instruct"
SEED = 20261119
SAMPLE = 40


def passage(row):
    return row["question"].strip().rstrip("?") + "? " + row["passage"]


def route(text, question_focus=False, implied=False):
    if register_answer(text) is not None:
        return "register"
    if report_chain_answer(text) is not None:
        return "report_chain"
    if implied:
        return "implied_evidence"
    if question_focus and prose_prompt(text)[0] != SINGLE_PASS:
        return "question_last"
    if evidence_passage(text) != text:
        return "aside_filter"
    return "unchanged_prompt"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, help="Optional local copy of the official dev.jsonl")
    parser.add_argument("--url", default="http://127.0.0.1:11434")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--implied", action="store_true", help="Evaluate ordinary implications on 160 new cases.")
    modes.add_argument("--question-focus", action="store_true",
                        help="Compare the experimental fallback on 120 fresh questions.")
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
    coverage = Counter(route(text, args.question_focus, args.implied) for text in texts)
    with urlopen(args.url + "/api/tags", timeout=30) as response:
        models = json.load(response)["models"]
    digest = next(m["digest"] for m in models if m["name"] == MODEL)
    seed = SEED
    indices = random.Random(seed).sample(range(len(data)), SAMPLE)
    policy = decide
    if args.question_focus or args.implied:
        prior = Path(__file__).with_name("results") / "boolq_trial.json"
        previous = [data[r["index"]] for r in json.loads(prior.read_text())["rows"]]
        if args.implied:
            focus = prior.with_name("boolq_question_focus.json")
            previous.extend(data[r["index"]] for r in json.loads(focus.read_text())["rows"])
        questions = {r["question"] for r in previous}
        passages = {r["passage"] for r in previous}
        eligible = [i for i, r in enumerate(data)
                    if r["question"] not in questions and r["passage"] not in passages]
        seed = 20261121 if args.implied else 20261120
        indices = random.Random(seed).sample(eligible, 160 if args.implied else 120)
        policy = implied_decide if args.implied else focused_decide
    rows = []
    for order, index in enumerate(indices):
        text = texts[index]
        expected = "yes" if data[index]["answer"] else "no"
        result = {"index": index, "route": route(text, args.question_focus, args.implied), "expected": expected}
        for arm in (("baseline", "rei") if order % 2 == 0 else ("rei", "baseline")):
            if arm == "rei":
                answer, tokens = policy(args.url, MODEL, text)
            else:
                answer, tokens = predict(args.url, MODEL, SINGLE_PASS, text)
            result[arm] = {"answer": answer.get("answer"), "tokens": tokens}
        rows.append(result)
    totals = {arm: {"correct": sum(r[arm]["answer"] == r["expected"] for r in rows),
                    "tokens": sum(r[arm]["tokens"] for r in rows)} for arm in ("baseline", "rei")}
    print(json.dumps({"data_url": URL, "sha256": DIGEST, "seed": seed, "policy": policy.__module__, "model": MODEL,
                      "model_digest": digest, "full_split_routes": coverage,
                      "sample_totals": totals, "rows": rows}))


if __name__ == "__main__":
    main()
