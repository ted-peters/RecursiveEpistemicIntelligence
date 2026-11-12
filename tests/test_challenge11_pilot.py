"""Challenge 11 optional Qwen investigation pilot tests (fully offline)."""
from __future__ import annotations

import copy
import io
import json
import unittest
from unittest.mock import patch

from rei0.models import digest
from research.challenge11.model_provider import (
    ModelChoiceError, QwenChoiceProvider,
)
from research.challenge11.pilot import (
    ARMS, ScriptedChoiceProvider, run, verify_report,
)
from research.challenge11.voi import InvestigationError


class InvestigativePilotTests(unittest.TestCase):
    def test_scripted_twin_arm_pilot_is_complete_but_not_model_intelligence(self):
        provider=ScriptedChoiceProvider()
        report=run(provider,count=4)
        self.assertEqual(report["mode"],"scripted-non-empirical-fixture")
        self.assertEqual(report["cases"],4)
        self.assertEqual(len(report["outcomes"]),8)
        self.assertEqual(report["summary"]["per_arm"]["recursive_voi"]["model_calls"],0)
        self.assertEqual(report["summary"]["per_arm"]["tool_self_critique"]["failed"],0)
        self.assertGreater(report["summary"]["per_arm"]["tool_self_critique"]["model_calls"],0)
        self.assertLessEqual(report["summary"]["per_arm"]["tool_self_critique"]["model_calls"],16)
        self.assertFalse(report["summary"]["actual_computation_matched"])
        self.assertTrue(report["summary"]["same_numeric_bayesian_tools_available"])
        self.assertTrue(report["summary"]["strong_conventional_exact_optimal_matches_recursive"])
        self.assertEqual(verify_report(report)["paired_outcomes"],8)

    def test_scripted_choices_get_numeric_tool_and_no_hidden_truth(self):
        class InspectProvider(ScriptedChoiceProvider):
            def __init__(self):
                super().__init__()
                self.seen=[]
            def respond(self,**kw):
                public=kw["public"]
                self.seen.append(json.loads(json.dumps(public)))
                return super().respond(**kw)
        provider=InspectProvider()
        run(provider,count=4)
        self.assertTrue(provider.seen)
        for v in provider.seen:
            self.assertIn("candidate_values",v)
            self.assertIn("current_probability_H1",v)
            self.assertIn("remaining_probe_budget",v)
            self.assertNotIn("truth",v)
            self.assertNotIn("outcomes",v)
            self.assertNotIn("latent_hypothesis",v)
            self.assertNotIn("signer_secret",v)
            self.assertEqual({x["id"] for x in v["candidate_values"]},
                             {x["id"] for x in v["available_probes"]})

    def test_fail_closed_model_choice_counts_as_failure_not_free_retrial(self):
        class Broken(ScriptedChoiceProvider):
            def respond(self,*,case_id,stage,public,max_output_tokens,timeout):
                if case_id=="c11-001" and stage=="revised_choice":
                    self.attempts.append({
                        "case_id":case_id,"stage":stage,
                        "status":"failed",
                        "reported_tokens_even_if_failed":None,
                    })
                    raise ModelChoiceError("synthetic invalid choice")
                return super().respond(
                    case_id=case_id,stage=stage,public=public,
                    max_output_tokens=max_output_tokens,timeout=timeout)
        report=run(Broken(),count=4)
        self.assertEqual(report["summary"]["per_arm"]["tool_self_critique"]["failed"],1)
        self.assertGreaterEqual(
            report["attempt_usage_by_stage"]["revised_choice"]["unknown_usage_calls"],1)
        self.assertEqual(verify_report(report)["cases"],4)

    def test_model_trial_regrade_detects_rewritten_truth_or_probe_path(self):
        report=run(ScriptedChoiceProvider(),count=4)
        data=copy.deepcopy(report)
        data["outcomes"][0]["decision"]["correct"]=not data["outcomes"][0]["decision"]["correct"]
        with self.assertRaisesRegex(InvestigationError,"checksum"):
            verify_report(data)
        data["report_sha256"]=digest({
            k:v for k,v in data.items() if k!="report_sha256"})
        with self.assertRaisesRegex(InvestigationError,"private gold"):
            verify_report(data)
        data=copy.deepcopy(report)
        data["outcomes"][0]["decision"]["chosen"]=["B","B"]
        data["report_sha256"]=digest({
            k:v for k,v in data.items() if k!="report_sha256"})
        with self.assertRaises(InvestigationError):
            verify_report(data)

    def test_model_extra_requests_must_be_bounded(self):
        report=run(ScriptedChoiceProvider(),count=4)
        self.assertEqual(report["summary"]["per_arm"]["recursive_voi"]["meter_reported_tokens"],0)
        self.assertLessEqual(
            report["summary"]["per_arm"]["tool_self_critique"]["model_calls"],
            4*4)


class ChoiceProviderTests(unittest.TestCase):
    def test_arm_and_case_ids_are_not_in_request(self):
        reqs=[]
        def fake_request(req,timeout):
            doc=json.loads(req.data)
            reqs.append(doc)
            body={"choices":[{"message":{"content":json.dumps({
                "choice":"A","reason":"synthetic mocked request"})},
                "finish_reason":"stop"}],"usage":{"total_tokens":37}}
            return io.BytesIO(json.dumps(body).encode())
        provider=QwenChoiceProvider("mockmodelsha","mockengine")
        payload={
            "question":"Find best investigation",
            "available_probes":[{"id":"A","sensitivity":.9,"false_positive":.1}],
            "candidate_values":[{"id":"A","immediate_expected_error":.1,
                                 "exact_remaining_budget_expected_error":.08}],
        }
        with patch("urllib.request.urlopen",side_effect=fake_request):
            a,t=provider.respond(case_id="c11-01",stage="draft_choice",public=payload)
            b,u=provider.respond(case_id="c11-99",stage="draft_choice",public=payload)
        self.assertEqual((a,t,b,u),("A",37,"A",37))
        self.assertEqual(reqs[0],reqs[1])
        self.assertNotIn("c11-01",json.dumps(reqs[0]))
        self.assertNotIn('"arm"',json.dumps(reqs[0]))
        self.assertEqual(provider.attempts[0]["request_sha256"],
                         provider.attempts[1]["request_sha256"])

    def test_parse_error_retains_successful_server_token_charge(self):
        provider=QwenChoiceProvider("mockmodelsha","engine")
        data={"choices":[{"message":{"content":"{not_json"},
                          "finish_reason":"stop"}],
              "usage":{"total_tokens":93}}
        with patch("urllib.request.urlopen",
                   return_value=io.BytesIO(json.dumps(data).encode())):
            with self.assertRaisesRegex(ModelChoiceError,"failed"):
                provider.respond(case_id="c11-001",stage="revised_choice",
                                 public={},max_output_tokens=160,timeout=3)
        self.assertEqual(provider.attempts[-1]["status"],"failed")
        self.assertEqual(provider.attempts[-1]["reported_tokens_even_if_failed"],93)
        self.assertEqual(provider.attempts[-1]["error_type"],"JSONDecodeError")


if __name__=="__main__":
    unittest.main()
