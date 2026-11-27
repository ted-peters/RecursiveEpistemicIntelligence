import sys
import unittest
from pathlib import Path
from unittest.mock import patch

EXPERIMENT = Path(__file__).resolve().parents[1] / "research" / "adaptive_rei"
with patch.object(sys, "path", [str(EXPERIMENT), *sys.path]):
    import adaptive_rei_benchmark as benchmark


class SingleFactSchemaTests(unittest.TestCase):
    def test_classification_and_quote(self):
        question = "Was the gate open? The gate was closed."
        for role, answer in (("supports", "yes"), ("contradicts", "no"), ("unresolved", "uncertain")):
            with self.subTest(role=role), patch.object(benchmark, "predict", return_value=({"relation": role}, 10)):
                result = benchmark.single_fact_verdict("", "", question)
                self.assertEqual(result["answer"], answer)
                self.assertEqual(result["graph"]["claims"][0]["evidence"][0]["quote"], "The gate was closed.")

    def test_invalid_relation_returns_no_verdict(self):
        with patch.object(benchmark, "predict", return_value=({"relation": []}, 10)):
            self.assertIsNone(benchmark.single_fact_verdict("", "", "Open? Closed.")["answer"])

    def test_empty_passage_is_rejected(self):
        with self.assertRaises(ValueError):
            benchmark.single_fact_verdict("", "", "Open? ")
