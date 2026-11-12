"""Challenge 10 offline diagnostics: separate LLM performance from trusted status computation.

The model outputs from Challenge 9 remain unchanged. We replay each
synthetic signed-review history to compute an independently authenticated
status, then explain where model proposals contradict it. The same resolver
is exposed to BOTH comparison arms; trivial mechanical correctness with a
shared tool is NOT a claim that REI outperforms a conventional AI.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any
import zipfile

from rei0.benchmark import BenchmarkError
from rei0.models import digest
from rei0.signed_state_decision import audit_model_proposal, resolve_signed_state
from research.challenge9.interventions import generate_cases, replay_case, STATES
from research.challenge9.paired_trial import ARMS, verify_trial


def read_result(path: str | Path) -> dict:
    """Read the original Actions JSON or the downloaded Actions ZIP artifact."""
    path = Path(path)
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            names = [n for n in archive.namelist() if n.endswith("paired-live.json")]
            if len(names) != 1:
                raise BenchmarkError("expected exactly one paired-live.json in archive")
            payload = archive.read(names[0])
            if len(payload) > 2_000_000:
                raise BenchmarkError("oversized model report")
            result = json.loads(payload)
    else:
        if path.stat().st_size > 2_000_000:
            raise BenchmarkError("oversized model report")
        result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict) or set(result) != {"report", "environment"}:
        raise BenchmarkError("invalid model experiment wrapper")
    if not isinstance(result["environment"], dict):
        raise BenchmarkError("invalid model environment")
    return result


def diagnose_trial(report: dict, *, seed: int = 20261111, count: int = 4) -> dict:
    """Regrade model answers and apply the SAME independent status tool to both.

    This is a diagnostic replay, NOT a new model test and NOT a hidden answer
    feed into model prompts. All synthetic cases and keys are already public.
    """
    verify_trial(report, seed=seed, count=count)
    cases = generate_cases(seed=seed, count=count)
    indexed = {(o["case_id"], o["arm"]): o for o in report["outcomes"]}
    records = []
    per_arm = {a: Counter() for a in ARMS}
    for case in cases:
        _, ledger = replay_case(case, return_ledger=True)
        decision = resolve_signed_state(ledger, "P")
        if decision.recorded_state != case.expected:
            raise BenchmarkError("signed state resolver diverges from independent oracle")
        one = {
            "case_id": case.id,
            "independent_oracle": case.expected,
            "trusted_signed_status": decision.recorded_state,
            "status_tool_sha256": decision.to_dict()["decision_sha256"],
            "arms": {},
        }
        for arm in ARMS:
            outcome = indexed[(case.id, arm)]
            inspection = audit_model_proposal(outcome["answer"], decision).to_dict()
            model_correct = outcome["error"] is None and inspection["disposition"] == "agrees"
            one["arms"][arm] = {
                "model_proposal": outcome["answer"],
                "disposition": inspection["disposition"],
                "reported_model_error": outcome["error"],
                "model_correct": model_correct,
                "same_tool_recorded_state": decision.recorded_state,
                "same_tool_matches_oracle": True,
                "model_calls": outcome["model_calls"],
                "reported_tokens": outcome["meter_reported_tokens"],
            }
            per_arm[arm]["model_correct"] += int(model_correct)
            per_arm[arm]["model_failed"] += int(outcome["error"] is not None)
            per_arm[arm]["model_calls"] += outcome["model_calls"]
            per_arm[arm]["reported_tokens"] += outcome["meter_reported_tokens"]
            per_arm[arm]["tool_correct"] += 1
        records.append(one)
    diff = {
        "self_critique": per_arm["self_critique"]["reported_tokens"],
        "rei12": per_arm["rei12"]["reported_tokens"],
    }
    if diff["self_critique"] <= 0:
        raise BenchmarkError("cannot compute relative token cost with zero usage")
    facts = {
        "mode": report["mode"],
        "model_fingerprint": report.get("model_fingerprint"),
        "cases": count,
        "per_arm": {a: dict(per_arm[a]) for a in ARMS},
        "paired_comparison": report["summary"]["primary_rei_minus_self_critique"],
        "rei_reported_token_savings_fraction": round(
            (diff["self_critique"] - diff["rei12"]) / diff["self_critique"], 6
        ),
        "tool_calls_per_arm": count,
        "trusted_tool_accuracy": "exact_by_definition_of_this_mechanical_status_task",
        "warnings": [
            "The shared deterministic tool computes an authenticated review status, not objective truth.",
            "The counterfactual tool results do not measure a live tool-augmented language model.",
            "This public four-case developmental trial cannot support a superiority conclusion.",
            "Actual consumed model computation was NOT matched between the two reasoning arms.",
            "Original model outputs and their logged failures remain unchanged.",
        ],
    }
    result = {
        "schema": "rei.challenge10.diagnostic.v1",
        "input_report_sha256": report["report_sha256"],
        "diagnostic": facts,
        "cases": records,
    }
    return {**result, "diagnostic_sha256": digest(result)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--count", type=int, default=4)
    parser.add_argument("--seed", type=int, default=20261111)
    args = parser.parse_args(argv)
    wrapped = read_result(args.input)
    result = diagnose_trial(wrapped["report"], seed=args.seed, count=args.count)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result["diagnostic"], indent=2))
    for case in result["cases"]:
        print(case["case_id"], "trusted:",case["trusted_signed_status"],
              "self-critique:",case["arms"]["self_critique"]["model_proposal"],
              "REI 1.2:",case["arms"]["rei12"]["model_proposal"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
