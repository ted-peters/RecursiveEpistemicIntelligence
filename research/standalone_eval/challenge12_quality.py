"""Challenge 12: real-model, multi-arm, cost-vs-accuracy development protocol.

Four arms, the SAME local Ollama model and the SAME question text per case:
  direct          one model call
  adaptive        REI routing policy, 1 or up to 4 model calls
  rei             original bounded REI graph, up to 4 model calls
  self_critique   conventional four-call draft/critique/check/revise

All final answers are independently scored against frozen multiple-choice keys.
A public 12-case task set is a development *smoke benchmark*, NOT blinded
held-out generalization evidence. Four calls is NOT equal token or compute cost.
Fixture mode is synthetic and NEVER evidence of model accuracy.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import time

from rei0.inquiry import ModelTurn
from rei0.local_ai import LocalAIError, LocalOllamaModel, StandaloneREI
from rei0.local_ai_router import choose_route
from rei0.models import digest
from research.standalone_eval.paired_quality import answer_letter

CASES_PATH=Path(__file__).with_name("challenge12_cases.json")
CASE_SCHEMA="rei.standalone.challenge12.public_cases.v1"
REPORT_SCHEMA="rei.standalone.challenge12.report.v1"
ARMS=("direct","adaptive","rei","self_critique")
FORMAT_PREFIX=(
    "Choose exactly ONE best answer, A, B, C or D. Explain briefly when "
    "helpful. Finish with an exact final line: Answer: X where X is your "
    "chosen capital letter. Do not claim external fact-checking.\n\n"
)
INVESTIGATION_PREFIX=(
    "Investigate the competing assumptions and possible mistakes in this "
    "problem before selecting the most defensible option.\n\n"
)
WARNINGS=[
    "Twelve PUBLIC handcrafted development questions: not a blinded held-out study.",
    "All task solutions are multiple-choice; not representative of real-world chat.",
    "Four model calls does not equal token/latency/compute matching.",
    "REI and self-critique are not authenticated empirical evidence.",
    "No claim of general REI superiority or trained REI-native language weights.",
]


class Challenge12Error(ValueError):
    pass


def load_cases(path: Path=CASES_PATH) -> tuple[list[dict],str]:
    doc=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc,dict) or doc.get("schema")!=CASE_SCHEMA:
        raise Challenge12Error("unexpected case schema")
    cases=doc.get("cases")
    if not isinstance(cases,list) or len(cases)!=12:
        raise Challenge12Error("exactly twelve preregistered cases are required")
    seen=set()
    for i,c in enumerate(cases):
        if not isinstance(c,dict) or set(c)!={"id","style","domain","question","correct"}:
            raise Challenge12Error("invalid case fields")
        if (not isinstance(c["id"],str) or
            not re.fullmatch(r"[a-z][a-z0-9-]{3,63}",c["id"]) or
            c["id"] in seen):
            raise Challenge12Error("invalid or duplicate case identifier")
        seen.add(c["id"])
        if (c["style"]!=("bounded" if i%2==0 else "investigate")
            or type(c["domain"]) is not str or not 1<=len(c["domain"])<=40
            or type(c["question"]) is not str
            or not 80<=len(c["question"])<=1800
            or type(c["correct"]) is not str or c["correct"] not in "ABCD"):
            raise Challenge12Error("invalid case style, domain, problem or answer")
        lines=re.findall(r"(?m)^([ABCD])\.\s+\S",c["question"])
        if lines!=list("ABCD"):
            raise Challenge12Error("four ordered answer options are required")
        if "Answer: " in c["question"]:
            raise Challenge12Error("answer key or final-answer marker in question")
    return cases,digest(doc)


def visible_question(case:dict)->str:
    """Only instructions and the task's public question enter model context."""
    return (INVESTIGATION_PREFIX if case["style"]=="investigate" else "")+FORMAT_PREFIX+case["question"]


def arm_order(case_index: int)->tuple[str,...]:
    n=case_index%len(ARMS)
    return ARMS[n:]+ARMS[:n]


def run_conventional_self_critique(provider, question: str)->dict:
    """Conventional FOUR call baseline, independent of REI graph machinery.

    Reuses Ollama's normal generation client and token meter. Uses no tools,
    outside verification, or REI-specific prompts. Reviewer text is only the
    model's own unverified opinion. No fallback if a stage fails.
    """
    system=("You are a local assistant completing a multiple-choice problem. "
            "Use only stated information, check arithmetic and logic, and "
            "be explicit about uncertainty. Do not invent external sources.")
    draft,_=provider.complete(system=system,user=question,
                              max_output_tokens=512,timeout=150)
    critique,_=provider.complete(
        system=system,
        user=json.dumps({
            "task":question,
            "draft_answer":draft[:2400],
            "instruction":("Find the most likely error in the draft, if any. "
                           "Explain concisely. Do NOT assume the draft is correct."),
        },ensure_ascii=False),
        max_output_tokens=512,timeout=150)
    check,_=provider.complete(
        system=system,
        user=json.dumps({
            "task":question,
            "draft_answer":draft[:1800],
            "criticisms":critique[:1800],
            "instruction":("Independently verify the option by logical or numerical "
                           "reasoning. If the criticism is wrong, say why. "
                           "No outside facts are available."),
        },ensure_ascii=False),
        max_output_tokens=512,timeout=150)
    final,_=provider.complete(
        system=system,
        user=json.dumps({
            "task":question,
            "draft_answer":draft[:1400],
            "criticism":critique[:1400],
            "independent_check":check[:1400],
            "instruction":("Answer the original task. End with exactly "
                           "Answer: X on the last line, with one letter A-D."),
        },ensure_ascii=False),
        max_output_tokens=512,timeout=150)
    if len(provider.attempts)!=4:
        raise Challenge12Error("self-critique baseline did not use four model calls")
    used=sum(a["tokens"] or 0 for a in provider.attempts)
    return {
        "answer":final.strip(),
        "mode":"self_critique",
        "audit":{
            "mode":"self_critique",
            "model_calls":len(provider.attempts),
            "model_reported_tokens":used,
            "graph_audit_head":None,
            "stop_reason":"self_critique_four_calls",
            "evidence_status":"not_verified",
            "note":"Conventional self-review, not external verification",
        },
    }


class SyntheticProvider:
    """No Ollama dependency; deliberately fake outputs for unit tests."""
    name="challenge12-synthetic-provider"
    def __init__(self):
        self.attempts=[]
    def initial(self, question, *, max_output_tokens, timeout):
        self.attempts.append({"status":"ok","tokens":7})
        return ModelTurn({
            "claim":"An unverified candidate answer.",
            "questions":[{"text":"What alternative matters?",
                          "target":"claim","priority":9}],
        },7)
    def expand(self, context, *, ordinal, max_output_tokens, timeout):
        self.attempts.append({"status":"ok","tokens":13})
        return ModelTurn({
            "reasons":["This may fit the prompt."],
            "objections":["It may fail under another assumption."],
            "followups":[],
            "note":"Synthetic provisional test",
        },13)
    def complete(self, *, system, user, max_output_tokens, timeout):
        self.attempts.append({"status":"ok","tokens":17})
        return "Synthetic answer, not a real model.\nAnswer: B",17


def evaluate(*, cases:list[dict], case_digest:str,
             shard_index:int, shards:int,
             provider_kind:str, model:str, endpoint:str,
             label:str)->dict:
    if (type(shards) is not int or type(shard_index) is not int or
        not 1<=shards<=12 or not 0<=shard_index<shards):
        raise Challenge12Error("invalid shard index/count")
    if provider_kind not in ("fixture","ollama_live"):
        raise Challenge12Error("provider kind must distinguish fixture and real model")
    if not isinstance(label,str) or not 1<=len(label)<=100:
        raise Challenge12Error("label required")
    indices=[i for i in range(len(cases)) if i%shards==shard_index]
    data={
        "schema":REPORT_SCHEMA,
        "provider_kind":provider_kind,
        "label":label,
        "model":"synthetic-fixture" if provider_kind=="fixture" else model,
        "case_set_digest":case_digest,
        "case_indices":indices,
        "shard_index":shard_index,
        "shards":shards,
        "arm_order_rule":"rotate_arms_by_global_case_index",
        "outcomes":[],
        "warnings":WARNINGS,
    }
    for i in indices:
        case=cases[i]
        task=visible_question(case)
        for mode in arm_order(i):
            provider=(SyntheticProvider() if provider_kind=="fixture" else
                      LocalOllamaModel(model=model,endpoint=endpoint))
            started=time.monotonic()
            response=None
            error=None
            try:
                if mode=="self_critique":
                    response=run_conventional_self_critique(provider,task)
                else:
                    agent=StandaloneREI(provider_factory=lambda:provider,
                                        model=("synthetic-fixture" if provider_kind=="fixture" else model),
                                        endpoint=endpoint)
                    response=agent.answer([{"role":"user","content":task}],mode=mode)
            except (ValueError,OSError,TimeoutError) as exc:
                error=type(exc).__name__
            took=round(time.monotonic()-started,3)
            attempts=[]
            for a in provider.attempts:
                tok=a.get("tokens")
                if tok is not None and (type(tok) is not int or tok<0):
                    raise Challenge12Error("provider metering invalid")
                attempts.append({"status":str(a.get("status","unknown"))[:48],
                                 "tokens":tok})
            answer=response.get("answer","") if response else ""
            audit=response.get("audit") if response else None
            grade=answer_letter(answer)
            if response is not None:
                if not isinstance(audit,dict) or response.get("mode")!=mode:
                    raise Challenge12Error("model returned malformed mode/audit")
                if (audit.get("model_calls")!=len(attempts) or
                    audit.get("model_reported_tokens")!=sum(a["tokens"] or 0 for a in attempts)):
                    raise Challenge12Error("provider usage disagrees with model audit")
                if audit.get("evidence_status") not in ("not_verified","model_proposals_only_unverified"):
                    raise Challenge12Error("model-authored text mislabeled as verified")
                if mode=="adaptive":
                    expected=choose_route([{"role":"user","content":task}]).selected_mode
                    if audit.get("execution_mode")!=expected:
                        raise Challenge12Error("adaptive execution route differs from policy")
            data["outcomes"].append({
                "case_id":case["id"],
                "mode":mode,
                "answer_text":answer,
                "extracted_letter":grade,
                "format_valid":grade is not None,
                "correct":error is None and grade==case["correct"],
                "error_type":error,
                "elapsed_seconds":took,
                "model_calls":len(attempts),
                "reported_tokens_known":sum(a["tokens"] or 0 for a in attempts),
                "unknown_usage_calls":sum(a["tokens"] is None for a in attempts),
                "attempts":attempts,
                "audit":audit,
            })
    return {**data,"report_sha256":digest(data)}


def verify(report:dict, *, cases:list[dict], case_digest:str)->dict:
    if not isinstance(report,dict) or report.get("schema")!=REPORT_SCHEMA:
        raise Challenge12Error("incorrect report schema")
    outer={k:v for k,v in report.items() if k!="report_sha256"}
    if digest(outer)!=report.get("report_sha256"):
        raise Challenge12Error("modified report digest")
    if report.get("case_set_digest")!=case_digest:
        raise Challenge12Error("wrong case set")
    shards=report.get("shards")
    index=report.get("shard_index")
    if type(shards) is not int or type(index) is not int or not 1<=shards<=12 or not 0<=index<shards:
        raise Challenge12Error("invalid report shard")
    indices=[i for i in range(len(cases)) if i%shards==index]
    if report.get("case_indices")!=indices:
        raise Challenge12Error("incorrect case selection or order")
    if report.get("arm_order_rule")!="rotate_arms_by_global_case_index":
        raise Challenge12Error("incorrect arm rotation")
    outcomes=report.get("outcomes")
    if not isinstance(outcomes,list) or len(outcomes)!=4*len(indices):
        raise Challenge12Error("incomplete arm coverage")
    summary={mode:{"total":0,"correct":0,"format_failures":0,"errors":0,
                   "calls":0,"tokens_known":0,"unknown_usage_calls":0,
                   "seconds":0.0} for mode in ARMS}
    by_case=[]
    for loc,i in enumerate(indices):
        case=cases[i]
        results={}
        for j,mode in enumerate(arm_order(i)):
            row=outcomes[loc*4+j]
            if row.get("case_id")!=case["id"] or row.get("mode")!=mode:
                raise Challenge12Error("missing, duplicated or reordered arms")
            letter=answer_letter(row.get("answer_text"))
            if (row.get("extracted_letter")!=letter or
                row.get("format_valid")!=(letter is not None) or
                row.get("correct")!=(row.get("error_type") is None and letter==case["correct"])):
                raise Challenge12Error("independent grader disagrees")
            attempts=row.get("attempts")
            if not isinstance(attempts,list) or len(attempts)!=row.get("model_calls"):
                raise Challenge12Error("attempts/calls mismatch")
            for a in attempts:
                if (not isinstance(a,dict) or set(a)!={"status","tokens"} or
                    type(a["status"]) is not str or
                    (a["tokens"] is not None and
                     (type(a["tokens"]) is not int or a["tokens"]<0))):
                    raise Challenge12Error("invalid attempt usage")
            tokens=sum(a["tokens"] or 0 for a in attempts)
            unknown=sum(a["tokens"] is None for a in attempts)
            if tokens!=row.get("reported_tokens_known") or unknown!=row.get("unknown_usage_calls"):
                raise Challenge12Error("usage totals fail independent check")
            if (type(row.get("elapsed_seconds")) not in (float,int) or
                not 0<=row["elapsed_seconds"]<=10000):
                raise Challenge12Error("invalid wall time")
            audit=row.get("audit")
            if audit is not None:
                if (audit.get("model_calls")!=len(attempts) or
                    audit.get("model_reported_tokens")!=tokens or
                    audit.get("evidence_status") not in
                    ("not_verified","model_proposals_only_unverified")):
                    raise Challenge12Error("untrusted or corrupted model audit")
                if mode=="adaptive":
                    task=visible_question(case)
                    expected=choose_route([{"role":"user","content":task}]).selected_mode
                    if (audit.get("execution_mode")!=expected or
                        audit.get("routing",{}).get("additional_router_model_calls")!=0):
                        raise Challenge12Error("routing audit inconsistent with policy")
                if mode=="self_critique" and len(attempts)!=4:
                    raise Challenge12Error("self-critique was not four calls")
                if mode=="direct" and len(attempts)!=1:
                    raise Challenge12Error("direct was not one call")
                if mode=="rei" and not 2<=len(attempts)<=4:
                    raise Challenge12Error("REI was not within expected call budget")
            x=summary[mode]
            x["total"]+=1
            x["correct"]+=int(row["correct"])
            x["format_failures"]+=int(not row["format_valid"])
            x["errors"]+=int(row["error_type"] is not None)
            x["calls"]+=len(attempts)
            x["tokens_known"]+=tokens
            x["unknown_usage_calls"]+=unknown
            x["seconds"]+=row["elapsed_seconds"]
            results[mode]=row["correct"]
        by_case.append({"case_id":case["id"],"style":case["style"],
                        "correct_by_mode":results})
    for v in summary.values():
        v["seconds"]=round(v["seconds"],3)
    return {"valid":True,"provider_kind":report["provider_kind"],
            "model":report["model"],
            "shard_index":index,"shards":shards,
            "case_count":len(indices),
            "summary":summary,"by_case":by_case,
            "report_sha256":report["report_sha256"]}


def aggregate(reports:list[dict], *, cases:list[dict], case_digest:str)->dict:
    if not reports:
        raise Challenge12Error("no reports to combine")
    shards=reports[0].get("shards")
    if len(reports)!=shards:
        raise Challenge12Error("missing shard reports")
    summaries=[verify(r,cases=cases,case_digest=case_digest) for r in reports]
    if (set(s["shard_index"] for s in summaries)!=set(range(shards))
        or len({s["provider_kind"] for s in summaries})!=1
        or len({s["model"] for s in summaries})!=1):
        raise Challenge12Error("duplicate, inconsistent or missing shards")
    total={k:{"total":0,"correct":0,"format_failures":0,"errors":0,
              "calls":0,"tokens_known":0,"unknown_usage_calls":0,
              "seconds":0.0} for k in ARMS}
    rows=[]
    for summary in summaries:
        rows.extend(summary["by_case"])
        for mode in ARMS:
            for key in total[mode]:
                total[mode][key]+=summary["summary"][mode][key]
    rows.sort(key=lambda row:next(i for i,c in enumerate(cases) if c["id"]==row["case_id"]))
    if len(rows)!=len(cases) or len({r["case_id"] for r in rows})!=len(cases):
        raise Challenge12Error("missing or repeated case")
    for mode in ARMS:
        total[mode]["seconds"]=round(total[mode]["seconds"],3)
    paired={
        "adaptive_both_correct":0,
        "adaptive_correct_direct_wrong":0,
        "direct_correct_adaptive_wrong":0,
        "both_wrong":0,
    }
    for row in rows:
        a=row["correct_by_mode"]["adaptive"]
        d=row["correct_by_mode"]["direct"]
        key=("adaptive_both_correct" if a and d else
             "adaptive_correct_direct_wrong" if a else
             "direct_correct_adaptive_wrong" if d else "both_wrong")
        paired[key]+=1
    return {
        "provider_kind":summaries[0]["provider_kind"],
        "model":summaries[0]["model"],
        "case_set_digest":case_digest,
        "case_count":len(cases),
        "shards":shards,
        "summary":total,
        "paired_adaptive_vs_direct":paired,
        "per_case_outcomes":rows,
        "warnings":WARNINGS,
        "conclusion":"Cost/accuracy DEVELOPMENT comparison only; not a generalization claim",
    }


def main(argv=None)->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--kind",choices=("fixture","live"),default="fixture")
    p.add_argument("--model",default="qwen3:4b-instruct")
    p.add_argument("--ollama-url",default="http://127.0.0.1:11434")
    p.add_argument("--shards",type=int,default=1)
    p.add_argument("--shard-index",type=int,default=0)
    p.add_argument("--label",default="challenge12-public-cost-quality")
    p.add_argument("--output",type=Path)
    p.add_argument("--verify-only",action="store_true")
    p.add_argument("--aggregate",type=Path,nargs="+")
    args=p.parse_args(argv)
    cases,case_digest=load_cases()
    if args.aggregate:
        docs=[json.loads(path.read_text()) for path in args.aggregate]
        print(json.dumps(aggregate(docs,cases=cases,case_digest=case_digest),indent=2))
        return 0
    if args.verify_only:
        if args.output is None:
            p.error("--verify-only requires --output")
        report=json.loads(args.output.read_text())
    else:
        report=evaluate(
            cases=cases,case_digest=case_digest,
            shard_index=args.shard_index,shards=args.shards,
            provider_kind=("fixture" if args.kind=="fixture" else "ollama_live"),
            model=args.model,endpoint=args.ollama_url,label=args.label)
        if args.output:
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",
                                   encoding="utf-8")
    result=verify(report,cases=cases,case_digest=case_digest)
    print(json.dumps(result,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
