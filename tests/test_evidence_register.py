import sys
import unittest
from pathlib import Path
from unittest.mock import patch

EXPERIMENT = Path(__file__).resolve().parents[1] / "research" / "adaptive_rei"
with patch.object(sys, "path", [str(EXPERIMENT), *sys.path]):
    import adaptive_rei_benchmark
    from report_chain import report_chain_answer
    from evidence_register import RULES, decide, evidence_passage, register_answer


class EvidenceRegisterTests(unittest.TestCase):
    def test_invalidated_chain_preserves_independent_evidence(self):
        lines = ["What is the answer for claim 3?", RULES, "Claim 1: yes.",
                 "Claim 2: yes if claim 1 is yes.", "Claim 3: yes if claim 2 is yes.",
                 "Claim 3: no."]
        with patch.object(adaptive_rei_benchmark, "predict", side_effect=AssertionError):
            self.assertEqual(decide("", "", "\n".join(lines)), ({"answer": "uncertain"}, 0))
            lines[2] = "Claim 1: no."
            self.assertEqual(decide("", "", "\n".join(lines)), ({"answer": "no"}, 0))

    def test_unsupported_register_uses_whole_prompt(self):
        for report in ("Claim 2: yes if claim 2 is yes.", "Prose that the parser cannot read."):
            passage = "\n".join(["What is the answer for claim 2?", RULES, report])
            self.assertIsNone(register_answer(passage))
            with patch.object(adaptive_rei_benchmark, "predict") as predict:
                decide("url", "model", passage)
                predict.assert_called_once_with("url", "model", adaptive_rei_benchmark.SINGLE_PASS, passage)

    def test_filter_keeps_contrasts_and_unmarked_claims(self):
        base = "Was it late? Arrival was logged at noon."
        self.assertEqual(evidence_passage(base + " Unrelated: the printer jammed."), base)
        for suffix in (" Unrelated: the clock was replaced, but it recorded the arrival.",
                       " The printer jammed.", " Unrelated: did the clock run fast?"):
            self.assertEqual(evidence_passage(base + suffix), base + suffix)


class ReportChainTests(unittest.TestCase):
    def test_withdrawal_changes_dependent_reports_only(self):
        passage = ("Did the latch move? The bulletin copied the report. The report copied the log. "
                   "The report says it did. The log says it did. The memo states it did not.")
        self.assertEqual(decide("", "", passage), ({"answer": "uncertain"}, 0))
        self.assertEqual(decide("", "", passage + " The log was withdrawn."), ({"answer": "no"}, 0))
        self.assertEqual(decide("", "", passage + " The memo was retracted."), ({"answer": "yes"}, 0))

    def test_unresolved_language_or_lineage_defers_the_entire_passage(self):
        question = "Did the flag rise? "
        for body in (
            "The report says it did. The log copied the report. An observer saw it stay down.",
            "The log says it did. The log copied the memo. The memo copied the log.",
            "The report says it did. The report copied the memo.",
            "The log says it did. The report copied the log. The report says it did not.",
            "The unreliable log says it did. The memo copied the unreliable log.",
        ):
            with self.subTest(body=body):
                self.assertIsNone(report_chain_answer(question + body))
                with patch.object(adaptive_rei_benchmark, "predict") as predict:
                    decide("url", "model", question + body)
                    predict.assert_called_once_with("url", "model", adaptive_rei_benchmark.SINGLE_PASS, question + body)
