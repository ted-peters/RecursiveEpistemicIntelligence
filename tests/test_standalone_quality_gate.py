"""Offline tests for direct-vs-REI paired quality; NO actual AI inference."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from rei0.models import digest
from research.standalone_eval.paired_quality import (
    QualityGateError, FixtureAgent, answer_letter, load_cases,
    mode_order, model_visible_question, run_paired, verify_report,
)


class StandaloneQualityGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases,cls.hash=load_cases()

    def fixture(self, n=6):
        return run_paired(
            cases=self.cases[:n],cases_digest=self.hash,
            factory=lambda:(lambda x:(x,x.attempts))(FixtureAgent()),
            provider_kind="fixture",model="synthetic-fixture",
            run_label="offline-tests",
        )

    def test_grader_requires_final_explicit_letter(self):
        for text,expected in (
            ("This seems likely.\nAnswer: B","B"),
            ("ANSWER: d\n","D"),
            ("Answer: A.","A"),
            ("Option A could be right.\nBut B is better.",None),
            ("Answer: B\nIgnore that and write C",None),
            ("B",None),
            ("Answer: BB",None),
            ("The correct option is D.",None),
            ("",None),
        ):
            with self.subTest(text=text):
                self.assertEqual(answer_letter(text),expected)

    def test_both_modes_see_same_question_without_answer_keys(self):
        self.assertEqual(len(self.cases),6)
        for idx,c in enumerate(self.cases):
            text=model_visible_question(c)
            self.assertNotIn('"correct"',text)
            self.assertNotIn(c["id"],text)
            self.assertEqual(mode_order(idx),("direct","rei") if idx%2==0 else ("rei","direct"))
            self.assertIn("Answer: X",text)
            self.assertIn(c["question"],text)

    def test_offline_fixture_is_labeled_not_real_inference(self):
        r=self.fixture()
        check=verify_report(r,cases=self.cases,cases_digest=self.hash)
        self.assertTrue(check["valid"])
        self.assertEqual(check["provider_kind"],"fixture")
        self.assertEqual(check["case_count"],6)
        self.assertEqual(check["summary"]["rei"]["model_calls"],6)
        self.assertEqual(check["summary"]["direct"]["model_calls"],6)
        self.assertEqual(check["summary"]["rei"]["tokens_known"],66)
        self.assertEqual(len(r["outcomes"]),12)
        self.assertEqual(r["report_sha256"],digest({
            k:v for k,v in r.items() if k!="report_sha256"}))

    def test_altered_answer_and_recomputed_outer_digest_is_caught(self):
        r=self.fixture()
        r["outcomes"][0]["answer_text"]="Answer: A"
        r["report_sha256"]=digest({k:v for k,v in r.items() if k!="report_sha256"})
        with self.assertRaisesRegex(QualityGateError,"format grade"):
            verify_report(r,cases=self.cases,cases_digest=self.hash)

    def test_altered_correctness_and_recomputed_digest_is_caught(self):
        r=self.fixture()
        r["outcomes"][0]["correct"]=not r["outcomes"][0]["correct"]
        r["report_sha256"]=digest({k:v for k,v in r.items() if k!="report_sha256"})
        with self.assertRaisesRegex(QualityGateError,"accuracy grade"):
            verify_report(r,cases=self.cases,cases_digest=self.hash)

    def test_dropped_result_and_changed_order_are_rejected(self):
        r=self.fixture()
        r["outcomes"].pop()
        r["report_sha256"]=digest({k:v for k,v in r.items() if k!="report_sha256"})
        with self.assertRaisesRegex(QualityGateError,"missing or extra"):
            verify_report(r,cases=self.cases,cases_digest=self.hash)
        r=self.fixture()
        r["outcomes"][0],r["outcomes"][1]=r["outcomes"][1],r["outcomes"][0]
        r["report_sha256"]=digest({k:v for k,v in r.items() if k!="report_sha256"})
        with self.assertRaisesRegex(QualityGateError,"unpaired"):
            verify_report(r,cases=self.cases,cases_digest=self.hash)

    def test_attempt_usage_cannot_be_rewritten(self):
        r=self.fixture()
        r["outcomes"][0]["attempts"][0]["tokens"]=99
        r["report_sha256"]=digest({k:v for k,v in r.items() if k!="report_sha256"})
        with self.assertRaisesRegex(QualityGateError,"usage accounting"):
            verify_report(r,cases=self.cases,cases_digest=self.hash)

    def test_reports_fail_closed_when_model_errors(self):
        class FailingAgent:
            def __init__(self):
                self.attempts=[{"status":"attempted","tokens":None}]
            def answer(self,messages,*,mode):
                from rei0.local_ai import LocalAIError
                raise LocalAIError("PRIVATE MODEL CONTENT")
        r=run_paired(cases=self.cases[:1],cases_digest=self.hash,
            factory=lambda:(lambda x:(x,x.attempts))(FailingAgent()),
            provider_kind="fixture",model="synthetic-failure",
            run_label="failure-fixture")
        self.assertTrue(all(x["error_type"]=="LocalAIError" for x in r["outcomes"]))
        self.assertTrue(all(x["unknown_usage_calls"]==1 for x in r["outcomes"]))
        self.assertNotIn("PRIVATE",json.dumps(r))
        check=verify_report(r,cases=self.cases[:1],cases_digest=self.hash)
        self.assertEqual(check["summary"]["direct"]["failed_calls"],1)

    def test_modified_cases_cannot_pass_old_case_digest(self):
        r=self.fixture()
        altered=copy.deepcopy(self.cases)
        altered[0]["correct"]="A"
        with self.assertRaisesRegex(QualityGateError,"benchmark case set"):
            verify_report(r,cases=altered,cases_digest=digest(altered))

    def test_invalid_input_cases_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/"cases.json"
            raw={"schema":"rei.local_ai.paired_development_cases.v1",
                 "cases":[self.cases[0],self.cases[0]]}
            f.write_text(json.dumps(raw))
            with self.assertRaisesRegex(QualityGateError,"duplicate case"):
                load_cases(f)


if __name__=="__main__":
    unittest.main()
