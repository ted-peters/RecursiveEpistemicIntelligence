"""REI 1.1 experimental controller: selective, evidence-aware bounded inquiry.

This controller makes *workflow* decisions, not truth or probability estimates.
It reads the original REI graph's verified evidence assessment; provisional model
arguments are never counted as verified evidence. Its scores are preregisterable
heuristics, not learned utilities. External evidence must already have been
independently admitted through graph validation.

Opt-in only; the original REI 1.0 inquiry engine's scheduling is unchanged
when no controller is supplied.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from .models import EvidenceState

if TYPE_CHECKING:
    from .inquiry import InquirySession, PendingQuestion


@dataclass(frozen=True)
class AdaptiveDecision:
    """Auditable request for exactly one next question, or an explicit stop."""

    question_id: str | None
    stop_reason: str | None
    audit: dict[str, Any]


@dataclass(frozen=True)
class AdaptiveController:
    """Prioritize epistemic risk, with explicit call and token reserves.

    The evidence-state bonuses prefer checking contradictions or evidence
    gaps, but do not equate SUPPORT_ONLY with objective truth. Depth is a
    computational penalty. A score below min_score halts expansion while
    keeping all unresolved questions visible in the graph. Do not interpret
    this score as a calibrated probability or real-world expected value.
    """

    min_score: int = 10
    reserve_tokens: int = 320

    _BONUS = {
        EvidenceState.NEITHER: 3,
        EvidenceState.SUPPORT_ONLY: 1,
        EvidenceState.ATTACK_ONLY: 1,
        EvidenceState.BOTH: 7,
    }

    def __post_init__(self) -> None:
        if type(self.min_score) is not int or not 0 <= self.min_score <= 40:
            raise ValueError("min_score must be an integer from 0 to 40")
        if type(self.reserve_tokens) is not int or not 0 <= self.reserve_tokens <= 100000:
            raise ValueError("reserve_tokens must be a nonnegative integer")

    def decide(self, session: "InquirySession", eligible: tuple["PendingQuestion", ...],
               *, remaining_calls: int, remaining_tokens: int) -> AdaptiveDecision:
        if not eligible:
            raise ValueError("adaptive controller requires eligible questions")
        if type(remaining_calls) is not int or type(remaining_tokens) is not int:
            raise ValueError("remaining budgets must be exact integers")
        if remaining_calls < 1 or remaining_tokens < 0:
            raise ValueError("adaptive controller cannot exceed resource budgets")

        ranked = []
        for q in eligible:
            if q.id not in session.graph.nodes or q.target_id not in session.graph.nodes:
                raise ValueError("adaptive candidate missing from graph")
            assessment = session.graph.assess(q.target_id)
            # The original graph ignores provisional model-authored reasons.
            score = (2 * q.priority - 2 * q.depth + self._BONUS[assessment.state]
                     + (2 if assessment.ignored_edges else 0))
            ranked.append(((-score, q.depth, q.order, q.id), q, score, assessment))

        ranked.sort(key=lambda r: r[0])
        _, chosen, score, assessment = ranked[0]
        audit = {
            "policy": "rei1.1-selective-evidence-budget-v1",
            "graph_audit_head": session.graph.audit_head,
            "candidate_count": len(eligible),
            "highest_score": score,
            "score_threshold": self.min_score,
            "target_id": chosen.target_id,
            "target_evidence_state": assessment.state.value,
            "verified_support_source_count": len(assessment.support_sources),
            "verified_attack_source_count": len(assessment.attack_sources),
            "ignored_unverified_or_duplicate_edges": len(assessment.ignored_edges),
            "remaining_calls": remaining_calls,
            "remaining_tokens": remaining_tokens,
            "token_reserve": self.reserve_tokens,
            "note": "Heuristic workflow score; not probability, verified truth, or a model improvement claim.",
        }
        if remaining_tokens <= self.reserve_tokens:
            return AdaptiveDecision(None, "adaptive_token_reserve", audit)
        if score < self.min_score:
            return AdaptiveDecision(None, "adaptive_low_value", audit)
        return AdaptiveDecision(chosen.id, None, audit)
