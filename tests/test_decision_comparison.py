import unittest
from research.standalone_eval.decision_comparison import analyze


class ComparisonTests(unittest.TestCase):
    def test_regressions_remain_visible_when_total_accuracy_ties(self):
        rows = []
        for side, arm, correct in (
            (0, "compact", True), (0, "targeted", False),
            (1, "compact", False), (1, "targeted", True),
        ):
            rows.append({"case":"sample", "side":side, "arm":arm,
                         "correct":correct, "choice":"A", "model_calls":1,
                         "model_reported_tokens":100, "unknown_usage_calls":0})
        result = analyze(rows)
        self.assertEqual(result["regressions"], 1)
        self.assertEqual(result["corrections"], 1)
        with self.assertRaises(ValueError):
            analyze(rows[:-1])
        with self.assertRaises(ValueError):
            analyze(rows + rows[:1])
