"""REI 1.2: signed-review evidence gate for recursive scheduling.

All tests are synthetic offline security/architecture checks, NOT measurements
of factual correctness or comparative model intelligence.
"""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from rei0.adaptive import AdaptiveController
from rei0.adaptive_engine import AdaptiveInquiryEngine
from rei0.authenticated_adaptive import AuthenticatedAdaptiveController
from rei0.adapters import ScriptedAdapter
from rei0.evidence import EvidenceLedger, EvidenceError
from rei0.inquiry import InquiryEngine, InquiryLimits, InquirySession
from rei0.models import EdgeKind, Provenance, SourceKind, Validation
from rei0.review import (Ed25519ReviewIssuer, Ed25519TrustedReviewer,
                         VerificationBoundary, ReviewError)

ROOT = Path(__file__).resolve().parents[1]
STAMP = "2026-11-11T00:00:00Z"
QUERY = "What evidence justifies the provisional claim?"


def make_pending(priority=1):
    script = json.loads((ROOT / "examples" / "inquiry_script.json").read_text())
    script["initial"]["payload"]["questions"] = [{
        "text": "Could the claimed evidence be contradicted?",
        "target": "claim", "priority": priority,
    }]
    provider = ScriptedAdapter(script)
    paused = InquiryEngine(
        provider, InquiryLimits(max_depth=0, max_steps=1, max_tokens=2000),
        clock=lambda: STAMP,
    ).run(QUERY)
    assert paused.stop_reason == "depth_budget"
    signer = Ed25519ReviewIssuer.generate("test-key", "external-reviewer")
    trust = VerificationBoundary({
        "test-key": Ed25519TrustedReviewer("external-reviewer",
                                           signer.public_key_bytes())
    })
    ledger = EvidenceLedger(paused.graph, trust, clock=lambda: STAMP)
    return paused, ledger, signer, provider


def submit(ledger, submission, side, *, group=None, kind=SourceKind.EXTERNAL):
    ledger.submit(
        submission_id=submission, evidence_id="e:" + submission,
        claim_id=next(n.id for n in ledger.graph.nodes.values()
                      if n.kind.value == "claim"),
        text="Fictional observation " + submission,
        artifact_bytes=("fictional artifact " + submission).encode(),
        provenance=Provenance("source:" + submission, kind,
                              group or "group:" + submission,
                              "fixture://" + submission, STAMP),
        polarity=side,
    )


def sign(ledger, issuer, sid, status):
    old = [r for r in ledger.review_receipts if r.submission_id == sid]
    receipt = issuer.issue(
        submission_id=sid, subject_digest=ledger.subject_digest(sid),
        decision=status, reason="fixture-only review",
        issued_at=STAMP, decision_index=len(old)+1,
        prior_signature=old[-1].signature if old else "0" * 64,
    )
    ledger.accept(receipt)
    return receipt


def verdict(session, ledger, *, min_score=8, reserve=0):
    return AuthenticatedAdaptiveController(
        ledger=ledger, min_score=min_score, reserve_tokens=reserve,
    ).decide(session, tuple(session.queue),
             remaining_calls=3, remaining_tokens=900)


class TrustedAdaptiveTests(unittest.TestCase):
    def test_unsigned_spoof_of_graph_verification_cannot_buy_recursion(self):
        session, ledger, issuer, _ = make_pending()
        submit(ledger, "s", EdgeKind.SUPPORTS)
        submit(ledger, "a", EdgeKind.ATTACKS)
        # This legacy API makes graph.assess() claim BOTH without any signer.
        for sid in ("s", "a"):
            ledger.graph.set_validation("node", "e:" + sid,
                 Validation.VERIFIED, verified_by="forged-label", reason="not signed")
            ledger.graph.set_validation("edge", "evidence-link:e:" + sid,
                 Validation.VERIFIED, verified_by="forged-label", reason="not signed")
        self.assertEqual(session.graph.assess(session.root_id).state.value, "BOTH")
        unsafe = AdaptiveController(min_score=8, reserve_tokens=0).decide(
            session, tuple(session.queue), remaining_calls=3, remaining_tokens=900)
        self.assertEqual(unsafe.question_id, session.queue[0].id)
        safe = verdict(session, ledger)
        self.assertEqual(safe.stop_reason, "adaptive_low_value")
        self.assertEqual(safe.audit["selected_evidence_state"], "NEITHER")
        self.assertEqual(safe.audit["authenticated_receipt_count"], 0)
        self.assertEqual(safe.audit["evidence_authority"], "signed_review_ledger")

    def test_signed_opposition_changes_priority_and_revocation_restores_stop(self):
        session, ledger, signer, _ = make_pending()
        submit(ledger, "s", EdgeKind.SUPPORTS)
        submit(ledger, "a", EdgeKind.ATTACKS)
        self.assertEqual(verdict(session, ledger).stop_reason, "adaptive_low_value")
        sign(ledger, signer, "s", Validation.VERIFIED)
        self.assertEqual(verdict(session, ledger).stop_reason, "adaptive_low_value")
        sign(ledger, signer, "a", Validation.VERIFIED)
        decision = verdict(session, ledger)
        self.assertEqual(decision.question_id, session.queue[0].id)
        self.assertEqual(decision.audit["selected_evidence_state"], "BOTH")
        self.assertEqual(decision.audit["authenticated_support_sources"], 1)
        self.assertEqual(decision.audit["authenticated_attack_sources"], 1)
        self.assertEqual(decision.audit["authenticated_receipt_count"], 2)
        sign(ledger, signer, "a", Validation.REVOKED)
        after = verdict(session, ledger)
        self.assertEqual(after.stop_reason, "adaptive_low_value")
        self.assertEqual(after.audit["selected_evidence_state"], "SUPPORT_ONLY")

    def test_signed_evidence_controls_an_actual_resumed_engine_step(self):
        session, ledger, signer, provider = make_pending()
        submit(ledger, "s", EdgeKind.SUPPORTS)
        submit(ledger, "a", EdgeKind.ATTACKS)
        sign(ledger, signer, "s", Validation.VERIFIED)
        sign(ledger, signer, "a", Validation.VERIFIED)
        runner = AdaptiveInquiryEngine(
            provider, InquiryLimits(max_depth=2, max_steps=1, max_tokens=2000),
            clock=lambda: STAMP,
            controller=AuthenticatedAdaptiveController(ledger, min_score=8, reserve_tokens=0),
        )
        result = runner.run(resume=session)
        self.assertEqual(result.steps, 1)
        self.assertEqual(result.trace[-2]["event"], "adaptive_select")
        self.assertEqual(result.trace[-2]["decision"]["selected_evidence_state"], "BOTH")
        self.assertEqual(InquirySession.from_dict(result.to_dict()).to_dict(), result.to_dict())
        self.assertEqual(result.graph.assess(result.root_id).state.value, "NEITHER",
                         "signed ledger decisions must never silently set graph validation")

    def test_unsigned_and_duplicate_submissions_cannot_raise_score(self):
        session, ledger, signer, _ = make_pending()
        submit(ledger, "s", EdgeKind.SUPPORTS, group="shared")
        sign(ledger, signer, "s", Validation.VERIFIED)
        submit(ledger, "dupe", EdgeKind.SUPPORTS, group="shared")
        sign(ledger, signer, "dupe", Validation.VERIFIED)
        submit(ledger, "pending", EdgeKind.ATTACKS)
        decision = verdict(session, ledger)
        self.assertEqual(decision.audit["selected_evidence_state"], "SUPPORT_ONLY")
        self.assertEqual(decision.audit["authenticated_support_sources"], 1)
        self.assertGreaterEqual(decision.audit["excluded_evidence_edges"], 1)
        self.assertEqual(decision.stop_reason, "adaptive_low_value")

    def test_model_sourced_submission_cannot_be_approved(self):
        session, ledger, signer, _ = make_pending()
        submit(ledger, "model-fabrication", EdgeKind.ATTACKS, kind=SourceKind.MODEL)
        with self.assertRaisesRegex(ReviewError, "model-generated"):
            sign(ledger, signer, "model-fabrication", Validation.VERIFIED)
        self.assertEqual(verdict(session, ledger).audit["selected_evidence_state"], "NEITHER")

    def test_wrong_key_causes_fail_closed_exception_not_fallback(self):
        session, ledger, signer, _ = make_pending()
        submit(ledger, "s", EdgeKind.SUPPORTS)
        sign(ledger, signer, "s", Validation.VERIFIED)
        other = Ed25519ReviewIssuer.generate("test-key", "external-reviewer")
        ledger._boundary = VerificationBoundary({
            "test-key": Ed25519TrustedReviewer("external-reviewer",
                                               other.public_key_bytes())
        })
        with self.assertRaisesRegex(ReviewError, "authentication"):
            verdict(session, ledger)

    def test_mismatched_graph_is_rejected_even_with_authentic_ledger(self):
        session, _, _, _ = make_pending()
        other_session, other_ledger, _, _ = make_pending()
        self.assertIsNot(session.graph, other_session.graph)
        with self.assertRaisesRegex(EvidenceError, "bound"):
            verdict(session, other_ledger)

    def test_token_reserve_protects_budget_even_when_conflicted(self):
        session, ledger, signer, _ = make_pending()
        submit(ledger, "s", EdgeKind.SUPPORTS)
        submit(ledger, "a", EdgeKind.ATTACKS)
        sign(ledger, signer, "s", Validation.VERIFIED)
        sign(ledger, signer, "a", Validation.VERIFIED)
        result = verdict(session, ledger, reserve=900)
        self.assertEqual(result.stop_reason, "adaptive_token_reserve")

    def test_reject_missing_ledger_and_invalid_remaining_budgets(self):
        session, ledger, _, _ = make_pending()
        with self.assertRaises(EvidenceError):
            AuthenticatedAdaptiveController(ledger=None)
        ctl = AuthenticatedAdaptiveController(ledger, min_score=8)
        with self.assertRaises(EvidenceError):
            ctl.decide(session, tuple(session.queue),
                       remaining_calls=True, remaining_tokens=800)
        with self.assertRaises(EvidenceError):
            ctl.decide(session, tuple(session.queue),
                       remaining_calls=0, remaining_tokens=800)
        with self.assertRaises(EvidenceError):
            ctl.decide(session, (), remaining_calls=3, remaining_tokens=800)


if __name__ == "__main__":
    unittest.main()
