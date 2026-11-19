"""Compare a frozen evidence policy with the existing single-pass prompt on Ollama."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

from adaptive_rei_benchmark import predict, SINGLE_PASS
from evidence_budget import evidence_instruction

HERE = Path(__file__).resolve().parent
MODEL = "qwen3:4b-instruct"


def run(url, cases, use_register=False):
    from evidence_register import decide
    with urlopen(url + "/api/tags", timeout=30) as response:
        models = json.load(response)["models"]
    digest = next(m["digest"] for m in models if m["name"] == MODEL)
    rows = []
    for i, (question, expected) in enumerate(cases):
        row = {"question": question, "expected": expected}
        arms = [("single", SINGLE_PASS), ("candidate", evidence_instruction(question))]
        for arm, instruction in (arms if i % 2 == 0 else reversed(arms)):
            if use_register and arm == "candidate":
                answer, tokens = decide(url, MODEL, question)
            else:
                answer, tokens = predict(url, MODEL, instruction, question)
            row[arm] = {"answer": answer.get("answer"), "tokens": tokens}
        rows.append(row)
    summary = {
        arm: {"correct": sum(r[arm]["answer"] == r["expected"] for r in rows),
              "tokens": sum(r[arm]["tokens"] for r in rows)}
        for arm in ("single", "candidate")
    }
    summary["meets_target"] = (
        summary["candidate"]["correct"] > summary["single"]["correct"]
        and summary["candidate"]["tokens"] <= summary["single"]["tokens"]
    )
    return {"model": MODEL, "model_digest": digest, "summary": summary, "rows": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:11434")
    parser.add_argument("--cases", type=Path, default=HERE / "evidence_budget_cases.json")
    parser.add_argument("--register", action="store_true", help="Use register resolution and explicit aside filtering.")
    args = parser.parse_args()
    report = run(args.url.rstrip("/"), json.loads(args.cases.read_bytes()), args.register)
    report["cases_sha256"] = hashlib.sha256(args.cases.read_bytes()).hexdigest()
    print(json.dumps(report))
