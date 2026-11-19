import unittest
from research.standalone_eval.numeric_decisions import choose


class NumericDecisionTests(unittest.TestCase):
    def test_numeric_rules_and_deferral(self):
        cases = (
            ({"rule":"max_sum","threshold":None,"A":[72,18],"B":[55,49]}, "B"),
            ({"rule":"min_sum","threshold":None,"A":[1],"B":[4]}, "A"),
            ({"rule":"all_at_least","threshold":60,"A":[82,51],"B":[68,74]}, "B"),
            ({"rule":"all_positive","threshold":None,"A":[8,-2],"B":[3,3]}, "B"),
            ({"rule":"unmeasured","threshold":None,"A":[],"B":[]}, "defer"),
            ({"rule":"max_sum","threshold":None,"A":[2],"B":[2]}, "defer"),
            ({"rule":"all_positive","threshold":None,"A":[1],"B":[1]}, "defer"),
            ({"rule":"max_sum","threshold":None,"A":[True],"B":[2]}, None),
            ({"rule":"max_sum","threshold":None,"A":[float("nan")],"B":[2]}, None),
            ({"rule":"unmeasured","threshold":None,"A":[1],"B":[]}, None),
        )
        for measurements, expected in cases:
            with self.subTest(measurements=measurements):
                self.assertEqual(choose(measurements), expected)

    def test_reference_validation_rejects_fabrication_and_duplicate_counts(self):
        from research.standalone_eval.numeric_decisions import referenced_values
        document = {"rule":"max_sum","threshold":None,
                    "A":[{"value":12,"ref":1}],"B":[{"value":7,"ref":2}]}
        passages = ["A completed 12.", "B completed 7."]
        self.assertEqual(choose(referenced_values(document, passages)), "A")
        document["A"] = [{"value":99,"ref":1}]
        self.assertIsNone(referenced_values(document, passages))
        document["A"] = [{"value":12,"ref":2}]
        self.assertIsNone(referenced_values(document, passages))
        document["A"] = [{"value":12,"ref":1}, {"value":12,"ref":1}]
        self.assertIsNone(referenced_values(document, passages))

    def test_text_measurements_preserve_source_numbers_and_energy_direction(self):
        from research.standalone_eval.numeric_decisions import text_measurements
        source = ["A reduced use by 5% and B reduced it by 3%.",
                  "A increased use by 2% and B reduced it by 4%."]
        document = {
            "A": [{"text":"5","ref":1,"direction":"decrease"},
                  {"text":"2","ref":2,"direction":"increase"}],
            "B": [{"text":"3","ref":1,"direction":"decrease"},
                  {"text":"4","ref":2,"direction":"decrease"}],
        }
        parsed = text_measurements(document, source, "all_positive", None, "decrease")
        self.assertEqual(parsed["A"], [5, -2])
        self.assertEqual(choose(parsed), "B")
        document["A"][0]["text"] = "5.000000000001"
        self.assertIsNone(text_measurements(document, source, "all_positive", None, "decrease"))

    def test_coverage_requires_percentage_measurements_from_both_sentences(self):
        from research.standalone_eval.numeric_decisions import missing_percentage_coverage
        candidates = [{"text":"8%","ref":1}, {"text":"3%","ref":1},
                      {"text":"2%","ref":2}, {"text":"4%","ref":2},
                      {"text":"7","ref":3}]
        passages = ["A gained 8% and B gained 3%.",
                    "A lost 2% and B gained 4%.", "A cost 7."]
        selection = {"A":[{"id":1}], "B":[{"id":2}]}
        self.assertEqual(missing_percentage_coverage(selection,candidates,passages),
                         {"A":[2],"B":[2]})
        selection["A"].append({"id":5})
        self.assertEqual(missing_percentage_coverage(selection,candidates,passages)["A"], [2])
        selection["A"].append({"id":3})
        selection["B"].append({"id":4})
        self.assertEqual(missing_percentage_coverage(selection,candidates,passages), {})
