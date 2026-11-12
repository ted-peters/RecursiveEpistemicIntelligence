"""Challenge 11: arm-blind structured Qwen choice adapter.

The model decides which *experiment* to perform. It never receives the
private latent H, hidden potential test outcomes, secret signing keys, arm
identifier, or scoring oracle. Both numeric VOI tools are in public context.

Model-assisted self-critique is a *different* computational method from an
exact mathematical planner; compare selection quality, report extra model
calls, and retain the exact-optimal conventional baseline.
"""
from __future__ import annotations

from hashlib import sha256
import json
import time
import urllib.error
import urllib.request

from rei0.models import digest
from research.challenge8.structured_provider import (
    ENDPOINT, MODEL_ALIAS,
)

SCHEMA={
    "type":"object",
    "additionalProperties":False,
    "properties":{
        "choice":{"type":"string","enum":["A","B","C","D","STOP"]},
        "reason":{"type":"string","minLength":1,"maxLength":240},
    },
    "required":["choice","reason"],
}
DRAFT_SYSTEM=(
    "You are planning an investigation of a hidden synthetic binary state. "
    "Choose one currently AVAILABLE probe A-D, or STOP if no further test "
    "reduces expected binary decision error. Each probe costs one unit and "
    "you must respect the stated budget. The input includes exact numeric "
    "one-step and remaining-budget Bayes error estimates, computed from "
    "the stated test likelihoods; you may use these values as tools. "
    "No withheld test outcomes are available. "
    "Return ONLY structured JSON with choice and concise reason."
)
FINAL_SYSTEM=(
    "Self-critique a provisional experiment choice, then select the best "
    "CURRENT available test A-D or STOP. Use the shared exact expected "
    "Bayes error with remaining budget and current posterior; a smaller "
    "final expected error is better. Do not invent any test outcome or "
    "change signed observations. Return ONLY structured JSON."
)


class ModelChoiceError(ValueError):
    pass


class QwenChoiceProvider:
    kind="qwen3-4b-live-arm-blind-probe-selection"
    def __init__(self, model_sha256: str, engine_commit: str):
        self.fingerprint=digest({
            "model":MODEL_ALIAS,
            "model_sha256":model_sha256,
            "engine":"llama.cpp","engine_commit":engine_commit,
            "temperature":0,"seed":711,
            "response_schema":"challenge11-probe-choice-v1",
            "arm_blind":True,
        })
        self.attempts=[]

    def respond(self, *, case_id: str, stage: str, public: dict,
                max_output_tokens: int = 160, timeout: float = 100.0) -> tuple[str,int]:
        if stage not in ("draft_choice","revised_choice"):
            raise ModelChoiceError("unsupported model stage")
        if not isinstance(public,dict):
            raise ModelChoiceError("public task must be an object")
        system=DRAFT_SYSTEM if stage=="draft_choice" else FINAL_SYSTEM
        request={
            "model":MODEL_ALIAS,
            "messages":[
                {"role":"system","content":system},
                {"role":"user","content":json.dumps(
                    {"task":public,"stage":stage},
                    ensure_ascii=False,sort_keys=True)},
            ],
            "response_format":{"type":"json_schema","json_schema":{
                "name":"c11_probe_choice","strict":True,"schema":SCHEMA}},
            "temperature":0,"seed":711,
            "max_tokens":max_output_tokens,"stream":False,
        }
        attempt={
            "case_id":case_id,"stage":stage,
            "request_sha256":digest(request),
            "reported_tokens_even_if_failed":None,
            "status":"failed","finish_reason":None,
        }
        started=time.monotonic()
        try:
            req=urllib.request.Request(
                ENDPOINT,data=json.dumps(request).encode("utf-8"),
                headers={"Content-Type":"application/json"},method="POST")
            with urllib.request.urlopen(req,timeout=timeout) as response:
                raw=response.read(65537)
            if len(raw)>65536:
                raise ModelChoiceError("oversized model response")
            parsed=json.loads(raw)
            count=parsed["usage"]["total_tokens"]
            if type(count) is not int or count<=0:
                raise ModelChoiceError("server reported invalid token count")
            attempt["reported_tokens_even_if_failed"]=count
            answer=parsed["choices"][0]
            attempt["finish_reason"]=answer.get("finish_reason")
            if attempt["finish_reason"]=="length":
                raise ModelChoiceError("model response truncated")
            doc=json.loads(answer["message"]["content"])
            if (not isinstance(doc,dict) or set(doc)!={"choice","reason"} or
                doc["choice"] not in ("A","B","C","D","STOP") or
                not isinstance(doc["reason"],str) or not 1<=len(doc["reason"])<=240):
                raise ModelChoiceError("model choice violates schema")
            attempt["status"]="parsed"
            return doc["choice"],count
        except (urllib.error.URLError,TimeoutError,ValueError,KeyError,
                TypeError,IndexError,OSError) as exc:
            attempt["error_type"]=type(exc).__name__
            raise ModelChoiceError(
                "model investigation choice failed ("+type(exc).__name__+")"
            ) from exc
        finally:
            attempt["elapsed_seconds"]=round(time.monotonic()-started,3)
            self.attempts.append(attempt)
