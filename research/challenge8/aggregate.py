"""Independently regrade and combine Challenge 8's six four-case result shards.

This is an audit of a *public synthetic development set*, not a blinded study.
Fail closed on missing/duplicate shards, mismatched experimental conditions,
invalid benchmark reports, and inconsistent attempt telemetry. Incomplete token
usage remains explicitly unknown, never zero-cost inference.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from rei0.benchmark import ARMS, grade, load_study, paired_intervals, read_json, verify_report

HERE = Path(__file__).resolve().parent
CONDITIONS = ("experiment_run_id", "model", "model_sha256", "llama_cpp_commit", "method", "constraints", "study")


class AggregateError(ValueError):
    """One or more required scientific-integrity checks failed."""


def subset(full_cases: dict, full_keys: dict, index: int, count: int) -> tuple[dict, dict]:
    cases, _ = load_study(full_cases, full_keys)
    ids = {case.id for i, case in enumerate(cases) if i % count == index}
    return (
        {"schema": full_cases["schema"], "cases": [c for c in full_cases["cases"] if c["id"] in ids]},
        {"schema": full_keys["schema"], "answers": [k for k in full_keys["answers"] if k["case_id"] in ids]},
    )


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AggregateError(message)


def _check_attempts(env: dict, report: dict) -> dict:
    attempts = env.get("attempts")
    _require(isinstance(attempts, list), "Missing provider attempt log")
    expected = {(o["case_id"], o["arm"]): o for o in report["outcomes"]}
    observed = defaultdict(list)
    tokens = Counter()
    unknown = Counter()
    errors = Counter()
    for attempt in attempts:
        _require(isinstance(attempt, dict), "Malformed attempt")
        key = (attempt.get("case_id"), attempt.get("arm"))
        _require(key in expected, "Attempt refers to an unknown case/arm")
        _require(attempt.get("stage") in ("draft", "critique", "final", "initial", "expand"),
                 "Unrecognized model stage")
        _require(attempt.get("status") in ("parsed", "failed"), "Invalid attempt status")
        used = attempt.get("reported_tokens_even_if_failed")
        _require(used is None or (type(used) is int and used > 0), "Invalid observed token count")
        observed[key].append(attempt)
        if used is None:
            unknown[key[1]] += 1
        else:
            tokens[key[1]] += used
        errors[key[1]] += (attempt["status"] == "failed")
    for key, outcome in expected.items():
        turns = observed[key]
        _require(len(turns) == outcome["model_calls"], "Attempt count does not match report")
        # The inherited meter can omit usage from a provider call that failed
        # to parse; the provider audit records usage even for that failure.
        known = sum(a["reported_tokens_even_if_failed"] or 0 for a in turns)
        _require(known >= outcome["reported_tokens"], "Report charges more tokens than observed")
        if all(a["status"] == "parsed" for a in turns):
            _require(known == outcome["reported_tokens"], "Parsed turn usage disagrees with report")
    _require(env.get("calls_attempted") == len(attempts), "Reported attempt count differs from log")
    _require(env.get("attempts_with_unknown_tokens") == sum(unknown.values()),
             "Reported unknown-token count differs from log")
    _require(env.get("measured_attempt_tokens_including_parse_failures") == sum(tokens.values()),
             "Reported token count differs from attempt log")
    saved = env.get("attempt_usage_by_arm")
    _require(isinstance(saved, dict) and set(saved) == set(ARMS), "Per-arm telemetry missing")
    for arm in ARMS:
        relevant = [a for a in attempts if a["arm"] == arm]
        _require(saved[arm] == {
            "attempted_calls": len(relevant),
            "server_reported_tokens_including_failed_parses": tokens[arm],
            "calls_with_unknown_tokens": unknown[arm],
            "calls_with_provider_error": errors[arm],
        }, f"Incorrect attempt telemetry for {arm}")
    return {arm: {
        "calls": sum(a["arm"] == arm for a in attempts),
        "known_tokens": tokens[arm],
        "unknown_token_calls": unknown[arm],
        "provider_failed_calls": errors[arm],
    } for arm in ARMS}


def aggregate_shards(paths: list[Path], full_cases: dict, full_keys: dict,
                     shard_count: int = 6) -> dict:
    """Verify individual reports and produce one independently regraded summary."""
    _require(type(shard_count) is int and 1 <= shard_count <= 24, "Invalid shard count")
    cases, keys = load_study(full_cases, full_keys)
    _require(len(cases) >= shard_count, "More shards than cases")
    _require(len(paths) == shard_count, "Require exactly one file per shard")
    all_outcomes = []
    totals = {arm: {"calls": 0, "known_tokens": 0, "unknown_token_calls": 0,
                    "provider_failed_calls": 0} for arm in ARMS}
    seen = set()
    conditions = None
    reference = None
    provenance = []
    for path in paths:
        data = read_json(path)
        env, report = data.get("environment"), data.get("report")
        _require(isinstance(env, dict) and isinstance(report, dict), "Missing report or environment")
        index = env.get("shard_index")
        _require(type(index) is int and 0 <= index < shard_count, "Invalid shard index")
        _require(index not in seen, "Duplicate shard index")
        seen.add(index)
        _require(env.get("shard_count") == shard_count, "Shard-count mismatch")
        c, k = subset(full_cases, full_keys, index, shard_count)
        _require(env.get("case_count") == len(c["cases"]), "Shard case-count mismatch")
        verify_report(report, c, k)  # Grades/checksum validated against THIS shard's expected cases.
        this_conditions = {name: env.get(name) for name in CONDITIONS}
        _require(all(this_conditions.values()), "Missing environment fingerprint")
        this_reference = {name: report.get(name) for name in
                          ("mode", "provider_fingerprint", "seed", "budgets")}
        _require(all(x is not None for x in this_reference.values()), "Report fingerprint incomplete")
        if conditions is None:
            conditions, reference = this_conditions, this_reference
        else:
            _require(conditions == this_conditions and reference == this_reference,
                     "Experiment settings differ across shards")
        attempt_metrics = _check_attempts(env, report)
        for arm in ARMS:
            for name, value in attempt_metrics[arm].items():
                totals[arm][name] += value
        all_outcomes.extend(report["outcomes"])
        provenance.append({"shard": index, "report_sha256": report["report_sha256"]})
    _require(seen == set(range(shard_count)), "Missing required shard")
    _require({(x["case_id"], x["arm"]) for x in all_outcomes} ==
             {(c.id, arm) for c in cases for arm in ARMS}, "Case/arm coverage incomplete")
    summary = {}
    for arm in ARMS:
        rows = [o for o in all_outcomes if o["arm"] == arm]
        correct = sum(grade(o, keys[o["case_id"]])["correct"] for o in rows)
        summary[arm] = {
            "correct": correct, "cases": len(cases), "accuracy": correct / len(cases),
            "failed_cases": sum(o["error"] is not None for o in rows),
            "abstentions": sum(o["error"] is None and o["answer"] is None for o in rows),
            "benchmark_meter_tokens": sum(o["reported_tokens"] for o in rows),
            **totals[arm],
        }
    # Paired differences are recomputed on all cases together, not averaged
    # from separate shard bootstrap intervals.
    pairs = paired_intervals(all_outcomes, keys, seed=reference["seed"])
    primary = pairs["rei_minus_self_critique"]
    return {
        "schema": "rei.challenge8.aggregate.v1",
        "study": "public_nonblind_synthetic_development_not_compute_matched",
        "case_count": len(cases), "shard_count": shard_count,
        "verified_shards": sorted(provenance, key=lambda x: x["shard"]),
        "environment": conditions, "benchmark": reference,
        "by_arm": summary,
        "primary_comparison": {
            "name": "rei_minus_self_critique",
            "paired_accuracy_difference": primary["paired_mean_difference"],
            "bootstrap_95_percent_interval": primary["bootstrap_95_percent_interval"],
            "cases": primary["pairs"],
        },
        "all_paired_comparisons": pairs,
        "compute_matched": False,
        "usage_complete": all(not a["unknown_token_calls"] for a in summary.values()),
        "warnings": [
            "Public synthetic development cases; NOT a blind or independent performance claim.",
            "Equal computation ceilings are not equal actual computation.",
            "Server-reported tokens are not exact wall-clock/energy measurements.",
            "Any unknown-token call makes total consumption a lower bound, not an exact cost.",
            "Checksums and oracle regrading detect consistency errors, not falsified raw inference.",
        ],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("shards", type=Path, nargs="+", help="All six independently archived shard JSON files")
    parser.add_argument("--cases", type=Path, default=HERE / "scaled_cases.json")
    parser.add_argument("--keys", type=Path, default=HERE / "scaled_keys.json")
    parser.add_argument("--output", type=Path, default=Path("challenge8-results/aggregate.json"))
    args = parser.parse_args(argv)
    result = aggregate_shards(args.shards, read_json(args.cases), read_json(args.keys))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("VERIFIED", result["case_count"], "cases across", result["shard_count"], "shards")
    for arm in ARMS:
        s = result["by_arm"][arm]
        print(f"{arm}: {s['correct']}/{s['cases']} correct, {s['failed_cases']} failed, "
              f"{s['known_tokens']} measured tokens, {s['unknown_token_calls']} unknown-token calls")
    print("PRIMARY REI minus self-critique:", result["primary_comparison"])
    print("NOT BLIND; NOT COMPUTE MATCHED; NOT A GENERAL SUPERIORITY CLAIM")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
