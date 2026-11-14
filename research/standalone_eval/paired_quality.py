"""Paired, reproducible REI-vs-direct local model evaluation.

The same Ollama model, public objective multiple-choice tasks, and deterministic
temperature are used in both arms. A separate programmatic grader computes
scores; the answer keys are NEVER placed in the model's prompt or scaffold.

This is a small PUBLIC development quality-gate, not a blinded scientific
benchmark. The modes have very different model-call costs and are NOT
compute matched. Do not confuse fixture mode with model inference.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
from typing import Callable

from rei0.local_ai import LocalAIError, LocalOllamaModel, StandaloneREI
from rei0.models import digest

SCHEMA = "rei.standalone.paired_quality.v1"
CASES_FILE = Path(__file__).with_name("cases.json")
ANSWER = re.compile(r"(?i)^Answer:\s*([ABCD])\.?$")
OPTIONS = frozenset("ABCD")
MODES = ("direct", "rei")
PREFIX = ("Select the single best option. A brief explanation is optional. "
          "Finish with a final line EXACTLY in the form Answer: X, "
          "where X is the one letter A, B, C, or D.\n\n")
WARNINGS = [
    "Public hand-authored development questions, NOT a blinded held-out benchmark.",
    "A correct multiple-choice letter is not a comprehensive measure of answer quality.",
    "Direct and REI do not have matched model-call, latency, or token budgets.",
    "The REI scaffold remains model-origin and is NOT authenticated factual evidence.",
    "This is not a proof of REI superiority or a trained REI-native foundation model.",
]


class QualityGateError(ValueError):
    pass


def load_cases(path: Path = CASES_FILE) -> tuple[list[dict], str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw,dict) or raw.get("schema") != "rei.local_ai.paired_development_cases.v1":
        raise QualityGateError("unexpected benchmark case schema")
    entries = raw.get("cases")
    if not isinstance(entries,list) or not 1 <= len(entries) <= 20:
        raise QualityGateError("benchmark must have 1-20 cases")
    seen=set()
    for entry in entries:
        if not isinstance(entry,dict) or set(entry) != {"id","domain","question","correct"}:
            raise QualityGateError("benchmark case keys incorrect")
        ident=entry["id"]
        if not isinstance(ident,str) or not re.fullmatch(r"[a-z][a-z0-9-]{2,63}",ident):
            raise QualityGateError("invalid case identifier")
        if ident in seen:
            raise QualityGateError("duplicate case")
        seen.add(ident)
        if (not isinstance(entry["question"],str) or
            not 50 <= len(entry["question"]) <= 1500 or
            not isinstance(entry["domain"],str) or
            not 1 <= len(entry["domain"]) <= 40 or
            entry["correct"] not in OPTIONS or type(entry["correct"]) is not str):
            raise QualityGateError("invalid benchmark question or key")
        if "Answer:" in entry["question"]:
            raise QualityGateError("answer final marker must not appear in a question")
    return entries,digest(raw)


def answer_letter(content: str) -> str | None:
    """Require exact, final Answer: LETTER (reject incidental text or guesses)."""
    if not isinstance(content,str):
        return None
    lines=[x.strip() for x in content.splitlines() if x.strip()]
    if not lines:
        return None
    match=ANSWER.fullmatch(lines[-1])
    return match.group(1).upper() if match else None


def model_visible_question(case: dict) -> str:
    """Never pass case keys, IDs or test scores to model context."""
    return PREFIX+case["question"]


def mode_order(case_index: int) -> tuple[str, str]:
    return MODES if case_index%2==0 else ("rei","direct")


def run_paired(*, cases: list[dict], cases_digest: str,
               factory: Callable, provider_kind: str,
               model: str, run_label: str) -> dict:
    if provider_kind not in ("fixture","ollama_live"):
        raise QualityGateError("provider_kind must clearly indicate fixture or real inference")
    if not isinstance(run_label,str) or not 1 <= len(run_label) <= 80:
        raise QualityGateError("run label is mandatory")
    outcomes=[]
    for idx,case in enumerate(cases):
        question=model_visible_question(case)
        for mode in mode_order(idx):
            agent,attempts=factory()
            start=time.monotonic()
            response=None
            failure=None
            try:
                response=agent.answer([{"role":"user","content":question}],mode=mode)
            except (LocalAIError,ValueError,OSError,TimeoutError) as exc:
                # Never copy raw user/model text or prompt fragments from errors.
                failure=type(exc).__name__
            elapsed=round(time.monotonic()-start,3)
            if response is not None:
                if (not isinstance(response,dict) or
                    response.get("mode") != mode or
                    not isinstance(response.get("answer"),str) or
                    not isinstance(response.get("audit"),dict)):
                    raise QualityGateError("runtime returned a malformed result")
            token_records=[]
            for attempt in attempts:
                if not isinstance(attempt,dict):
                    raise QualityGateError("invalid model attempt")
                tok=attempt.get("tokens")
                if tok is not None and (type(tok) is not int or tok < 0):
                    raise QualityGateError("invalid model metering")
                token_records.append({
                    "status":str(attempt.get("status","unknown"))[:40],
                    "tokens":tok,
                })
            answer=response["answer"] if response else ""
            answer_choice=answer_letter(answer)
            result={
                "case_id":case["id"],
                "mode":mode,
                "answer_text":answer,
                "extracted_final_answer":answer_choice,
                "correct":failure is None and answer_choice==case["correct"],
                "format_valid":answer_choice is not None,
                "error_type":failure,
                "model_calls":len(token_records),
                "known_reported_tokens":sum(x["tokens"] or 0 for x in token_records),
                "unknown_usage_calls":sum(x["tokens"] is None for x in token_records),
                "elapsed_seconds":elapsed,
                "audit":response["audit"] if response else None,
                "attempts":token_records,
            }
            if response and response["audit"].get("model_calls") != result["model_calls"]:
                raise QualityGateError("model call count mismatch")
            if response and response["audit"].get("model_reported_tokens") != result["known_reported_tokens"]:
                raise QualityGateError("usage meter mismatch")
            outcomes.append(result)
    data={
        "schema":SCHEMA,
        "provider_kind":provider_kind,
        "run_label":run_label,
        "model":model,
        "case_set_digest":cases_digest,
        "case_count":len(cases),
        "case_ids":[x["id"] for x in cases],
        "order_rule":"even_index_direct_first_odd_index_rei_first",
        "outcomes":outcomes,
        "warnings":WARNINGS,
    }
    return {**data,"report_sha256":digest(data)}


def verify_report(report: dict, *, cases: list[dict],
                  cases_digest: str) -> dict:
    if not isinstance(report,dict) or report.get("schema")!=SCHEMA:
        raise QualityGateError("unexpected study report")
    body={k:v for k,v in report.items() if k!="report_sha256"}
    if digest(body)!=report.get("report_sha256"):
        raise QualityGateError("report integrity hash mismatch")
    if report.get("case_set_digest") != cases_digest:
        raise QualityGateError("different or modified benchmark case set")
    if report.get("case_ids") != [x["id"] for x in cases]:
        raise QualityGateError("wrong case order")
    if report.get("case_count")!=len(cases) or len(report.get("outcomes",[]))!=2*len(cases):
        raise QualityGateError("missing or extra paired results")
    counts={k:{"correct":0,"total":0,"format_failures":0,"failed_calls":0,
               "model_calls":0,"tokens_known":0,"unknown_usage_calls":0,
               "elapsed_seconds":0.0} for k in MODES}
    for idx,c in enumerate(cases):
        for offset,mode in enumerate(mode_order(idx)):
            row=report["outcomes"][2*idx+offset]
            if row["case_id"]!=c["id"] or row["mode"]!=mode:
                raise QualityGateError("unpaired or reordered model output")
            answer=answer_letter(row["answer_text"])
            if answer != row["extracted_final_answer"] or row["format_valid"] != (answer is not None):
                raise QualityGateError("invalid independent format grade")
            if row["correct"] != (row["error_type"] is None and answer==c["correct"]):
                raise QualityGateError("incorrect independent accuracy grade")
            if not isinstance(row["attempts"],list):
                raise QualityGateError("no provider-attempt record")
            if row["model_calls"]!=len(row["attempts"]):
                raise QualityGateError("model call count differs from raw attempts")
            for a in row["attempts"]:
                if (not isinstance(a,dict) or set(a)!={"status","tokens"}
                    or type(a["status"]) is not str
                    or (a["tokens"] is not None and
                        (type(a["tokens"]) is not int or a["tokens"]<0))):
                    raise QualityGateError("corrupt provider usage")
            known=sum(a["tokens"] or 0 for a in row["attempts"])
            unknown=sum(a["tokens"] is None for a in row["attempts"])
            if known!=row["known_reported_tokens"] or unknown!=row["unknown_usage_calls"]:
                raise QualityGateError("incorrect provider usage accounting")
            if row["audit"] is not None:
                if row["audit"]["model_calls"]!=row["model_calls"] or row["audit"]["model_reported_tokens"]!=known:
                    raise QualityGateError("model audit mismatch")
                if row["audit"].get("evidence_status") not in ("not_verified","model_proposals_only_unverified"):
                    raise QualityGateError("model-origin evidence was mislabeled as verified")
            if row["error_type"] is None and not row["answer_text"].strip():
                raise QualityGateError("successful answer cannot be empty")
            if (type(row["elapsed_seconds"]) not in (float,int)
                or not 0<=row["elapsed_seconds"]<=4000):
                raise QualityGateError("invalid elapsed time")
            stats=counts[mode]
            stats["total"]+=1
            stats["correct"]+=int(row["correct"])
            stats["format_failures"]+=int(not row["format_valid"])
            stats["failed_calls"]+=int(row["error_type"] is not None)
            stats["model_calls"]+=row["model_calls"]
            stats["tokens_known"]+=known
            stats["unknown_usage_calls"]+=unknown
            stats["elapsed_seconds"]+=row["elapsed_seconds"]
    for mode in MODES:
        counts[mode]["accuracy"]=counts[mode]["correct"]/len(cases)
        counts[mode]["elapsed_seconds"]=round(counts[mode]["elapsed_seconds"],3)
    return {
        "valid":True,
        "case_count":len(cases),
        "provider_kind":report["provider_kind"],
        "summary":counts,
        "paired_delta_correct_REI_minus_direct":counts["rei"]["correct"]-counts["direct"]["correct"],
        "report_sha256":report["report_sha256"],
        "warning":"Public development set; small and not compute-matched; does not show general superiority",
    }


class FixtureAgent:
    """Intentionally synthetic fake; never describe as genuine model inference."""
    def __init__(self):
        self.attempts=[]
    def answer(self, messages, *, mode):
        self.attempts.append({"status":"fixture","tokens":11})
        return {"mode":mode,"answer":"A mock answer.\nAnswer: B",
                "audit":{"mode":mode,"model_calls":1,"model_reported_tokens":11,
                         "evidence_status":"not_verified"}}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--kind",choices=("fixture","live"),default="fixture")
    p.add_argument("--model",default="qwen3:4b-instruct")
    p.add_argument("--ollama-url",default="http://127.0.0.1:11434")
    p.add_argument("--output",type=Path)
    p.add_argument("--verify-only",action="store_true")
    p.add_argument("--label",default="six-public-development-questions-20261114")
    p.add_argument("--count",type=int,default=6)
    args=p.parse_args(argv)
    cases,case_digest=load_cases()
    if not 1<=args.count<=len(cases):
        p.error("--count must select 1 to the entire case set")
    cases=cases[:args.count]
    if args.verify_only:
        if not args.output:
            p.error("--verify-only needs --output")
        result=verify_report(json.loads(args.output.read_text()),
                             cases=cases,cases_digest=case_digest)
        print("INDEPENDENT REGRADING:",json.dumps(result,indent=2))
        return 0
    if args.kind=="fixture":
        factory=lambda:(lambda x:(x,x.attempts))(FixtureAgent())
    else:
        def factory():
            model=LocalOllamaModel(model=args.model,endpoint=args.ollama_url)
            return (StandaloneREI(provider_factory=lambda:model,model=args.model,
                                  endpoint=args.ollama_url),model.attempts)
    report=run_paired(cases=cases,cases_digest=case_digest,
                      factory=factory,provider_kind=("fixture" if args.kind=="fixture"
                                                       else "ollama_live"),
                      model=("synthetic-fixture" if args.kind=="fixture" else args.model),
                      run_label=args.label)
    result=verify_report(report,cases=cases,cases_digest=case_digest)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",
                               encoding="utf-8")
    print("PAIRED QUALITY:",json.dumps(result,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
