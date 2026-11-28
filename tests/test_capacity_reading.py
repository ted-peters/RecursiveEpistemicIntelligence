import sys
import unittest
from pathlib import Path
from unittest.mock import patch

EXPERIMENT = Path(__file__).resolve().parents[1] / "research/adaptive_rei"
with patch.object(sys, "path", [str(EXPERIMENT), *sys.path]):
    from capacity_reading import read_capacity


class CapacityTests(unittest.TestCase):
    def test_strict_boundary_depends_on_headroom(self):
        claim = "The tin can hold more than 1 liter."
        for passage, expected in (
            ("The capacity of the tin is 1,000 mL.", "no"),
            ("The tin contains 1000 mL.", "gap"),
            ("The tin contains 1000 mL and has some room left.", "yes"),
        ):
            with self.subTest(passage=passage):
                self.assertEqual(read_capacity(claim, passage)[0], expected)

    def test_incomplete_observation_does_not_prove_an_upper_bound(self):
        self.assertEqual(read_capacity("The vat can hold at most 2 litres.",
                                       "The vat currently contains 1 litre.")[0], "gap")

    def test_subject_and_fill_direction(self):
        claim = "The vat can hold at least 2 liters."
        self.assertEqual(read_capacity(claim, "The capacity of the tub is 3 liters.")[0], "gap")
        self.assertIsNone(read_capacity(claim, "It takes 1 liter to fill the half-full vat completely."))
