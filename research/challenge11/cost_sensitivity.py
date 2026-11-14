"""Challenge 11C: exact, cost-aware value-of-information stress test.

A purely mathematical counterfactual using known synthetic likelihoods.
This does NOT run Qwen or establish REI-specific advantage: recursive
lookahead and cost-aware dynamic programming are conventional Bayes decision
theory. The objective is expected classification error + cost * probes used.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import argparse
import json
import math
from pathlib import Path
from typing import Any

from rei0.models import digest
from .voi import (
    BUDGET, Probe, SEED, InvestigationError, bayes_risk,
    generate, optimal_risk, prob_positive, select, update,
)

SCHEMA = "rei.challenge11.cost_frontier.v1"
COSTS = (0.0,0.01,0.02,0.05)
SEEDS = (20261114,20261115,20261116,20261117,20261118)


def _validate_cost(cost: float):
    if type(cost) not in (float,int) or not math.isfinite(cost) or cost < 0:
        raise InvestigationError("test cost must be a finite nonnegative number")


@lru_cache(maxsize=100000)
def optimal_with_cost(p: float, probes: tuple[Probe,...], budget: int,
                      cost: float) -> float:
    """Standard conventional Bellman optimum including expected probe cost."""
    _validate_cost(cost)
    if type(budget) is not int or budget < 0:
        raise InvestigationError("invalid investigation budget")
    best = bayes_risk(p)
    if not budget or not probes:
        return best
    for probe in probes:
        rest = tuple(x for x in probes if x.id != probe.id)
        q = prob_positive(p,probe)
        trial = (
            cost + q*optimal_with_cost(update(p,probe,True),rest,budget-1,cost)
            + (1-q)*optimal_with_cost(update(p,probe,False),rest,budget-1,cost)
        )
        best = min(best,trial)
    return best


def _cost_opt_choice(p: float, probes: tuple[Probe,...],
                     budget: int, cost: float) -> str | None:
    _validate_cost(cost)
    stop=bayes_risk(p)
    if not budget or not probes:
        return None
    scored=[]
    for probe in probes:
        rest=tuple(x for x in probes if x.id!=probe.id)
        q=prob_positive(p,probe)
        v=cost+q*optimal_with_cost(update(p,probe,True),rest,budget-1,cost) + (
            1-q)*optimal_with_cost(update(p,probe,False),rest,budget-1,cost)
        scored.append((v,probe.id))
    v,winner=min(scored)
    return winner if v < stop-1e-12 else None


def expected_policy_metrics(p: float, probes: tuple[Probe,...], budget: int,
                            *, policy: str, cost: float = 0.0) -> tuple[float,float]:
    """Return (expected 0-1 error, expected tests); no sampled hidden outcomes."""
    _validate_cost(cost)
    if policy == "cost_optimal":
        choice = _cost_opt_choice(p,probes,budget,cost)
    elif policy in ("recursive_voi","greedy_voi"):
        choice,_ = select(p,probes,budget,policy=policy)
    elif policy == "stop":
        choice=None
    else:
        raise InvestigationError("unknown comparison policy")
    if choice is None:
        return bayes_risk(p),0.0
    probe=next(x for x in probes if x.id==choice)
    remaining=tuple(x for x in probes if x.id!=choice)
    q=prob_positive(p,probe)
    e1,n1=expected_policy_metrics(update(p,probe,True),remaining,budget-1,
                                  policy=policy,cost=cost)
    e0,n0=expected_policy_metrics(update(p,probe,False),remaining,budget-1,
                                  policy=policy,cost=cost)
    return (q*e1+(1-q)*e0,1.0+q*n1+(1-q)*n0)


def run_sensitivity(*, seeds: tuple[int,...] = SEEDS,
                    count_per_seed: int = 200,
                    costs: tuple[float,...] = COSTS) -> dict:
    if not seeds or len(set(seeds))!=len(seeds):
        raise InvestigationError("unique study seeds required")
    if not costs or len(set(costs))!=len(costs):
        raise InvestigationError("unique non-repeated cost assumptions required")
    for cost in costs:
        _validate_cost(cost)
    cases=[c for seed in seeds for c in generate(seed=seed,count=count_per_seed)]
    results=[]
    for cost in costs:
        sums={key:[0.0,0.0] for key in ("stop","greedy_voi","recursive_voi","cost_optimal")}
        changed=0
        for case in cases:
            for arm in sums:
                err,measurements=expected_policy_metrics(
                    case.prior,case.probes,BUDGET,policy=arm,cost=cost)
                sums[arm][0]+=err
                sums[arm][1]+=measurements
                if arm=="cost_optimal":
                    if _cost_opt_choice(case.prior,case.probes,BUDGET,cost) != (
                        select(case.prior,case.probes,BUDGET,policy="recursive_voi")[0]):
                        changed+=1
                    optimum=optimal_with_cost(case.prior,case.probes,BUDGET,cost)
                    if abs(err+cost*measurements-optimum)>1e-10:
                        raise InvestigationError("cost-optimal policy does not match independent Bellman value")
        records={}
        for arm,(sumerr,sumn) in sums.items():
            meanerr=sumerr/len(cases)
            meanprobes=sumn/len(cases)
            records[arm]={
                "mean_exact_expected_error":meanerr,
                "mean_expected_probes":meanprobes,
                "mean_total_expected_cost":meanerr+cost*meanprobes,
            }
        if records["cost_optimal"]["mean_total_expected_cost"] > min(
            records[policy]["mean_total_expected_cost"]
            for policy in ("greedy_voi","recursive_voi","stop"))+1e-10:
            raise InvestigationError("cost-optimal baseline failed dominance requirement")
        results.append({
            "cost_per_observation_in_wrong_decision_units":cost,
            "sampled_synthetic_cases":len(cases),
            "cost_optimal_first_decisions_different_from_risk_only_lookahead":changed,
            "strategies":records,
        })
    public={
        "schema":SCHEMA,
        "study_type":"public_synthetic_exact_probability_math_not_live_ai",
        "seeds":list(seeds),
        "cases_per_seed":count_per_seed,
        "case_count":len(cases),
        "public_inputs_digest":digest([{
            "id":f"{idx:03d}:{c.id}",
            "prior":c.prior,
            "probes":[p.to_dict() for p in c.probes],
        } for idx,c in enumerate(cases)]),
        "cost_results":results,
        "warnings":[
            "Probe cost is hypothetical; exact Bayesian formulas assume known independent test likelihoods.",
            "No LLM inference, real-world source validation or novel AI advantage is demonstrated.",
            "The exact cost-aware dynamic planner is a strong conventional baseline, not unique to REI.",
            "Expected risks and expected test counts are analytic, not a sample of realized final decisions.",
            "The public data generator and cost grid were declared in source before CI execution.",
        ],
    }
    return {**public,"report_sha256":digest(public)}


def verify_sensitivity(report: dict) -> dict:
    if not isinstance(report,dict) or report.get("schema")!=SCHEMA:
        raise InvestigationError("invalid cost-frontier report")
    if digest({k:v for k,v in report.items() if k!="report_sha256"}) != report.get("report_sha256"):
        raise InvestigationError("cost report checksum mismatch")
    expected=run_sensitivity(seeds=tuple(report["seeds"]),
                              count_per_seed=report["cases_per_seed"],
                              costs=tuple(x["cost_per_observation_in_wrong_decision_units"]
                                          for x in report["cost_results"]))
    if report!=expected:
        raise InvestigationError("independently recomputed cost frontier does not match")
    return {"valid":True,"cases":report["case_count"],
            "cost_levels":len(report["cost_results"]),
            "sha256":report["report_sha256"],
            "warning":"Exact synthetic expected-risk replay, no model test"}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path)
    p.add_argument("--verify-only",action="store_true")
    args=p.parse_args(argv)
    if args.verify_only:
        if not args.output:
            p.error("--verify-only requires --output")
        print(json.dumps(verify_sensitivity(json.loads(args.output.read_text())),indent=2))
        return 0
    result=run_sensitivity()
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print("COST FRONTIER:",json.dumps(result["cost_results"],indent=2))
    print("WARNING: Known-likelihood mathematical planning, no language model used")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
