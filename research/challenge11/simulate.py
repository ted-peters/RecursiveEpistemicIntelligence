"""Challenge 11: signed observation delivery and paired decision-policy audit.

The private environment, not any planner or model, holds the latent H and
pre-drawn potential test outcomes. Every revealed observation is admitted
through the existing signed EvidenceLedger before the posterior is updated.
A receipt is provenance of the synthetic review decision, not proof that
the real-world proposition is true.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, asdict
from hashlib import sha256
import json
import math
from typing import Any

from rei0.evidence import EvidenceLedger
from rei0.graph import EpistemicGraph
from rei0.models import (
    EdgeKind, Node, NodeKind, Provenance, SourceKind, Validation, digest,
)
from rei0.review import (
    Ed25519ReviewIssuer, Ed25519TrustedReviewer, VerificationBoundary,
)

from .voi import (
    BUDGET, InvestigationError, Probe, Scenario, SEED,
    bayes_risk, choice_table, generate, optimal_risk, policy_risk,
    public_digest, select, update,
)

STAMP = "2026-11-12T00:00:00Z"
SCHEMA = "rei.challenge11.signed_active_investigation.v1"
ARMS = ("recursive_voi", "greedy_voi")


@dataclass(frozen=True)
class Outcome:
    case_id: str
    policy: str
    chosen: tuple[str, ...]
    observations: tuple[dict[str, Any], ...]
    final_p: float
    prediction: bool
    correct: bool
    brier: float
    probe_count: int
    signed_receipts: int
    final_signed_evidence_state: str
    evidence_audit_head: str
    graph_audit_head: str
    exact_expected_bayes_error: float
    optimal_expected_bayes_error: float
    regret_over_optimal: float

    def to_dict(self) -> dict:
        return {
            **asdict(self),
            "chosen": list(self.chosen),
            "observations": [dict(x) for x in self.observations],
        }


class PrivateTestEnvironment:
    """Owns private world, synthetic signing authority and ledger.

    User/model policy receives public_view() and a post-review observation,
    never this object or its signer. Separate policy arms are reset using the
    same pre-drawn potential outcomes for strict paired intervention comparison.
    """

    def __init__(self, scenario: Scenario):
        self.__case = scenario
        self.__draws = dict(scenario.outcomes)
        self.__signer = Ed25519ReviewIssuer.generate("c11-ephemeral","trusted-fixture-review")
        trust = VerificationBoundary({
            "c11-ephemeral": Ed25519TrustedReviewer(
                "trusted-fixture-review",self.__signer.public_key_bytes())
        })
        graph = EpistemicGraph("challenge11-hidden-test-observations",
                                max_nodes=25,max_edges=25,clock=lambda: STAMP)
        graph.add_node(Node("H1",NodeKind.CLAIM,
                            "Synthetic hypothesis H1 is the hidden true state",
                            Provenance("problem-author",SourceKind.HUMAN,"task",
                                       "fixture://hidden-hypothesis", STAMP),STAMP))
        self.ledger = EvidenceLedger(graph, trust, clock=lambda: STAMP)
        self.posterior = scenario.prior
        self.available = scenario.probes
        self.observations: list[dict] = []
        self.chosen: list[str] = []

    def public_view(self) -> dict[str, Any]:
        return self.__case.public(
            posterior=self.posterior,
            remaining=self.available,
            observations=tuple(self.observations),
        )

    def perform(self, probe_id: str) -> dict[str, Any]:
        """Only a current test with remaining budget is allowed; sign and verify."""
        if len(self.chosen) >= BUDGET:
            raise InvestigationError("investigation budget exhausted")
        current = next((p for p in self.available if p.id == probe_id),None)
        if current is None:
            raise InvestigationError("unavailable or repeated investigation choice")
        result = self.__draws[probe_id]
        submission = "signed-measurement:"+probe_id
        self.ledger.submit(
            submission_id=submission,evidence_id="measurement:"+probe_id,
            claim_id="H1",text=("POSITIVE" if result else "NEGATIVE")+" result for "+probe_id,
            artifact_bytes=json.dumps({
                "case_id":self.__case.id,
                "probe_id":probe_id,"positive":result,
            },sort_keys=True).encode(),
            provenance=Provenance(
                "fixture-measurement:"+probe_id,SourceKind.EXTERNAL,
                "independent-probe:"+probe_id,"synthetic://challenge11/"+probe_id,STAMP),
            polarity=EdgeKind.SUPPORTS if result else EdgeKind.ATTACKS,
        )
        prior_receipts=self.ledger.review_receipts
        signed=self.__signer.issue(
            submission_id=submission,subject_digest=self.ledger.subject_digest(submission),
            decision=Validation.VERIFIED,
            reason="Fixture measurement was admitted; does not assert real-world truth",
            issued_at=STAMP,decision_index=1,prior_signature="0"*64,
        )
        self.ledger.accept(signed)
        if len(self.ledger.review_receipts) != len(prior_receipts)+1:
            raise InvestigationError("signed review was not accepted")
        state=self.ledger.assess("H1")
        if (("measurement:"+probe_id) not in (
            state.support_evidence if result else state.attack_evidence)):
            raise InvestigationError("signed measurement missing from trusted state")
        self.posterior=update(self.posterior,current,result)
        self.available=tuple(x for x in self.available if x.id != probe_id)
        self.chosen.append(probe_id)
        public={
            "probe_id":probe_id,
            "result":"POSITIVE" if result else "NEGATIVE",
            "signed_review_status":"VERIFIED",
            "signed_review_ledger_head":self.ledger.audit_head,
        }
        self.observations.append(public)
        return dict(public)

    def conclude(self, policy: str, expected_risk: float) -> Outcome:
        """A posterior threshold is a Bayes-optimal final action for 0-1 loss."""
        self.ledger.assess("H1")
        predicted = self.posterior >= 0.5
        truth = self.__case.truth  # used only by trusted evaluator
        optimum=optimal_risk(self.__case.prior,self.__case.probes,BUDGET)
        regret=max(0,expected_risk-optimum)
        return Outcome(
            case_id=self.__case.id,policy=policy,
            chosen=tuple(self.chosen),observations=tuple(self.observations),
            final_p=self.posterior,prediction=predicted,
            correct=predicted == truth,brier=(self.posterior-int(truth))**2,
            probe_count=len(self.chosen),
            signed_receipts=len(self.ledger.review_receipts),
            final_signed_evidence_state=self.ledger.assess("H1").state.value,
            evidence_audit_head=self.ledger.audit_head,
            graph_audit_head=self.ledger.graph.audit_head,
            exact_expected_bayes_error=expected_risk,
            optimal_expected_bayes_error=optimum,
            regret_over_optimal=regret,
        )


def run_case(scenario: Scenario, policy: str) -> Outcome:
    """A policy cannot inspect the private truth or potential observations."""
    if policy not in ARMS:
        raise InvestigationError("unsupported policy")
    env=PrivateTestEnvironment(scenario)
    expected=policy_risk(scenario.prior,scenario.probes,BUDGET,policy=policy)
    for _ in range(BUDGET):
        selection,_ = select(env.posterior,env.available,
                             BUDGET-len(env.chosen),policy=policy)
        if selection is None:
            break
        env.perform(selection)
    return env.conclude(policy,expected)


def run_audit(seed: int = SEED, count: int = 24) -> dict:
    """Pure offline paired benchmark, plus exact counterfactual Bayes risk."""
    cases=generate(seed,count)
    results=[run_case(c,arm).to_dict() for c in cases for arm in ARMS]
    summary={}
    for arm in ARMS:
        rows=[x for x in results if x["policy"]==arm]
        summary[arm]={
            "cases":len(rows),
            "realized_correct":sum(r["correct"] for r in rows),
            "realized_accuracy":sum(r["correct"] for r in rows)/len(rows),
            "mean_brier":sum(r["brier"] for r in rows)/len(rows),
            "mean_exact_expected_bayes_error":sum(
                r["exact_expected_bayes_error"] for r in rows)/len(rows),
            "mean_regret_vs_optimal":sum(r["regret_over_optimal"] for r in rows)/len(rows),
            "measurements":sum(r["probe_count"] for r in rows),
            "verified_fixture_receipts":sum(r["signed_receipts"] for r in rows),
            "model_calls":0,
        }
    differences=[
        r["regret_over_optimal"] for r in results if r["policy"]=="greedy_voi"
    ]
    payload={
        "schema":SCHEMA,
        "dataset":"public_synthetic_development_not_hidden_evaluation",
        "seed":seed,"count":count,
        "public_dataset_digest":public_digest(cases),
        "case_protocol":"two_budget_same_draws_same_probe_pool_independent_signed_fixture",
        "summary":summary,
        "number_of_cases_where_lookahead_beats_greedy_in_expected_risk":sum(
            x>1e-9 for x in differences),
        "outcomes":results,
        "warnings":[
            "Exact Bayesian dynamic programming is conventional math, not trained REI or AI superiority.",
            "Only model-observed facts are signed by ephemeral synthetic reviewers; approval is not objective truth.",
            "Realized case accuracy has sampling noise; exact expected risk is a less noisy policy comparison.",
            "The public development generator is not blinded or independently held out.",
            "Policies have the same two-probe budget; the exact optimizer is a strong conventional baseline and ties lookahead by construction.",
        ],
    }
    return {**payload,"report_sha256":digest(payload)}


def verify_audit(report: dict) -> dict:
    """Independent re-run, same cases and private draws; detect tampered grading."""
    if not isinstance(report,dict) or "report_sha256" not in report:
        raise InvestigationError("report missing checksum")
    original_digest=report["report_sha256"]
    if digest({k:v for k,v in report.items() if k!="report_sha256"})!=original_digest:
        raise InvestigationError("report checksum invalid")
    required=run_audit(report["seed"],report["count"])
    if report != required:
        raise InvestigationError("report does not reproduce under independent replay")
    return {"valid":True,"cases":report["count"],"outcomes":len(report["outcomes"]),
            "sha256":original_digest,
            "warning":"Replayed synthetic fixture, not authenticated model-run attestation"}


def main(argv=None):
    import argparse
    from pathlib import Path
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--count",type=int,default=24)
    p.add_argument("--seed",type=int,default=SEED)
    p.add_argument("--output",type=Path)
    p.add_argument("--verify-only",action="store_true")
    args=p.parse_args(argv)
    if args.verify_only:
        if not args.output:
            p.error("--verify-only requires --output")
        stored=json.loads(args.output.read_text())
        print(json.dumps(verify_audit(stored),sort_keys=True))
        return 0
    result=run_audit(args.seed,args.count)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print("SUMMARY:",json.dumps(result["summary"],indent=2))
    print("EXPECTED_RISK_IMPROVEMENT_CASES:",
          result["number_of_cases_where_lookahead_beats_greedy_in_expected_risk"])
    print("CHECKSUM:",result["report_sha256"])
    print("WARNING: OFFLINE probability simulation, NO LIVE AI TEST.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
