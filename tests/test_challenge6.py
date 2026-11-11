"""Offline safety/integrity checks; passing these is NOT an accuracy result."""
import json
from pathlib import Path
import unittest
from rei0.benchmark import ARMS, load_study, Limits, run_benchmark, verify_report

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'research' / 'challenge6'

class Challenge6DataTests(unittest.TestCase):
    def test_cases_and_reference_keys_well_formed(self):
        cases, keys = load_study(json.loads((BASE/'cases.json').read_text()),
                                 json.loads((BASE/'keys.json').read_text()))
        self.assertEqual(6,len(cases))
        self.assertEqual(6,len(keys))
        self.assertEqual(4,len(ARMS))
        self.assertEqual(1,sum(k.unanswerable for k in keys.values()))

    def test_no_answer_keys_in_model_prompt(self):
        cases, keys = load_study(json.loads((BASE/'cases.json').read_text()),
                                 json.loads((BASE/'keys.json').read_text()))
        for c in cases:
            self.assertTrue(c.id in keys)
            self.assertNotIn('"acceptable"', c.prompt())
            self.assertNotIn('"unanswerable"', c.prompt())

    def test_pilot_budget_explicit(self):
        budgets = Limits(max_calls=3, max_tokens=2600, max_seconds=140,
                         max_output_tokens=320, steps=1)
        self.assertEqual(3, budgets.max_calls)

    def test_model_is_external_to_repository(self):
        # Don't bundle 2.5GB of model weights or external credentials in this public repo.
        self.assertFalse(any(BASE.glob('*.gguf')))

if __name__=='__main__': unittest.main()
