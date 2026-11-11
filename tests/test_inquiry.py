"""Deterministic inquiry tests; no API keys or external network required."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from rei0 import (EpistemicGraph, Edge, EdgeKind, Node, NodeKind, EvidenceState,
                  GraphError, InquiryEngine, InquiryError, InquiryLimits,
                  InquirySession, ScriptedAdapter, ChatCompletionsAdapter)
from rei0.inquiry import InitialDraft, ExpansionDraft, QuestionDraft, ModelTurn

ROOT = Path(__file__).resolve().parent.parent
FIXED = "2026-11-10T00:00:00Z"
QUESTION = "Should an explanation make AI more trustworthy?"


def engine(**limits):
    values = {"max_steps": 4, "max_depth": 3, "max_model_calls": 6,
              "max_tokens": 6000, "max_seconds": 30}
    values.update(limits)
    return InquiryEngine(ScriptedAdapter.load(ROOT / "examples" / "inquiry_script.json"),
                         InquiryLimits(**values), clock=lambda: FIXED)


class SchemaTests(unittest.TestCase):
    def test_initial_requires_questions(self):
        with self.assertRaises(InquiryError):
            InitialDraft.parse({"claim": "maybe", "questions": []})

    def test_unexpected_field_is_rejected(self):
        with self.assertRaises(InquiryError):
            InitialDraft.parse({"claim": "maybe", "questions": [{"text": "why"}], "verify": True})

    def test_invalid_priority_is_rejected(self):
        for value in (-1, 11, True, 1.5):
            with self.subTest(priority=value), self.assertRaises(InquiryError):
                QuestionDraft.parse({"text": "why", "priority": value})

    def test_missing_reason_reference_is_rejected(self):
        with self.assertRaises(InquiryError):
            ExpansionDraft.parse({"reasons": [], "objections": [],
                                  "followups": [{"text": "why", "target": "reason"}], "note": "none"})

    def test_no_extra_controls_allowed(self):
        with self.assertRaises(InquiryError):
            ExpansionDraft.parse({"reasons": ["r"], "objections": [], "followups": [], "note": "n",
                                  "disable_guard": True})

    def test_model_turn_usage_validation(self):
        with self.assertRaises(InquiryError):
            ModelTurn({"claim": "c"}, -1)
        with self.assertRaises(InquiryError):
            ModelTurn({"claim": "c"}, True)

    def test_limit_validation(self):
        for kw in ({"max_steps": 0}, {"max_seconds": -1}, {"max_depth": -1},
                   {"max_tokens": True}, {"max_model_calls": 0}):
            with self.subTest(kwargs=kw), self.assertRaises(InquiryError):
                InquiryLimits(**kw)


class EngineTests(unittest.TestCase):
    def test_provisional_graph_and_audit(self):
        s = engine(max_steps=3).run(QUESTION)
        self.assertEqual(s.steps, 3)
        self.assertEqual(s.model_calls, 4)
        self.assertEqual(s.stop_reason, "step_budget")
        self.assertEqual(s.graph.assess(s.root_id).state, EvidenceState.NEITHER)
        self.assertEqual(len([x for x in s.graph.nodes.values() if x.kind == NodeKind.ARGUMENT]), 3)
        self.assertEqual(len([x for x in s.graph.nodes.values() if x.kind == NodeKind.OBJECTION]), 3)
        self.assertEqual(len(s.graph.explored_questions), 3)
        self.assertEqual(len(s.queue), 2)
        self.assertTrue(all(n.validation.value == "pending" for n in s.graph.nodes.values()))
        self.assertTrue(all(e.validation.value == "pending" for e in s.graph.edges.values()))

    def test_depth_budget_preserves_frontier(self):
        s = engine(max_depth=1).run(QUESTION)
        self.assertEqual(s.steps, 2)
        self.assertEqual(s.stop_reason, "depth_budget")
        # The remaining root-level falsification question can still be investigated.
        self.assertTrue(any(q.depth == 1 for q in s.queue))
        self.assertEqual(s.graph.assess(s.root_id).state, EvidenceState.NEITHER)

    def test_zero_depth_never_expands(self):
        s = engine(max_depth=0).run(QUESTION)
        self.assertEqual(s.stop_reason, "depth_budget")
        self.assertEqual(s.steps, 0)
        self.assertEqual(s.model_calls, 1)

    def test_max_one_step(self):
        s = engine(max_steps=1).run(QUESTION)
        self.assertEqual(s.stop_reason, "step_budget")
        self.assertEqual(s.steps, 1)
        self.assertEqual(len(s.queue), 2)

    def test_model_call_budget(self):
        s = engine(max_model_calls=1).run(QUESTION)
        self.assertEqual(s.stop_reason, "model_call_budget")
        self.assertEqual(s.steps, 0)

    def test_token_budget(self):
        s = engine(max_tokens=40).run(QUESTION)
        self.assertEqual(s.stop_reason, "reported_token_overrun")
        self.assertEqual(s.steps, 0)
        self.assertTrue(s.queue)
        self.assertEqual(len(s.graph.nodes), 3)
        self.assertEqual(s.tokens_used, 36 + 54)

    def test_initial_exceeds_token_budget(self):
        with self.assertRaises(InquiryError):
            engine(max_tokens=35).run(QUESTION)

    def test_graph_budget_preflight_is_atomic(self):
        s = engine(max_nodes=5).run(QUESTION)
        self.assertEqual(s.stop_reason, "graph_budget")
        self.assertEqual(s.steps, 0)
        self.assertEqual(len(s.graph.nodes), 3)
        self.assertFalse(s.graph.explored_questions)

    def test_finite_script_exhaustion_preserves_frontier(self):
        fixture = json.loads((ROOT / "examples" / "inquiry_script.json").read_text())
        fixture["responses"] = []
        s = InquiryEngine(ScriptedAdapter(fixture), InquiryLimits(), clock=lambda: FIXED).run(QUESTION)
        self.assertEqual(s.stop_reason, "model_error")
        self.assertEqual(s.steps, 0)
        self.assertEqual(len(s.queue), 2)
        self.assertEqual(s.trace[-1]["error_type"], "InquiryError")

    def test_no_progress_is_not_marked_explored(self):
        fixture = json.loads((ROOT / "examples" / "inquiry_script.json").read_text())
        fixture["responses"][0] = {"payload": {"reasons": [], "objections": [],
                                               "followups": [], "note": "no further result"}, "tokens_used": 10}
        s = InquiryEngine(ScriptedAdapter(fixture), InquiryLimits(), clock=lambda: FIXED).run(QUESTION)
        self.assertEqual(s.stop_reason, "no_progress")
        self.assertEqual(len(s.graph.explored_questions), 0)

    def test_duplicate_followups_do_not_create_nodes(self):
        fixture = json.loads((ROOT / "examples" / "inquiry_script.json").read_text())
        fixture["responses"][0]["payload"]["followups"] = [
            {"text": "What observation could falsify this claim?", "priority": 2},
            {"text": "  WHAT   observation could falsify this claim? ", "priority": 9}]
        s = InquiryEngine(ScriptedAdapter(fixture), InquiryLimits(max_steps=1), clock=lambda: FIXED).run(QUESTION)
        self.assertEqual(len(s.queue), 1)
        self.assertEqual(len(s.graph.open_questions()), 1)

    def test_two_runs_reproduce_exact_graph_with_fixed_clock(self):
        a = engine(max_steps=2).run(QUESTION)
        b = engine(max_steps=2).run(QUESTION)
        self.assertEqual(a.to_dict(), b.to_dict())

    def test_resume_equals_one_continuous_run(self):
        partial = engine(max_steps=1).run(QUESTION)
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "checkpoint.json"
            partial.save(file)
            loaded = InquirySession.load(file)
            completed = engine(max_steps=3).run(resume=loaded)
            continuous = engine(max_steps=3).run(QUESTION)
            self.assertEqual(completed.to_dict(), continuous.to_dict())
            self.assertEqual(completed.graph.audit_head, continuous.graph.audit_head)

    def test_resume_rejects_changed_question(self):
        partial = engine(max_steps=1).run(QUESTION)
        with self.assertRaises(InquiryError):
            engine(max_steps=3).run("Different", resume=partial)

    def test_checkpoint_checksum_catches_edit(self):
        s = engine(max_steps=1).run(QUESTION)
        data = s.to_dict()
        data["queue"][0]["priority"] = 10
        with self.assertRaises(InquiryError):
            InquirySession.from_dict(data)

    def test_checkpoint_rejects_invalid_queue_even_when_rehashed(self):
        from rei0.models import digest
        s = engine(max_steps=1).run(QUESTION)
        data = s.to_dict()
        data["queue"][0]["target_id"] = "not-real"
        payload = {k: v for k,v in data.items() if k != "checkpoint_hash"}
        data["checkpoint_hash"] = digest(payload)
        with self.assertRaises(InquiryError):
            InquirySession.from_dict(data)

    def test_open_questions_survive_graph_roundtrip(self):
        s = engine(max_steps=1).run(QUESTION)
        graph = EpistemicGraph.from_dict(s.graph.to_dict())
        self.assertEqual(graph.explored_questions, s.graph.explored_questions)
        self.assertEqual({q.id for q in graph.open_questions()}, {q.id for q in s.graph.open_questions()})

    def test_questions_edges_are_typed(self):
        s = engine(max_steps=1).run(QUESTION)
        self.assertTrue(any(e.kind == EdgeKind.QUESTIONS for e in s.graph.edges.values()))
        for e in s.graph.edges.values():
            if e.kind == EdgeKind.QUESTIONS:
                self.assertEqual(s.graph.nodes[e.source].kind, NodeKind.OPEN_QUESTION)

    def test_workflow_mark_does_not_confer_evidence(self):
        s = engine(max_steps=1).run(QUESTION)
        self.assertEqual(s.graph.assess(s.root_id).state.value, "NEITHER")
        s2 = EpistemicGraph.from_dict(s.graph.to_dict())
        self.assertEqual(s2.assess(s2.nodes[s.root_id].id).state.value, "NEITHER")

    def test_scripted_input_does_not_change_claim_without_matching_fixture(self):
        s = engine(max_steps=1).run("Unrelated prompt")
        self.assertIn("explanation", s.graph.nodes[s.root_id].text)

    def test_time_budget_limits_inquiry(self):
        # Fake monotonic clock advances 10 seconds on each read.
        tick = iter([0, 1, 2, 50, 51, 52])
        result = InquiryEngine(ScriptedAdapter.load(ROOT / "examples" / "inquiry_script.json"),
                               InquiryLimits(max_seconds=5), clock=lambda: FIXED,
                               monotonic=lambda: next(tick)).run(QUESTION)
        self.assertEqual(result.stop_reason, "time_budget")

    def test_existing_graph_cycles_still_blocked(self):
        s = engine(max_steps=1).run(QUESTION)
        first_argument = next(n for n in s.graph.nodes.values() if n.kind == NodeKind.ARGUMENT)
        with self.assertRaises(GraphError):
            from rei0.models import Provenance, SourceKind
            p = Provenance("reviewer", SourceKind.MODEL, "reviewer", "demo://reviewer", FIXED)
            s.graph.add_edge(Edge("cycle", s.root_id, first_argument.id, EdgeKind.SUPPORTS,
                                  p, s.graph.method_version, FIXED))


class AdapterTests(unittest.TestCase):
    def test_invalid_http_endpoint_rejected(self):
        with self.assertRaises(InquiryError):
            ChatCompletionsAdapter(model="test", endpoint="http://untrusted.example/api")

    def test_no_key_fails_explicitly(self):
        adapter = ChatCompletionsAdapter(model="model-test")
        with patch.dict("os.environ", {"REI_LLM_API_KEY": ""}):
            with self.assertRaisesRegex(InquiryError, "REI_LLM_API_KEY"):
                adapter.initial(QUESTION, max_output_tokens=100, timeout=2)

    def test_mocked_https_response_parsed(self):
        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, limit):
                return json.dumps({"choices": [{"message": {"content": json.dumps({
                    "claim": "test", "questions": [{"text": "why", "priority": 5}]})}}],
                    "usage": {"total_tokens": 67}}).encode()
        class FakeOpener:
            def open(self, req, timeout):
                self.request = req
                return FakeResponse()
        opener = FakeOpener()
        with patch.dict("os.environ", {"REI_LLM_API_KEY": "only-for-unit-test"}):
            with patch("rei0.adapters.build_opener", return_value=opener):
                turn = ChatCompletionsAdapter(model="test").initial(QUESTION, max_output_tokens=100, timeout=3)
        self.assertEqual(turn.tokens_used, 67)
        self.assertEqual(turn.payload["claim"], "test")
        self.assertEqual(opener.request.full_url, "https://api.openai.com/v1/chat/completions")

    def test_bad_network_json_raises(self):
        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, limit): return b"[]"
        class FakeOpener:
            def open(self, req, timeout): return FakeResponse()
        with patch.dict("os.environ", {"REI_LLM_API_KEY": "fake"}):
            with patch("rei0.adapters.build_opener", return_value=FakeOpener()):
                with self.assertRaises(InquiryError):
                    ChatCompletionsAdapter(model="test").initial(QUESTION, max_output_tokens=100, timeout=3)


class CLITests(unittest.TestCase):
    def cli(self, *args):
        return subprocess.run([sys.executable, "-m", "rei0", *args], cwd=ROOT, capture_output=True, text=True)

    def test_inquire_cli(self):
        result = self.cli("inquiry-demo", "--max-steps", "2")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["steps"], 2)

    def test_checkpoint_verify_and_resume(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder)/"session.json")
            result = self.cli("inquiry-demo", "--max-steps", "1", "--checkpoint", path)
            self.assertEqual(result.returncode, 0, result.stderr)
            verified = self.cli("verify-checkpoint", path)
            self.assertEqual(verified.returncode, 0, verified.stderr)
            resumed = self.cli("resume", path, "--script", "examples/inquiry_script.json", "--max-steps", "3")
            self.assertEqual(resumed.returncode, 0, resumed.stderr)
            self.assertEqual(json.loads(resumed.stdout)["steps"], 3)

    def test_inquire_requires_explicit_adapter(self):
        result = self.cli("inquire", QUESTION)
        self.assertEqual(result.returncode, 2)
        self.assertIn("--script", result.stderr)

    def test_live_without_model_fails_closed(self):
        result = self.cli("inquire", QUESTION, "--live")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--model", result.stderr)


if __name__ == "__main__":
    unittest.main()
