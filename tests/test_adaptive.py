"""REI 1.1 adaptive controller tests: deterministic, offline, no live AI calls."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from rei0.adaptive import AdaptiveController, AdaptiveDecision
from rei0.graph import EpistemicGraph
from rei0.inquiry import InquiryEngine, InquiryError, InquiryLimits, InquirySession
from rei0.adapters import ScriptedAdapter
from rei0.models import (
    Edge, EdgeKind, EvidenceState, Node, NodeKind, Provenance, SourceKind, Validation,
)

ROOT = Path(__file__).resolve().parents[1]
FIXED = "2026-11-11T00:00:00Z"
QUESTION = "Is the provisional claim supported?"


def script(priority=9):
    doc = json.loads((ROOT / "examples" / "inquiry_script.json").read_text())
    doc["initial"]["payload"]["questions"] = [
        {"text": "What would change this assessment?", "target": "claim", "priority": priority}
    ]
    return doc


def inquiry(doc, *, controller=None, max_steps=1, max_depth=2, max_tokens=1000):
    return InquiryEngine(
        ScriptedAdapter(doc),
        InquiryLimits(max_steps=max_steps, max_depth=max_depth,
                      max_tokens=max_tokens, max_model_calls=4),
        controller=controller, clock=lambda: FIXED,
    )


def add_evidence(graph: EpistemicGraph, root_id: str, doc: str,
                 side: EdgeKind, *, kind=SourceKind.EXTERNAL):
    evidence = Provenance(
        source_id=doc, source_kind=kind, source_group=doc,
        reference="synthetic://" + doc, observed_at=FIXED)
    reviewer = Provenance(
        source_id="curator-" + doc, source_kind=SourceKind.EXTERNAL,
        source_group="curator-" + doc,
        reference="synthetic://review/" + doc, observed_at=FIXED)
    graph.add_node(Node(doc, NodeKind.EVIDENCE, "Synthetic document " + doc,
                        evidence, FIXED))
    graph.add_edge(Edge("edge-" + doc, doc, root_id, side, reviewer,
                        graph.method_version, FIXED))
    graph.set_validation("node", doc, Validation.VERIFIED,
                         verified_by="independent-review", reason="synthetic authorization")
    graph.set_validation("edge", "edge-" + doc, Validation.VERIFIED,
                         verified_by="independent-review", reason="synthetic authorization")


class AdaptiveControllerTests(unittest.TestCase):
    def test_legacy_scheduler_remains_byte_for_byte_identical(self):
        doc = script(priority=9)
        original = inquiry(doc).run(QUESTION)
        explicit_none = inquiry(doc, controller=None).run(QUESTION)
        self.assertEqual(original.to_dict(), explicit_none.to_dict())
        self.assertEqual(original.steps, 1)
        self.assertFalse(any(t["event"].startswith("adaptive") for t in original.trace))

    def test_high_priority_can_be_investigated(self):
        result = inquiry(script(priority=9), controller=AdaptiveController()).run(QUESTION)
        self.assertEqual(result.steps, 1)
        self.assertEqual(result.stop_reason, "step_budget")
        self.assertEqual(result.trace[1]["event"], "adaptive_select")
        self.assertEqual(result.trace[1]["decision"]["target_evidence_state"], "NEITHER")
        self.assertEqual(result.graph.assess(result.root_id).state, EvidenceState.NEITHER)
        self.assertTrue(all(n.validation == Validation.PENDING
                            for n in result.graph.nodes.values()))
        self.assertEqual(InquirySession.from_dict(result.to_dict()).to_dict(), result.to_dict())

    def test_low_value_stops_without_erasing_unresolved_question(self):
        result = inquiry(script(priority=1), controller=AdaptiveController()).run(QUESTION)
        self.assertEqual(result.stop_reason, "adaptive_low_value")
        self.assertEqual(result.steps, 0)
        self.assertEqual(result.model_calls, 1)
        self.assertEqual(len(result.queue), 1)
        self.assertEqual(result.trace[-1]["event"], "adaptive_stop")
        self.assertEqual(len(result.graph.explored_questions), 0)

    def test_token_reserve_prevents_expensive_expansion(self):
        result = inquiry(script(priority=10),
                         controller=AdaptiveController(reserve_tokens=100),
                         max_tokens=130).run(QUESTION)
        self.assertEqual(result.stop_reason, "adaptive_token_reserve")
        self.assertEqual(result.steps, 0)
        self.assertEqual(result.model_calls, 1)
        self.assertEqual(result.tokens_used, 36)

    def test_conflicting_verified_sources_change_selection_then_revoke(self):
        doc = script(priority=1)
        # Construct an original inquiry frontier without expanding it.
        pending = inquiry(doc, max_depth=0).run(QUESTION)
        self.assertEqual(pending.stop_reason, "depth_budget")
        controller = AdaptiveController(min_score=8, reserve_tokens=0)
        prior = controller.decide(pending, tuple(pending.queue),
                                  remaining_calls=3, remaining_tokens=900)
        self.assertEqual(prior.stop_reason, "adaptive_low_value")
        self.assertEqual(prior.audit["target_evidence_state"], "NEITHER")
        add_evidence(pending.graph, pending.root_id, "s1", EdgeKind.SUPPORTS)
        add_evidence(pending.graph, pending.root_id, "a1", EdgeKind.ATTACKS)
        both = controller.decide(pending, tuple(pending.queue),
                                 remaining_calls=3, remaining_tokens=900)
        self.assertEqual(pending.graph.assess(pending.root_id).state, EvidenceState.BOTH)
        self.assertEqual(both.question_id, pending.queue[0].id)
        self.assertEqual(both.audit["verified_support_source_count"], 1)
        self.assertEqual(both.audit["verified_attack_source_count"], 1)
        # A reviewer can revoke a supporting record without changing model text.
        pending.graph.set_validation("node", "a1", Validation.REVOKED,
                                     verified_by="independent-review", reason="fixture revocation")
        after = controller.decide(pending, tuple(pending.queue),
                                  remaining_calls=3, remaining_tokens=900)
        self.assertEqual(pending.graph.assess(pending.root_id).state, EvidenceState.SUPPORT_ONLY)
        self.assertEqual(after.stop_reason, "adaptive_low_value")

    def test_model_authored_documents_never_acquire_evidence_bonus(self):
        pending = inquiry(script(priority=1), max_depth=0).run(QUESTION)
        add_evidence(pending.graph, pending.root_id, "fake-model-doc",
                     EdgeKind.SUPPORTS, kind=SourceKind.MODEL)
        decision = AdaptiveController(min_score=8).decide(
            pending, tuple(pending.queue), remaining_calls=3, remaining_tokens=900)
        self.assertEqual(decision.audit["target_evidence_state"], "NEITHER")
        self.assertEqual(decision.stop_reason, "adaptive_low_value")

    def test_invalid_controller_cannot_select_nonexistent_question(self):
        class InvalidController:
            def decide(self, session, eligible, *, remaining_calls, remaining_tokens):
                return AdaptiveDecision("not-a-question", None, {})
        with self.assertRaisesRegex(InquiryError, "noneligible"):
            inquiry(script(), controller=InvalidController()).run(QUESTION)

    def test_parameters_and_budgets_fail_closed(self):
        for settings in ({"min_score": True}, {"reserve_tokens": -1},
                         {"min_score": 41}, {"reserve_tokens": 1.5}):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                AdaptiveController(**settings)
        session = inquiry(script(), max_depth=0).run(QUESTION)
        with self.assertRaises(ValueError):
            AdaptiveController().decide(session, tuple(session.queue),
                                        remaining_calls=True, remaining_tokens=900)
        with self.assertRaises(ValueError):
            AdaptiveController().decide(session, (),
                                        remaining_calls=2, remaining_tokens=900)


if __name__ == "__main__":
    unittest.main()
