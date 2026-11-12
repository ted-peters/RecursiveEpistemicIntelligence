"""Offline Challenge 9 paired-trial and arm-blind-provider tests.

A scripted responder checks orchestration ONLY; its answers are not real
intelligence measurements. Live model inference is never triggered by CI.
"""
from __future__ import annotations

from collections import Counter
import io
import json
import unittest
from unittest.mock import patch

from rei0.benchmark import BenchmarkError
from rei0.inquiry import ModelTurn
from rei0.models import digest
from research.challenge9.arm_blind_provider import ArmBlindLocalProvider
from research.challenge9.paired_trial import (
    ARMS, _model_case, run_trial, verify_trial,
)
from research.challenge9.interventions import generate_cases, replay_case


class ScriptedResponder:
    kind="scripted_fixture_not_live_inference"
    fingerprint="synthetic-twin-arm-protocol-test"

    def __init__(self, fail_expand=False):
        self.calls=[]
        self.attempts=[]
        self.fail_expand=fail_expand

    def respond(self, *, case_id, arm, stage, context,
                max_output_tokens, timeout):
        self.calls.append({"case_id":case_id,"arm":arm,
                           "stage":stage,"context":context})
        fail=(self.fail_expand and case_id=="c9-04" and
              arm=="rei12" and stage=="expand")
        self.attempts.append({
            "case_id":case_id,"arm":arm,"stage":stage,
            "reported_tokens_even_if_failed":15,
            "status":"failed" if fail else "parsed",
        })
        if fail:
            raise ValueError("synthetic failed expansion")
        if stage=="initial":
            result={"claim":"This is a provisional inference about P.",
                    "questions":[{"text":"Could contrary reports overturn P?",
                                  "target":"claim","priority":9}]}
        elif stage=="expand":
            result={"reasons":["A signed report is present"],
                    "objections":["A source can later be revoked"],
                    "followups":[],"note":"Provisional analysis only"}
        elif stage=="critique":
            result={"critique":"Check revocations and duplicate source groups."}
        else:
            result={"answer":"NEITHER","confidence":0.5,
                    "rationale":"Synthetic fixture reply, not a model."}
        return ModelTurn(result,15)


class PairedTrialTests(unittest.TestCase):
    def test_simulated_four_case_pair_is_complete_and_regraded(self):
        fixture=ScriptedResponder()
        result=run_trial(fixture,count=4)
        self.assertEqual(result["mode"],fixture.kind)
        self.assertEqual(result["case_count"],4)
        self.assertEqual(len(result["outcomes"]),8)
        self.assertEqual(result["summary"]["arms"]["self_critique"]["correct"],1)
        self.assertEqual(result["summary"]["arms"]["rei12"]["correct"],1)
        self.assertEqual(result["summary"]["arms"]["self_critique"]["model_calls"],12)
        self.assertEqual(result["summary"]["arms"]["rei12"]["model_calls"],9)
        self.assertEqual(result["summary"]["primary_rei_minus_self_critique"]
                         ["paired_accuracy_difference"],0)
        self.assertFalse(result["summary"]["primary_rei_minus_self_critique"]
                         ["compute_matched"])
        self.assertEqual(result["attempt_usage"]["rei12"]["attempts"],9)
        self.assertEqual(result["attempt_usage"]["self_critique"]["attempts"],12)
        self.assertEqual(verify_trial(result,seed=20261111,count=4)["outcomes"],8)

    def test_only_contradictory_signed_cases_trigger_extra_inquiry(self):
        fixture=ScriptedResponder()
        result=run_trial(fixture,count=4)
        rei={row["case_id"]:row for row in result["outcomes"]
             if row["arm"]=="rei12"}
        self.assertEqual(rei["c9-01"]["method"]["steps"],0)
        self.assertEqual(rei["c9-02"]["method"]["steps"],0)
        self.assertEqual(rei["c9-03"]["method"]["steps"],0)
        self.assertEqual(rei["c9-04"]["method"]["steps"],1)
        self.assertEqual(rei["c9-04"]["method"]["stop_reason"],"step_budget")

    def test_same_authenticated_docket_reaches_both_methods(self):
        fixture=ScriptedResponder()
        run_trial(fixture,count=4)
        by_case={}
        for call in fixture.calls:
            if call["stage"]=="final":
                by_case.setdefault(call["case_id"],{})[call["arm"]]=(
                    call["context"]["trusted_docket"]
                )
        self.assertEqual(set(by_case),{"c9-01","c9-02","c9-03","c9-04"})
        for views in by_case.values():
            self.assertEqual(views["rei12"],views["self_critique"])
            for row in views["rei12"]["evidence"]:
                self.assertNotIn("answer",row)
                self.assertNotIn("expected",row)
        for call in fixture.calls:
            payload=json.dumps(call["context"])
            self.assertNotIn('"expected":',payload)
            self.assertNotIn('"oracle":',payload)
            self.assertNotIn('"private_key":',payload)

    def test_synthetic_provider_error_counts_as_failed_not_abstention(self):
        fixture=ScriptedResponder(fail_expand=True)
        report=run_trial(fixture,count=4)
        target=next(row for row in report["outcomes"]
                    if row["case_id"]=="c9-04" and row["arm"]=="rei12")
        self.assertIsNotNone(target["error"])
        self.assertIsNone(target["answer"])
        self.assertEqual(report["summary"]["arms"]["rei12"]["failed"],1)
        self.assertEqual(report["summary"]["arms"]["rei12"]["abstained"],0)
        self.assertEqual(report["attempt_usage"]["rei12"]["provider_failed_calls"],1)

    def test_tampered_or_duplicated_report_is_detected(self):
        report=run_trial(ScriptedResponder(),count=4)
        report["outcomes"][0]["answer"]="BOTH"
        with self.assertRaisesRegex(BenchmarkError,"checksum"):
            verify_trial(report,seed=20261111,count=4)
        report["report_sha256"]=digest({
            k:v for k,v in report.items() if k!="report_sha256"
        })
        with self.assertRaisesRegex(BenchmarkError,"summary"):
            verify_trial(report,seed=20261111,count=4)
        report=run_trial(ScriptedResponder(),count=4)
        report["outcomes"][0]=dict(report["outcomes"][1])
        report["report_sha256"]=digest({
            k:v for k,v in report.items() if k!="report_sha256"
        })
        with self.assertRaises(BenchmarkError):
            verify_trial(report,seed=20261111,count=4)

    def test_public_case_contains_no_gold_field(self):
        c=generate_cases()[0]
        public=replay_case(c)["public_docket"]
        model_case=_model_case(c,public)
        self.assertEqual(model_case.category,"signed_evidence_revision")
        context=json.loads(model_case.context)
        self.assertEqual(context,public)
        self.assertNotIn("expected",context)
        self.assertNotIn("oracle",context)
        self.assertNotIn("final_state",context)


class ArmBlindProviderTests(unittest.TestCase):
    def test_same_stage_request_is_byte_identical_across_arms(self):
        sent=[]
        def reply(req,timeout):
            body=json.loads(req.data)
            sent.append(body)
            payload={"choices":[{"message":{"content":json.dumps({
                "answer":"NEITHER","confidence":0.5,
                "rationale":"synthetic provider reply"
            })},"finish_reason":"stop"}],"usage":{"total_tokens":42}}
            return io.BytesIO(json.dumps(payload).encode("utf-8"))
        p=ArmBlindLocalProvider("sha","engine")
        with patch("urllib.request.urlopen",side_effect=reply):
            for arm in ARMS:
                p.respond(case_id="fiction",arm=arm,stage="final",
                          context={"question":"question","trusted_docket":{"evidence":[]}},
                          max_output_tokens=320,timeout=3)
        self.assertEqual(sent[0],sent[1])
        self.assertNotIn('"arm"',json.dumps(sent[0]))
        self.assertNotIn('"case_id"',json.dumps(sent[0]))
        self.assertEqual(p.attempts[0]["request_sha256"],p.attempts[1]["request_sha256"])
        self.assertEqual(sum(a["reported_tokens_even_if_failed"] for a in p.attempts),84)

    def test_invalid_json_still_charges_server_tokens(self):
        p=ArmBlindLocalProvider("sha","engine")
        body={"choices":[{"message":{"content":"{invalid"},
                          "finish_reason":"stop"}],
              "usage":{"total_tokens":101}}
        with patch("urllib.request.urlopen",
                   return_value=io.BytesIO(json.dumps(body).encode("utf-8"))):
            with self.assertRaisesRegex(ValueError,"structured model response failed"):
                p.respond(case_id="c9-01",arm="rei12",stage="final",
                          context={},max_output_tokens=320,timeout=3)
        self.assertEqual(p.attempts[0]["status"],"failed")
        self.assertEqual(p.attempts[0]["reported_tokens_even_if_failed"],101)
        self.assertEqual(p.attempts[0]["error_type"],"JSONDecodeError")


if __name__=="__main__":
    unittest.main()
