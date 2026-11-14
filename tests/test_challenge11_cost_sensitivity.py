"""Challenge 11C: cost-sensitive exact Bayesian planning, no AI inference."""
from __future__ import annotations

import copy
import math
import unittest

from rei0.models import digest
from research.challenge11.cost_sensitivity import (
    expected_policy_metrics, optimal_with_cost, run_sensitivity,
    verify_sensitivity, InvestigationError,
)
from research.challenge11.voi import generate, optimal_risk, bayes_risk


class CostAwareInvestigationTests(unittest.TestCase):
    def test_zero_cost_exact_planner_matches_original_optimal_risk(self):
        for c in generate(seed=20261114,count=8):
            err,n=expected_policy_metrics(
                c.prior,c.probes,2,policy="cost_optimal",cost=0)
            self.assertAlmostEqual(err,optimal_risk(c.prior,c.probes,2),places=11)
            self.assertAlmostEqual(
                err,optimal_with_cost(c.prior,c.probes,2,0),places=11)
            self.assertLessEqual(n,2)

    def test_high_investigation_cost_causes_stop(self):
        for c in generate(seed=20261114,count=8):
            err,n=expected_policy_metrics(
                c.prior,c.probes,2,policy="cost_optimal",cost=1)
            self.assertEqual(n,0)
            self.assertEqual(err,bayes_risk(c.prior))
            self.assertEqual(
                optimal_with_cost(c.prior,c.probes,2,1),
                bayes_risk(c.prior))

    def test_cost_aware_optimum_dominates_risk_only_and_greedy(self):
        for c in generate(seed=20261114,count=12):
            for cost in (0,.01,.02,.05,.5):
                best=optimal_with_cost(c.prior,c.probes,2,cost)
                for arm in ("recursive_voi","greedy_voi","stop","cost_optimal"):
                    with self.subTest(c=c.id,cost=cost,arm=arm):
                        err,n=expected_policy_metrics(
                            c.prior,c.probes,2,policy=arm,cost=cost)
                        self.assertLessEqual(best,err+cost*n+1e-10)
                e,n=expected_policy_metrics(
                    c.prior,c.probes,2,policy="cost_optimal",cost=cost)
                self.assertAlmostEqual(best,e+cost*n,places=10)

    def test_larger_cost_cannot_raise_optimal_expected_probe_count(self):
        for c in generate(seed=20261114,count=8):
            ns=[
                expected_policy_metrics(
                    c.prior,c.probes,2,policy="cost_optimal",cost=cost)[1]
                for cost in (0,.01,.02,.05,1)
            ]
            for i in range(1,len(ns)):
                self.assertLessEqual(ns[i],ns[i-1]+1e-10)

    def test_multi_seed_frontier_has_expected_cases_and_auditable_digest(self):
        d=run_sensitivity(seeds=(20261114,20261115),count_per_seed=8,
                          costs=(0,.01,.05))
        self.assertEqual(d["case_count"],16)
        self.assertEqual(len(d["cost_results"]),3)
        self.assertEqual(
            d["report_sha256"],
            digest({k:v for k,v in d.items() if k!="report_sha256"}))
        self.assertEqual(verify_sensitivity(d)["cases"],16)
        for level in d["cost_results"]:
            methods=level["strategies"]
            self.assertLessEqual(
                methods["cost_optimal"]["mean_total_expected_cost"],
                methods["greedy_voi"]["mean_total_expected_cost"]+1e-10)
            self.assertLessEqual(
                methods["cost_optimal"]["mean_total_expected_cost"],
                methods["recursive_voi"]["mean_total_expected_cost"]+1e-10)

    def test_tampered_frontier_is_independently_rejected(self):
        data=run_sensitivity(seeds=(20261114,),count_per_seed=4,
                             costs=(0,.01))
        other=copy.deepcopy(data)
        other["cost_results"][1]["strategies"]["greedy_voi"][
            "mean_expected_probes"]+=1
        with self.assertRaisesRegex(InvestigationError,"checksum"):
            verify_sensitivity(other)
        other["report_sha256"]=digest({
            k:v for k,v in other.items() if k!="report_sha256"
        })
        with self.assertRaisesRegex(InvestigationError,"recomputed"):
            verify_sensitivity(other)

    def test_invalid_costs_and_study_parameters_rejected(self):
        c=generate(seed=20261114,count=4)[0]
        for cost in (-1,True,float("nan"),float("inf")):
            with self.subTest(cost=cost),self.assertRaises(InvestigationError):
                optimal_with_cost(c.prior,c.probes,2,cost)
        with self.assertRaises(InvestigationError):
            run_sensitivity(seeds=(20261114,20261114),count_per_seed=4)
        with self.assertRaises(InvestigationError):
            run_sensitivity(seeds=(20261114,),count_per_seed=4,costs=(.01,.01))


if __name__=="__main__":
    unittest.main()
