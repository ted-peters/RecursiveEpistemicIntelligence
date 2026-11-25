"""Paired, shared-call comparison of lexical eligibility with budgeted review."""
import argparse
import hashlib
import json
from pathlib import Path
import random
from urllib.request import urlopen

from adaptive_rei_benchmark import SINGLE_PASS, predict
from boolq_trial import DIGEST, MODEL, URL, ORIGINAL, FOCUS, IMPLIED, passage, sample_indices
from compact_review_trial import ROOT
from plain_verdict import decide as plain_decide
from selective_review import review


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path)
    parser.add_argument("--url", default="http://127.0.0.1:11434")
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--shards", type=int, default=1)
    args = parser.parse_args()
    if not 0 <= args.shard < args.shards:
        parser.error("shard index outside shard count")
    if args.data:
        raw = args.data.read_bytes()
    else:
        with urlopen(URL, timeout=60) as response:
            raw = response.read()
    if hashlib.sha256(raw).hexdigest() != DIGEST:
        raise ValueError("Unexpected dataset checksum")
    data = list(map(json.loads, raw.splitlines()))
    files = (ORIGINAL, FOCUS, IMPLIED, "boolq_plain_verdict.json")
    used = set(sample_indices(data, 20261123, 240, files))
    for filename in (*files, "evidence_first_review.json", "compact_review_trial.json", "budgeted_review_trial.json"):
        report = json.loads((ROOT / "results" / filename).read_text())
        used.update(r["index"] for r in report["rows"] if r.get("suite", "boolq") == "boolq")
    questions = {data[i]["question"] for i in used}
    passages = {data[i]["passage"] for i in used}
    pool = [i for i, r in enumerate(data) if r["question"] not in questions and r["passage"] not in passages]
    indices = random.Random(20261127).sample(pool, 240)
    cases = [("boolq", i, passage(data[i]), "yes" if data[i]["answer"] else "no") for i in indices]
    controls = json.loads((ROOT / "overlap_controls.json").read_text())
    cases.extend(("control", i, q, a) for i, (q, a) in enumerate(controls))
    with urlopen(args.url + "/api/tags", timeout=30) as response:
        digest = next(m["digest"] for m in json.load(response)["models"] if m["name"] == MODEL)
    rows = []
    for suite, i, text, expected in cases[args.shard::args.shards]:
        first, tokens = plain_decide(args.url, MODEL, text)
        candidate, cost = review(args.url, MODEL, text, first, tokens, check_overlap=True)
        # A surviving call uses the identical prompt, parameters and model in both arms.
        # Charge its full cost to both. Run the comparator separately on skipped calls.
        if candidate.get("review_skipped") == "low_question_overlap":
            current, current_cost = review(args.url, MODEL, text, first, tokens, skip_gaps=True)
        else:
            current, current_cost = candidate, cost
        baseline, baseline_cost = predict(args.url, MODEL, SINGLE_PASS, text)
        rows.append({"suite": suite, "index": i, "expected": expected,
                     "single_pass": baseline.get("answer"), "single_pass_tokens": baseline_cost,
                     "plain": first["answer"], "plain_tokens": tokens,
                     "budgeted": current["answer"], "budgeted_tokens": current_cost,
                     "candidate": candidate["answer"], "candidate_tokens": cost,
                     "skip": candidate.get("review_skipped"), "citation": candidate["citation"]})
    summary = {}
    for suite in ("boolq", "control"):
        group = [r for r in rows if r["suite"] == suite]
        summary[suite] = {arm: {"correct": sum(r[arm] == r["expected"] for r in group),
                                "questions": len(group), "tokens": sum(r[arm + "_tokens"] for r in group)}
                          for arm in ("single_pass", "plain", "budgeted", "candidate")}
    print(json.dumps({"model": MODEL, "digest": digest, "data_sha256": DIGEST,
                      "seed": 20261127, "excluded": len(used), "summary": summary, "rows": rows}))


if __name__ == "__main__":
    main()
