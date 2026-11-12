"""Challenge 10 authenticated status tool: deterministic offline tests only."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from rei0.benchmark import BenchmarkError
from rei0.evidence import EvidenceError
from rei0.models import digest
from rei0.signed_state_decision import (
    audit_model_proposal, resolve_signed_state,
)
from research.challenge9.interventions import generate_cases, replay_case
from research.challenge9.run_trial import ScriptedFixtureProvider
from research.challenge9.paired_trial import run_trial
from research.challenge10.diagnose import read_result, diagnose_trial


class SignedStatusDecisionTests(unittest.TestCase):
    def test_each_case_resolves_exact_independent_state(self):
        for case in generate_cases():
            with self.subTest(case=case.id):
                _, ledger = replay_case(case, return_ledger=True)
                decision = resolve_signed_state(ledger, "P")
                self.assertEqual(decision.recorded_state, case.expected)
                self.assertEqual(decision.evidence_audit_head, ledger.audit_head)
                self.assertEqual(decision.graph_audit_head, ledger.graph.audit_head)
                self.assertEqual(decision.review_receipts, 5)
                self.assertEqual(decision.to_dict()["decision_sha256"],
                                 digest({k:v for k,v in decision.to_dict().items()
                                         if k != "decision_sha256"}))
                # The decision is a pure read: no ledger/graph events added.
                before = ledger.to_dict()
                self.assertEqual(resolve_signed_state(ledger, "P"), decision)
                self.assertEqual(ledger.to_dict(), before)

    def test_signed_conflict_cannot_be_erased_by_fake_graph_labels(self):
        case = generate_cases()[3]
        _, ledger = replay_case(case, return_ledger=True)
        trusted = resolve_signed_state(ledger, "P")
        self.assertEqual(trusted.recorded_state, "BOTH")
        self.assertEqual(len(trusted.supporting_source_groups), 1)
        self.assertEqual(len(trusted.opposing_source_groups), 1)
        self.assertNotEqual(ledger.graph.assess("P").state.value,
                            trusted.recorded_state)

    def test_neither_is_not_objective_falsity(self):
        _, ledger = replay_case(generate_cases()[0], return_ledger=True)
        result = resolve_signed_state(ledger, "P").to_dict()
        self.assertEqual(result["recorded_evidence_state"], "NEITHER")
        self.assertIn("not verification", result["warning"])

    def test_distinguishes_valid_invalid_and_disagreeing_model_proposals(self):
        _, ledger = replay_case(generate_cases()[2], return_ledger=True)
        decision = resolve_signed_state(ledger, "P")
        self.assertEqual(decision.recorded_state, "ATTACK_ONLY")
        for guess, label in (
            ("ATTACK_ONLY", "agrees"),
            (" attack_only ", "agrees"),
            ("NEITHER", "contradicts"),
            ("I feel uncertain", "invalid"),
            ("", "invalid"),
            (None, "abstained"),
        ):
            with self.subTest(guess=guess):
                result = audit_model_proposal(guess, decision)
                self.assertEqual(result.disposition, label)
                self.assertEqual(result.trusted_state, "ATTACK_ONLY")
                self.assertEqual(result.decision_sha256,
                                 decision.to_dict()["decision_sha256"])

    def test_fails_closed_for_bad_ledger_or_unknown_claim(self):
        _, ledger = replay_case(generate_cases()[0], return_ledger=True)
        with self.assertRaises(EvidenceError):
            resolve_signed_state(None, "P")
        for ident in ("", "missing", "e:A"):
            with self.subTest(id=ident), self.assertRaises(EvidenceError):
                resolve_signed_state(ledger, ident)
        decision = resolve_signed_state(ledger, "P")
        with self.assertRaises(EvidenceError):
            audit_model_proposal(5, decision)
        with self.assertRaises(EvidenceError):
            audit_model_proposal("NEITHER", None)

    def test_wrong_verifier_key_does_not_fallback_to_unsigned_graph(self):
        from rei0.review import (
            Ed25519ReviewIssuer, Ed25519TrustedReviewer, VerificationBoundary,
            ReviewError,
        )
        _, ledger = replay_case(generate_cases()[3], return_ledger=True)
        unknown = Ed25519ReviewIssuer.generate(
            "challenge9-ephemeral", "independent-fixture-reviewer")
        ledger._boundary = VerificationBoundary({
            "challenge9-ephemeral": Ed25519TrustedReviewer(
                "independent-fixture-reviewer", unknown.public_key_bytes())
        })
        with self.assertRaises(ReviewError):
            resolve_signed_state(ledger, "P")


class DiagnosticTests(unittest.TestCase):
    def fixture(self):
        return run_trial(ScriptedFixtureProvider(), count=4)

    def test_all_cases_get_identical_trusted_status_tool_in_both_arms(self):
        report = self.fixture()
        results = diagnose_trial(report, count=4)
        self.assertEqual(results["input_report_sha256"], report["report_sha256"])
        self.assertEqual(results["diagnostic"]["cases"], 4)
        self.assertEqual(results["diagnostic"]["per_arm"]["self_critique"]["tool_correct"],4)
        self.assertEqual(results["diagnostic"]["per_arm"]["rei12"]["tool_correct"],4)
        for case in results["cases"]:
            self.assertEqual(case["trusted_signed_status"],case["independent_oracle"])
            self.assertEqual(
                case["arms"]["rei12"]["same_tool_recorded_state"],
                case["arms"]["self_critique"]["same_tool_recorded_state"])
        self.assertEqual(results["diagnostic_sha256"],
                         digest({k:v for k,v in results.items()
                                 if k != "diagnostic_sha256"}))

    def test_original_model_proposals_not_modified(self):
        report = self.fixture()
        before = json.loads(json.dumps(report))
        result = diagnose_trial(report, count=4)
        self.assertEqual(report, before)
        for row in report["outcomes"]:
            item = next(c for c in result["cases"] if c["case_id"] == row["case_id"])
            self.assertEqual(item["arms"][row["arm"]]["model_proposal"], row["answer"])

    def test_fails_closed_on_report_forgery_and_missing_pairs(self):
        report = self.fixture()
        report["outcomes"][0]["answer"] = "BOTH"
        with self.assertRaisesRegex(BenchmarkError, "checksum"):
            diagnose_trial(report, count=4)
        good = self.fixture()
        with self.assertRaises(BenchmarkError):
            diagnose_trial(good, count=8)

    def test_can_read_machine_report_from_json_or_github_zip(self):
        report = self.fixture()
        wrapper = {"report":report,"environment":{"mode":"fixture"}}
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "paired-live.json"
            path.write_text(json.dumps(wrapper),encoding="utf-8")
            self.assertEqual(read_result(path),wrapper)
            zipped = Path(td) / "downloaded.zip"
            with zipfile.ZipFile(zipped,"w") as z:
                z.write(path,"paired-live.json")
            self.assertEqual(read_result(zipped),wrapper)
            with zipfile.ZipFile(zipped,"a") as z:
                z.writestr("second/paired-live.json",json.dumps(wrapper))
            with self.assertRaises(BenchmarkError):
                read_result(zipped)


if __name__ == "__main__":
    unittest.main()
