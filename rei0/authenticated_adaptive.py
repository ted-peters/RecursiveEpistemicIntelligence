"""REI 1.2: signed-review-gated adaptive scheduling.

A graph node marked VERIFIED by graph.set_validation is NOT authenticated.
For security-sensitive decisions, require EvidenceLedger.assess(), which
rechecks independently configured review signatures and revocations.

This module does not fetch sources, sign reviews, establish real-world truth,
or change the archived REI 1.0 / REI 1.1 implementations.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .adaptive import AdaptiveController, AdaptiveDecision
from .evidence import EvidenceLedger, EvidenceError
from .inquiry import InquirySession, PendingQuestion
from .review import VerificationBoundary


@dataclass(frozen=True)
class AuthenticatedAdaptiveController:
    """Select inquiry targets using *authenticated* review decisions only.

    The ledger and its VerificationBoundary must originate outside the model's
    control. Never accept arbitrary caller-declared graph validation as proof.
    These scores are scheduling heuristics, not probabilities or truth claims.
    """

    ledger: EvidenceLedger
    min_score: int = 10
    reserve_tokens: int = 320

    def __post_init__(self) -> None:
        if not isinstance(self.ledger, EvidenceLedger):
            raise EvidenceError("trusted EvidenceLedger required")
        # Reuse the historical bounds contract without modifying its behavior.
        AdaptiveController(self.min_score, self.reserve_tokens)

    def decide(
        self, session: InquirySession, eligible: tuple[PendingQuestion, ...],
        *, remaining_calls: int, remaining_tokens: int,
    ) -> AdaptiveDecision:
        if not isinstance(session, InquirySession) or self.ledger.graph is not session.graph:
            raise EvidenceError("authenticated ledger must be bound to this inquiry graph")
        if not eligible:
            raise EvidenceError("no eligible inquiry questions")
        if type(remaining_calls) is not int or type(remaining_tokens) is not int:
            raise EvidenceError("remaining budgets must be exact integers")
        if remaining_calls < 1 or remaining_tokens < 0:
            raise EvidenceError("resource budget already exhausted")

        ranked: list[tuple[tuple[int, int, int, str], PendingQuestion, int, Any]] = []
        for q in eligible:
            if not isinstance(q, PendingQuestion):
                raise EvidenceError("invalid pending question")
            if q.id not in session.graph.nodes or q.target_id not in session.graph.nodes:
                raise EvidenceError("candidate references unknown graph entity")
            if q.id not in {item.id for item in session.queue}:
                raise EvidenceError("candidate not in current inquiry frontier")
            # This method re-verifies all signed receipts and revocations.
            # Graph.assess() alone must NOT be used for this decision.
            assessment = self.ledger.assess(q.target_id)
            # No reward for ignored, unsigned or duplicate edges; these may be
            # attacker-controlled and must not purchase extra model calls.
            score = (
                2 * q.priority - 2 * q.depth
                + AdaptiveController._BONUS[assessment.state]
            )
            ranked.append(((-score, q.depth, q.order, q.id), q, score, assessment))
        ranked.sort(key=lambda item: item[0])
        _, selected, score, assessment = ranked[0]
        audit = {
            "policy": "rei1.2-authenticated-reviews-adaptive-v1",
            "evidence_authority": "signed_review_ledger",
            "graph_audit_head": session.graph.audit_head,
            "review_ledger_audit_head": self.ledger.audit_head,
            "authenticated_receipt_count": len(self.ledger.review_receipts),
            "candidate_count": len(ranked),
            "selected_target_id": selected.target_id,
            "selected_evidence_state": assessment.state.value,
            "authenticated_support_sources": len(assessment.support_sources),
            "authenticated_attack_sources": len(assessment.attack_sources),
            "excluded_evidence_edges": len(assessment.ignored_edges),
            "score": score,
            "min_score": self.min_score,
            "remaining_calls": remaining_calls,
            "remaining_tokens": remaining_tokens,
            "reserve_tokens": self.reserve_tokens,
            "warning": (
                "Authenticated reviewer decisions establish admission only; "
                "they do not prove source content or objective truth."
            ),
        }
        if remaining_tokens <= self.reserve_tokens:
            return AdaptiveDecision(None, "adaptive_token_reserve", audit)
        if score < self.min_score:
            return AdaptiveDecision(None, "adaptive_low_value", audit)
        return AdaptiveDecision(selected.id, None, audit)

def load_authenticated_inquiry(
    session_path: str | Path, ledger_path: str | Path,
    boundary: VerificationBoundary, *,
    min_score: int = 10, reserve_tokens: int = 320,
) -> tuple[InquirySession, AuthenticatedAdaptiveController]:
    """Restore a checkpoint AND its matching signed-review ledger, fail closed.

    The caller must provide independently configured public verifier keys.
    Both files must describe exactly the same graph snapshot. This detects
    accidentally paired or diverging histories; it is not an external audit
    anchor. Do not supply signer secrets to this function or the model.
    """
    if not isinstance(boundary, VerificationBoundary):
        raise EvidenceError("independent VerificationBoundary required")
    session = InquirySession.load(session_path)
    ledger = EvidenceLedger.load(ledger_path, boundary)
    if session.graph.to_dict() != ledger.graph.to_dict():
        raise EvidenceError("inquiry checkpoint and signed evidence graph differ")
    # The controller requires object identity to prevent accidental trust
    # changes between independently materialized graph copies.
    session.graph = ledger.graph
    return session, AuthenticatedAdaptiveController(
        ledger=ledger, min_score=min_score, reserve_tokens=reserve_tokens,
    )
