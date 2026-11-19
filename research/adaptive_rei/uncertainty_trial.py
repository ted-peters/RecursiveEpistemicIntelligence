"""Measure an experimental verdict policy on existing controls with all three labels."""
import argparse
import json
from pathlib import Path

from adaptive_rei_benchmark import SINGLE_PASS, predict
from boolq_trial import MODEL
from implied_evidence import decide as implied_decide
from plain_verdict import decide as plain_decide


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("policy", choices=("implied", "plain"))
    parser.add_argument("--url", default="http://127.0.0.1:11434")
    args = parser.parse_args()
    decide = {"implied": implied_decide, "plain": plain_decide}[args.policy]
    rows = []
    for filename in ("aside_cases.json", "evidence_budget_cases.json"):
        cases = json.loads(Path(__file__).with_name(filename).read_text())
        for i, (question, expected) in enumerate(cases):
            row = {"suite": filename, "index": i, "expected": expected}
            for arm in (("baseline", "rei") if i % 2 == 0 else ("rei", "baseline")):
                if arm == "rei":
                    answer, tokens = decide(args.url, MODEL, question)
                else:
                    answer, tokens = predict(args.url, MODEL, SINGLE_PASS, question)
                row[arm] = {"answer": answer.get("answer"), "tokens": tokens}
            rows.append(row)
    print(json.dumps(rows))


if __name__ == "__main__":
    main()
