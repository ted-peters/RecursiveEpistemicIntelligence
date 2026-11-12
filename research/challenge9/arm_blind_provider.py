"""Challenge 9 arm-blind local Qwen inference adapter.

Both arms receive identical system policies for a given stage. No arm name,
oracle label, signature secret or answer key is placed into requests. This
adapter logs provider-reported usage even if JSON parsing subsequently fails.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from rei0.benchmark import _STAGE_SYSTEM
from rei0.inquiry import ModelTurn
from rei0.models import digest
from research.challenge8.structured_provider import (
    MODEL_ALIAS, ENDPOINT, stage_schema,
)


class ArmBlindLocalProvider:
    kind = "live_local_arm_blind_schema_constrained_challenge9"

    def __init__(self, model_sha256: str, engine_commit: str):
        self.fingerprint = digest({
            "model": MODEL_ALIAS, "model_sha256":model_sha256,
            "engine":"llama.cpp", "engine_commit":engine_commit,
            "interface":"challenge9-arm-blind-json-schema-v1",
            "temperature":0, "seed":711,
        })
        self.attempts: list[dict] = []

    def respond(self, *, case_id: str, arm: str, stage: str, context: dict,
                max_output_tokens: int, timeout: float) -> ModelTurn:
        if stage not in _STAGE_SYSTEM:
            raise ValueError("unknown model stage")
        if arm not in ("self_critique", "rei12"):
            raise ValueError("unknown model trial arm")
        # IMPORTANT: arm and case ID are ONLY used for local audit logs.
        # They MUST NOT be serialized in messages passed to the model.
        payload = {
            "model": MODEL_ALIAS,
            "messages": [
                {"role":"system","content":_STAGE_SYSTEM[stage]},
                {"role":"user","content":json.dumps(
                    {"stage":stage,"context":context},
                    ensure_ascii=False,sort_keys=True)},
            ],
            "response_format":{"type":"json_schema","json_schema":{
                "name":"c9_"+stage,
                "strict":True,
                "schema":stage_schema(stage),
            }},
            "temperature":0,
            "seed":711,
            "max_tokens":max_output_tokens,
            "stream":False,
        }
        attempt={
            "case_id":case_id,"arm":arm,"stage":stage,
            "request_sha256":digest(payload),
            "reported_tokens_even_if_failed":None,
            "status":"failed",
            "finish_reason":None,
        }
        started=time.monotonic()
        try:
            req=urllib.request.Request(
                ENDPOINT, data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type":"application/json"},method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw=response.read(65537)
            if len(raw)>65536:
                raise ValueError("oversized model response")
            data=json.loads(raw)
            used=data["usage"]["total_tokens"]
            if type(used) is not int or used <= 0:
                raise ValueError("unknown or invalid server token count")
            attempt["reported_tokens_even_if_failed"]=used
            choice=data["choices"][0]
            attempt["finish_reason"]=choice.get("finish_reason")
            if attempt["finish_reason"]=="length":
                raise ValueError("model output was truncated")
            result=json.loads(choice["message"]["content"])
            if not isinstance(result,dict):
                raise ValueError("model result must be object")
            attempt["status"]="parsed"
            return ModelTurn(result,used)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError,
                ValueError, TypeError, KeyError, IndexError, OSError) as exc:
            attempt["error_type"]=type(exc).__name__
            raise ValueError(
                f"challenge9 structured model response failed ({type(exc).__name__})"
            ) from exc
        finally:
            attempt["elapsed_seconds"]=round(time.monotonic()-started,3)
            self.attempts.append(attempt)
