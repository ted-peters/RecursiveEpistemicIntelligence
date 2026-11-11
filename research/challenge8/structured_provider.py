"""Schema-constrained, auditable model adapter shared by ALL experiment arms.

Scientific control: every arm uses this SAME provider, underlying Qwen model,
model digest, generation limits, and stage-specific output constraint.
It does not repair wrong answers or treat model-authored evidence as verified.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import urllib.error
import urllib.request

from rei0.benchmark import _STAGE_SYSTEM
from rei0.inquiry import ModelTurn

MODEL_ALIAS = "qwen3-4b-instruct-2507-q4_k_m"
EXPECTED_MODEL_SHA256 = "85e4a5b7b8ef0e48af0e8658f5aaab9c2324c76c1641493f4d1e25fce54b18b9"
ENDPOINT = "http://127.0.0.1:8099/v1/chat/completions"

# Restricting lengths and the number of proposed questions reduces truncation.
# These are valid SUBSETS of the original REI-1.0 parser's accepted schemas;
# the initial and expand stages are identical for fixed-depth and REI.
QUESTION = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "text": {"type": "string", "minLength": 1, "maxLength": 240},
        "target": {"type": "string", "enum": ["claim", "reason"]},
        "priority": {"type": "integer", "minimum": 0, "maximum": 10},
    },
    "required": ["text", "target", "priority"],
}


def stage_schema(stage: str) -> dict:
    if stage in ("draft", "final"):
        props = {
            "answer": {"type": ["string", "null"], "maxLength": 200},
            "confidence": {"type": ["number", "null"], "minimum": 0, "maximum": 1},
            "rationale": {"type": "string", "minLength": 1, "maxLength": 360},
        }
    elif stage == "critique":
        props = {"critique": {"type": "string", "minLength": 1, "maxLength": 380}}
    elif stage == "initial":
        question = {**QUESTION, "properties": {**QUESTION["properties"],
                                     "target": {"type": "string", "enum": ["claim"]}}}
        props = {
            "claim": {"type": "string", "minLength": 1, "maxLength": 360},
            "questions": {"type": "array", "items": question, "minItems": 1, "maxItems": 2},
        }
    elif stage == "expand":
        props = {
            "reasons": {"type": "array", "items": {"type": "string", "minLength": 1, "maxLength": 240}, "minItems": 1, "maxItems": 2},
            "objections": {"type": "array", "items": {"type": "string", "minLength": 1, "maxLength": 240}, "maxItems": 2},
            "followups": {"type": "array", "items": QUESTION, "maxItems": 2},
            "note": {"type": "string", "minLength": 1, "maxLength": 300},
        }
    else:
        raise ValueError("unsupported stage")
    return {"type": "object", "additionalProperties": False,
            "properties": props, "required": list(props)}


def verify_model(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(8 * 1024 * 1024), b""):
            h.update(block)
    digest = h.hexdigest()
    if digest != EXPECTED_MODEL_SHA256:
        raise ValueError("Downloaded model SHA-256 does not match the previously pinned model")
    return digest


class StructuredLocalProvider:
    kind = "live_local_model_schema_constrained_all_arms"

    def __init__(self, model_sha256: str, engine_commit: str):
        self.fingerprint = hashlib.sha256(json.dumps({
            "model": MODEL_ALIAS, "sha256": model_sha256,
            "engine": "llama.cpp", "engine_commit": engine_commit,
            "response_format": "stage_specific_json_schema_v1_all_arms",
            "temperature": 0, "seed": 711,
        }, sort_keys=True).encode()).hexdigest()
        self.attempts = []

    def respond(self, *, case_id: str, arm: str, stage: str, context: dict,
                max_output_tokens: int, timeout: float) -> ModelTurn:
        # Never includes answer keys in prompts. Same stage prompt as old runner.
        request = {
            "model": MODEL_ALIAS,
            "messages": [
                {"role": "system", "content": _STAGE_SYSTEM[stage]},
                {"role": "user", "content": json.dumps({"stage": stage, "arm": arm, "context": context},
                                                      ensure_ascii=False, sort_keys=True)},
            ],
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "rei_" + stage,
                "strict": True,
                "schema": stage_schema(stage),
            }},
            "temperature": 0, "seed": 711,
            "max_tokens": max_output_tokens,
            "stream": False,
        }
        obs = {"case_id": case_id, "arm": arm, "stage": stage,
               "reported_tokens_even_if_failed": None, "status": "failed", "finish_reason": None}
        try:
            req = urllib.request.Request(ENDPOINT, data=json.dumps(request).encode("utf-8"),
                                         method="POST", headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as res:
                content = res.read(65537)
            if len(content) > 65536:
                raise ValueError("oversized model-server response")
            doc = json.loads(content)
            usage = doc["usage"]["total_tokens"]
            if type(usage) is not int or usage <= 0:
                raise ValueError("missing exact model token usage")
            obs["reported_tokens_even_if_failed"] = usage
            choice = doc["choices"][0]
            obs["finish_reason"] = choice.get("finish_reason")
            if choice.get("finish_reason") == "length":
                raise ValueError("truncated generation: reached output-token cap")
            parsed = json.loads(choice["message"]["content"])
            if not isinstance(parsed, dict):
                raise ValueError("model output is not an object")
            obs["status"] = "parsed"
            return ModelTurn(parsed, usage)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError,
                ValueError, KeyError, TypeError, IndexError, OSError) as exc:
            obs["error_type"] = type(exc).__name__
            # Do not log raw proprietary model text, tokens, credentials, or server URLs.
            raise ValueError(f"structured model request failed ({type(exc).__name__})") from exc
        finally:
            self.attempts.append(obs)