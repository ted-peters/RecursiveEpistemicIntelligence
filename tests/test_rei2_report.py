"""Small offline tests for REI 2.0 preflight grader; no real inference."""
import copy
import unittest

from rei0.models import digest
from rei0.local_ai_router import choose_route
from research.standalone_eval.challenge12_quality import load_cases, visible_question
from research.standalone_eval.rei2_preflight_live import (
    SCHEMA, TASKS, PreflightError, expected_rows, verify,
)


class REI2ReportChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases, cls.case_digest = load_cases()

    def test_two_public_tasks_each_have_the_required_arms(self):
        self.assertEqual(TASKS, ((0, ("direct", "adaptive")),
                                 (9, ("adaptive", "rei"))))
        self.assertEqual(len(expected_rows(self.cases)), 4)
        self.assertEqual(self.cases[0]["correct"], "B")
        self.assertEqual(self.cases[9]["correct"], "B")

    def test_prompts_are_public_only_and_router_is_predictable(self):
        for i, mode in expected_rows(self.cases):
            with self.subTest(case=i, mode=mode):
                task = visible_question(self.cases[i])
                self.assertIn("Answer: X", task)
                self.assertNotIn(self.cases[i]["id"], task)
                self.assertNotIn('"correct"', task)
                selected = choose_route([{"role": "user", "content": task}])
                self.assertEqual(selected.selected_mode,
                                 "direct" if i == 0 else "rei")

    def synthetic_envelope(self):
        """This is a fabricated TEST fixture; its source is explicitly fixture."""
        rows = []
        for index, mode in expected_rows(self.cases):
            route = "direct" if index == 0 else "rei"
            attempts = [{"status": "synthetic", "tokens": 1}]
            if mode == "rei" or (mode == "adaptive" and route == "rei"):
                attempts = attempts * 3
            audit = {
                "model_calls": len(attempts),
                "model_reported_tokens": len(attempts),
                "evidence_status": ("not_verified" if route == "direct"
                                    else "model_proposals_only_unverified"),
            }
            if mode == "adaptive":
                audit["execution_mode"] = route
                audit["routing"] = {"additional_router_model_calls": 0}
            rows.append({
                "case_id": self.cases[index]["id"],
                "requested_mode": mode,
                "answer": "Synthetic output.\nAnswer: B",
                "final_letter": "B",
                "correct": True,
                "error_type": None,
                "model_calls": len(attempts),
                "reported_tokens_known": len(attempts),
                "unknown_usage_calls": 0,
                "elapsed_seconds": 0.001,
                "attempts": attempts,
                "audit": audit,
            })
        data = {
            "schema": SCHEMA, "provider_kind": "fixture",
            "label": "synthetic-test-only", "model": "fake-not-real",
            "case_set_digest": self.case_digest,
            "task_order": [self.cases[i]["id"] + ":" + mode
                           for i, mode in expected_rows(self.cases)],
            "outcomes": rows, "warnings": [],
        }
        return {**data, "report_sha256": digest(data)}

    def test_fake_report_cannot_be_presented_as_real_inference(self):
        fake = self.synthetic_envelope()
        with self.assertRaisesRegex(PreflightError, "genuine"):
            verify(fake)

    def test_tampering_detected_before_fake_provenance(self):
        fake = self.synthetic_envelope()
        fake["outcomes"][0]["answer"] = "Answer: D"
        with self.assertRaisesRegex(PreflightError, "integrity"):
            verify(fake)

    def test_malformed_schema_fails_closed(self):
        fake = self.synthetic_envelope()
        fake["schema"] = "fake"
        with self.assertRaisesRegex(PreflightError, "schema"):
            verify(fake)


if __name__ == "__main__":
    unittest.main()
