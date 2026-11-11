"""Challenge 8: same four REI benchmark arms, schema-constrained model IO."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from rei0.benchmark import Limits, read_json, run_benchmark, verify_report, load_study
from .structured_provider import StructuredLocalProvider, verify_model, MODEL_ALIAS

ROOT = Path(__file__).resolve().parents[2]


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--model-file", type=Path, required=True)
    p.add_argument("--engine-commit", required=True)
    p.add_argument("--cases", type=Path, default=ROOT/"research"/"challenge7"/"cases.json")
    p.add_argument("--keys", type=Path, default=ROOT/"research"/"challenge7"/"keys.json")
    p.add_argument("--output", type=Path, default=Path("challenge8-results/structured.json"))
    p.add_argument("--shard-index", type=int, default=0)
    p.add_argument("--shard-count", type=int, default=1)
    p.add_argument("--verify-only", action="store_true")
    a = p.parse_args(argv)
    cases = read_json(a.cases)
    keys = read_json(a.keys)
    parsed, parsed_keys = load_study(cases, keys)
    if not 1 <= a.shard_count <= 24 or not 0 <= a.shard_index < a.shard_count:
        p.error("Invalid shard index/count")
    if a.shard_count > len(parsed):
        p.error("More shards than cases")
    chosen_ids = {c.id for i, c in enumerate(parsed) if i % a.shard_count == a.shard_index}
    cases = {"schema": cases["schema"], "cases": [c for c in cases["cases"] if c["id"] in chosen_ids]}
    keys = {"schema": keys["schema"], "answers": [k for k in keys["answers"] if k["case_id"] in chosen_ids]}
    if a.verify_only:
        recorded = json.loads(a.output.read_text())
        print("VERIFIED:", verify_report(recorded["report"], cases, keys))
        return 0
    sha = verify_model(a.model_file)
    provider = StructuredLocalProvider(sha, a.engine_commit)
    limits = Limits(max_calls=3, max_tokens=2600, max_seconds=140, max_output_tokens=320, steps=1)
    report = run_benchmark(cases, keys, provider, limits=limits, seed=24011)
    verified = verify_report(report, cases, keys)
    attempted = provider.attempts
    known = [x["reported_tokens_even_if_failed"] for x in attempted
             if x["reported_tokens_even_if_failed"] is not None]
    per_arm = {}
    for arm in ("baseline", "self_critique", "fixed_depth", "rei"):
        relevant = [a for a in attempted if a["arm"] == arm]
        per_arm[arm] = {
            "attempted_calls": len(relevant),
            "server_reported_tokens_including_failed_parses": sum(
                a["reported_tokens_even_if_failed"] or 0 for a in relevant),
            "calls_with_unknown_tokens": sum(
                a["reported_tokens_even_if_failed"] is None for a in relevant),
            "calls_with_provider_error": sum(a["status"] == "failed" for a in relevant),
        }
    # One stable identity across all shards of a single GitHub workflow attempt.
    # Local multi-shard invocations must set REI_EXPERIMENT_RUN_ID themselves.
    experiment_run_id = os.environ.get("REI_EXPERIMENT_RUN_ID")
    if not experiment_run_id and os.environ.get("GITHUB_RUN_ID"):
        experiment_run_id = ("github-actions:" + os.environ["GITHUB_RUN_ID"] + ":" +
                             os.environ.get("GITHUB_RUN_ATTEMPT", "1"))
    summary = {
        "experiment_run_id": experiment_run_id,
        "model": MODEL_ALIAS, "model_sha256": sha,
        "llama_cpp_commit": a.engine_commit, "run_utc": datetime.now(timezone.utc).isoformat(),
        "method": "schema_constrained_json_v1_applied_to_all_four_arms",
        "study": "public_nonblind_development_experiment_no_inference_of_general_superiority",
        "shard_index": a.shard_index, "shard_count": a.shard_count,
        "case_count": len(chosen_ids), "calls_attempted": len(attempted),
        "measured_attempt_tokens_including_parse_failures": sum(known),
        "attempts_with_unknown_tokens": len(attempted)-len(known),
        "attempts": attempted, "attempt_usage_by_arm": per_arm,
        "constraints": {"max_calls":3,"max_tokens":2600,"max_seconds":140,"max_output_tokens":320,"steps":1},
        "warning": "Token-use data may be incomplete for timeouts. No ground-truth key enters model prompts.",
    }
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps({"report": report, "environment": summary}, indent=2))
    print("VERIFIED:", verified)
    print("SUMMARY:", json.dumps(report["summary"], indent=2))
    print("ATTEMPT_USAGE_BY_ARM:", json.dumps(per_arm, indent=2))
    print("MEASURED_ATTEMPT_TOKENS:", summary["measured_attempt_tokens_including_parse_failures"])
    print("ATTEMPTS_WITH_UNKNOWN_TOKENS:", summary["attempts_with_unknown_tokens"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())