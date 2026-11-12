"""Challenge 9 software-only signed-evidence intervention tests.

These tests exercise an independent event reducer vs the actual authenticated
EvidenceLedger. They do NOT exercise a language model or prove AI superiority.
"""
from __future__ import annotations

from collections import Counter
import unittest

from rei0.models import digest
from research.challenge9.interventions import (
    Case, Challenge9Error, STATES, audit, generate_cases, oracle_trace,
    replay_case,
)


class SignedInterventionTests(unittest.TestCase):
    def test_twelve_cases_balance_the_four_final_states(self):
        cases = generate_cases()
        self.assertEqual(len(cases), 12)
        self.assertEqual(Counter(c.expected for c in cases),
                         Counter({name: 3 for name in STATES}))
        self.assertEqual(cases, generate_cases())
        self.assertNotEqual(cases, generate_cases(seed=123456))

    def test_every_signed_checkpoint_matches_independent_reducer(self):
        for case in generate_cases():
            with self.subTest(case=case.id):
                result = replay_case(case)
                self.assertEqual(result["states"], oracle_trace(case.events))
                self.assertEqual(result["final_state"], case.expected)
                self.assertGreater(result["signed_receipts"], 0)
                self.assertEqual(result["forged_assertions"], 2)

    def test_unsigned_labels_disagree_with_trusted_ledger(self):
        cases = generate_cases()
        trusted_only = [
            replay_case(case) for case in cases if case.expected == "NEITHER"
        ]
        self.assertEqual(len(trusted_only), 3)
        for record in trusted_only:
            self.assertEqual(record["final_state"], "NEITHER")
            self.assertEqual(record["unsafe_legacy_graph_state"], "ATTACK_ONLY")

    def test_model_authored_and_forged_docs_remain_pending(self):
        case = generate_cases()[0]
        result = replay_case(case)
        docs = {row["id"]: row for row in result["public_docket"]["evidence"]}
        self.assertEqual(docs["M"]["source_kind"], "model")
        self.assertEqual(docs["M"]["signed_review_status"], "PENDING")
        self.assertEqual(docs["D"]["signed_review_status"], "PENDING")
        self.assertEqual(docs["A"]["signed_review_status"], "REVOKED")
        self.assertEqual(docs["B"]["signed_review_status"], "REVOKED")
        self.assertEqual(docs["C"]["signed_review_status"], "REVOKED")

    def test_docket_only_exposes_shared_verified_status_not_oracle(self):
        result = replay_case(generate_cases()[3])
        dossier = result["public_docket"]
        self.assertEqual(set(dossier), {"claim", "review_policy", "evidence"})
        self.assertEqual(len(dossier["evidence"]), 5)
        for row in dossier["evidence"]:
            self.assertEqual(set(row), {
                "id", "origin_group", "source_kind", "side", "signed_review_status",
            })
            self.assertNotIn("final_state", row)
            self.assertNotIn("private_key", row)
            self.assertNotIn("oracle", row)

    def test_duplicate_source_retraction_keeps_independent_copy_active(self):
        case = generate_cases()[3]
        t = oracle_trace(case.events)
        verify_b = next(i for i,e in enumerate(case.events)
                        if e["op"] == "VERIFY" and e["doc"] == "B")
        revoke_b = next(i for i,e in enumerate(case.events)
                        if e["op"] == "REVOKE" and e["doc"] == "B")
        self.assertEqual(t[verify_b], "SUPPORT_ONLY" if not any(
            e["op"] == "VERIFY" and e["doc"] == "C"
            for e in case.events[:verify_b+1]) else "BOTH")
        self.assertEqual(t[revoke_b], "BOTH")

    def test_illegal_review_transitions_rejected_by_oracle(self):
        for events in (
            [{"op": "VERIFY", "doc": "not-present"}],
            [{"op": "SUBMIT", "doc": "X", "origin": "g",
              "side": "SUPPORT", "kind": "external"},
             {"op": "REVOKE", "doc": "X"}],
            [{"op": "SUBMIT", "doc": "X", "origin": "g",
              "side": "SUPPORT", "kind": "model"},
             {"op": "VERIFY", "doc": "X"}],
            [{"op": "SUBMIT", "doc": "X", "origin": "g",
              "side": "SUPPORT", "kind": "external"},
             {"op": "VERIFY", "doc": "X"}, {"op": "VERIFY", "doc": "X"}],
        ):
            with self.subTest(events=events), self.assertRaises(Challenge9Error):
                oracle_trace(events)

    def test_unauthorized_events_cannot_change_gold(self):
        doc = {"op": "SUBMIT", "doc": "D", "origin": "fake",
               "side": "ATTACK", "kind": "external"}
        events = [doc, {"op": "FORGE", "doc": "D"}]
        self.assertEqual(oracle_trace(events), ["NEITHER", "NEITHER"])
        with self.assertRaises(Challenge9Error):
            replay_case(Case("bad", "BOTH", tuple(events)))

    def test_audit_aggregates_including_unknown_model_performance(self):
        report = audit()
        self.assertEqual(report["summary"]["cases"], 12)
        self.assertEqual(report["summary"]["independent_oracle_agreement"], 12)
        self.assertEqual(report["summary"]["final_state_counts"],
                         {state:3 for state in STATES})
        self.assertEqual(report["summary"]["legacy_graph_disagrees_with_signed_ledger"], 9)
        self.assertEqual(report["summary"]["forged_review_assertions_ignored"], 24)
        self.assertGreater(report["summary"]["signed_checkpoints_validated"], 120)
        self.assertEqual(report["summary"]["live_model_inference_calls"], 0)
        self.assertEqual(report["report_sha256"],
                         digest({k:v for k,v in report.items() if k != "report_sha256"}))
        self.assertEqual(report, audit())

    def test_invalid_generator_parameters_rejected(self):
        for kw in ({"seed":True}, {"seed":-1}, {"count":5}, {"count":0},
                   {"count":101}, {"count":True}):
            with self.subTest(kw=kw), self.assertRaises(Challenge9Error):
                generate_cases(**kw)


if __name__ == "__main__":
    unittest.main()
