import sys
import unittest
from pathlib import Path
from unittest.mock import patch

EXPERIMENT = Path(__file__).resolve().parents[1] / "research" / "adaptive_rei"
with patch.object(sys, "path", [str(EXPERIMENT), *sys.path]):
    from quantity_comparison import quantity_role, quantity_verdict


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

    def test_scaled_boundary_does_not_round_long_decimals(self):
        q = 'Is this claim true: "The rail measured more than 1 meter."? '
        self.assertEqual(quantity_verdict(q + "The rail measured 100.00000000000000000000000000001 centimeters."), "yes")
        self.assertEqual(quantity_verdict(q + "The rail measured 100 centimeters."), "no")

    def test_new_length_and_volume_units_cannot_mix(self):
        q = 'Is this claim true: "The pipe measured at least 2 millimeters."? '
        self.assertIsNone(quantity_verdict(q + "The pipe measured 2 milliliters."))

    def test_subject_identity_and_alias_scope(self):
        question = 'Is this claim true: "The field bag weighed at most 1 kilogram."? '
        for text, expected in (
            ("The scale reading for the tool bag was 1010 grams.", "gap"),
            ("The scale reading for the field bag was 1010 grams.", "no"),
            ("The pack, also called the field bag, weighed 990 grams.", "yes"),
            ("The pack, also called the field bag, never weighed 990 grams.", None),
            ("The tool bag weighed 1010 grams. The field bag weighed less.", None),
        ):
            with self.subTest(text=text):
                self.assertEqual(quantity_role(question + text), expected)

    def test_other_property_and_ambiguous_units(self):
        question = 'Is this claim true: "The drum held at least 2 liters."? '
        self.assertEqual(quantity_role(question + "The drum itself had a mass of 3 kilograms."), "gap")
        self.assertIsNone(quantity_role(question + "The drum contained 3 kilograms."))
        self.assertIsNone(quantity_role(question + "The drum weighed 3 kilograms and held 2 liters."))

    def test_partial_volume_at_boundary(self):
        for bound, expected in (("at most", "gap"), ("at least", "yes"),
                                ("less than", "no"), ("more than", "gap")):
            with self.subTest(bound=bound):
                q = f'Is this claim true: "The jug held {bound} 1 liter."? '
                self.assertEqual(quantity_role(q + "There were 1000 milliliters of water in the jug."), expected)

    def test_partial_volume_requires_matching_container_and_volume_unit(self):
        q = 'Is this claim true: "The jug held at least 1 liter."? '
        self.assertEqual(quantity_role(q + "There were 1000 milliliters of water in the pot."), "gap")
        self.assertIsNone(quantity_role(q + "There were 1000 grams of water in the jug."))
        self.assertEqual(quantity_role(q + "The total volume of liquid in the jug was 900 milliliters."), "no")

    def test_inclusive_ranges_against_small_integer_oracle(self):
        for low in range(3):
            for high in range(low, 3):
                for limit in range(3):
                    for wording, outcomes in (
                        ("at most", [v <= limit for v in range(low, high + 1)]),
                        ("at least", [v >= limit for v in range(low, high + 1)]),
                        ("more than", [v > limit for v in range(low, high + 1)]),
                        ("less than", [v < limit for v in range(low, high + 1)]),
                    ):
                        q = (f'Is this claim true: "The tile weighed {wording} {limit} grams."? '
                             f'The tile weighed between {low} and {high} grams, inclusive.')
                        expected = "yes" if all(outcomes) else "gap" if any(outcomes) else "no"
                        with self.subTest(question=q):
                            self.assertEqual(quantity_role(q), expected)

    def test_reversed_range_is_unusable(self):
        q = 'Is this claim true: "The tray cost at most two dollars."? '
        self.assertEqual(quantity_role(q + "The tray cost between 3 and 1 dollars, inclusive."), "gap")
