"""Reproducible comparison of compact and targeted decision candidates."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys

from rei0.local_ai import LocalAIError, LocalOllamaModel, StandaloneREI
from .numeric_decisions import targeted_decision
from .paired_values import compact_decision
from .text_validation_cases import CASES


def compare(agent, provider, cases=CASES):
    records = []
    for index, case in enumerate(cases):
        for side, priority in enumerate(case.priorities):
            order = ("compact", "targeted") if (index + side) % 2 == 0 else ("targeted", "compact")
            for arm in order:
                before = len(provider.attempts)
                try:
                    result = (compact_decision(agent, case, priority) if arm == "compact"
                              else targeted_decision(agent, case, priority, provider=provider))
                except (LocalAIError, OSError, TimeoutError) as exc:
                    attempts = provider.attempts[before:]
                    result = {"choice": None, "error": type(exc).__name__,
                              "model_calls": len(attempts),
                              "model_reported_tokens": sum(x["tokens"] or 0 for x in attempts)}
                attempts = provider.attempts[before:]
                unknown_usage = sum(x.get("tokens") is None for x in attempts)
                result["model_calls"] = len(attempts)
                result["model_reported_tokens"] = sum(x.get("tokens") or 0 for x in attempts)
                records.append({
                    "case": case.name, "side": side, "arm": arm,
                    "expected": case.expected_recommendations[side],
                    "correct": result["choice"] == case.expected_recommendations[side],
                    "unknown_usage_calls": unknown_usage, **result,
                })
                print(f"{len(records)} decisions completed", file=sys.stderr, flush=True)
    return records


def analyze(records):
    indexed = {(r["case"], r["side"], r["arm"]): r for r in records}
    if len(indexed) != len(records):
        raise ValueError("duplicate decision records")
    keys = {(r["case"], r["side"]) for r in records}
    if not keys or set(indexed) != {(case, side, arm) for case, side in keys
                                   for arm in ("compact", "targeted")}:
        raise ValueError("comparison requires both arms for every decision")
    summary = {}
    for arm in ("compact", "targeted"):
        rows = [indexed[case, side, arm] for case, side in sorted(keys)]
        summary[arm] = {
            "correct": sum(row["correct"] for row in rows),
            "decisions": len(rows),
            "invalid": sum(row["choice"] is None for row in rows),
            "calls": sum(row["model_calls"] for row in rows),
            "known_tokens": sum(row["model_reported_tokens"] for row in rows),
            "unknown_usage_calls": sum(row["unknown_usage_calls"] for row in rows),
        }
    regressions = sum(indexed[key + ("compact",)]["correct"]
                      and not indexed[key + ("targeted",)]["correct"] for key in keys)
    corrections = sum(not indexed[key + ("compact",)]["correct"]
                      and indexed[key + ("targeted",)]["correct"] for key in keys)
    return {"arms": summary, "corrections": corrections, "regressions": regressions,
            "decision": "review_results_on_fresh_cases_before_changing_default"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists; choose a new filename")
    provider = LocalOllamaModel()
    status = provider.doctor()
    if not status["model_downloaded"]:
        parser.error("required Ollama model is unavailable")
    agent = StandaloneREI(provider_factory=lambda: provider)
    records = compare(agent, provider)
    report = {
        "schema": "rei.decision_comparison.v1",
        "model": provider.model,
        "case_digest": hashlib.sha256(json.dumps(
            [asdict(case) for case in CASES], sort_keys=True).encode()).hexdigest(),
        "source_digests": {
            name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
            for name in ("decision_comparison.py", "numeric_decisions.py", "paired_values.py")
        },
        "case_status": "previously_used_public_development_cases",
        "summary": analyze(records), "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
