"""Challenge 9 CLI: free synthetic pipeline smoke test or explicitly opted-in live trial.

The offline fixture is a software integration test only. The live mode uses the
same pinned Qwen model for both arms and never embeds gold keys in requests.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from rei0.inquiry import ModelTurn
from .arm_blind_provider import ArmBlindLocalProvider
from .paired_trial import ARMS, run_trial, verify_trial
from research.challenge8.structured_provider import MODEL_ALIAS, verify_model


class ScriptedFixtureProvider:
    kind = "scripted_fixture_not_empirical"
    fingerprint = "challenge9-fixed-json-fixture-v1"

    def __init__(self):
        self.attempts = []

    def respond(self, *, case_id, arm, stage, context,
                max_output_tokens, timeout):
        self.attempts.append({
            "case_id": case_id, "arm": arm, "stage": stage,
            "reported_tokens_even_if_failed": 15, "status": "parsed",
            "finish_reason": "stop",
        })
        if stage == "initial":
            result = {"claim": "Provisional claim P",
                      "questions": [{"text": "What changes the evidential status?",
                                     "target": "claim", "priority": 9}]}
        elif stage == "expand":
            result = {"reasons": ["The synthetic dossier has recorded reviews"],
                      "objections": ["Reviews could be revoked"],
                      "followups": [],
                      "note": "Synthetic fixture: no actual inference"}
        elif stage == "critique":
            result = {"critique": "Reconsider trusted reviews, not forged claims"}
        else:
            result = {"answer": "NEITHER", "confidence": 0.5,
                      "rationale": "Fixed scripted output, not a model prediction"}
        return ModelTurn(result, 15)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", choices=("fixture", "live"), default="fixture")
    p.add_argument("--count", type=int, choices=(4, 8, 12), default=4)
    p.add_argument("--seed", type=int, default=20261111)
    p.add_argument("--model-file", type=Path)
    p.add_argument("--engine-commit")
    p.add_argument("--output", type=Path, default=Path("challenge9-results/paired.json"))
    p.add_argument("--verify-only", action="store_true")
    args = p.parse_args(argv)

    if args.verify_only:
        try:
            saved = json.loads(args.output.read_text(encoding="utf-8"))
            result = verify_trial(saved["report"], seed=args.seed, count=args.count)
        except (OSError, KeyError, ValueError, TypeError) as exc:
            p.error(f"saved report cannot be verified: {exc}")
        print("INDEPENDENT REGRADE:", json.dumps(result, sort_keys=True))
        return 0

    if args.mode == "live":
        if args.model_file is None or not args.engine_commit:
            p.error("--model-file and --engine-commit are required for live mode")
        model_sha = verify_model(args.model_file)
        provider = ArmBlindLocalProvider(model_sha, args.engine_commit)
    else:
        model_sha = None
        provider = ScriptedFixtureProvider()

    report = run_trial(provider, seed=args.seed, count=args.count)
    verified = verify_trial(report, seed=args.seed, count=args.count)
    environment = {
        "mode": args.mode,
        "model": MODEL_ALIAS if args.mode == "live" else "SCRIPTED_FIXTURE_NOT_A_MODEL",
        "model_sha256": model_sha,
        "llama_cpp_commit": args.engine_commit if args.mode == "live" else None,
        "run_utc": datetime.now(timezone.utc).isoformat(),
        "study_class": "nonblind_public_synthetic_development",
        "primary_comparator": "self_critique",
        "actual_compute_matched": False,
        "run_origin": os.environ.get("GITHUB_RUN_ID"),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps({"report": report, "environment": environment}, indent=2)+"\n",
        encoding="utf-8",
    )
    print("VERIFIED:", json.dumps(verified, sort_keys=True))
    print("SUMMARY:", json.dumps(report["summary"], indent=2))
    print("ATTEMPT_USAGE:", json.dumps(report["attempt_usage"], indent=2))
    print("WARNING: This development set is PUBLIC, not blind or compute matched.")
    if args.mode == "fixture":
        print("WARNING: SCRIPTED FIXTURE; ALL ANSWERS ARE FAKE MODEL RESPONSES.")
    step_summary = os.getenv("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as out:
            out.write("## Challenge 9 — Signed evidence, paired development pilot\n\n")
            out.write(
                f"**Mode:** {args.mode}. Public synthetic development cases: "
                f"{args.count}. Not blind or consumed-compute matched.\n\n"
            )
            out.write("| Arm | Correct | Failed | Calls | Meter tokens |\n")
            out.write("|---|---:|---:|---:|---:|\n")
            for arm in ARMS:
                row = report["summary"]["arms"][arm]
                out.write(
                    f"| {arm} | {row['correct']}/{row['cases']} | "
                    f"{row['failed']} | {row['model_calls']} | "
                    f"{row['meter_reported_tokens']} |\n"
                )
            out.write("\n")
            out.write(
                "This is a **synthetic fixture**, NOT an AI-performance test.\n"
                if args.mode == "fixture"
                else "Real model calls; exploratory only, not a superiority claim.\n"
            )
            out.write(
                "\nProvider tokens from failed calls may be absent in the meter; "
                "inspect ATTEMPT_USAGE and its unknown-usage fields in the result.\n"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
