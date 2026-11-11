"""In-memory typed multigraph with auditable events and conservative evidence semantics.

No neural model is involved: graph updates and assessments are deterministic.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping

from .models import (
    Assessment, Edge, EdgeKind, EvidenceState, Node, NodeKind, SourceKind,
    Validation, digest, require_utc,
)


class GraphError(ValueError):
    """Invalid graph edit or serialization."""


class CycleError(GraphError):
    """Proposed relation creates a cyclic justificatory dependency."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class EpistemicGraph:
    SCHEMA_VERSION = "rei0.graph.v1"
    _DEPENDENT_KINDS = {NodeKind.CLAIM, NodeKind.ARGUMENT, NodeKind.OBJECTION, NodeKind.METHOD_CLAIM}
    _CLAIM_LIKE = {NodeKind.CLAIM, NodeKind.ARGUMENT, NodeKind.METHOD_CLAIM}

    def __init__(self, method_version: str = "rei-0.1", *, max_nodes: int = 10_000,
                 max_edges: int = 30_000, clock: Callable[[], str] | None = None):
        if not isinstance(method_version, str) or not method_version.strip():
            raise GraphError("method version must be nonempty")
        if not isinstance(max_nodes, int) or isinstance(max_nodes, bool) or max_nodes <= 0:
            raise GraphError("max_nodes must be a positive integer")
        if not isinstance(max_edges, int) or isinstance(max_edges, bool) or max_edges <= 0:
            raise GraphError("max_edges must be a positive integer")
        self._method_version = method_version
        self._max_nodes = max_nodes
        self._max_edges = max_edges
        self._nodes: dict[str, Node] = {}
        self._edges: dict[str, Edge] = {}
        self._explored_questions: set[str] = set()
        self._events: list[dict[str, Any]] = []
        self._clock = clock or utc_now

    @property
    def method_version(self) -> str:
        return self._method_version

    @property
    def max_nodes(self) -> int:
        return self._max_nodes

    @property
    def max_edges(self) -> int:
        return self._max_edges

    @property
    def nodes(self) -> Mapping[str, Node]:
        return MappingProxyType(self._nodes)

    @property
    def edges(self) -> Mapping[str, Edge]:
        return MappingProxyType(self._edges)

    @property
    def explored_questions(self) -> frozenset[str]:
        return frozenset(self._explored_questions)

    @property
    def events(self) -> tuple[dict[str, Any], ...]:
        # Return independent copies: audit records must not be modified by callers.
        return tuple(json.loads(json.dumps(event)) for event in self._events)

    @property
    def audit_head(self) -> str:
        return self._events[-1]["event_hash"] if self._events else "0" * 64

    def _record(self, kind: str, payload: dict[str, Any]) -> None:
        record = {"sequence": len(self._events) + 1, "previous_hash": self.audit_head,
                  "kind": kind, "payload": payload}
        record["event_hash"] = digest(record)
        self._events.append(record)

    def add_node(self, node: Node) -> None:
        self._apply_add_node(node)
        self._record("add_node", node.to_dict())

    def _apply_add_node(self, node: Node) -> None:
        if node.validation != Validation.PENDING:
            raise GraphError("new nodes must begin pending and be independently reviewed")
        if node.id in self._nodes:
            raise GraphError(f"duplicate node ID: {node.id}")
        if len(self._nodes) >= self.max_nodes:
            raise GraphError("node budget exceeded")
        self._nodes[node.id] = node

    def add_edge(self, edge: Edge) -> None:
        self._apply_add_edge(edge)
        self._record("add_edge", edge.to_dict())

    def _apply_add_edge(self, edge: Edge) -> None:
        if edge.validation != Validation.PENDING:
            raise GraphError("new edges must begin pending and be independently reviewed")
        if edge.id in self._edges:
            raise GraphError(f"duplicate edge ID: {edge.id}")
        if len(self._edges) >= self.max_edges:
            raise GraphError("edge budget exceeded")
        if edge.source not in self._nodes or edge.target not in self._nodes:
            raise GraphError("edge endpoints must exist")
        if edge.method_version != self.method_version:
            raise GraphError("edge method_version must match this graph's active version")
        self._check_edge_types(edge)
        if self.would_create_cycle(edge):
            raise CycleError(f"justificatory cycle via {edge.source} -> {edge.target}")
        self._edges[edge.id] = edge

    def _check_edge_types(self, edge: Edge) -> None:
        a, b = self._nodes[edge.source].kind, self._nodes[edge.target].kind
        if edge.kind in {EdgeKind.SUPPORTS, EdgeKind.ATTACKS}:
            if a not in self._CLAIM_LIKE | {NodeKind.EVIDENCE, NodeKind.OBJECTION, NodeKind.TEST} \
                    or b not in self._CLAIM_LIKE:
                raise GraphError("supports/attacks require a reason or evidence -> claim-like target")
        elif edge.kind == EdgeKind.QUESTIONS:
            if a != NodeKind.OPEN_QUESTION or b not in self._CLAIM_LIKE:
                raise GraphError("questions requires open_question -> claim-like target")
        elif edge.kind == EdgeKind.DEPENDS_ON:
            if a not in self._DEPENDENT_KINDS or b not in self._CLAIM_LIKE | {NodeKind.EVIDENCE, NodeKind.TEST}:
                raise GraphError("depends_on requires a dependent assertion and a premise")
        elif edge.kind == EdgeKind.TESTS:
            if a != NodeKind.TEST or b not in self._CLAIM_LIKE:
                raise GraphError("tests requires test -> claim-like target")
        elif edge.kind == EdgeKind.REVISES:
            if a not in self._CLAIM_LIKE or b not in self._CLAIM_LIKE:
                raise GraphError("revises requires two claim-like nodes")
        elif edge.kind == EdgeKind.DERIVED_USING:
            if a not in self._CLAIM_LIKE or b != NodeKind.METHOD_CLAIM:
                raise GraphError("derived_using requires assertion -> method_claim")
        elif edge.kind == EdgeKind.DUPLICATES:
            if a != b or a not in {NodeKind.EVIDENCE, NodeKind.CLAIM}:
                raise GraphError("duplicates requires two evidence nodes or two claim nodes")
        if edge.source == edge.target and edge.kind in {EdgeKind.SUPPORTS, EdgeKind.DEPENDS_ON, EdgeKind.DUPLICATES}:
            raise CycleError("self-referential support/dependency/duplicate is not permitted")

    def _dependency_arc(self, edge: Edge) -> tuple[str, str] | None:
        # Canonical direction: dependent claim -> prerequisite.
        if edge.kind == EdgeKind.SUPPORTS:
            return edge.target, edge.source
        if edge.kind == EdgeKind.DEPENDS_ON:
            return edge.source, edge.target
        return None

    def would_create_cycle(self, edge: Edge) -> bool:
        """Check cycle across both supports and depends_on relationships."""
        arc = self._dependency_arc(edge)
        if arc is None:
            return False
        dependent, premise = arc
        if dependent == premise:
            return True
        adjacency: dict[str, set[str]] = {}
        for existing in self._edges.values():
            link = self._dependency_arc(existing)
            if link is not None:
                adjacency.setdefault(link[0], set()).add(link[1])
        stack = [premise]
        visited: set[str] = set()
        while stack:
            current = stack.pop()
            if current == dependent:
                return True
            if current not in visited:
                visited.add(current)
                stack.extend(sorted(adjacency.get(current, ()), reverse=True))
        return False

    def set_validation(self, entity: str, identifier: str, status: Validation,
                       *, verified_by: str, reason: str) -> None:
        timestamp = self._clock()
        require_utc(timestamp)
        payload = {"entity": entity, "id": identifier, "status": status.value,
                   "verified_by": verified_by, "reason": reason, "occurred_at": timestamp}
        self._apply_validation(payload)
        self._record("validation", payload)

    def _apply_validation(self, payload: dict[str, Any]) -> None:
        entity, identifier = payload["entity"], payload["id"]
        status = Validation(payload["status"])
        reviewer, reason = payload["verified_by"], payload["reason"]
        require_utc(payload["occurred_at"])
        if not isinstance(reviewer, str) or not reviewer.strip():
            raise GraphError("validation must name a reviewer")
        if not isinstance(reason, str) or not reason.strip():
            raise GraphError("validation must give a reason")
        collection = self._nodes if entity == "node" else self._edges if entity == "edge" else None
        if collection is None or identifier not in collection:
            raise GraphError("unknown entity or ID")
        current = collection[identifier]
        transitions = {Validation.PENDING: {Validation.VERIFIED, Validation.REJECTED},
                       Validation.VERIFIED: {Validation.REVOKED}}
        if status not in transitions.get(current.validation, set()):
            raise GraphError(f"disallowed validation transition {current.validation.value} -> {status.value}")
        if current.provenance.source_id == reviewer:
            raise GraphError("source cannot be its own declared reviewer")
        collection[identifier] = replace(current, validation=status, verified_by=reviewer)

    def _evidence_groups(self) -> dict[str, str]:
        """Resolve declared source groups and verified duplicate links."""
        evidence = {k: v for k, v in self._nodes.items() if v.kind == NodeKind.EVIDENCE}
        parent = {key: key for key in evidence}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: str, b: str) -> None:
            x, y = find(a), find(b)
            if x != y:
                parent[max(x, y)] = min(x, y)

        by_group: dict[str, str] = {}
        for identifier in sorted(evidence):
            group = evidence[identifier].provenance.source_group
            if group in by_group:
                union(identifier, by_group[group])
            else:
                by_group[group] = identifier
        for e in self._edges.values():
            if e.kind == EdgeKind.DUPLICATES and e.validation == Validation.VERIFIED \
                    and e.source in evidence and e.target in evidence:
                union(e.source, e.target)

        members: dict[str, list[str]] = {}
        for identifier in sorted(evidence):
            members.setdefault(find(identifier), []).append(identifier)
        labels = {root: min(evidence[x].provenance.source_group for x in ids)
                  for root, ids in members.items()}
        return {identifier: labels[find(identifier)] for identifier in evidence}

    def assess(self, claim_id: str) -> Assessment:
        if claim_id not in self._nodes or self._nodes[claim_id].kind not in self._CLAIM_LIKE:
            raise GraphError("assessment requires an existing claim-like node")
        groups = self._evidence_groups()
        by_polarity: dict[EdgeKind, dict[str, str]] = {EdgeKind.SUPPORTS: {}, EdgeKind.ATTACKS: {}}
        ignored: list[tuple[str, str]] = []
        for edge in sorted(self._edges.values(), key=lambda e: e.id):
            if edge.target != claim_id or edge.kind not in by_polarity:
                continue
            source = self._nodes[edge.source]
            reason = None
            if source.kind != NodeKind.EVIDENCE:
                reason = "argument_not_independent_evidence"
            elif edge.validation != Validation.VERIFIED:
                reason = "edge_not_verified"
            elif source.validation != Validation.VERIFIED:
                reason = "evidence_not_verified"
            elif source.provenance.source_kind == SourceKind.MODEL:
                reason = "model_output_not_external_evidence"
            else:
                group = groups[source.id]
                if group in by_polarity[edge.kind]:
                    reason = "dependent_or_duplicate_source"
                else:
                    by_polarity[edge.kind][group] = source.id
            if reason is not None:
                ignored.append((edge.id, reason))
        support = by_polarity[EdgeKind.SUPPORTS]
        attack = by_polarity[EdgeKind.ATTACKS]
        return Assessment(claim_id=claim_id, state=EvidenceState.from_bits(bool(support), bool(attack)),
                          support_evidence=tuple(support[k] for k in sorted(support)),
                          attack_evidence=tuple(attack[k] for k in sorted(attack)),
                          support_sources=tuple(sorted(support)), attack_sources=tuple(sorted(attack)),
                          ignored_edges=tuple(ignored), method_version=self.method_version)

    def explore_question(self, identifier: str, *, actor: str, note: str) -> None:
        """Mark a question investigated, NOT philosophically settled.

        Only an investigated question leaves the active inquiry frontier;
        any deeper questions remain open. This is a workflow record, not evidence.
        """
        payload = {"id": identifier, "actor": actor, "note": note, "occurred_at": self._clock()}
        self._apply_exploration(payload)
        self._record("explore_question", payload)

    def _apply_exploration(self, payload: dict[str, Any]) -> None:
        if set(payload) != {"id", "actor", "note", "occurred_at"}:
            raise GraphError("malformed exploration event")
        identifier = payload["id"]
        if identifier not in self._nodes or self._nodes[identifier].kind != NodeKind.OPEN_QUESTION:
            raise GraphError("unknown open question")
        if identifier in self._explored_questions:
            raise GraphError("question already explored")
        for field in ("actor", "note"):
            if not isinstance(payload[field], str) or not payload[field].strip():
                raise GraphError("exploration actor and note required")
        require_utc(payload["occurred_at"])
        self._explored_questions.add(identifier)

    def open_questions(self) -> tuple[Node, ...]:
        return tuple(sorted((n for n in self._nodes.values()
                            if n.kind == NodeKind.OPEN_QUESTION and n.id not in self._explored_questions),
                            key=lambda n: n.id))

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": self.SCHEMA_VERSION, "method_version": self.method_version,
                "max_nodes": self.max_nodes, "max_edges": self.max_edges,
                "events": json.loads(json.dumps(self._events))}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EpistemicGraph:
        if not isinstance(data, dict) or set(data) != {"schema_version", "method_version", "max_nodes", "max_edges", "events"}:
            raise GraphError("unexpected graph document keys")
        if data["schema_version"] != cls.SCHEMA_VERSION:
            raise GraphError("unsupported graph schema version")
        graph = cls(data["method_version"], max_nodes=data["max_nodes"], max_edges=data["max_edges"])
        if not isinstance(data["events"], list):
            raise GraphError("events must be a list")
        for sequence, record in enumerate(data["events"], start=1):
            if not isinstance(record, dict) or set(record) != {"sequence", "previous_hash", "kind", "payload", "event_hash"}:
                raise GraphError("malformed audit event")
            if type(record["sequence"]) is not int or record["sequence"] != sequence:
                raise GraphError("audit sequence invalid")
            if record["previous_hash"] != graph.audit_head:
                raise GraphError("broken audit chain")
            if digest({k: record[k] for k in ("sequence", "previous_hash", "kind", "payload")}) != record["event_hash"]:
                raise GraphError("audit event hash mismatch")
            kind, payload = record["kind"], record["payload"]
            try:
                if kind == "add_node":
                    obj = Node.from_dict(payload)
                    if obj.to_dict() != payload:
                        raise GraphError("malformed node payload")
                    graph._apply_add_node(obj)
                elif kind == "add_edge":
                    obj = Edge.from_dict(payload)
                    if obj.to_dict() != payload:
                        raise GraphError("malformed edge payload")
                    graph._apply_add_edge(obj)
                elif kind == "explore_question":
                    graph._apply_exploration(payload)
                elif kind == "validation":
                    if set(payload) != {"entity", "id", "status", "verified_by", "reason", "occurred_at"}:
                        raise GraphError("malformed validation payload")
                    graph._apply_validation(payload)
                else:
                    raise GraphError(f"unknown event kind: {kind}")
            except (KeyError, TypeError, ValueError) as exc:
                raise GraphError(f"invalid audit event {sequence}: {exc}") from exc
            graph._events.append(json.loads(json.dumps(record)))
        if graph.to_dict() != data:
            raise GraphError("graph content did not round-trip exactly")
        return graph

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                              encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> EpistemicGraph:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
