from pathlib import Path
import sys
import unittest
from unittest.mock import patch

EXPERIMENT = Path(__file__).resolve().parents[1] / "research" / "adaptive_rei"
with patch.object(sys, "path", [str(EXPERIMENT), *sys.path]):
    import selective_review


class SelectiveReviewTests(unittest.TestCase):
    passage = "Was the door open? The sign was missing. The door stood open throughout."

    def test_review_only_for_metered_uncertain_answer(self):
        for answer, tokens in (("yes", 30), ("no", 25), (None, 20), ("uncertain", 0)):
            with self.subTest(answer=answer), patch.object(selective_review, "plain_decide",
                    return_value=({"answer": answer}, tokens)), patch.object(
                    selective_review, "predict", side_effect=AssertionError):
                result, used = selective_review.decide("", "", self.passage)
                self.assertEqual((result["answer"], used), (answer, tokens))

    def test_require_valid_reference_and_bill_every_review(self):
        for index in (2, 0, -1, 3, True, "2", None):
            with self.subTest(index=index), patch.object(selective_review, "plain_decide",
                    return_value=({"answer": "uncertain"}, 50)), patch.object(
                    selective_review, "predict", return_value=({"answer": "yes", "statement": index}, 70)):
                result, used = selective_review.decide("", "", self.passage)
                self.assertEqual(used, 120)
                valid = type(index) is int and index == 2
                self.assertEqual(result["answer"], "yes" if valid else "uncertain")
                self.assertEqual(result["citation"], "The door stood open throughout." if valid else None)

    def test_budgeted_skips_terminal_gap_without_spending_tokens(self):
        text = "Was crate B inspected? Its log copied crate A. No independent record survives."
        with patch.object(selective_review, "predict", side_effect=AssertionError):
            result, total = selective_review.review("", "", text, {"answer": "uncertain"}, 23, skip_gaps=True)
        self.assertEqual((result["answer"], total, result["review_tokens"]), ("uncertain", 23, 0))
        self.assertEqual(result["review_skipped"], "explicit_evidence_gap")

    def test_budgeted_keeps_review_after_contrasting_observation(self):
        text = "Was it sealed? No independent record survives, but the inspector saw it sealed."
        with patch.object(selective_review, "predict", return_value=({"answer": "yes", "statement": 1}, 30)):
            result, total = selective_review.review("", "", text, {"answer": "uncertain"}, 23, skip_gaps=True)
        self.assertEqual((result["answer"], total), ("yes", 53))
        self.assertIn("the inspector saw it sealed", result["citation"])
