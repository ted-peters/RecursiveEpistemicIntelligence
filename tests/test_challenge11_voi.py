"""Challenge 11: tests for epistemic investigation selection and signed outcomes.

Synthetic simulation tests, NOT live language model evaluations.
"""
from __future__ import annotations

import copy
import json
import math
from unittest import TestCase
import unittest

from rei0.evidence import EvidenceError
from rei0.review import (
    Ed25519ReviewIssuer, Ed25519TrustedReviewer, VerificationBoundary, ReviewError,
)
from research.challenge11.voi import (
    BUDGET, EPS, InvestigationError, Probe, Scenario, bayes_risk,
    choice_table, generate, optimal_risk, policy_risk, prob_positive,
    public_digest, select, update,
)
from research.challenge11.simulate import (
    PrivateTestEnvironment, run_case, run_audit, verify_audit,
)


class ActiveInvestigationTests(TestCase):
    def test_bayes_update_is_correct_for_both_possible_outcomes(self):
        probe = Probe("test", 0.8, 0.2)
        self.assertAlmostEqual(prob_positive(.5,probe), .5)
        self.assertAlmostEqual(update(.5,probe,True), .8)
        self.assertAlmostEqual(update(.5,probe,False), .2)
        q=prob_positive(.3,probe)
        self.assertAlmostEqual(q*update(.3,probe,True) +
                               (1-q)*update(.3,probe,False), .3)
        self.assertEqual(bayes_risk(.5),.5)
        with self.assertRaises(InvestigationError):
            update(.5,probe,"POSITIVE")

    def test_exact_optimal_lookahead_matches_recursive_policy_expected_risk(self):
        for c in generate(count=24):
            a=optimal_risk(c.prior,c.probes,BUDGET)
            b=policy_risk(c.prior,c.probes,BUDGET,policy="recursive_voi")
            greedy=policy_risk(c.prior,c.probes,BUDGET,policy="greedy_voi")
            with self.subTest(case=c.id):
                self.assertAlmostEqual(a,b,places=11)
                self.assertLessEqual(a,greedy+1e-10)
                self.assertLessEqual(a,bayes_risk(c.prior)+1e-10)

    def test_one_step_greedy_equals_one_step_exact(self):
        c=generate(count=4)[0]
        for p in (.2,.35,.5,.7,.9):
            self.assertEqual(
                select(p,c.probes,1,policy="recursive_voi")[0],
                select(p,c.probes,1,policy="greedy_voi")[0],
            )

    def test_generated_public_data_cannot_expose_truth_or_unobserved_outcomes(self):
        a=generate(count=8)
        self.assertEqual(a,generate(count=8))
        self.assertNotEqual(a,generate(seed=123456,count=8))
        for c in a:
            public=c.public()
            self.assertEqual(public["remaining_probe_budget"],2)
            self.assertEqual(public["observations"],[])
            self.assertEqual(set(public),{
                "question","hypotheses","prior_probability_H1",
                "current_probability_H1","remaining_probe_budget",
                "available_probes","observations","assumptions",
            })
            rendered=json.dumps(public)
            self.assertNotIn('"truth"',rendered)
            self.assertNotIn('"outcomes"',rendered)
            self.assertNotIn('"seed"',rendered)
        # The digest is independent of hidden draws, not a secret-key fingerprint.
        c=a[0]
        changed=Scenario(c.id,c.prior,c.probes,not c.truth,
                         tuple((pid,not value) for pid,value in c.outcomes))
        self.assertEqual(public_digest((c,)),public_digest((changed,)))

    def test_choice_utilities_are_shared_for_all_methods(self):
        c=generate(count=4)[0]
        rows=choice_table(c.prior,c.probes,2)
        self.assertEqual(len(rows),4)
        self.assertEqual({r["id"] for r in rows},{"A","B","C","D"})
        for row in rows:
            self.assertGreaterEqual(row["immediate_expected_error"],0)
            self.assertGreaterEqual(row["exact_remaining_budget_expected_error"],0)
            self.assertLessEqual(row["exact_remaining_budget_expected_error"],
                                 row["immediate_expected_error"]+1e-7)
            self.assertNotIn("truth",row)
            self.assertNotIn("positive",row)

    def test_only_one_observation_can_be_revealed_per_probe_and_only_after_signature(self):
        c=generate(count=4)[0]
        env=PrivateTestEnvironment(c)
        before=env.ledger.assess("H1")
        self.assertEqual(before.state.value,"NEITHER")
        observation=env.perform("A")
        self.assertEqual(observation["signed_review_status"],"VERIFIED")
        self.assertEqual(env.ledger.assess("H1").state.value,
                         "SUPPORT_ONLY" if observation["result"]=="POSITIVE"
                         else "ATTACK_ONLY")
        self.assertEqual(len(env.ledger.review_receipts),1)
        with self.assertRaises(InvestigationError):
            env.perform("A")
        env.perform("B")
        with self.assertRaises(InvestigationError):
            env.perform("C")
        self.assertEqual(len(env.ledger.review_receipts),2)

    def test_receipt_verifier_tampering_must_fail_closed(self):
        c=generate(count=4)[0]
        env=PrivateTestEnvironment(c)
        env.perform("A")
        bad=Ed25519ReviewIssuer.generate("c11-ephemeral","trusted-fixture-review")
        env.ledger._boundary=VerificationBoundary({
            "c11-ephemeral":Ed25519TrustedReviewer(
                "trusted-fixture-review",bad.public_key_bytes()),
        })
        with self.assertRaises(ReviewError):
            env.ledger.assess("H1")

    def test_paired_case_has_same_potential_outcomes_under_either_policy(self):
        for c in generate(count=12):
            a=run_case(c,"recursive_voi")
            b=run_case(c,"greedy_voi")
            truth=dict(c.outcomes)
            for row in (a,b):
                with self.subTest(case=c.id,policy=row.policy):
                    self.assertLessEqual(row.probe_count,2)
                    self.assertEqual(row.probe_count,row.signed_receipts)
                    self.assertEqual(len(set(row.chosen)),len(row.chosen))
                    for observed in row.observations:
                        self.assertEqual(
                            observed["result"],
                            "POSITIVE" if truth[observed["probe_id"]] else "NEGATIVE")
                    self.assertEqual(row.correct,row.prediction==c.truth)
                    self.assertGreaterEqual(row.exact_expected_bayes_error,0)
                    self.assertLessEqual(row.exact_expected_bayes_error,.5)
                    self.assertGreaterEqual(row.regret_over_optimal,0)

    def test_audit_is_deterministic_in_metrics_but_signatures_are_ephemeral(self):
        # Raw ledger audit heads change because the ephemeral review keys sign,
        # but the *task*, decisions, and expected-risk metrics are deterministic.
        a=run_audit(count=8)
        b=run_audit(count=8)
        self.assertEqual(a["summary"],b["summary"])
        self.assertEqual(a["public_dataset_digest"],b["public_dataset_digest"])
        self.assertEqual([x["chosen"] for x in a["outcomes"]],
                         [x["chosen"] for x in b["outcomes"]])
        self.assertEqual(a["summary"]["recursive_voi"]["model_calls"],0)
        self.assertEqual(a["summary"]["greedy_voi"]["model_calls"],0)
        self.assertEqual(a["summary"]["recursive_voi"]["mean_regret_vs_optimal"],0)
        self.assertGreaterEqual(
            a["summary"]["greedy_voi"]["mean_regret_vs_optimal"],0)
        self.assertEqual(len(a["outcomes"]),16)

    def test_report_checksum_and_replay_is_not_keyless_proof_of_authenticity(self):
        report=run_audit(count=4)
        self.assertEqual(verify_audit(report)["cases"],4)
        tampered=copy.deepcopy(report)
        tampered["outcomes"][0]["correct"]=False
        with self.assertRaisesRegex(InvestigationError,"checksum"):
            verify_audit(tampered)

    def test_invalid_probes_and_policies_fail_closed(self):
        for spec in (("X",0,0.4),("X",0.5,0.6),("X",1.0,.4),
                     ("",.9,.3),("X",float("nan"),.2)):
            with self.subTest(spec=spec),self.assertRaises(InvestigationError):
                Probe(*spec)
        for kw in ({"seed":True},{"seed":-1},{"count":3},
                   {"count":5},{"count":201},{"count":True}):
            with self.subTest(kw=kw),self.assertRaises(InvestigationError):
                generate(**kw)
        c=generate(count=4)[0]
        with self.assertRaises(InvestigationError):
            select(c.prior,c.probes,2,policy="not-a-policy")
        with self.assertRaises(InvestigationError):
            run_case(c,"not-a-policy")


if __name__=="__main__":
    unittest.main()
