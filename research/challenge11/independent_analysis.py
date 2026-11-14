"""Independent Challenge 11 live-selection audit, without new model inference.

Checks the existing archived report and every model choice against the hidden
synthetic scenario and exact first-choice *optimal-continuation* Bayes risk.
A single observed history cannot establish Qwen's full counterfactual policy
risk. Models receive the same numeric utilities; the REI-labelled planner is
itself an exact conventional Bayesian algorithm, not a separate trained AI.

This analyzer does not change or rewrite Challenge 11 experiment source.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import zipfile

from rei0.models import digest
from .pilot import ARMS, MAX_CALLS, SCHEMA, verify_report
from .voi import BUDGET, generate, optimal_risk, test_value, bayes_risk

DIAGNOSTIC_SCHEMA = "rei.challenge11.independent_choice_audit.v1"


class AuditError(ValueError):
    pass


def load_raw_report(path: str | Path) -> dict:
    """Read an archived JSON, or the published GitHub ZIP without extracting."""
    path = Path(path)
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            chosen = [n for n in archive.namelist() if n.endswith("choice-live.json")]
            if len(chosen) != 1:
                raise AuditError("expected exactly one choice-live.json in ZIP")
            info = archive.getinfo(chosen[0])
            if info.file_size > 2_000_000:
                raise AuditError("oversized archived report")
            data = json.loads(archive.read(info))
    else:
        if path.stat().st_size > 2_000_000:
            raise AuditError("oversized report")
        data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise AuditError("expected original Challenge 11 paired pilot JSON")
    return data


def _near(a, b, *, tol=1e-10):
    return (isinstance(a,(float,int)) and type(a) is not bool
            and math.isfinite(a) and abs(a-b) <= tol)


def audit_report(report: dict) -> dict:
    """Independently scrutinize the paired outcome paths and provider accounting."""
    primary = verify_report(report)
    cases = generate(report["seed"], report["cases"])
    catalog = {c.id: c for c in cases}
    attempts = defaultdict(list)
    for row in report["provider_attempts"]:
        if not isinstance(row,dict):
            raise AuditError("provider attempt must be object")
        cid = row.get("case_id")
        if cid not in catalog:
            raise AuditError("provider attempt has unknown case ID")
        if row.get("stage") not in ("draft_choice","revised_choice"):
            raise AuditError("unknown model request stage")
        attempts[cid].append(row)
    results = []
    wrong_choice_cases = 0
    nonoptimal_first_choices = 0
    for c in cases:
        rows = {r["arm"]:r for r in report["outcomes"] if r["case_id"]==c.id}
        oracle = optimal_risk(c.prior,c.probes,BUDGET)
        exact = rows["recursive_voi"]
        model = rows["tool_self_critique"]
        if exact["model_calls"] != 0 or exact["meter_reported_tokens"] != 0:
            raise AuditError("exact non-model planner must not consume model calls")
        if exact["decision"]["correct"] != (exact["decision"]["prediction"] == c.truth):
            raise AuditError("exact controller correctness mismatch")
        if not _near(exact["decision"]["exact_expected_bayes_error"], oracle):
            raise AuditError("exact planner changed its expected risk")
        if exact["decision"]["chosen"] == model["decision"]["chosen"]:
            same_path = True
        else:
            same_path = False
            wrong_choice_cases += 1
        rows_for_case = attempts[c.id]
        if len(rows_for_case) != model["model_calls"]:
            raise AuditError("model call count differs from provider attempt records")
        if len(rows_for_case) > MAX_CALLS:
            raise AuditError("model requests exceeded case budget")
        if [x["stage"] for x in rows_for_case] != (
            ["draft_choice","revised_choice"] * (len(rows_for_case)//2)
            + (["draft_choice"] if len(rows_for_case) % 2 else [])
        ):
            raise AuditError("model calls have unexpected stage order")
        known = [
            x["reported_tokens_even_if_failed"]
            for x in rows_for_case
            if x.get("reported_tokens_even_if_failed") is not None
        ]
        if any(type(n) is not int or n <= 0 for n in known):
            raise AuditError("invalid server token usage")
        if sum(known) < model["meter_reported_tokens"]:
            raise AuditError("model meter exceeds provider-reported totals")
        if all(x["status"]=="parsed" for x in rows_for_case):
            if sum(known) != model["meter_reported_tokens"]:
                raise AuditError("model token meter diverges from provider accounting")
        trace = model["trace"]
        selected_from_trace = [
            t["revised_choice"] for t in trace if t["revised_choice"] != "STOP"
        ]
        if selected_from_trace != model["decision"]["chosen"]:
            raise AuditError("model selection trace differs from signed measurements")
        for row in model["decision"]["observations"]:
            if row.get("signed_review_status") != "VERIFIED":
                raise AuditError("unreviewed observation was passed to reasoning")
            head = row.get("signed_review_ledger_head")
            if (not isinstance(head,str) or len(head)!=64
                or any(ch not in "0123456789abcdef" for ch in head)):
                raise AuditError("observation has missing or invalid audit digest")
        first = (
            model["decision"]["chosen"][0] if model["decision"]["chosen"]
            else ("STOP" if trace else None)
        )
        if first is None:
            expected_regret = None
        elif first == "STOP":
            expected_regret = max(0.0, bayes_risk(c.prior)-oracle)
        else:
            selected = next((p for p in c.probes if p.id==first),None)
            if selected is None:
                raise AuditError("first choice not in available probes")
            risk_after_first = test_value(
                c.prior,selected,c.probes,BUDGET-1,lookahead=True)
            expected_regret = max(0.0,risk_after_first-oracle)
        if expected_regret is not None and expected_regret < 1e-12:
            expected_regret=0.0
        observed_regret = model["first_selection_regret_with_optimal_continuation"]
        if (expected_regret is None) != (observed_regret is None):
            raise AuditError("unexpected missing first-choice regret")
        if expected_regret is not None and not _near(observed_regret,expected_regret):
            raise AuditError("model's claimed first-choice regret disagrees with audit")
        if expected_regret is not None and expected_regret > 1e-10:
            nonoptimal_first_choices+=1
        results.append({
            "case_id":c.id,
            "model_first_choice":first,
            "exact_first_choice":(
                exact["decision"]["chosen"][0] if exact["decision"]["chosen"] else "STOP"),
            "identical_probe_sequence":same_path,
            "model_first_choice_regret_with_optimal_continuation":expected_regret,
            "model_correct":model["error"] is None and model["decision"]["correct"],
            "exact_correct":exact["error"] is None and exact["decision"]["correct"],
            "model_calls":model["model_calls"],
            "model_server_reported_tokens_including_failed_parses":sum(known),
            "model_reported_token_usage_unknown_calls":sum(
                x.get("reported_tokens_even_if_failed") is None for x in rows_for_case),
        })
    model_total = sum(x["model_server_reported_tokens_including_failed_parses"]
                      for x in results)
    spent_unknown = sum(x["model_reported_token_usage_unknown_calls"] for x in results)
    measured_correct = sum(x["model_correct"] for x in results)
    expected_exact = sum(x["exact_correct"] for x in results)
    mean_regret = sum(x["model_first_choice_regret_with_optimal_continuation"] or 0
                      for x in results)/len(results)
    original_summary=report["summary"]["per_arm"]
    if (measured_correct != original_summary["tool_self_critique"]["correct"]
        or expected_exact != original_summary["recursive_voi"]["correct"]):
        raise AuditError("regraded accuracy disagrees with original report")
    result={
        "schema":DIAGNOSTIC_SCHEMA,
        "original_report_sha256":primary["report_sha256"],
        "study_kind":"public_nonblind_prior_knowledge_toy_domain",
        "cases":len(cases),
        "seed":report["seed"],
        "summary":{
            "exact_conventional_bayesian_correct":expected_exact,
            "qwen_tool_self_critique_correct":measured_correct,
            "cases_with_different_probe_sequences":wrong_choice_cases,
            "qwen_first_choices_with_strict_positive_optimal_continuation_regret":
                nonoptimal_first_choices,
            "mean_qwen_first_choice_regret_if_remaining_steps_optimal":mean_regret,
            "model_reported_tokens_including_failed_parses":model_total,
            "calls_with_unknown_model_usage":spent_unknown,
            "actual_computation_matched":False,
            "claims_about_full_qwen_policy_expected_loss":"NOT_IDENTIFIABLE_FROM_ONE_PATH",
        },
        "cases_detail":results,
        "warnings":[
            "Bayesian planning is a conventional algorithm available to both systems.",
            "All outcomes and test likelihoods are synthetically generated under known assumptions.",
            "This is a public development run, not a blinded independently held-out test.",
            "Only first-choice regret assuming optimal later choices is identifiable from one path.",
            "Review audit hashes are not externally anchored signatures of real-world source truth.",
            "The original report and public seed determine scores: no independent real-world validation.",
        ],
    }
    return {**result,"diagnostic_sha256":digest(result)}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input",required=True,type=Path)
    p.add_argument("--output",type=Path)
    args=p.parse_args(argv)
    d=audit_report(load_raw_report(args.input))
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(d,indent=2)+"\n",encoding="utf-8")
    print("INDEPENDENT CHOICE AUDIT:",json.dumps(d["summary"],indent=2))
    for item in d["cases_detail"]:
        print(item["case_id"],"exact:",item["exact_first_choice"],
              "model:",item["model_first_choice"],
              "first_choice_regret:",item["model_first_choice_regret_with_optimal_continuation"])
    return 0


if __name__=="__main__":
    raise SystemExit(main())
