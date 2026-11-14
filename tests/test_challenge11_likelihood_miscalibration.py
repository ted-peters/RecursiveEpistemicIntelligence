"""Challenge 11D exact likelihood-miscalibration stress tests; no model inference."""
from __future__ import annotations

import copy
import math
import unittest

from rei0.models import digest
from research.challenge11.cost_sensitivity import (
    expected_policy_metrics,
)
from research.challenge11.likelihood_miscalibration import (
    ARMS, exact_true_policy_risk, run_study, true_likelihoods,
    verify_study, InvestigationError,
)
from research.challenge11.voi import (
    Probe, generate,
)


class MiscalibratedEvidenceTests(unittest.TestCase):
    def test_zero_distortion_matches_exact_earlier_cost_planner(self):
        for c in generate(seed=20261119,count=8):
            true=true_likelihoods(c.probes,c.id,0)
            self.assertEqual(true,c.probes)
            for arm,reference in (
                ("nominal_recursive","recursive_voi"),
                ("nominal_greedy","greedy_voi"),
                ("nominal_cost_optimal","cost_optimal"),
                ("privileged_true_cost_optimal","cost_optimal"),
            ):
                with self.subTest(case=c.id,policy=arm):
                    actual=exact_true_policy_risk(
                        prior=c.prior,assumed=c.probes,true=true,
                        policy=arm,cost=.02)
                    expected=expected_policy_metrics(
                        c.prior,c.probes,2,policy=reference,cost=.02)
                    self.assertAlmostEqual(actual[0],expected[0],places=10)
                    self.assertAlmostEqual(actual[1],expected[1],places=10)

    def test_exact_integral_with_one_noisy_probe(self):
        nominal=(Probe("A",.8,.2),)
        true=(Probe("A",.9,.1),)
        err,n=exact_true_policy_risk(
            prior=.5,assumed=nominal,true=true,
            budget=1,policy="nominal_recursive",cost=0)
        self.assertAlmostEqual(err,.1,places=12)
        self.assertAlmostEqual(n,1,places=12)
        err,n=exact_true_policy_risk(
            prior=.5,assumed=nominal,true=true,
            budget=1,policy="nominal_cost_optimal",cost=1)
        self.assertEqual((err,n),(.5,0))

    def test_misestimated_reliability_never_leaks_into_nominal_policy(self):
        original=generate(seed=20261119,count=4)[0]
        a=true_likelihoods(original.probes,"20261119:"+original.id,.15)
        b=true_likelihoods(original.probes,"20261119:"+original.id,.15)
        self.assertEqual(a,b)
        self.assertEqual([x.id for x in a],[x.id for x in original.probes])
        self.assertTrue(any(p!=q for p,q in zip(a,original.probes)))
        for p in a:
            self.assertGreater(p.sensitivity,p.false_positive)
            self.assertLess(p.sensitivity,1)
            self.assertGreater(p.false_positive,0)
        self.assertNotEqual(
            a,true_likelihoods(original.probes,"other-case",.15))

    def test_privileged_oracle_is_upper_bound_not_fair_comparator(self):
        scenarios=generate(seed=20261119,count=12)
        for c in scenarios:
            t=true_likelihoods(c.probes,c.id,.10)
            outcomes={
                arm:exact_true_policy_risk(
                    prior=c.prior,assumed=c.probes,true=t,
                    policy=arm,cost=.02)
                for arm in ARMS
            }
            optimal=outcomes["privileged_true_cost_optimal"]
            best=optimal[0]+.02*optimal[1]
            for arm in ARMS:
                with self.subTest(case=c.id,arm=arm):
                    err,n=outcomes[arm]
                    self.assertGreaterEqual(err,-1e-10)
                    self.assertLessEqual(err,.5+1e-10)
                    self.assertGreaterEqual(n,0)
                    self.assertLessEqual(n,2+1e-10)
                    self.assertLessEqual(best,err+.02*n+1e-10)

    def test_audited_multiseed_report_and_replay(self):
        result=run_study(seeds=(20261119,20261120),
                         count_per_seed=8,distortions=(0.,.05,.1),cost=.02)
        self.assertEqual(result["total_nominal_scenarios"],16)
        self.assertEqual(len(result["results"]),3)
        self.assertEqual(result["report_sha256"],digest({
            k:v for k,v in result.items() if k!="report_sha256"}))
        self.assertEqual(verify_study(result)["nominal_scenarios"],16)
        zerocost=result["results"][0]["policies"]
        self.assertAlmostEqual(
            zerocost["nominal_cost_optimal"]["mean_true_total_expected_cost"],
            zerocost["privileged_true_cost_optimal"]["mean_true_total_expected_cost"],
            places=10)

    def test_tampered_signed_summary_does_not_bypass_independent_rerun(self):
        original=run_study(seeds=(20261119,),count_per_seed=4,
                           distortions=(0.,.05),cost=.02)
        altered=copy.deepcopy(original)
        altered["results"][1]["policies"]["nominal_recursive"][
            "mean_true_expected_error"]+=.01
        with self.assertRaisesRegex(InvestigationError,"checksum"):
            verify_study(altered)
        altered["report_sha256"]=digest({
            k:v for k,v in altered.items() if k!="report_sha256"
        })
        with self.assertRaisesRegex(InvestigationError,"recomputed"):
            verify_study(altered)

    def test_parameter_validation_prevents_invalid_oracle_queries(self):
        c=generate(seed=20261119,count=4)[0]
        for d in (-.01,.41,float("nan"),True):
            with self.subTest(d=d),self.assertRaises(InvestigationError):
                true_likelihoods(c.probes,c.id,d)
        for cost in (-1,True,float("nan")):
            with self.subTest(cost=cost),self.assertRaises(InvestigationError):
                exact_true_policy_risk(
                    prior=c.prior,assumed=c.probes,true=c.probes,
                    policy="nominal_cost_optimal",cost=cost)
        with self.assertRaises(InvestigationError):
            exact_true_policy_risk(
                prior=c.prior,assumed=c.probes,true=c.probes[:-1],
                policy="nominal_cost_optimal")
        with self.assertRaises(InvestigationError):
            run_study(seeds=(20261119,20261119),count_per_seed=4)
        with self.assertRaises(InvestigationError):
            run_study(seeds=(20261119,),count_per_seed=5)


if __name__=="__main__":
    unittest.main()
