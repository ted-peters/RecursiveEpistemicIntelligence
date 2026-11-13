"""Challenge 11 optional live paired investigation-selection comparison.

Primary *algorithmic* benchmark is exact expected Bayes error against the
strong conventional dynamic-programming optimum and myopic VOI control.

This optional real-model pilot compares REI's deterministic recursive probe
planner against a Qwen3-based self-critique *selection* policy that sees
exactly the same public probabilities and numeric utility table. Both
final H decisions are made by the same Bayes posterior threshold, not by
LLM text. This tests choice quality, not broad LLM answer intelligence.

Never claim resource matching: recursive planning uses zero model calls,
whereas Qwen self-critique uses up to four model calls per two-probe case.
"""
from __future__ import annotations

from dataclasses import asdict
import argparse
import json
import math
import os
from pathlib import Path
import time
from typing import Any

from rei0.benchmark import BenchmarkError
from rei0.models import digest
from research.challenge8.structured_provider import EXPECTED_MODEL_SHA256, MODEL_ALIAS, verify_model
from .model_provider import QwenChoiceProvider, ModelChoiceError
from .simulate import PrivateTestEnvironment, run_case
from .voi import (
    BUDGET, SEED, Probe, InvestigationError, choice_table, generate,
    optimal_risk, prob_positive, public_digest, select, test_value, update,
)

SCHEMA = "rei.challenge11.public_live_development_pilot.v1"
ARMS = ("recursive_voi", "tool_self_critique")
MAX_CALLS = 4
MAX_REPORTED_TOKENS = 3200
MAX_SECONDS = 220
OUTPUT_TOKENS = 160


class ScriptedChoiceProvider:
    """Offline fake response fixture, not model inference."""
    kind = "scripted-non-empirical-fixture"
    fingerprint = "c11-scripted-choice-fixture-v1"

    def __init__(self):
        self.attempts: list[dict] = []

    def respond(self, *, case_id: str, stage: str, public: dict,
                max_output_tokens: int, timeout: float) -> tuple[str, int]:
        if stage not in ("draft_choice","revised_choice"):
            raise ModelChoiceError("unsupported simulated stage")
        rows = public["candidate_values"]
        key = ("immediate_expected_error" if stage=="draft_choice" else
               "exact_remaining_budget_expected_error")
        answer = min(rows, key=lambda x:(x[key],x["id"]))["id"] if rows else "STOP"
        if rows and min(x[key] for x in rows) >= min(
            public["current_probability_H1"],1-public["current_probability_H1"])-1e-12:
            answer="STOP"
        self.attempts.append({
            "case_id":case_id,"stage":stage,
            "status":"parsed","reported_tokens_even_if_failed":20,
            "finish_reason":"stop",
        })
        return answer,20


def _arm_run(case, arm: str, provider) -> dict:
    if arm not in ARMS:
        raise InvestigationError("unknown trial arm")
    if arm == "recursive_voi":
        data = run_case(case,"recursive_voi").to_dict()
        return {
            "case_id":case.id, "arm":arm, "error":None,
            "model_calls":0, "meter_reported_tokens":0,
            "first_selection_regret_with_optimal_continuation":0.0,
            "decision":data,
            "trace":[],
            "elapsed_seconds":0.0,
        }
    env=PrivateTestEnvironment(case)
    began=time.monotonic()
    used=0
    calls=0
    error=None
    trace=[]
    first_choice_regret=None
    for ordinal in range(BUDGET):
        if calls+2>MAX_CALLS or used>=MAX_REPORTED_TOKENS:
            error="model call/token budget exhausted before choice"
            break
        remaining=BUDGET-len(env.chosen)
        public=env.public_view()
        public["candidate_values"]=choice_table(env.posterior,env.available,remaining)
        # Shared numeric tool: the recursive planner and conventional model
        # both have these exactly computed candidate utilities.
        timeleft=MAX_SECONDS-(time.monotonic()-began)
        if timeleft<=0:
            error="model policy elapsed-time budget exhausted"
            break
        try:
            calls+=1
            draft,tokens=provider.respond(
                case_id=case.id,stage="draft_choice",public=public,
                max_output_tokens=OUTPUT_TOKENS,timeout=min(100,timeleft))
            used+=tokens
            public["provisional_choice"]=draft
            timeleft=MAX_SECONDS-(time.monotonic()-began)
            if timeleft<=0 or used>=MAX_REPORTED_TOKENS:
                raise ModelChoiceError("budget exhausted before revised decision")
            calls+=1
            final,tokens=provider.respond(
                case_id=case.id,stage="revised_choice",public=public,
                max_output_tokens=OUTPUT_TOKENS,timeout=min(100,timeleft))
            used+=tokens
            choices={p.id for p in env.available}
            if final != "STOP" and final not in choices:
                raise ModelChoiceError("model selected unavailable probe")
            if ordinal==0:
                best=optimal_risk(case.prior,case.probes,BUDGET)
                if final=="STOP":
                    first_choice_regret=min(case.prior,1-case.prior)-best
                else:
                    p=next(x for x in case.probes if x.id==final)
                    first_choice_regret=test_value(
                        case.prior,p,case.probes,BUDGET-1,lookahead=True)-best
                first_choice_regret=max(0,first_choice_regret)
                if first_choice_regret<1e-12:
                    first_choice_regret=0.0
            trace.append({
                "step":ordinal,"draft_choice":draft,"revised_choice":final,
                "calls":calls,"meter_reported_tokens":used,
                "public_view_sha256":digest(public),
            })
            if used>MAX_REPORTED_TOKENS:
                raise ModelChoiceError("model exceeded total reported token ceiling")
            if final=="STOP":
                break
            env.perform(final)
        except (ModelChoiceError,InvestigationError,ValueError,TypeError,OSError) as exc:
            error=type(exc).__name__+": "+str(exc)[:150]
            break
    # We do NOT claim a policy's expected risk without knowing the policy's
    # choices under ALL counterfactual observations; only observed world
    # accuracy/Brier and a first-choice optimal-continuation regret are known.
    decision=env.conclude("tool_self_critique",expected_risk=None).to_dict()
    return {
        "case_id":case.id, "arm":arm,"error":error,
        "model_calls":calls,"meter_reported_tokens":used,
        "first_selection_regret_with_optimal_continuation":first_choice_regret,
        "decision":decision,"trace":trace,
        "elapsed_seconds":round(time.monotonic()-began,3),
    }


def _summarize(rows: list[dict], cases) -> dict:
    summary={}
    for arm in ARMS:
        relevant=[r for r in rows if r["arm"]==arm]
        if len(relevant)!=len(cases):
            raise InvestigationError("missing trial outcome")
        valid=[r for r in relevant if r["error"] is None]
        summary[arm]={
            "cases":len(relevant),
            "correct":sum(r["decision"]["correct"] for r in valid),
            "failed":len(relevant)-len(valid),
            "realized_accuracy_with_failures_counting_as_wrong":
                sum(r["decision"]["correct"] for r in valid)/len(relevant),
            "mean_brier_valid_only":(
                sum(r["decision"]["brier"] for r in valid)/len(valid) if valid else None),
            "probes_used":sum(r["decision"]["probe_count"] for r in relevant),
            "model_calls":sum(r["model_calls"] for r in relevant),
            "meter_reported_tokens":sum(r["meter_reported_tokens"] for r in relevant),
            "first_choice_optimal_continuation_regret":(
                sum(r["first_selection_regret_with_optimal_continuation"]
                    for r in relevant
                    if r["first_selection_regret_with_optimal_continuation"] is not None)/
                len([r for r in relevant if
                     r["first_selection_regret_with_optimal_continuation"] is not None])
                if any(r["first_selection_regret_with_optimal_continuation"] is not None
                       for r in relevant) else None),
        }
    return {
        "per_arm":summary,
        "paired_accuracy_difference_rei_minus_model":(
            summary["recursive_voi"]["correct"]-
            summary["tool_self_critique"]["correct"])/len(cases),
        "actual_computation_matched":False,
        "same_numeric_bayesian_tools_available":True,
        "strong_conventional_exact_optimal_matches_recursive":True,
    }


def run(provider, *, seed: int=SEED, count: int=4) -> dict:
    if not hasattr(provider,"respond") or not hasattr(provider,"kind"):
        raise InvestigationError("choice provider must declare kind and respond")
    cases=generate(seed,count)
    outcomes=[]
    for c in cases:
        for arm in ARMS:
            outcomes.append(_arm_run(c,arm,provider))
    usage={}
    for stage in ("draft_choice","revised_choice"):
        a=[x for x in provider.attempts if x["stage"]==stage]
        known=[x["reported_tokens_even_if_failed"] for x in a if
               x.get("reported_tokens_even_if_failed") is not None]
        usage[stage]={
            "attempts":len(a),"reported_tokens_even_if_failed":sum(known),
            "unknown_usage_calls":len(a)-len(known),
            "failed_requests":sum(x["status"]=="failed" for x in a),
        }
    body={
        "schema":SCHEMA,"mode":provider.kind,
        "model_fingerprint":getattr(provider,"fingerprint",None),
        "seed":seed,"cases":count,
        "public_dataset_digest":public_digest(cases),
        "policy_budget":BUDGET,
        "model_limit_per_case":{
            "max_calls":MAX_CALLS,
            "max_reported_tokens":MAX_REPORTED_TOKENS,
            "max_seconds":MAX_SECONDS,
            "max_output_tokens_per_call":OUTPUT_TOKENS,
        },
        "outcomes":outcomes,
        "summary":_summarize(outcomes,cases),
        "provider_attempts":provider.attempts,
        "attempt_usage_by_stage":usage,
        "warnings":[
            "Public synthetic development data, NOT a blind independent holdout.",
            "Exact recursive Bayesian planning is a conventional dynamic program.",
            "Both policies can read exactly the same numeric utilities and observations.",
            "The model-based comparator uses model tokens; mathematical planner uses none. Not compute matched.",
            "The model policy's full counterfactual expected loss cannot be calculated from a single observed run.",
            "A signed measurement attests synthetic review admission, not objective truth.",
            "Hash alone is not a cryptographic model-run attestation.",
        ],
    }
    return {**body,"report_sha256":digest(body)}


def verify_report(report: dict) -> dict:
    if not isinstance(report,dict) or report.get("schema")!=SCHEMA:
        raise InvestigationError("wrong Challenge 11 report schema")
    content={k:v for k,v in report.items() if k!="report_sha256"}
    if digest(content)!=report.get("report_sha256"):
        raise InvestigationError("report checksum does not match")
    cases=generate(report["seed"],report["cases"])
    if report["public_dataset_digest"]!=public_digest(cases):
        raise InvestigationError("dataset reference differs")
    rows=report["outcomes"]
    expected={(c.id,a) for c in cases for a in ARMS}
    if (len(rows)!=len(expected) or
        {(r["case_id"],r["arm"]) for r in rows}!=expected):
        raise InvestigationError("missing, repeated or invalid case/arm pair")
    if _summarize(rows,cases)!=report["summary"]:
        raise InvestigationError("paired grade differs from recorded answers")
    # Independence of the score: replay private potential outcomes for every
    # revealed model choice, rather than trusting an 'accuracy' boolean.
    by_id={c.id:c for c in cases}
    for row in rows:
        c=by_id[row["case_id"]]
        if row["arm"]=="recursive_voi":
            expected_data=run_case(c,"recursive_voi").to_dict()
            for field in ("chosen","final_p","prediction","correct","brier",
                          "probe_count","exact_expected_bayes_error"):
                if row["decision"][field]!=expected_data[field]:
                    raise InvestigationError("recursive arm replay differs")
        env=PrivateTestEnvironment(c)
        for probe_id in row["decision"]["chosen"]:
            env.perform(probe_id)
        predicted=env.posterior>=.5
        if row["decision"]["correct"]!=(predicted==c.truth):
            raise InvestigationError("private gold truth grade differs")
        if not math.isclose(row["decision"]["final_p"],env.posterior,abs_tol=1e-10):
            raise InvestigationError("posterior differs from observed probes")
        if not math.isclose(row["decision"]["brier"],(env.posterior-int(c.truth))**2,abs_tol=1e-10):
            raise InvestigationError("Brier score differs from independent replay")
        recorded=[x["result"] for x in row["decision"]["observations"]]
        if recorded != [x["result"] for x in env.observations]:
            raise InvestigationError("model path reported false evidence")
        if row["model_calls"]>MAX_CALLS:
            raise InvestigationError("model calls exceeded policy budget")
    return {"valid":True,"cases":len(cases),"paired_outcomes":len(rows),
            "report_sha256":report["report_sha256"],
            "warning":"Replay consistency, not authenticated model inference attestation"}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode",choices=["fixture","live"],default="fixture")
    p.add_argument("--count",type=int,choices=[4,8,12],default=4)
    p.add_argument("--seed",type=int,default=SEED)
    p.add_argument("--model-file",type=Path)
    p.add_argument("--engine-commit")
    p.add_argument("--output",type=Path,default=Path("challenge11-results/pilot.json"))
    p.add_argument("--verify-only",action="store_true")
    args=p.parse_args(argv)
    if args.verify_only:
        stored=json.loads(args.output.read_text())
        print("INDEPENDENT REGRADE:",json.dumps(verify_report(stored)))
        return 0
    if args.mode=="live":
        if not args.model_file or not args.engine_commit:
            p.error("live mode requires pinned --model-file and --engine-commit")
        provider=QwenChoiceProvider(verify_model(args.model_file),args.engine_commit)
    else:
        provider=ScriptedChoiceProvider()
    result=run(provider,seed=args.seed,count=args.count)
    verified=verify_report(result)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print("VERIFIED:",json.dumps(verified))
    print("SUMMARY:",json.dumps(result["summary"],indent=2))
    print("PROVIDER ATTEMPT USAGE:",json.dumps(result["attempt_usage_by_stage"],indent=2))
    print("WARNING:",result["warnings"][0])
    if args.mode=="fixture":
        print("WARNING: SCRIPTED RESPONSE FIXTURE; NO MODEL INFERENCE EXECUTED.")
    step_summary=os.getenv("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary,"a",encoding="utf-8") as out:
            out.write("## Challenge 11 — Probe-choice pilot\n\n")
            out.write(f"Mode: **{args.mode}**. Public development cases: **{args.count}**. Not compute matched.\n\n")
            out.write("| Method | Correct | Failed | Model calls | Tokens (successful turns) |\n|---|---:|---:|---:|---:|\n")
            for arm in ARMS:
                item=result["summary"]["per_arm"][arm]
                out.write(f"| {arm} | {item['correct']}/{item['cases']} | {item['failed']} | {item['model_calls']} | {item['meter_reported_tokens']} |\n")
            out.write("\nUse provider attempt-usage fields for failed/unknown tokens. Exact Bayesian optimum is conventional math, not REI superiority.\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
