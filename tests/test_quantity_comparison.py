import sys
import unittest
from pathlib import Path
from unittest.mock import patch

EXPERIMENT = Path(__file__).resolve().parents[1] / "research" / "adaptive_rei"
with patch.object(sys, "path", [str(EXPERIMENT), *sys.path]):
    from quantity_comparison import quantity_verdict


class QuantityTests(unittest.TestCase):
    def test_boundary_and_decimal(self):
        for bound, expected in (("at least", "yes"), ("at most", "yes"),
                                ("more than", "no"), ("less than", "no")):
            with self.subTest(bound=bound):
                question = f'Is this claim true: "The pot held {bound} two liters."? The pot contained 2.00 liters.'
                self.assertEqual(quantity_verdict(question), expected)

    def test_unknown_or_mismatched_facts_fall_through(self):
        for passage in ("The pot could hold 3 liters.", "The tin contained 3 liters.",
                        "The pot contained 3 grams.", "The pot contained 3 liters yesterday.",
                        "The pot contained 3 liters. The reading was disputed.",
                        "The pot held at most 3 liters.", "The pot contained fewer than 3 liters."):
            with self.subTest(passage=passage):
                self.assertIsNone(quantity_verdict('Is this claim true: "The pot held at least two liters."? ' + passage))
