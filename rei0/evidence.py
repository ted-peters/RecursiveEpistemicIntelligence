"""REI-0.3: evidence submission, authenticated review, secure assessment & replay.

Model-generated text is never admitted as independently verified evidence. Graph
`set_validation` is a legacy, unauthenticated declaration and MUST NOT be used to
make trusted decisions. Use EvidenceLedger.assess(), which checks signed reviews.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Callable

from .graph import EpistemicGraph, GraphError, utc_now
from .models import (Assessment, Edge, EdgeKind, EvidenceState, Node, NodeKind,
                     Provenance, SourceKind, Validation, digest, require_utc)
from .review import ReviewError, ReviewIssuer, ReviewReceipt, VerificationBoundary, _hex_digest, _name


class EvidenceError(ValueError):
    """Invalid submission or ledger transition."""


@dataclass(frozen=True)
class EvidenceSubmission:
    submission_id: str
    evidence_id: str
    link_id: str
    claim_id: str
    artifact_sha256: str
    submitted_at: str

    def __post_init__(self) -> None:
        for key in ('submission_id', 'evidence_id', 'link_id', 'claim_id'):
            _name(getattr(self, key), key)
        _hex_digest(self.artifact_sha256, 'artifact_sha256')
        require_utc(self.submitted_at)

    def to_dict(self) -> dict[str, str]:
        return {'submission_id': self.submission_id, 'evidence_id': self.evidence_id,
                'link_id': self.link_id, 'claim_id': self.claim_id,
                'artifact_sha256': self.artifact_sha256, 'submitted_at': self.submitted_at}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvidenceSubmission:
        if not isinstance(data, dict) or set(data) != {
            'submission_id', 'evidence_id', 'link_id', 'claim_id', 'artifact_sha256', 'submitted_at'
        }:
            raise EvidenceError('invalid submission schema')
        return cls(**data)


def _stable_node(node: Node) -> dict[str, Any]:
    result = node.to_dict()
    result.pop('validation'); result.pop('verified_by')
    return result


def _stable_edge(edge: Edge) -> dict[str, Any]:
    result = edge.to_dict()
    result.pop('validation'); result.pop('verified_by')
    return result


class EvidenceLedger:
    SCHEMA_VERSION = 'rei0.evidence.v1'
    def __init__(self, graph: EpistemicGraph, boundary: VerificationBoundary,
                 *, clock: Callable[[], str] | None = None):
        if not isinstance(graph, EpistemicGraph) or not isinstance(boundary, VerificationBoundary):
            raise EvidenceError('graph and trusted VerificationBoundary required')
        self.graph = graph
        self._boundary = boundary
        self._clock = clock or utc_now
        self._submissions: dict[str, EvidenceSubmission] = {}
        self._reviews: dict[str, list[ReviewReceipt]] = {}
        self._events: list[dict[str, Any]] = []

    @property
    def audit_head(self) -> str:
        return self._events[-1]['event_hash'] if self._events else '0' * 64

    @property
    def submissions(self) -> tuple[EvidenceSubmission, ...]:
        return tuple(self._submissions[k] for k in sorted(self._submissions))

    @property
    def events(self) -> tuple[dict[str, Any], ...]:
        return tuple(json.loads(json.dumps(x)) for x in self._events)

    @property
    def review_receipts(self) -> tuple[ReviewReceipt, ...]:
        return tuple(r for k in sorted(self._reviews) for r in self._reviews[k])

    def _append(self, kind: str, payload: dict[str, Any]) -> None:
        record = {'sequence': len(self._events) + 1, 'previous_hash': self.audit_head,
                  'kind': kind, 'payload': payload}
        record['event_hash'] = digest(record)
        self._events.append(record)

    def _validate_submission(self, submission: EvidenceSubmission) -> None:
        if submission.evidence_id not in self.graph.nodes or submission.link_id not in self.graph.edges:
            raise EvidenceError('evidence or link is missing from graph')
        if submission.claim_id not in self.graph.nodes:
            raise EvidenceError('target claim missing from graph')
        n, e, c = (self.graph.nodes[submission.evidence_id],
                   self.graph.edges[submission.link_id], self.graph.nodes[submission.claim_id])
        if n.kind != NodeKind.EVIDENCE or c.kind not in EpistemicGraph._CLAIM_LIKE:
            raise EvidenceError('submission node or target type invalid')
        if e.source != n.id or e.target != c.id or e.kind not in (EdgeKind.SUPPORTS, EdgeKind.ATTACKS):
            raise EvidenceError('submission evidence relationship invalid')
        if e.method_version != self.graph.method_version:
            raise EvidenceError('review method version mismatch')
        if n.provenance != e.provenance:
            raise EvidenceError('link provenance differs from submitted evidence')

    def subject_digest(self, submission_id: str) -> str:
        s = self._submissions.get(submission_id)
        if s is None:
            raise EvidenceError('unknown submission ID')
        self._validate_submission(s)
        node, edge, claim = (self.graph.nodes[s.evidence_id], self.graph.edges[s.link_id],
                             self.graph.nodes[s.claim_id])
        return digest({'scope': 'rei0.evidence.subject.v1', 'submission': s.to_dict(),
                       'node': _stable_node(node), 'edge': _stable_edge(edge),
                       'target_claim': _stable_node(claim), 'method_version': self.graph.method_version})

    def submit(self, *, submission_id: str, evidence_id: str, claim_id: str,
               text: str, artifact_bytes: bytes, provenance: Provenance,
               polarity: EdgeKind, link_id: str | None = None) -> EvidenceSubmission:
        """Ingest caller-declared evidence, keep it PENDING until a signed review.

        artifact_bytes are hashed; they are not claimed to be authentic or true.
        Store original artifacts separately in controlled storage if required.
        """
        _name(submission_id, 'submission_id'); _name(evidence_id, 'evidence_id')
        _name(claim_id, 'claim_id')
        if submission_id in self._submissions:
            raise EvidenceError('duplicate submission ID')
        if not isinstance(text, str) or not text.strip() or len(text) > 50_000:
            raise EvidenceError('evidence text must be nonempty and <= 50000 characters')
        if not isinstance(artifact_bytes, bytes) or not artifact_bytes or len(artifact_bytes) > 2_000_000:
            raise EvidenceError('artifact must contain 1-2000000 bytes')
        if not isinstance(provenance, Provenance):
            raise EvidenceError('invalid provenance')
        if polarity not in (EdgeKind.SUPPORTS, EdgeKind.ATTACKS):
            raise EvidenceError('polarity must be supports or attacks')
        if claim_id not in self.graph.nodes or self.graph.nodes[claim_id].kind not in EpistemicGraph._CLAIM_LIKE:
            raise EvidenceError('claim target does not exist')
        link_id = link_id if link_id is not None else 'evidence-link:' + evidence_id
        _name(link_id, 'link_id')
        if evidence_id in self.graph.nodes or link_id in self.graph.edges:
            raise EvidenceError('evidence ID or link ID already in graph')
        if len(self.graph.nodes) >= self.graph.max_nodes or len(self.graph.edges) >= self.graph.max_edges:
            raise EvidenceError('graph resource budget exceeded')
        timestamp = self._clock()
        require_utc(timestamp)
        node = Node(evidence_id, NodeKind.EVIDENCE, text, provenance, timestamp)
        edge = Edge(link_id, evidence_id, claim_id, polarity, provenance, self.graph.method_version, timestamp)
        self.graph.add_node(node)
        # A fresh evidence node cannot create a support dependency cycle.
        self.graph.add_edge(edge)
        s = EvidenceSubmission(submission_id, evidence_id, link_id, claim_id,
                               sha256(artifact_bytes).hexdigest(), timestamp)
        self._submissions[submission_id] = s
        self._reviews[submission_id] = []
        self._append('submitted', s.to_dict())
        return s

    def _validate_receipt(self, receipt: ReviewReceipt) -> None:
        s = self._submissions.get(receipt.submission_id)
        if s is None:
            raise ReviewError('receipt references unknown submission')
        self._boundary.verify(receipt)
        if receipt.subject_digest != self.subject_digest(receipt.submission_id):
            raise ReviewError('receipt subject no longer matches evidence, provenance, or claim')
        previous = self._reviews[receipt.submission_id]
        prev_signature = previous[-1].signature if previous else '0' * 64
        if receipt.prior_signature != prev_signature or receipt.decision_index != len(previous) + 1:
            raise ReviewError('review sequence, prior signature, or replay is invalid')
        issued = datetime.fromisoformat(receipt.issued_at.replace('Z', '+00:00'))
        submitted = datetime.fromisoformat(s.submitted_at.replace('Z', '+00:00'))
        if issued < submitted:
            raise ReviewError('review timestamp precedes evidence submission')
        if previous and issued < datetime.fromisoformat(previous[-1].issued_at.replace('Z', '+00:00')):
            raise ReviewError('review timestamp precedes previous signed decision')
        prior_state = previous[-1].decision if previous else Validation.PENDING
        if receipt.decision not in {Validation.PENDING: {Validation.VERIFIED, Validation.REJECTED},
                                    Validation.VERIFIED: {Validation.REVOKED}}.get(prior_state, set()):
            raise ReviewError('invalid review state transition')
        source = self.graph.nodes[s.evidence_id].provenance
        if receipt.reviewer_id == source.source_id:
            raise ReviewError('evidence source cannot approve its own submission')
        if receipt.decision == Validation.VERIFIED and source.source_kind == SourceKind.MODEL:
            raise ReviewError('model-generated evidence is not independently admissible')

    def accept(self, receipt: ReviewReceipt) -> None:
        if not isinstance(receipt, ReviewReceipt):
            raise ReviewError('signed ReviewReceipt required')
        self._validate_receipt(receipt)
        self._reviews[receipt.submission_id].append(receipt)
        self._append('reviewed', receipt.to_dict())

    def issue_and_accept(self, issuer: ReviewIssuer, submission_id: str,
                         decision: Validation, reason: str) -> ReviewReceipt:
        """Convenience for a TRUSTED review process, never call from an LLM tool."""
        if not isinstance(issuer, ReviewIssuer) or not isinstance(decision, Validation):
            raise ReviewError('trusted issuer and Validation required')
        _name(reason, 'reason', 2000)
        prior = self._reviews.get(submission_id)
        if prior is None:
            raise ReviewError('unknown submission')
        at = self._clock()
        require_utc(at)
        receipt = issuer.issue(submission_id=submission_id,
                               subject_digest=self.subject_digest(submission_id),
                               decision=decision, reason=reason, issued_at=at,
                               decision_index=len(prior) + 1,
                               prior_signature=prior[-1].signature if prior else '0' * 64)
        self.accept(receipt)
        return receipt

    def _status(self, submission_id: str) -> Validation:
        reviews = self._reviews[submission_id]
        return reviews[-1].decision if reviews else Validation.PENDING

    def _check_all_receipts(self) -> None:
        # Recheck authentication against independent key material, even when loaded.
        for s in self._submissions.values():
            for receipt in self._reviews[s.submission_id]:
                self._boundary.verify(receipt)
                if receipt.subject_digest != self.subject_digest(s.submission_id):
                    raise ReviewError('graph content changed after review')

    def assess(self, claim_id: str) -> Assessment:
        """Trusted information status: only authenticated, current reviews count."""
        if claim_id not in self.graph.nodes or self.graph.nodes[claim_id].kind not in EpistemicGraph._CLAIM_LIKE:
            raise EvidenceError('assessment requires claim-like node')
        self._check_all_receipts()
        # Union equivalent source groups, exact reference IDs, and artifact/content hashes.
        accepted = [s for s in self.submissions if s.claim_id == claim_id and
                    self._status(s.submission_id) == Validation.VERIFIED]
        parent = {s.submission_id: s.submission_id for s in accepted}
        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        def union(a: str, b: str) -> None:
            x,y = find(a), find(b)
            if x != y:
                parent[max(x,y)] = min(x,y)
        seen: dict[tuple[str,str], str] = {}
        for s in accepted:
            n = self.graph.nodes[s.evidence_id]
            identity = (('group', n.provenance.source_group),
                        ('reference', n.provenance.reference),
                        ('artifact', s.artifact_sha256),
                        ('content', sha256(n.text.encode('utf-8')).hexdigest()))
            for marker in identity:
                if marker in seen:
                    union(s.submission_id, seen[marker])
                else:
                    seen[marker] = s.submission_id
        labels: dict[str, str] = {}
        for s in accepted:
            representative = find(s.submission_id)
            group = self.graph.nodes[s.evidence_id].provenance.source_group
            labels[representative] = min(group, labels.get(representative, group))
        by_polarity: dict[EdgeKind, dict[str,str]] = {EdgeKind.SUPPORTS: {}, EdgeKind.ATTACKS: {}}
        ignored: list[tuple[str,str]] = []
        for s in self.submissions:
            if s.claim_id != claim_id:
                continue
            status = self._status(s.submission_id)
            if status != Validation.VERIFIED:
                ignored.append((s.link_id, f'not_authenticated_verified:{status.value}'))
                continue
            group = labels[find(s.submission_id)]
            polarity = self.graph.edges[s.link_id].kind
            if group in by_polarity[polarity]:
                ignored.append((s.link_id, 'dependent_or_duplicate_source'))
            else:
                by_polarity[polarity][group] = s.evidence_id
        supports, attacks = by_polarity[EdgeKind.SUPPORTS], by_polarity[EdgeKind.ATTACKS]
        return Assessment(claim_id, EvidenceState.from_bits(bool(supports), bool(attacks)),
                          tuple(supports[k] for k in sorted(supports)),
                          tuple(attacks[k] for k in sorted(attacks)),
                          tuple(sorted(supports)), tuple(sorted(attacks)), tuple(ignored),
                          method_version=self.graph.method_version)

    def to_dict(self) -> dict[str, Any]:
        return {'schema_version': self.SCHEMA_VERSION, 'graph': self.graph.to_dict(),
                'events': json.loads(json.dumps(self._events))}

    @classmethod
    def from_dict(cls, document: dict[str, Any], boundary: VerificationBoundary,
                  *, clock: Callable[[], str] | None = None) -> EvidenceLedger:
        if not isinstance(document, dict) or set(document) != {'schema_version', 'graph', 'events'} \
           or document.get('schema_version') != cls.SCHEMA_VERSION or not isinstance(document['events'], list):
            raise EvidenceError('invalid evidence ledger schema')
        graph = EpistemicGraph.from_dict(document['graph'])
        ledger = cls(graph, boundary, clock=clock)
        for index, event in enumerate(document['events'], start=1):
            if not isinstance(event, dict) or set(event) != {'sequence','previous_hash','kind','payload','event_hash'}:
                raise EvidenceError('malformed evidence event')
            if type(event['sequence']) is not int or event['sequence'] != index or event['previous_hash'] != ledger.audit_head:
                raise EvidenceError('evidence event order or history is invalid')
            if digest({k:event[k] for k in ('sequence','previous_hash','kind','payload')}) != event['event_hash']:
                raise EvidenceError('evidence event hash mismatch')
            if event['kind'] == 'submitted':
                s = EvidenceSubmission.from_dict(event['payload'])
                if s.submission_id in ledger._submissions:
                    raise EvidenceError('duplicate submission in audit history')
                ledger._validate_submission(s)
                ledger._submissions[s.submission_id] = s
                ledger._reviews[s.submission_id] = []
            elif event['kind'] == 'reviewed':
                receipt = ReviewReceipt.from_dict(event['payload'])
                ledger._validate_receipt(receipt)
                ledger._reviews[receipt.submission_id].append(receipt)
            else:
                raise EvidenceError('unknown evidence event kind')
            ledger._events.append(json.loads(json.dumps(event)))
        ledger._check_all_receipts()
        if ledger.to_dict() != document:
            raise EvidenceError('ledger cannot round-trip exactly')
        return ledger

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False, indent=2) + '\n',
                              encoding='utf-8')

    @classmethod
    def load(cls, path: str | Path, boundary: VerificationBoundary,
             *, clock: Callable[[], str] | None = None) -> EvidenceLedger:
        return cls.from_dict(json.loads(Path(path).read_text(encoding='utf-8')), boundary, clock=clock)
