"""Challenge 11 independent real-model audit tests: offline, no live calls."""
from __future__ import annotations

import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from rei0.models import digest
from research.challenge11.independent_analysis import (
    AuditError, audit_report, load_raw_report,
)
from research.challenge11.pilot import (
    ScriptedChoiceProvider, run, _summarize,
)
from research.challenge11.voi import generate


def reseal(report):
    report["report_sha256"] = digest({
        k:v for k,v in report.items() if k!="report_sha256"
    })


class IndependentChoiceAuditTests(unittest.TestCase):
    def sample(self):
        return run(ScriptedChoiceProvider(),seed=20261112,count=4)

    def test_four_case_scripted_audit_satisfies_all_constraints(self):
        report=self.sample()
        data=audit_report(report)
        self.assertEqual(data["cases"],4)
        self.assertEqual(data["original_report_sha256"],report["report_sha256"])
        self.assertEqual(data["summary"]["exact_conventional_bayesian_correct"],4)
        self.assertEqual(data["summary"]["qwen_tool_self_critique_correct"],4)
        self.assertEqual(data["summary"]["calls_with_unknown_model_usage"],0)
        self.assertEqual(
            data["summary"]["model_reported_tokens_including_failed_parses"],
            report["summary"]["per_arm"]["tool_self_critique"]["meter_reported_tokens"],
        )
        self.assertEqual(data["summary"]["claims_about_full_qwen_policy_expected_loss"],
                         "NOT_IDENTIFIABLE_FROM_ONE_PATH")
        self.assertEqual(data["diagnostic_sha256"],digest({
            k:v for k,v in data.items() if k!="diagnostic_sha256"
        }))

    def test_new_seed_regrades_without_using_old_answer_keys(self):
        report=run(ScriptedChoiceProvider(),seed=20261114,count=12)
        data=audit_report(report)
        self.assertEqual(data["cases"],12)
        self.assertEqual(len(data["cases_detail"]),12)
        self.assertEqual(data["seed"],20261114)

    def test_provider_accounting_mismatch_is_not_free_inference(self):
        report=self.sample()
        changed=copy.deepcopy(report)
        changed["provider_attempts"][0]["reported_tokens_even_if_failed"]+=300
        reseal(changed)
        with self.assertRaisesRegex(AuditError,"diverges"):
            audit_report(changed)

    def test_trace_cannot_hide_the_selected_probe(self):
        report=self.sample()
        changed=copy.deepcopy(report)
        chosen=next(r for r in changed["outcomes"]
                    if r["arm"]=="tool_self_critique")
        chosen["trace"][0]["revised_choice"]="D" if (
            chosen["trace"][0]["revised_choice"]!="D") else "A"
        reseal(changed)
        with self.assertRaisesRegex(AuditError,"trace differs"):
            audit_report(changed)

    def test_unreviewed_observation_cannot_be_reported_as_signed(self):
        report=self.sample()
        changed=copy.deepcopy(report)
        x=next(r for r in changed["outcomes"]
               if r["arm"]=="tool_self_critique" and r["decision"]["observations"])
        x["decision"]["observations"][0]["signed_review_status"]="PENDING"
        reseal(changed)
        with self.assertRaisesRegex(AuditError,"unreviewed"):
            audit_report(changed)

    def test_first_choice_regret_is_independently_recomputed(self):
        report=self.sample()
        changed=copy.deepcopy(report)
        item=next(r for r in changed["outcomes"]
                  if r["arm"]=="tool_self_critique")
        item["first_selection_regret_with_optimal_continuation"]+=.05
        # Update summary to defeat an aggregate-only integrity check.
        changed["summary"]=_summarize(changed["outcomes"],generate(20261112,4))
        reseal(changed)
        with self.assertRaisesRegex(AuditError,"first-choice regret"):
            audit_report(changed)

    def test_artifact_loader_accepts_only_one_paired_report(self):
        report=self.sample()
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"choice-live.json"
            path.write_text(json.dumps(report),encoding="utf-8")
            self.assertEqual(load_raw_report(path),report)
            archive=Path(td)/"archived.zip"
            with zipfile.ZipFile(archive,"w") as z:
                z.write(path,"choice-live.json")
                z.writestr("policy-audit.json",json.dumps({"unrelated":True}))
            self.assertEqual(load_raw_report(archive),report)
            with zipfile.ZipFile(archive,"a") as z:
                z.writestr("subfolder/choice-live.json",json.dumps(report))
            with self.assertRaisesRegex(AuditError,"exactly one"):
                load_raw_report(archive)


if __name__=="__main__":
    unittest.main()
