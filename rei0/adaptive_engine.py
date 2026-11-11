"""REI 1.1 opt-in engine. Archived InquiryEngine remains unchanged."""
from __future__ import annotations
import time
from .adaptive import AdaptiveController
from .graph import utc_now
from .inquiry import InquiryEngine, InquiryError, InquiryLimits, InquirySession, ExpansionDraft
from .models import NodeKind, EdgeKind


class AdaptiveInquiryEngine(InquiryEngine):
    """Original graph semantics with new, auditable, evidence-aware scheduling."""

    def __init__(self, model, limits: InquiryLimits | None = None, *,
                 controller: AdaptiveController | None = None,
                 clock=utc_now, monotonic=time.monotonic):
        super().__init__(model, limits, clock=clock, monotonic=monotonic)
        self.controller = controller if controller is not None else AdaptiveController()

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
            choice = self.controller.decide(
                session, tuple(eligible),
                remaining_calls=self.limits.max_model_calls - session.model_calls,
                remaining_tokens=self.limits.max_tokens - session.tokens_used)
            if not isinstance(choice.audit, dict):
                raise InquiryError("adaptive controller must return audit metadata")
            if choice.question_id is None:
                if choice.stop_reason not in ("adaptive_low_value", "adaptive_token_reserve"):
                    raise InquiryError("invalid adaptive stop")
                session.stop_reason = choice.stop_reason
                session.trace.append({"event": "adaptive_stop", "decision": choice.audit})
                break
            if choice.stop_reason is not None:
                raise InquiryError("controller returned both a stop and selection")
            selected = [q for q in eligible if q.id == choice.question_id]
            if len(selected) != 1:
                raise InquiryError("adaptive controller selected a noneligible question")
            current = selected[0]
            session.trace.append({"event": "adaptive_select",
                                  "question_id": current.id, "decision": choice.audit})
            context = {
                "question": session.question,
                "claim": session.graph.nodes[session.root_id].text,
                "challenge": session.graph.nodes[current.id].text,
                "target": session.graph.nodes[current.target_id].text,
                "depth": current.depth,
                "arguments": [n.text for n in session.graph.nodes.values()
                              if n.kind == NodeKind.ARGUMENT][-6:],
                "objections": [n.text for n in session.graph.nodes.values()
                               if n.kind == NodeKind.OBJECTION][-6:],
            }
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
                break
            if session.tokens_used > self.limits.max_tokens:
                session.stop_reason = "reported_token_overrun"
                session.trace.append({"event": "token_overrun", "question_id": current.id})
                break
            if not draft.reasons and not draft.objections and not draft.followups:
                session.stop_reason = "no_progress"
                session.trace.append({"event": "no_progress", "question_id": current.id})
                break
            count = len(draft.reasons) + len(draft.objections) + len(draft.followups)
            if not self._preflight(session, count, count):
                session.stop_reason = "graph_budget"
                break
            if len(session.queue) - 1 + len(draft.followups) > self.limits.max_questions:
                session.stop_reason = "question_budget"
                break
            first_reason = None
            for reason_text in draft.reasons:
                item = self._add(session, NodeKind.ARGUMENT, reason_text)
                first_reason = first_reason or item
                self._edge(session, item, current.target_id, EdgeKind.SUPPORTS)
            for objection in draft.objections:
                item = self._add(session, NodeKind.OBJECTION, objection)
                self._edge(session, item, current.target_id, EdgeKind.ATTACKS)
            added = self._questions(session, draft.followups,
                                    current.target_id, first_reason, current.depth + 1)
            session.graph.explore_question(
                current.id, actor="rei11_adaptive_controller",
                note="Investigated; new arguments remain provisional")
            session.queue.remove(current)
            session.steps += 1
            session.trace.append({
                "event": "challenge_investigated", "step": session.steps,
                "question_id": current.id, "target_id": current.target_id,
                "depth": current.depth, "reason_count": len(draft.reasons),
                "objection_count": len(draft.objections), "new_questions": added,
                "tokens_used": turn.tokens_used, "note": draft.note,
            })
        return session
