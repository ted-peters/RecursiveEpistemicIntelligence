"""Bounded, inspectable recursive inquiry. All model output remains unverified.

A philosophical challenge remains open even after the workflow explores it; this
engine only records which work items have been *investigated*. No inference
from arguments to verified evidence is performed.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import time
from typing import Any, Callable, Protocol

from .graph import EpistemicGraph, GraphError, utc_now
from .models import Edge, EdgeKind, Node, NodeKind, Provenance, SourceKind, digest


class InquiryError(ValueError):
    """A malformed model result, invalid checkpoint, or inquiry configuration."""


def _string(value: Any, name: str, max_len: int = 1000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > max_len:
        raise InquiryError(f"{name} must be nonempty text of at most {max_len} characters")
    return value.strip()


def _keys(value: Any, required: set[str], optional: set[str] = frozenset()) -> dict:
    if not isinstance(value, dict) or not required.issubset(value) or set(value) - required - optional:
        raise InquiryError(f"expected fields {sorted(required)}, optional {sorted(optional)}")
    return value


def _list_text(value: Any, field_name: str, maximum: int) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > maximum:
        raise InquiryError(f"{field_name} must be a list of at most {maximum} items")
    return tuple(_string(x, field_name, 600) for x in value)


@dataclass(frozen=True)
class QuestionDraft:
    text: str
    target: str = "claim"  # claim or the first reason created by this expansion
    priority: int = 5      # bounded heuristic, never treated as calibrated utility

    @classmethod
    def parse(cls, value: dict[str, Any]) -> QuestionDraft:
        data = _keys(value, {"text"}, {"target", "priority"})
        target = data.get("target", "claim")
        priority = data.get("priority", 5)
        if target not in ("claim", "reason"):
            raise InquiryError("question target must be claim or reason")
        if type(priority) is not int or not (0 <= priority <= 10):
            raise InquiryError("question priority must be an integer between 0 and 10")
        return cls(_string(data["text"], "question", 400), target, priority)


@dataclass(frozen=True)
class InitialDraft:
    claim: str
    questions: tuple[QuestionDraft, ...]

    @classmethod
    def parse(cls, value: dict[str, Any]) -> InitialDraft:
        data = _keys(value, {"claim", "questions"})
        questions = data["questions"]
        if not isinstance(questions, list) or not (1 <= len(questions) <= 4):
            raise InquiryError("initial questions must contain 1–4 items")
        q = tuple(QuestionDraft.parse(x) for x in questions)
        if any(x.target != "claim" for x in q):
            raise InquiryError("initial questions must target claim")
        return cls(_string(data["claim"], "claim", 800), q)


@dataclass(frozen=True)
class ExpansionDraft:
    reasons: tuple[str, ...]
    objections: tuple[str, ...]
    followups: tuple[QuestionDraft, ...]
    note: str

    @classmethod
    def parse(cls, value: dict[str, Any]) -> ExpansionDraft:
        data = _keys(value, {"reasons", "objections", "followups", "note"})
        reasons = _list_text(data["reasons"], "reasons", 3)
        objections = _list_text(data["objections"], "objections", 3)
        followups = data["followups"]
        if not isinstance(followups, list) or len(followups) > 4:
            raise InquiryError("followups must be a list of at most four questions")
        parsed = tuple(QuestionDraft.parse(x) for x in followups)
        if any(q.target == "reason" for q in parsed) and not reasons:
            raise InquiryError("follow-up requires a reason that was not provided")
        return cls(reasons, objections, parsed, _string(data["note"], "note", 600))


@dataclass(frozen=True)
class ModelTurn:
    payload: dict[str, Any]
    tokens_used: int

    def __post_init__(self) -> None:
        if not isinstance(self.payload, dict):
            raise InquiryError("model payload must be a JSON object")
        if type(self.tokens_used) is not int or self.tokens_used < 0:
            raise InquiryError("model usage must be a nonnegative integer")


class InquiryModel(Protocol):
    name: str

    def initial(self, question: str, *, max_output_tokens: int, timeout: float) -> ModelTurn: ...

    def expand(self, context: dict[str, Any], *, ordinal: int,
               max_output_tokens: int, timeout: float) -> ModelTurn: ...


@dataclass(frozen=True)
class InquiryLimits:
    max_steps: int = 4
    max_depth: int = 3
    max_model_calls: int = 6
    max_tokens: int = 6000
    max_seconds: float = 30.0
    max_questions: int = 20
    max_nodes: int = 120
    max_edges: int = 180
    max_output_tokens: int = 384

    def __post_init__(self) -> None:
        for name in ("max_steps", "max_depth", "max_model_calls", "max_tokens", "max_questions",
                     "max_nodes", "max_edges", "max_output_tokens"):
            value = getattr(self, name)
            if type(value) is not int or value < (0 if name == "max_depth" else 1):
                raise InquiryError(f"{name} must be a positive integer (depth may be zero)")
        if not isinstance(self.max_seconds, (float, int)) or isinstance(self.max_seconds, bool) or not (0 < self.max_seconds <= 3600):
            raise InquiryError("max_seconds must be between 0 and 3600")


@dataclass(frozen=True)
class PendingQuestion:
    id: str
    target_id: str
    depth: int
    priority: int
    order: int

    @classmethod
    def parse(cls, data: Any) -> PendingQuestion:
        _keys(data, {"id", "target_id", "depth", "priority", "order"})
        for field_name in ("depth", "priority", "order"):
            if type(data[field_name]) is not int or data[field_name] < 0:
                raise InquiryError("pending queue has invalid numeric field")
        if data["priority"] > 10:
            raise InquiryError("priority out of range")
        return cls(_string(data["id"], "id", 80), _string(data["target_id"], "target_id", 80),
                   data["depth"], data["priority"], data["order"])


@dataclass
class InquirySession:
    question: str
    root_id: str
    graph: EpistemicGraph
    queue: list[PendingQuestion]
    next_id: int
    next_order: int
    steps: int = 0
    model_calls: int = 0
    tokens_used: int = 0
    trace: list[dict[str, Any]] = field(default_factory=list)
    stop_reason: str = "not_started"

    def _payload(self) -> dict[str, Any]:
        return {"schema_version": "rei0.inquiry.v1", "question": self.question,
                "root_id": self.root_id, "graph": self.graph.to_dict(),
                "queue": [asdict(q) for q in self.queue], "next_id": self.next_id,
                "next_order": self.next_order, "steps": self.steps,
                "model_calls": self.model_calls, "tokens_used": self.tokens_used,
                "trace": self.trace, "stop_reason": self.stop_reason}

    def to_dict(self) -> dict[str, Any]:
        payload = self._payload()
        return {**payload, "checkpoint_hash": digest(payload)}

    @classmethod
    def from_dict(cls, document: dict[str, Any]) -> InquirySession:
        if not isinstance(document, dict) or "checkpoint_hash" not in document:
            raise InquiryError("checkpoint missing checksum")
        payload = {k: v for k, v in document.items() if k != "checkpoint_hash"}
        needed = {"schema_version", "question", "root_id", "graph", "queue", "next_id", "next_order",
                  "steps", "model_calls", "tokens_used", "trace", "stop_reason"}
        _keys(payload, needed)
        if digest(payload) != document["checkpoint_hash"]:
            raise InquiryError("checkpoint checksum mismatch")
        if payload["schema_version"] != "rei0.inquiry.v1":
            raise InquiryError("checkpoint schema unsupported")
        graph = EpistemicGraph.from_dict(payload["graph"])
        root = payload["root_id"]
        if root not in graph.nodes or graph.nodes[root].kind != NodeKind.CLAIM:
            raise InquiryError("checkpoint root claim missing")
        if not isinstance(payload["queue"], list) or not isinstance(payload["trace"], list):
            raise InquiryError("checkpoint queue or trace malformed")
        queue = [PendingQuestion.parse(q) for q in payload["queue"]]
        if len({q.id for q in queue}) != len(queue):
            raise InquiryError("duplicate pending question")
        if {q.id for q in queue} != {q.id for q in graph.open_questions()}:
            raise InquiryError("pending queue does not match unresolved graph frontier")
        for q in queue:
            if q.id not in graph.nodes or graph.nodes[q.id].kind != NodeKind.OPEN_QUESTION or q.id in graph.explored_questions:
                raise InquiryError("checkpoint queue references an invalid or explored question")
            if not any(e.kind == EdgeKind.QUESTIONS and e.source == q.id and e.target == q.target_id
                       for e in graph.edges.values()):
                raise InquiryError("question/target relationship missing")
        for name in ("next_id", "next_order", "steps", "model_calls", "tokens_used"):
            if type(payload[name]) is not int or payload[name] < 0:
                raise InquiryError("invalid checkpoint counters")
        if payload["next_id"] < 1 or payload["next_order"] < len(queue):
            raise InquiryError("invalid checkpoint sequencing")
        if payload["steps"] != len(graph.explored_questions):
            raise InquiryError("step count does not match explored graph questions")
        if payload["steps"] >= payload["model_calls"] or not isinstance(payload["stop_reason"], str):
            raise InquiryError("invalid checkpoint progress")
        _string(payload["question"], "question", 3000)
        # The checkpoint is an experimental integrity check, not an authenticated record.
        return cls(payload["question"], root, graph, queue, payload["next_id"], payload["next_order"],
                   payload["steps"], payload["model_calls"], payload["tokens_used"],
                   payload["trace"], payload["stop_reason"])

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), sort_keys=True, indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> InquirySession:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def report(self) -> dict[str, Any]:
        claim = self.graph.nodes[self.root_id]
        return {"question": self.question, "root_claim": {"id": claim.id, "text": claim.text,
                "validation": claim.validation.value}, "evidence_assessment": self.graph.assess(self.root_id).to_dict(),
                "reason_nodes": [{"id": n.id, "text": n.text, "validation": n.validation.value}
                                 for n in self.graph.nodes.values() if n.kind == NodeKind.ARGUMENT],
                "objection_nodes": [{"id": n.id, "text": n.text, "validation": n.validation.value}
                                    for n in self.graph.nodes.values() if n.kind == NodeKind.OBJECTION],
                "open_frontier": [{"id": q.id, "target_id": q.target_id, "depth": q.depth,
                                   "question": self.graph.nodes[q.id].text, "priority": q.priority}
                                  for q in sorted(self.queue, key=lambda q: (-q.priority, q.depth, q.order))],
                "steps": self.steps, "model_calls": self.model_calls,
                "reported_tokens_used": self.tokens_used, "stop_reason": self.stop_reason,
                "graph_audit_head": self.graph.audit_head,
                "trace": self.trace,
                "warning": "All model arguments are provisional. No real-world evidence or truth verification occurs."}


def _normal(text: str) -> str:
    return " ".join(text.casefold().split())


class InquiryEngine:
    def __init__(self, model: InquiryModel, limits: InquiryLimits | None = None,
                 *, clock: Callable[[], str] = utc_now,
                 monotonic: Callable[[], float] = time.monotonic):
        self.model = model
        self.limits = limits or InquiryLimits()
        self.clock = clock
        self.monotonic = monotonic

    def _origin(self, tag: str) -> Provenance:
        source = _string(self.model.name, "model name", 80)
        return Provenance(source, SourceKind.MODEL, source, f"model-output://{source}/{tag}", self.clock())

    def _add(self, session: InquirySession, kind: NodeKind, text: str) -> str:
        identifier = f"{kind.value}-{session.next_id:05d}"
        session.next_id += 1
        session.graph.add_node(Node(identifier, kind, text, self._origin(identifier), self.clock()))
        return identifier

    def _edge(self, session: InquirySession, source: str, target: str, kind: EdgeKind) -> None:
        identifier = f"edge-{session.next_id:05d}"
        session.next_id += 1
        session.graph.add_edge(Edge(identifier, source, target, kind,
                                    self._origin(identifier), session.graph.method_version, self.clock()))

    def _questions(self, session: InquirySession, drafts: tuple[QuestionDraft, ...],
                   target_id: str, reason_id: str | None, depth: int) -> int:
        existing = {( _normal(session.graph.nodes[e.source].text), e.target)
                    for e in session.graph.edges.values() if e.kind == EdgeKind.QUESTIONS}
        created = 0
        for draft in drafts:
            target = reason_id if draft.target == "reason" else target_id
            if target is None:
                raise InquiryError("question targets a missing reason")
            key = (_normal(draft.text), target)
            if key in existing:
                continue
            existing.add(key)
            qid = self._add(session, NodeKind.OPEN_QUESTION, draft.text)
            self._edge(session, qid, target, EdgeKind.QUESTIONS)
            session.queue.append(PendingQuestion(qid, target, depth, draft.priority, session.next_order))
            session.next_order += 1
            created += 1
        return created

    def _preflight(self, session: InquirySession, num_nodes: int, num_edges: int) -> bool:
        return len(session.graph.nodes) + num_nodes <= min(session.graph.max_nodes, self.limits.max_nodes) \
            and len(session.graph.edges) + num_edges <= min(session.graph.max_edges, self.limits.max_edges)

    def _call_budget(self, session: InquirySession, started: float) -> tuple[str | None, int, float]:
        if session.model_calls >= self.limits.max_model_calls:
            return "model_call_budget", 0, 0
        if session.tokens_used >= self.limits.max_tokens:
            return "token_budget", 0, 0
        remaining = self.limits.max_seconds - (self.monotonic() - started)
        if remaining <= 0:
            return "time_budget", 0, 0
        return None, min(self.limits.max_output_tokens, self.limits.max_tokens - session.tokens_used), remaining

    def _start(self, question: str, started: float) -> InquirySession:
        question = _string(question, "input question", 3000)
        if self.limits.max_model_calls < 1:
            raise InquiryError("initial proposal requires one model call")
        remaining = self.limits.max_seconds - (self.monotonic() - started)
        if remaining <= 0:
            raise InquiryError("no time remains for initial proposal")
        turn = self.model.initial(question, max_output_tokens=min(self.limits.max_output_tokens, self.limits.max_tokens),
                                  timeout=remaining)
        draft = InitialDraft.parse(turn.payload)
        if turn.tokens_used > self.limits.max_tokens:
            raise InquiryError("initial model response exceeded token budget")
        if self.monotonic() - started > self.limits.max_seconds:
            raise InquiryError("initial model response exceeded time budget")
        graph = EpistemicGraph("rei-0.2", max_nodes=self.limits.max_nodes,
                               max_edges=self.limits.max_edges, clock=self.clock)
        session = InquirySession(question, "", graph, [], next_id=1, next_order=0,
                                 tokens_used=turn.tokens_used, model_calls=1)
        needed = 1 + len(draft.questions)
        if not self._preflight(session, needed, len(draft.questions)) or len(draft.questions) > self.limits.max_questions:
            raise InquiryError("initial graph or question budget too small")
        session.root_id = self._add(session, NodeKind.CLAIM, draft.claim)
        self._questions(session, draft.questions, session.root_id, None, 0)
        session.trace.append({"event": "initial_proposal", "claim_id": session.root_id,
                              "questions_created": len(session.queue), "tokens_used": turn.tokens_used})
        return session

    def run(self, question: str | None = None, *, resume: InquirySession | None = None) -> InquirySession:
        started = self.monotonic()
        if resume is None:
            if question is None:
                raise InquiryError("question required for a new inquiry")
            session = self._start(question, started)
        else:
            if question is not None and question != resume.question:
                raise InquiryError("cannot change the question when resuming")
            session = resume
            # Replay restores data, not the injected clock; rebind for this run.
            session.graph._clock = self.clock
            if session.graph.method_version != "rei-0.2":
                raise InquiryError("incompatible inquiry graph version")
            if len(session.queue) > self.limits.max_questions:
                raise InquiryError("loaded inquiry exceeds question budget")
        session.stop_reason = "running"
        while True:
            if not session.queue:
                session.stop_reason = "frontier_exhausted"
                break
            if session.steps >= self.limits.max_steps:
                session.stop_reason = "step_budget"
                break
            if len(session.queue) > self.limits.max_questions:
                session.stop_reason = "question_budget"
                break
            reason, tokens_left, time_left = self._call_budget(session, started)
            if reason:
                session.stop_reason = reason
                break
            eligible = [q for q in session.queue if q.depth < self.limits.max_depth]
            if not eligible:
                session.stop_reason = "depth_budget"
                break
            current = min(eligible, key=lambda q: (-q.priority, q.depth, q.order))
            context = {"question": session.question, "claim": session.graph.nodes[session.root_id].text,
                       "challenge": session.graph.nodes[current.id].text,
                       "target": session.graph.nodes[current.target_id].text, "depth": current.depth,
                       "arguments": [n.text for n in session.graph.nodes.values() if n.kind == NodeKind.ARGUMENT][-6:],
                       "objections": [n.text for n in session.graph.nodes.values() if n.kind == NodeKind.OBJECTION][-6:]}
            try:
                turn = self.model.expand(context, ordinal=session.steps,
                                         max_output_tokens=tokens_left, timeout=time_left)
                draft = ExpansionDraft.parse(turn.payload)
            except (InquiryError, OSError, ValueError) as exc:
                session.stop_reason = "model_error"
                session.trace.append({"event": "model_error", "question_id": current.id,
                                      "error_type": type(exc).__name__})
                break
            session.model_calls += 1
            session.tokens_used += turn.tokens_used
            if self.monotonic() - started > self.limits.max_seconds:
                session.stop_reason = "time_budget"
                session.trace.append({"event": "time_overrun", "question_id": current.id})
                break  # Discard late model output, keep question open
            if session.tokens_used > self.limits.max_tokens:
                session.stop_reason = "reported_token_overrun"
                session.trace.append({"event": "token_overrun", "question_id": current.id})
                break  # Do not incorporate an over-budget response
            if not draft.reasons and not draft.objections and not draft.followups:
                session.stop_reason = "no_progress"
                session.trace.append({"event": "no_progress", "question_id": current.id})
                break
            # Conservative preflight: count every generated question, even if later deduplicated.
            nodes = len(draft.reasons) + len(draft.objections) + len(draft.followups)
            if not self._preflight(session, nodes, nodes):
                session.stop_reason = "graph_budget"
                break
            if len(session.queue) - 1 + len(draft.followups) > self.limits.max_questions:
                session.stop_reason = "question_budget"
                break
            first_reason = None
            for reasoning in draft.reasons:
                id_ = self._add(session, NodeKind.ARGUMENT, reasoning)
                first_reason = first_reason or id_
                self._edge(session, id_, current.target_id, EdgeKind.SUPPORTS)
            for objection in draft.objections:
                id_ = self._add(session, NodeKind.OBJECTION, objection)
                self._edge(session, id_, current.target_id, EdgeKind.ATTACKS)
            created = self._questions(session, draft.followups, current.target_id, first_reason, current.depth + 1)
            session.graph.explore_question(current.id, actor="inquiry_controller",
                                           note="Investigated; arguments remain provisional and may generate new questions")
            session.queue.remove(current)
            session.steps += 1
            session.trace.append({"event": "challenge_investigated", "step": session.steps,
                                  "question_id": current.id, "target_id": current.target_id,
                                  "depth": current.depth, "reason_count": len(draft.reasons),
                                  "objection_count": len(draft.objections),
                                  "new_questions": created, "tokens_used": turn.tokens_used,
                                  "note": draft.note})
        return session
