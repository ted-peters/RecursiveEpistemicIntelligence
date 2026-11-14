"""Challenge 11D: exact planning under miscalibrated evidence likelihoods.

The investigation controller receives NOMINAL synthetic test likelihoods, but
the private environment evaluates answers under deterministic, perturbed TRUE
likelihoods. No hidden outcome samples or model calls are required: 0-1 loss
and probe count are integrated over every possible H and both possible
outcomes at each selected probe.

The true-parameter planner is a PRIVILEGED INFORMATIONAL ORACLE (upper
bound), NOT a fair conventional comparator. The nominal cost-optimal and
greedy planners both receive precisely the same misspecified probabilities
as nominal lookahead. All policies are conventional mathematical algorithms.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
import random
from typing import Any

from rei0.models import digest
from .cost_sensitivity import _cost_opt_choice
from .voi import BUDGET, Probe, InvestigationError, generate, select, update

SCHEMA = "rei.challenge11.likelihood_miscalibration.v1"
STUDY_SEEDS = (20261119,20261120,20261121,20261122,20261123)
CASE_COUNT_PER_SEED = 100
DISTORTIONS = (0.0,0.05,0.10,0.15)
PROBE_COST = 0.02
ARMS = ("nominal_recursive","nominal_greedy","nominal_cost_optimal",
        "privileged_true_cost_optimal")


def _distortion(value: float) -> float:
    if type(value) not in (float,int) or not math.isfinite(value) or not 0 <= value <= .4:
        raise InvestigationError("distortion must be finite and between 0 and 0.4")
    return float(value)


def true_likelihoods(nominal: tuple[Probe,...], case_key: str,
                     distortion: float) -> tuple[Probe,...]:
    """The evaluator alone computes perturbed test reliability.

    The output is never supplied to any nominal policy. Parameter changes
    are deterministic for replay, without using the hidden H or outcomes.
    """
    distortion = _distortion(distortion)
    if not isinstance(case_key,str) or not case_key:
        raise InvestigationError("case key required")
    if distortion == 0:
        return nominal
    result=[]
    for probe in nominal:
        key=sha256((case_key+"|"+probe.id+"|likelihood-noise-v1").encode()).digest()
        rng=random.Random(int.from_bytes(key[:8],"big"))
        s=max(.03,min(.97,probe.sensitivity+rng.uniform(-distortion,distortion)))
        f=max(.01,min(s-.01,probe.false_positive+rng.uniform(-distortion,distortion)))
        result.append(Probe(probe.id,s,f))
    return tuple(result)


def exact_true_policy_risk(*, prior: float,
                           assumed: tuple[Probe,...],
                           true: tuple[Probe,...],
                           policy: str,
                           cost: float = PROBE_COST,
                           budget: int = BUDGET) -> tuple[float,float]:
    """Return (expected true error, expected observations) for a whole policy.

    Critical: decisions and posteriors in a nominal arm use ONLY assumed
    likelihoods; actual path weights use private true likelihoods. Integrate
    every possible observation branch and the hidden binary H exactly.
    """
    if policy not in ARMS or type(budget) is not int or budget < 0:
        raise InvestigationError("invalid policy or budget")
    if type(cost) not in (float,int) or not math.isfinite(cost) or cost < 0:
        raise InvestigationError("invalid test cost")
    if type(prior) not in (float,int) or not 0 < prior < 1:
        raise InvestigationError("invalid prior")
    if ({p.id for p in assumed} != {p.id for p in true} or
        len(assumed) != len(true)):
        raise InvestigationError("nominal and true probes must have identical IDs")
    assumed_map={p.id:p for p in assumed}
    true_map={p.id:p for p in true}
    oracle=policy=="privileged_true_cost_optimal"

    def visit(m1: float, m0: float, posterior: float,
              remaining: tuple[str,...], probes_left: int) -> tuple[float,float]:
        if probes_left == 0 or not remaining:
            return (m0 if posterior >= .5 else m1,0.0)
        offered=tuple((true_map if oracle else assumed_map)[pid]
                      for pid in remaining)
        if policy=="nominal_recursive":
            choice,_=select(posterior,offered,probes_left,policy="recursive_voi")
        elif policy=="nominal_greedy":
            choice,_=select(posterior,offered,probes_left,policy="greedy_voi")
        else:
            choice=_cost_opt_choice(posterior,offered,probes_left,cost)
        if choice is None:
            return (m0 if posterior >= .5 else m1,0.0)
        nominal_probe=(true_map if oracle else assumed_map)[choice]
        true_probe=true_map[choice]
        future=tuple(pid for pid in remaining if pid!=choice)
        total_error=0.0
        # One probe is paid for once when this branch is visited.
        total_probes=m1+m0
        for positive in (True,False):
            likelihood_1=(true_probe.sensitivity if positive
                          else 1-true_probe.sensitivity)
            likelihood_0=(true_probe.false_positive if positive
                          else 1-true_probe.false_positive)
            mass1=m1*likelihood_1
            mass0=m0*likelihood_0
            # The oracle uniquely has access to the true likelihoods.
            # Every other policy updates with the NOMINAL likelihoods.
            updated=update(posterior,nominal_probe,positive)
            sub_error,sub_probes=visit(mass1,mass0,updated,future,probes_left-1)
            total_error+=sub_error
            total_probes+=sub_probes
        return (total_error,total_probes)

    return visit(float(prior),1.0-float(prior),float(prior),
                 tuple(p.id for p in assumed),budget)


def run_study(*, seeds: tuple[int,...]=STUDY_SEEDS,
              count_per_seed: int=CASE_COUNT_PER_SEED,
              distortions: tuple[float,...]=DISTORTIONS,
              cost: float=PROBE_COST) -> dict:
    if (not seeds or any(type(s) is not int for s in seeds)
        or len(seeds)!=len(set(seeds))):
        raise InvestigationError("unique integer seeds required")
    if type(count_per_seed) is not int or count_per_seed<4 or count_per_seed%4:
        raise InvestigationError("case count must be divisible by four")
    if not distortions or len(set(distortions))!=len(distortions):
        raise InvestigationError("unique distortion levels required")
    for x in distortions:
        _distortion(x)
    if type(cost) not in (float,int) or not math.isfinite(cost) or cost < 0:
        raise InvestigationError("nonnegative finite test cost required")
    # The identical nominal cases are reused at every distortion level.
    cases=[(seed,c) for seed in seeds for c in generate(seed,count_per_seed)]
    result=[]
    for distortion in distortions:
        sums={arm:[0.,0.] for arm in ARMS}
        worse_count=0
        for seed,c in cases:
            truth=true_likelihoods(c.probes,f"{seed}:{c.id}",distortion)
            for arm in ARMS:
                err,n=exact_true_policy_risk(
                    prior=c.prior,assumed=c.probes,true=truth,
                    policy=arm,cost=cost)
                sums[arm][0]+=err
                sums[arm][1]+=n
            # Detect when ignoring calibration uncertainty costs real utility.
            oracle_cost=(sum(sums["privileged_true_cost_optimal"])
                         if False else None)  # never compare accumulated sums
            del oracle_cost
            nominal_cost = exact_true_policy_risk(
                prior=c.prior, assumed=c.probes, true=truth,
                policy="nominal_cost_optimal",cost=cost)
            privileged_cost = exact_true_policy_risk(
                prior=c.prior, assumed=c.probes, true=truth,
                policy="privileged_true_cost_optimal",cost=cost)
            if (nominal_cost[0]+cost*nominal_cost[1]
                > privileged_cost[0]+cost*privileged_cost[1]+1e-10):
                worse_count+=1
        arms={}
        for arm,(error,probes) in sums.items():
            avg_error=error/len(cases)
            avg_probes=probes/len(cases)
            arms[arm]={
                "mean_true_expected_error":avg_error,
                "mean_true_expected_probes":avg_probes,
                "mean_true_total_expected_cost":avg_error+cost*avg_probes,
            }
        privileged=arms["privileged_true_cost_optimal"]["mean_true_total_expected_cost"]
        for arm in ARMS:
            if arms[arm]["mean_true_total_expected_cost"]<privileged-1e-10:
                raise InvestigationError("privileged oracle upper bound violated")
        result.append({
            "maximum_absolute_likelihood_perturbation":distortion,
            "cases":len(cases),
            "cost_per_probe":cost,
            "cases_where_nominal_cost_policy_has_strict_regret_vs_privileged_oracle":
                worse_count,
            "policies":arms,
        })
    payload={
        "schema":SCHEMA,
        "study_type":"synthetic_exact_expected_loss_with_mispecified_likelihoods",
        "seeds":list(seeds),
        "cases_per_seed":count_per_seed,
        "total_nominal_scenarios":len(cases),
        "likelihood_perturbations":list(distortions),
        "per_measurement_cost":cost,
        "nominal_dataset_digest":digest([
            {"seed":seed,"id":c.id,"prior":c.prior,
             "probes":[p.to_dict() for p in c.probes]}
            for seed,c in cases]),
        "results":result,
        "warnings":[
            "All methods are conventional mathematical policies, not live language models.",
            "The privileged true-likelihood planner is an unfair INFORMATIONAL UPPER BOUND only.",
            "Nominal controllers share identical miscalibrated public test parameters.",
            "Expected errors and probe usage integrate all possible observations; no Monte Carlo truth sampling.",
            "Synthetic independent binary tests with deterministic bounded perturbations, not empirically calibrated evidence.",
            "The generator and perturbation seeds are public development data, not a blind holdout.",
        ],
    }
    return {**payload,"report_sha256":digest(payload)}


def verify_study(report: dict) -> dict:
    if not isinstance(report,dict) or report.get("schema")!=SCHEMA:
        raise InvestigationError("wrong miscalibration study schema")
    if digest({k:v for k,v in report.items() if k!="report_sha256"})!=report.get("report_sha256"):
        raise InvestigationError("miscalibration study checksum mismatch")
    expected=run_study(seeds=tuple(report["seeds"]),
                       count_per_seed=report["cases_per_seed"],
                       distortions=tuple(report["likelihood_perturbations"]),
                       cost=report["per_measurement_cost"])
    if report!=expected:
        raise InvestigationError("mismatched independently recomputed miscalibration study")
    return {"valid":True,"nominal_scenarios":report["total_nominal_scenarios"],
            "perturbation_levels":len(report["results"]),
            "report_sha256":report["report_sha256"],
            "warning":"Exact synthetic mathematical replay, not live inference"}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path)
    p.add_argument("--verify-only",action="store_true")
    args=p.parse_args(argv)
    if args.verify_only:
        if not args.output:
            p.error("--verify-only requires --output")
        print("REPLAY:",json.dumps(verify_study(json.loads(args.output.read_text())),indent=2))
        return 0
    result=run_study()
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print("LIKELIHOOD MISCALIBRATION:",json.dumps(result["results"],indent=2))
    print("WARNING: PRIVILEGED ORACLE IS NOT A FAIR CONVENTIONAL COMPARATOR.")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
