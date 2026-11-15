"""Challenge 12 independent grading and cost-accounting tests (NO real model)."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from rei0.local_ai_router import choose_route
from rei0.models import digest
from research.standalone_eval.challenge12_quality import (
    ARMS, Challenge12Error, SyntheticProvider, aggregate, arm_order,
    evaluate, load_cases, run_conventional_self_critique,
    verify, visible_question,
)


class Challenge12ProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases,cls.case_digest=load_cases()
        cls.reports=[
            evaluate(cases=cls.cases,case_digest=cls.case_digest,
                     shard_index=i,shards=3,provider_kind="fixture",
                     model="no-model-fixture",endpoint="unused",
                     label="offline-12case-test") for i in range(3)
        ]

    def test_predeclared_case_set_and_balanced_styles(self):
        self.assertEqual(len(self.cases),12)
        self.assertEqual(len({x["id"] for x in self.cases}),12)
        self.assertEqual(sum(c["style"]=="bounded" for c in self.cases),6)
        self.assertEqual(sum(c["style"]=="investigate" for c in self.cases),6)
        self.assertTrue(all(c["correct"] in "ABCD" for c in self.cases))

    def test_adaptive_route_is_deterministic_and_key_is_never_in_context(self):
        for i,c in enumerate(self.cases):
            with self.subTest(c=c["id"]):
                task=visible_question(c)
                route=choose_route([{"role":"user","content":task}])
                self.assertEqual(
                    route.selected_mode,
                    "direct" if c["style"]=="bounded" else "rei")
                self.assertNotIn(c["id"],task)
                self.assertNotIn('"correct"',task)
                self.assertNotIn('"case_id"',task)
                self.assertEqual(route.audit()["additional_router_model_calls"],0)
                self.assertEqual(arm_order(i)[0],ARMS[i%4])

    def test_independent_replay_and_aggregation_cover_every_case_arm(self):
        for i,report in enumerate(self.reports):
            checked=verify(report,cases=self.cases,case_digest=self.case_digest)
            self.assertTrue(checked["valid"])
            self.assertEqual(checked["provider_kind"],"fixture")
            self.assertEqual(checked["case_count"],4)
            self.assertEqual(checked["shard_index"],i)
            self.assertEqual(len(report["outcomes"]),16)
            self.assertEqual(
                report["report_sha256"],
                digest({k:v for k,v in report.items() if k!="report_sha256"}))
        combined=aggregate(self.reports,cases=self.cases,case_digest=self.case_digest)
        self.assertEqual(combined["case_count"],12)
        self.assertEqual(combined["provider_kind"],"fixture")
        self.assertEqual(len(combined["per_case_outcomes"]),12)
        self.assertEqual(combined["summary"]["direct"]["calls"],12)
        self.assertEqual(combined["summary"]["self_critique"]["calls"],48)
        self.assertEqual(combined["summary"]["rei"]["calls"],36)
        self.assertEqual(combined["summary"]["adaptive"]["calls"],24)
        self.assertTrue(all(v["total"]==12 for v in combined["summary"].values()))

    def test_four_call_conventional_self_critique_is_not_rei(self):
        provider=SyntheticProvider()
        outcome=run_conventional_self_critique(provider,visible_question(self.cases[0]))
        self.assertEqual(outcome["mode"],"self_critique")
        self.assertEqual(outcome["audit"]["model_calls"],4)
        self.assertEqual(outcome["audit"]["model_reported_tokens"],68)
        self.assertIsNone(outcome["audit"]["graph_audit_head"])
        self.assertEqual(outcome["audit"]["evidence_status"],"not_verified")

    def test_report_digest_rejects_unreported_changes(self):
        r=copy.deepcopy(self.reports[0])
        r["outcomes"][0]["correct"]=not r["outcomes"][0]["correct"]
        with self.assertRaisesRegex(Challenge12Error,"modified report digest"):
            verify(r,cases=self.cases,case_digest=self.case_digest)

    def test_recomputed_digest_cannot_override_independent_answer_grader(self):
        r=copy.deepcopy(self.reports[0])
        r["outcomes"][0]["correct"]=not r["outcomes"][0]["correct"]
        r["report_sha256"]=digest({k:v for k,v in r.items() if k!="report_sha256"})
        with self.assertRaisesRegex(Challenge12Error,"independent grader"):
            verify(r,cases=self.cases,case_digest=self.case_digest)

    def test_recomputed_digest_cannot_invent_token_meters(self):
        r=copy.deepcopy(self.reports[0])
        r["outcomes"][0]["attempts"][0]["tokens"]=999
        r["report_sha256"]=digest({k:v for k,v in r.items() if k!="report_sha256"})
        with self.assertRaisesRegex(Challenge12Error,"usage totals"):
            verify(r,cases=self.cases,case_digest=self.case_digest)

    def test_recomputed_digest_cannot_hide_adaptive_route(self):
        r=copy.deepcopy(self.reports[0])
        row=next(x for x in r["outcomes"] if x["mode"]=="adaptive")
        row["audit"]["execution_mode"]="invalid"
        r["report_sha256"]=digest({k:v for k,v in r.items() if k!="report_sha256"})
        with self.assertRaisesRegex(Challenge12Error,"routing audit"):
            verify(r,cases=self.cases,case_digest=self.case_digest)

    def test_missing_duplicate_or_wrong_shards_fail(self):
        for bad in (self.reports[:2],
                    [self.reports[0],self.reports[1],self.reports[1]]):
            with self.assertRaises(Challenge12Error):
                aggregate(bad,cases=self.cases,case_digest=self.case_digest)
        r=copy.deepcopy(self.reports[0])
        r["case_indices"]=[1,2,3,4]
        r["report_sha256"]=digest({k:v for k,v in r.items() if k!="report_sha256"})
        with self.assertRaisesRegex(Challenge12Error,"selection"):
            verify(r,cases=self.cases,case_digest=self.case_digest)

    def test_modified_case_key_or_style_cannot_be_regraded_as_original(self):
        modified=copy.deepcopy(self.cases)
        modified[0]["correct"]="A"
        with self.assertRaisesRegex(Challenge12Error,"wrong case set"):
            verify(self.reports[0],cases=modified,case_digest=digest(modified))

    def test_input_case_schema_is_strict(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"cases.json"
            doc=json.loads(Path(__file__).resolve().parent.parent.joinpath(
                "research/standalone_eval/challenge12_cases.json"
            ).read_text())
            doc["cases"][1]["style"]="bounded"
            p.write_text(json.dumps(doc))
            with self.assertRaisesRegex(Challenge12Error,"style"):
                load_cases(p)

    def test_four_arms_use_one_exact_prompt_per_case(self):
        # The evaluator constructs this prompt once before iterating arms.
        # All labels/scores remain outside the visible question.
        prompts=[visible_question(c) for c in self.cases]
        self.assertEqual(len(set(prompts)),12)
        self.assertTrue(all("Answer: X" in prompt for prompt in prompts))
        self.assertTrue(all("A." in p and "D." in p for p in prompts))


if __name__=="__main__":
    unittest.main()
