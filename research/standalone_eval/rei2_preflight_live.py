"""REI 2.0 *candidate*, small real-Qwen paired smoke, NOT release certification.

Uses two public Challenge 12 development cases, two arms each (Direct and
Adaptive on a bounded task; Adaptive and Full REI on an investigative task).
The real Ollama model is invoked. No test answer key enters a model prompt.
A separate verifier reopens the case file and checks route, grade and usage.
This is NOT a held-out test, cost-matched study, or the R4/R5/R6 release gate.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from rei0.local_ai import StandaloneREI, LocalOllamaModel, LocalAIError
from rei0.local_ai_router import choose_route
from rei0.models import digest
from research.standalone_eval.challenge12_quality import load_cases, visible_question
from research.standalone_eval.paired_quality import answer_letter

SCHEMA = "rei2.candidate.public_real_smoke.v1"
TASKS = ((0, ("direct", "adaptive")), (9, ("adaptive", "rei")))
WARNINGS = [
    "This test calls real local Ollama; questions are PUBLIC development examples.",
    "It is not 200 independently keyed held-out tasks, repeated seeds, or matched tokens.",
    "Accuracy based on the final Answer: X marker; formatting errors count as incorrect.",
    "All REI claims remain provisional model-generated content, not verified evidence.",
    "REI 2.0 is not yet a stable release, and these results cannot certify its gates.",
]


class PreflightError(ValueError):
    pass


def expected_rows(cases):
    return [(i, mode) for i, modes in TASKS for mode in modes]


def run_live(*, model_name: str, endpoint: str, label: str) -> dict:
    cases, case_hash = load_cases()
    report = {
        "schema": SCHEMA,
        "provider_kind": "ollama_live",
        "label": label,
        "model": model_name,
        "case_set_digest": case_hash,
        "task_order": [c["id"] + ":" + mode
                       for i, mode in expected_rows(cases)
                       for c in [cases[i]]],
        "outcomes": [],
        "warnings": WARNINGS,
    }
    for index, mode in expected_rows(cases):
        case = cases[index]
        task = visible_question(case)
        provider = LocalOllamaModel(model=model_name, endpoint=endpoint)
        agent = StandaloneREI(provider_factory=lambda: provider,
                              model=model_name, endpoint=endpoint)
        start = time.monotonic()
        response = None
        err = None
        try:
            response = agent.answer([{"role": "user", "content": task}], mode=mode)
        except (LocalAIError, OSError, TimeoutError, ValueError) as exc:
            # Exclude possibly private content from exceptions in the report.
            err = type(exc).__name__
        elapsed = round(time.monotonic() - start, 3)
        attempts = [{"status": str(a["status"])[:48],
                     "tokens": a.get("tokens")}
                    for a in provider.attempts]
        letter = answer_letter(response["answer"]) if response else None
        result = {
            "case_id": case["id"],
            "requested_mode": mode,
            "answer": response["answer"] if response else "",
            "final_letter": letter,
            "correct": err is None and letter == case["correct"],
            "error_type": err,
            "model_calls": len(attempts),
            "reported_tokens_known": sum(a["tokens"] or 0 for a in attempts),
            "unknown_usage_calls": sum(a["tokens"] is None for a in attempts),
            "elapsed_seconds": elapsed,
            "attempts": attempts,
            "audit": response["audit"] if response else None,
        }
        report["outcomes"].append(result)
        print("REAL:", result["case_id"], mode,
              "calls", result["model_calls"],
              "tokens", result["reported_tokens_known"],
              "correct", result["correct"],
              "error", result["error_type"], flush=True)
    return {**report, "report_sha256": digest(report)}


def verify(report: dict) -> dict:
    cases, case_hash = load_cases()
    if not isinstance(report, dict) or report.get("schema") != SCHEMA:
        raise PreflightError("invalid report schema")
    body = {key: value for key, value in report.items() if key != "report_sha256"}
    if digest(body) != report.get("report_sha256"):
        raise PreflightError("report integrity mismatch")
    if report.get("provider_kind") != "ollama_live":
        raise PreflightError("only genuine local Qwen inferences qualify")
    if report.get("case_set_digest") != case_hash:
        raise PreflightError("case set does not match frozen keys")
    order = [cases[i]["id"] + ":" + mode for i, mode in expected_rows(cases)]
    if report.get("task_order") != order:
        raise PreflightError("incorrect task order")
    rows = report.get("outcomes")
    if not isinstance(rows, list) or len(rows) != len(order):
        raise PreflightError("missing paired responses")
    summary = {"valid": True, "real_model": report["model"],
               "task_count": len(order), "scored_correct": 0,
               "invalid_answer_formats": 0, "failed_requests": 0,
               "total_model_calls": 0, "known_reported_tokens": 0,
               "unknown_usage_calls": 0, "elapsed_seconds": 0.0,
               "details": [], "release_gate": "NOT_CERTIFIED"}
    for result, (index, mode) in zip(rows, expected_rows(cases)):
        case = cases[index]
        if (result.get("case_id") != case["id"] or
            result.get("requested_mode") != mode):
            raise PreflightError("wrong or reordered case/mode")
        letter = answer_letter(result.get("answer"))
        if (letter != result.get("final_letter") or
            result.get("correct") != (result.get("error_type") is None
                                      and letter == case["correct"])):
            raise PreflightError("incorrect independent grade")
        attempts = result.get("attempts")
        if not isinstance(attempts, list) or len(attempts) != result.get("model_calls"):
            raise PreflightError("call attempt mismatch")
        for a in attempts:
            if not isinstance(a, dict) or set(a) != {"status", "tokens"}:
                raise PreflightError("invalid attempt fields")
            if (type(a["status"]) is not str or
                (a["tokens"] is not None and
                 (type(a["tokens"]) is not int or a["tokens"] < 0))):
                raise PreflightError("invalid provider usage fields")
        total = sum(a["tokens"] or 0 for a in attempts)
        unknown = sum(a["tokens"] is None for a in attempts)
        if (total != result.get("reported_tokens_known") or
            unknown != result.get("unknown_usage_calls")):
            raise PreflightError("token meter mismatch")
        if (type(result.get("elapsed_seconds")) not in (int, float)
            or not 0 <= result["elapsed_seconds"] <= 3000):
            raise PreflightError("invalid elapsed time")
        audit = result.get("audit")
        if audit is not None:
            if (audit.get("model_calls") != len(attempts)
                or audit.get("model_reported_tokens") != total
                or audit.get("evidence_status") not in
                ("not_verified", "model_proposals_only_unverified")):
                raise PreflightError("invalid model audit or false verified claim")
            if mode == "adaptive":
                expected = choose_route([{"role": "user",
                                         "content": visible_question(case)}]).selected_mode
                if (audit.get("execution_mode") != expected or
                    audit.get("routing", {}).get("additional_router_model_calls") != 0):
                    raise PreflightError("adaptive routing audit inconsistent")
            if mode == "direct" and len(attempts) != 1:
                raise PreflightError("direct mode not one call")
            if mode == "rei" and not 2 <= len(attempts) <= 4:
                raise PreflightError("full REI exceeded model call policy")
        summary["scored_correct"] += int(result["correct"])
        summary["invalid_answer_formats"] += int(letter is None)
        summary["failed_requests"] += int(result.get("error_type") is not None)
        summary["total_model_calls"] += len(attempts)
        summary["known_reported_tokens"] += total
        summary["unknown_usage_calls"] += unknown
        summary["elapsed_seconds"] += result["elapsed_seconds"]
        summary["details"].append({
            "case": case["id"], "requested_mode": mode,
            "executed_mode": audit.get("execution_mode", mode) if audit else None,
            "correct": result["correct"], "valid_format": letter is not None,
            "error_type": result.get("error_type"), "model_calls": len(attempts),
            "tokens": total,
        })
    summary["elapsed_seconds"] = round(summary["elapsed_seconds"], 3)
    return summary


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", default="qwen3:4b-instruct")
    p.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--verify-only", action="store_true")
    args = p.parse_args(argv)
    if args.verify_only:
        report = json.loads(args.output.read_text(encoding="utf-8"))
    else:
        report = run_live(model_name=args.model, endpoint=args.ollama_url,
                          label="rei2-public-preflight-20261115")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n",
                               encoding="utf-8")
    print("INDEPENDENT REGRADING:", json.dumps(verify(report), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
