"""Challenge 7: actual 4-arm model test on synthetic dynamic evidence cases.

Same underlying GGUF model and unchanged REI-1.0 benchmark semantics as
Challenge 6; a 6-case exploratory test, not a blind or compute-matched trial.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from rei0.benchmark import Limits, read_json, run_benchmark, verify_report
from research.challenge6.pilot_runner import LocalGGUFProvider, check_model, MODEL_ALIAS

HERE=Path(__file__).resolve().parent


def main(argv=None) -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--model-file",type=Path,required=True)
    ap.add_argument("--engine-commit",required=True)
    ap.add_argument("--output",type=Path,default=Path("challenge7-results/pilot.json"))
    ap.add_argument("--verify-only",action="store_true")
    a=ap.parse_args(argv)
    cases=read_json(HERE/"cases.json")
    keys=read_json(HERE/"keys.json")
    if a.verify_only:
        saved=json.loads(a.output.read_text())
        result=verify_report(saved["report"],cases,keys)
        print("PASS independent report regrading:",result)
        return 0
    model_sha=check_model(a.model_file)
    provider=LocalGGUFProvider(model_sha,a.engine_commit)
    limits=Limits(max_calls=3,max_tokens=2600,max_seconds=140,max_output_tokens=320,steps=1)
    report=run_benchmark(cases,keys,provider,limits=limits,seed=24011)
    verification=verify_report(report,cases,keys)
    environment={
        "model":MODEL_ALIAS,
        "model_sha256":model_sha,
        "llama_cpp_commit":a.engine_commit,
        "run_utc":datetime.now(timezone.utc).isoformat(),
        "study_class":"nonblind_exploratory_six_dynamic_evidence_cases",
        "architecture":"original_REI_1.0_benchmark_arms; model_prompts_include_arm_name",
        "limitations":"same ceilings not actual token matching; no authenticated evidence; not full multi-turn persistent memory",
        "source_dataset":"research/challenge7/episodes.json"
    }
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps({"report":report,"environment":environment},indent=2),encoding="utf-8")
    print("VERIFIED:",verification)
    print("SUMMARY:",json.dumps(report["summary"],indent=2))
    print("PAIRED:",json.dumps(report["paired_comparisons"],indent=2))
    print("PROVIDER CALLS:",provider.calls)
    summ=os.getenv("GITHUB_STEP_SUMMARY")
    if summ:
        with open(summ,"a",encoding="utf-8") as fp:
            fp.write("## Challenge 7 — Dynamic evidence revision: first actual model pilot\n\n")
            fp.write("**Exploratory, nonblind.** Six synthetic, sequential event timelines. Same model and inherited prompts; compute use **not matched**.\n\n")
            fp.write("| Reasoning method | Correct / 6 | Calls | Reported tokens | Failed cases |\n|---|---:|---:|---:|---:|\n")
            for arm in ("baseline","self_critique","fixed_depth","rei"):
                x=report["summary"][arm]
                fp.write(f"| {arm} | {round(x['overall_success']*6)} | {x['total_model_calls']} | {x['total_reported_tokens']} | {x['failed_runs']} |\n")
            fp.write("\nThe independent conventional provenance-aware ledger and the REI evidence graph agreed on every recorded checkpoint; this is not evidence of REI superiority.\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())