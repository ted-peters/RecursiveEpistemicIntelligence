"""Challenge 10 trusted deterministic resolution of signed-review evidence states.

A general-purpose language model is not the authority for mechanically
defined evidence-state questions. The verified ledger determines that narrow
state; the model can draft an explanation, but it cannot overrule signed
admission, revocation, or source-group deduplication.

IMPORTANT: A signed reviewer decision authenticates approval metadata, NOT
the real-world truth of a claim, a scientific conclusion, or a model answer.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .evidence import EvidenceLedger, EvidenceError
from .models import EvidenceState, NodeKind, digest


@dataclass(frozen=True)
class SignedStateDecision:
    """Immutable exact-status result with an independently recomputable audit."""

    claim_id: str
    recorded_state: str
    supporting_evidence_ids: tuple[str, ...]
    opposing_evidence_ids: tuple[str, ...]
    supporting_source_groups: tuple[str, ...]
    opposing_source_groups: tuple[str, ...]
    excluded_links: tuple[tuple[str, str], ...]
    graph_audit_head: str
    evidence_audit_head: str
    review_receipts: int
    method: str = "rei1.3-trusted-signed-status-v1"

    def __post_init__(self) -> None:
        if self.recorded_state not in {x.value for x in EvidenceState}:
            raise EvidenceError("unrecognized signed evidence state")

    def to_dict(self) -> dict[str, Any]:
        body = {
            "method": self.method,
            "claim_id": self.claim_id,
            "recorded_evidence_state": self.recorded_state,
            "supporting_evidence_ids": list(self.supporting_evidence_ids),
            "opposing_evidence_ids": list(self.opposing_evidence_ids),
            "supporting_source_groups": list(self.supporting_source_groups),
            "opposing_source_groups": list(self.opposing_source_groups),
            "excluded_links": [list(e) for e in self.excluded_links],
            "graph_audit_head": self.graph_audit_head,
            "evidence_audit_head": self.evidence_audit_head,
            "review_receipts": self.review_receipts,
            "warning": (
                "Only an authenticated *review-admission state* was resolved; "
                "this is not verification that the proposition is true."
            ),
        }
        return {**body, "decision_sha256": digest(body)}


@dataclass(frozen=True)
class ModelProposalAudit:
    """Distinguish a model's provisional answer from the trusted ledger result."""

    proposal: str | None
    disposition: str
    trusted_state: str
    decision_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_proposal": self.proposal,
            "disposition": self.disposition,
            "trusted_recorded_state": self.trusted_state,
            "trusted_decision_sha256": self.decision_sha256,
            "warning": "A model proposal cannot override authenticated evidence admission.",
        }


def resolve_signed_state(ledger: EvidenceLedger, claim_id: str) -> SignedStateDecision:
    """Compute the four-state *recorded evidence status* without an LLM.

    The EvidenceLedger implementation checks reviewer signatures and current
    revocations before returning; unauthenticated graph validation labels are
    deliberately not used. Never accept a model-supplied ledger or key registry
    as a new trust authority.
    """
    if not isinstance(ledger, EvidenceLedger):
        raise EvidenceError("trusted signed evidence ledger required")
    if not isinstance(claim_id, str) or not claim_id.strip():
        raise EvidenceError("valid claim ID required")
    graph = ledger.graph
    if claim_id not in graph.nodes or graph.nodes[claim_id].kind not in (
        NodeKind.CLAIM, NodeKind.METHOD_CLAIM,
    ):
        raise EvidenceError("cannot resolve missing or nonclaim node")
    state = ledger.assess(claim_id)  # cryptographic review checks, fail closed
    return SignedStateDecision(
        claim_id=claim_id,
        recorded_state=state.state.value,
        supporting_evidence_ids=state.support_evidence,
        opposing_evidence_ids=state.attack_evidence,
        supporting_source_groups=state.support_sources,
        opposing_source_groups=state.attack_sources,
        excluded_links=state.ignored_edges,
        graph_audit_head=graph.audit_head,
        evidence_audit_head=ledger.audit_head,
        review_receipts=len(ledger.review_receipts),
    )


def audit_model_proposal(
    proposal: str | None, decision: SignedStateDecision,
) -> ModelProposalAudit:
    """Grade a model's structured response against the authenticated ledger.

    Only for questions whose requested answer is exactly the four-valued
    recorded evidence state. Other tasks need separate rules and evaluation.
    """
    if not isinstance(decision, SignedStateDecision):
        raise EvidenceError("trusted signed decision required")
    if proposal is not None and not isinstance(proposal, str):
        raise EvidenceError("proposal must be a string or null")
    normalized = proposal.strip().upper() if isinstance(proposal, str) else None
    if proposal is None:
        disposition = "abstained"
    elif normalized not in {x.value for x in EvidenceState}:
        disposition = "invalid"
    elif normalized == decision.recorded_state:
        disposition = "agrees"
    else:
        disposition = "contradicts"
    return ModelProposalAudit(
        proposal=proposal, disposition=disposition,
        trusted_state=decision.recorded_state,
        decision_sha256=decision.to_dict()["decision_sha256"],
    )
