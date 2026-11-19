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
from plain_verdict import decide as plain_decide

# Byte-identical mirror of the original Google release, verified below.
URL = ("https://raw.githubusercontent.com/svinkapeppa/boolq/"
       "65cad7c96c62f80b37394434fc4bf5a6148ccafc/dev.jsonl")
DIGEST = "ebc29ea3808c5c611672384b3de56e83349fe38fc1fe876fd29b674d81d0a80a"
MODEL = "qwen3:4b-instruct"
SEED = 20261119
SAMPLE = 40


def passage(row):
    return row["question"].strip().rstrip("?") + "? " + row["passage"]


# Prior result files identify every question and passage seen before the trial.
ORIGINAL = "boolq_trial.json"
FOCUS = "boolq_question_focus.json"
IMPLIED = "boolq_implied.json"
TRIALS = {
    "original": (SEED, SAMPLE, decide, ()),
    "question_last": (20261120, 120, focused_decide, (ORIGINAL,)),
    "implied_evidence": (20261121, 160, implied_decide, (ORIGINAL, FOCUS)),
    "plain_verdict": (20261122, 200, plain_decide, (ORIGINAL, FOCUS, IMPLIED)),
}


def sample_indices(data, seed, size, prior_files):
    previous = []
    for name in prior_files:
        report = json.loads((Path(__file__).with_name("results") / name).read_text())
        previous.extend(data[r["index"]] for r in report["rows"])
    questions = {r["question"] for r in previous}
    passages = {r["passage"] for r in previous}
    eligible = [i for i, r in enumerate(data)
                if r["question"] not in questions and r["passage"] not in passages]
    return random.Random(seed).sample(eligible, size)


def route(text, trial):
    if register_answer(text) is not None:
        return "register"
    if report_chain_answer(text) is not None:
        return "report_chain"
    if trial in ("plain_verdict", "implied_evidence"):
        return trial
    if trial == "question_last" and prose_prompt(text)[0] != SINGLE_PASS:
        return trial
    if evidence_passage(text) != text:
        return "aside_filter"
    return "unchanged_prompt"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, help="Optional local copy of the official dev.jsonl")
    parser.add_argument("--url", default="http://127.0.0.1:11434")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--plain", dest="trial", action="store_const", const="plain_verdict", help="Test a plain verdict on 200 new cases.")
    modes.add_argument("--implied", dest="trial", action="store_const", const="implied_evidence", help="Evaluate ordinary implications on 160 new cases.")
    modes.add_argument("--question-focus", dest="trial", action="store_const", const="question_last",
                        help="Compare the experimental fallback on 120 fresh questions.")
    parser.set_defaults(trial="original")
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
    coverage = Counter(route(text, args.trial) for text in texts)
    with urlopen(args.url + "/api/tags", timeout=30) as response:
        models = json.load(response)["models"]
    digest = next(m["digest"] for m in models if m["name"] == MODEL)
    seed, size, policy, prior_files = TRIALS[args.trial]
    indices = sample_indices(data, seed, size, prior_files)
    rows = []
    for order, index in enumerate(indices):
        text = texts[index]
        expected = "yes" if data[index]["answer"] else "no"
        result = {"index": index, "route": route(text, args.trial), "expected": expected}
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
