"""Typed, immutable objects for the REI-0 epistemic graph."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
from typing import Any
import json
from datetime import datetime


def canonical_json(value: Any) -> str:
    """Stable UTF-8 serialization for event hashes (not a digital signature)."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def require_utc(value: str) -> None:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("timestamp must be an ISO 8601 UTC string ending in Z")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid timestamp") from exc
    if parsed.utcoffset().total_seconds() != 0:
        raise ValueError("timestamp must be UTC")


class NodeKind(str, Enum):
    CLAIM = "claim"
    EVIDENCE = "evidence"
    ARGUMENT = "argument"
    OBJECTION = "objection"
    METHOD_CLAIM = "method_claim"
    TEST = "test"
    OPEN_QUESTION = "open_question"


class EdgeKind(str, Enum):
    SUPPORTS = "supports"
    ATTACKS = "attacks"
    DEPENDS_ON = "depends_on"
    TESTS = "tests"
    REVISES = "revises"
    DERIVED_USING = "derived_using"
    DUPLICATES = "duplicates"
    QUESTIONS = "questions"


class SourceKind(str, Enum):
    EXTERNAL = "external"
    HUMAN = "human"
    MODEL = "model"
    SYSTEM = "system"


class Validation(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    REVOKED = "revoked"


class EvidenceState(str, Enum):
    NEITHER = "NEITHER"
    SUPPORT_ONLY = "SUPPORT_ONLY"
    ATTACK_ONLY = "ATTACK_ONLY"
    BOTH = "BOTH"

    @classmethod
    def from_bits(cls, support: bool, attack: bool) -> EvidenceState:
        return {
            (False, False): cls.NEITHER,
            (True, False): cls.SUPPORT_ONLY,
            (False, True): cls.ATTACK_ONLY,
            (True, True): cls.BOTH,
        }[(bool(support), bool(attack))]


@dataclass(frozen=True)
class Provenance:
    """Declaration of origin, not cryptographic proof of authentic evidence.

    source_group indicates dependence: two observations from the same underlying
    source may be separate graph nodes but never earn two independent credits.
    """
    source_id: str
    source_kind: SourceKind
    source_group: str
    reference: str
    observed_at: str

    def __post_init__(self) -> None:
        if any(not isinstance(v, str) or not v.strip() for v in
               (self.source_id, self.source_group, self.reference)):
            raise ValueError("provenance fields must be nonempty strings")
        if not isinstance(self.source_kind, SourceKind):
            raise TypeError("source_kind must be SourceKind")
        require_utc(self.observed_at)

    @property
    def fingerprint(self) -> str:
        return digest(self.to_dict())

    def to_dict(self) -> dict[str, str]:
        return {
            "source_id": self.source_id,
            "source_kind": self.source_kind.value,
            "source_group": self.source_group,
            "reference": self.reference,
            "observed_at": self.observed_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Provenance:
        return cls(source_id=data["source_id"], source_kind=SourceKind(data["source_kind"]),
                   source_group=data["source_group"], reference=data["reference"],
                   observed_at=data["observed_at"])


@dataclass(frozen=True)
class Node:
    id: str
    kind: NodeKind
    text: str
    provenance: Provenance
    created_at: str
    validation: Validation = Validation.PENDING
    verified_by: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("node ID must be nonempty")
        if not isinstance(self.kind, NodeKind):
            raise TypeError("kind must be NodeKind")
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("node text must be nonempty")
        if not isinstance(self.provenance, Provenance):
            raise TypeError("provenance must be Provenance")
        if not isinstance(self.validation, Validation):
            raise TypeError("validation must be Validation")
        require_utc(self.created_at)
        if self.validation != Validation.PENDING:
            if not self.verified_by or not self.verified_by.strip():
                raise ValueError("decided validation must name a reviewer")
        elif self.verified_by is not None:
            raise ValueError("pending node cannot have reviewer")

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind.value, "text": self.text,
                "provenance": self.provenance.to_dict(), "created_at": self.created_at,
                "validation": self.validation.value, "verified_by": self.verified_by}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Node:
        return cls(id=data["id"], kind=NodeKind(data["kind"]), text=data["text"],
                   provenance=Provenance.from_dict(data["provenance"]), created_at=data["created_at"],
                   validation=Validation(data.get("validation", "pending")), verified_by=data.get("verified_by"))


@dataclass(frozen=True)
class Edge:
    id: str
    source: str
    target: str
    kind: EdgeKind
    provenance: Provenance
    method_version: str
    created_at: str
    validation: Validation = Validation.PENDING
    verified_by: str | None = None

    def __post_init__(self) -> None:
        if any(not isinstance(v, str) or not v.strip() for v in
               (self.id, self.source, self.target, self.method_version)):
            raise ValueError("edge identifier and endpoints/method version must be nonempty")
        if not isinstance(self.kind, EdgeKind):
            raise TypeError("kind must be EdgeKind")
        if not isinstance(self.provenance, Provenance):
            raise TypeError("provenance must be Provenance")
        if not isinstance(self.validation, Validation):
            raise TypeError("validation must be Validation")
        require_utc(self.created_at)
        if self.validation != Validation.PENDING:
            if not self.verified_by or not self.verified_by.strip():
                raise ValueError("decided validation must name a reviewer")
        elif self.verified_by is not None:
            raise ValueError("pending edge cannot have reviewer")

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "source": self.source, "target": self.target,
                "kind": self.kind.value, "provenance": self.provenance.to_dict(),
                "method_version": self.method_version, "created_at": self.created_at,
                "validation": self.validation.value, "verified_by": self.verified_by}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Edge:
        return cls(id=data["id"], source=data["source"], target=data["target"],
                   kind=EdgeKind(data["kind"]), provenance=Provenance.from_dict(data["provenance"]),
                   method_version=data["method_version"], created_at=data["created_at"],
                   validation=Validation(data.get("validation", "pending")), verified_by=data.get("verified_by"))


@dataclass(frozen=True)
class Assessment:
    claim_id: str
    state: EvidenceState
    support_evidence: tuple[str, ...] = field(default_factory=tuple)
    attack_evidence: tuple[str, ...] = field(default_factory=tuple)
    support_sources: tuple[str, ...] = field(default_factory=tuple)
    attack_sources: tuple[str, ...] = field(default_factory=tuple)
    ignored_edges: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    method_version: str = "rei-0.1"
    confidence: float | None = None  # Not calibrated in REI-0

    def to_dict(self) -> dict[str, Any]:
        return {"claim_id": self.claim_id, "state": self.state.value,
                "support_evidence": list(self.support_evidence),
                "attack_evidence": list(self.attack_evidence),
                "support_sources": list(self.support_sources), "attack_sources": list(self.attack_sources),
                "ignored_edges": [{"edge_id": k, "reason": v} for k, v in self.ignored_edges],
                "method_version": self.method_version, "confidence": self.confidence}
