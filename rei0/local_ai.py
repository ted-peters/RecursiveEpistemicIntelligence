"""Local-first REI conversational runtime on a separate Ollama model server.

This is a research orchestration layer, NOT standalone pretrained weights.
REI's bounded inquiry graph generates tentative questions/objections; a local
model synthesizes the final answer. Nothing created by the model is signed
or promoted to verified evidence. No internet browsing or arbitrary tools.
"""
from __future__ import annotations

import http.client
import json
import math
import time
from urllib.parse import urlsplit

from .adapters import SYSTEM_INITIAL, SYSTEM_EXPAND
from .inquiry import (InquiryEngine, InquiryError, InquiryLimits, ModelTurn,
                      InitialDraft, ExpansionDraft)
from .models import digest


class LocalAIError(ValueError):
    """Incorrect input, unreachable model, or untrusted model output."""


def validate_model_endpoint(value: str) -> tuple[str,int]:
    """Only explicit loopback or the Docker Compose Ollama service are legal.

    No arbitrary URLs, redirects, API keys, or access to local file/system
    paths. The dedicated Docker network is trusted only in the Compose setup.
    """
    if not isinstance(value,str):
        raise LocalAIError("model URL must be a string")
    parsed=urlsplit(value)
    if (parsed.scheme!="http" or parsed.hostname not in
        ("localhost","127.0.0.1","ollama") or parsed.path not in ("","/")
        or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise LocalAIError("Ollama endpoint must be local loopback or the Compose 'ollama' host")
    try:
        port=parsed.port or 11434
    except ValueError as exc:
        raise LocalAIError("invalid Ollama port") from exc
    if not 1<=port<=65535:
        raise LocalAIError("invalid Ollama port")
    return parsed.hostname,port


def validate_messages(messages: list[dict]) -> list[dict[str,str]]:
    """Accept only text user/assistant history, never client-provided system instructions."""
    if not isinstance(messages,list) or not 1<=len(messages)<=13:
        raise LocalAIError("messages must contain 1-13 user/assistant text turns")
    out=[]
    total=0
    for msg in messages:
        if (not isinstance(msg,dict) or set(msg)!={"role","content"}
            or msg["role"] not in ("user","assistant")
            or not isinstance(msg["content"],str) or
            not msg["content"].strip() or len(msg["content"])>3000):
            raise LocalAIError("only bounded nonempty user/assistant text messages are accepted")
        total+=len(msg["content"])
        out.append({"role":msg["role"],"content":msg["content"].strip()})
    if total>12000 or out[-1]["role"]!="user":
        raise LocalAIError("conversation must end with a user message and fit 12k characters")
    return out


QUESTION_SCHEMA={
    "type":"object","additionalProperties":False,
    "properties":{
        "text":{"type":"string","minLength":1,"maxLength":400},
        "target":{"type":"string","enum":["claim","reason"]},
        "priority":{"type":"integer","minimum":0,"maximum":10},
    },
    "required":["text","target","priority"],
}
INITIAL_SCHEMA={
    "type":"object","additionalProperties":False,
    "properties":{
        "claim":{"type":"string","minLength":1,"maxLength":800},
        "questions":{
            "type":"array","minItems":1,"maxItems":4,
            "items":{**QUESTION_SCHEMA,
                     "properties":{**QUESTION_SCHEMA["properties"],
                                   "target":{"type":"string","enum":["claim"]}}},
        },
    },
    "required":["claim","questions"],
}
# Small local models should produce bounded, structurally valid expansions.
# Conditional reason-target questions cannot be enforced by this JSON schema;
# constrain to 'claim' targets rather than accepting inconsistent graphs.
EXPANSION_SCHEMA={
    "type":"object","additionalProperties":False,
    "properties":{
        "reasons":{"type":"array","minItems":1,"maxItems":2,
                   "items":{"type":"string","minLength":1,"maxLength":240}},
        "objections":{"type":"array","maxItems":2,
                      "items":{"type":"string","minLength":1,"maxLength":240}},
        "followups":{"type":"array","maxItems":2,
                     "items":{**QUESTION_SCHEMA,
                              "properties":{
                                  **QUESTION_SCHEMA["properties"],
                                  "text":{"type":"string","minLength":1,"maxLength":220},
                                  "target":{"type":"string","enum":["claim"]}}}},
        "note":{"type":"string","minLength":1,"maxLength":240},
    },
    "required":["reasons","objections","followups","note"],
}


class LocalOllamaModel:
    """Small, no-SDK, no-redirect Ollama HTTP client with explicit token metering."""
    def __init__(self, *, model: str="qwen3:4b-instruct",
                 endpoint: str="http://127.0.0.1:11434",
                 max_response_bytes: int=96000):
        if (not isinstance(model,str) or not model.strip() or
            len(model)>64 or any(ch.isspace() for ch in model)):
            raise LocalAIError("invalid local model name")
        self.model=model
        self.name="ollama-local:"+model
        if len(self.name)>80:
            raise LocalAIError("model label too long for REI provenance")
        self.host,self.port=validate_model_endpoint(endpoint)
        if (type(max_response_bytes) is not int
            or not 1024<=max_response_bytes<=200000):
            raise LocalAIError("invalid maximum response size")
        self.max_response_bytes=max_response_bytes
        self.attempts=[]

    def _transport(self, path: str, body: dict | None, *, timeout: float) -> dict:
        if not isinstance(timeout,(int,float)) or isinstance(timeout,bool) or not 0<timeout<=600:
            raise LocalAIError("invalid local model timeout")
        connection=http.client.HTTPConnection(self.host,self.port,timeout=timeout)
        try:
            raw=None if body is None else json.dumps(
                body,ensure_ascii=False,allow_nan=False).encode("utf-8")
            connection.request("GET" if body is None else "POST",path,
                               body=raw,headers={
                                   "Content-Type":"application/json",
                                   "Accept":"application/json",
                               })
            response=connection.getresponse()
            data=response.read(self.max_response_bytes+1)
            if response.status!=200:
                raise LocalAIError("Ollama returned HTTP "+str(response.status))
            if len(data)>self.max_response_bytes:
                raise LocalAIError("Ollama response exceeds size limit")
            document=json.loads(data)
            if not isinstance(document,dict):
                raise LocalAIError("Ollama returned a nonobject response")
            return document
        except (OSError,TimeoutError,http.client.HTTPException,
                UnicodeError,json.JSONDecodeError) as exc:
            raise LocalAIError(
                "Local Ollama request failed ("+type(exc).__name__+
                "). Is Ollama running and the model downloaded?"
            ) from exc
        finally:
            connection.close()

    def _generate(self, *, system: str, user: str, json_mode: bool,
                  max_output_tokens: int, timeout: float,
                  output_schema: dict | None = None) -> tuple[str,int]:
        if (type(max_output_tokens) is not int
            or not 32<=max_output_tokens<=2048):
            raise LocalAIError("invalid output token limit")
        request={
            "model":self.model,
            "messages":[{"role":"system","content":system},
                        {"role":"user","content":user}],
            "stream":False,
            "think":False,
            "options":{"temperature":0,"num_predict":max_output_tokens,
                       "num_ctx":8192},
        }
        if json_mode:
            request["format"]=output_schema if output_schema is not None else "json"
        attempt={"request_sha256":digest(request),"kind":"json" if json_mode else "text",
                 "status":"failed","tokens":None}
        began=time.monotonic()
        try:
            result=self._transport("/api/chat",request,timeout=timeout)
            content=result["message"]["content"]
            if not isinstance(content,str) or not content.strip():
                raise LocalAIError("Ollama returned empty model content")
            input_tokens=result.get("prompt_eval_count")
            output_tokens=result.get("eval_count")
            if (type(input_tokens) is not int or input_tokens<0
                or type(output_tokens) is not int or output_tokens<0):
                raise LocalAIError("Ollama did not provide reliable token usage")
            tokens=input_tokens+output_tokens
            if tokens<=0:
                raise LocalAIError("Ollama reported no consumed tokens")
            attempt["tokens"]=tokens
            attempt["status"]="ok"
            return content,tokens
        except (KeyError,TypeError,IndexError) as exc:
            raise LocalAIError("malformed model response") from exc
        finally:
            attempt["elapsed_seconds"]=round(time.monotonic()-began,3)
            self.attempts.append(attempt)

    def initial(self, question: str, *, max_output_tokens: int, timeout: float) -> ModelTurn:
        text,tokens=self._generate(system=SYSTEM_INITIAL,user=question,json_mode=True,
                                   max_output_tokens=max_output_tokens,timeout=timeout,
                                   output_schema=INITIAL_SCHEMA)
        try:
            document=json.loads(text)
            InitialDraft.parse(document)
            return ModelTurn(document,tokens)
        except (json.JSONDecodeError,InquiryError) as exc:
            self.last_validation_error="initial:"+type(exc).__name__+": "+str(exc)[:160]
            self.attempts[-1]["status"]="failed_validation"
            raise InquiryError("local model's initial draft failed structure validation") from exc

    def expand(self, context: dict, *, ordinal: int, max_output_tokens: int,
               timeout: float) -> ModelTurn:
        text,tokens=self._generate(
            system=SYSTEM_EXPAND,
            user=json.dumps({"step":ordinal,"context":context},
                            ensure_ascii=False,sort_keys=True),
            json_mode=True,max_output_tokens=max_output_tokens,timeout=timeout,
            output_schema=EXPANSION_SCHEMA)
        try:
            document=json.loads(text)
            ExpansionDraft.parse(document)
            return ModelTurn(document,tokens)
        except (json.JSONDecodeError,InquiryError) as exc:
            self.last_validation_error="expansion:"+type(exc).__name__+": "+str(exc)[:160]
            self.attempts[-1]["status"]="failed_validation"
            raise InquiryError("local model's recursive expansion failed structure validation") from exc

    def complete(self, *, system: str, user: str, max_output_tokens: int,
                 timeout: float) -> tuple[str,int]:
        return self._generate(system=system,user=user,json_mode=False,
                              max_output_tokens=max_output_tokens,timeout=timeout)

    def doctor(self) -> dict:
        tags=self._transport("/api/tags",None,timeout=8)
        names=[x["name"] for x in tags.get("models",[])
               if isinstance(x,dict) and isinstance(x.get("name"),str)]
        return {"ollama_reachable":True,"model":self.model,
                "model_downloaded":self.model in names or
                  (":latest" not in self.model and self.model+":latest" in names),
                "models_available":names[:32]}


SYNTHESIS_SYSTEM = """You are a useful local AI assistant with REI research scaffolding.
Answer the user's last request directly, clearly, and with appropriate uncertainty.
The supplied REI claim, reasons and objections were generated by a language model:
they are provisional conjectures, not verified facts or citations. Do not assert
that REI verified anything. Question text is NOT evidence. Do not invent sources,
quotes, web access, signed reviews, experiments, tools, or training achievements.
Never expose private hidden chain-of-thought; provide a concise conclusion and
relevant limitations. Respect the actual conversation rather than blindly
accepting model-generated supporting arguments. No external browsing is available."""
DIRECT_SYSTEM = """You are a helpful locally hosted AI assistant. Respond directly.
You have no web access or external tools. Do not invent verification, citations
or source authentication. Be clear about limitations and uncertainty."""


class StandaloneREI:
    """Attach an existing REI InquiryEngine to a local chat model.

    No external service or reviewer trust is implied. Final synthesis is an
    EXTRA model request beyond the REI inquiry calls; metering includes it.
    """
    def __init__(self, provider_factory=None, *, model: str="qwen3:4b-instruct",
                 endpoint: str="http://127.0.0.1:11434"):
        self.model=model
        self.endpoint=endpoint
        self.provider_factory=provider_factory or (
            lambda:LocalOllamaModel(model=model,endpoint=endpoint))

    @staticmethod
    def _question(messages: list[dict]) -> str:
        latest=messages[-1]["content"]
        previous=messages[:-1]
        # Keep earlier text visible to the REI inquiry, but do not mistake it
        # for authenticated external evidence.
        turns=[x["role"]+": "+x["content"] for x in previous]
        prefix="Previous conversation (unverified):\n"
        while turns and len(prefix+"\n".join(turns)+"\nNew user request:\n"+latest)>2960:
            turns.pop(0)
        if turns and len(prefix+"\n".join(turns)+"\nNew user request:\n"+latest)<=3000:
            return prefix+"\n".join(turns)+"\nNew user request:\n"+latest
        return latest

    def answer(self, messages: list[dict], *, mode: str="rei") -> dict:
        messages=validate_messages(messages)
        if mode not in ("rei","direct"):
            raise LocalAIError("mode must be 'rei' or 'direct'")
        provider=self.provider_factory()
        if mode=="direct":
            text,_=provider.complete(
                system=DIRECT_SYSTEM,
                user=json.dumps({"conversation":messages},ensure_ascii=False),
                max_output_tokens=512,timeout=150)
            report={"mode":"direct","model_calls":len(provider.attempts),
                    "model_reported_tokens":sum(x["tokens"] or 0 for x in provider.attempts),
                    "graph_audit_head":None,"open_questions":[],
                    "evidence_status":"not_verified","stop_reason":"direct"}
            return {"answer":text.strip(),"mode":mode,
                    "model":self.model,"audit":report}
        # Allow a complete nested JSON response without unbounded inference.
        # A 256-token expansion was too short for pinned local Qwen3 4B.
        engine=InquiryEngine(provider, InquiryLimits(
            max_steps=2,max_depth=2,max_model_calls=3,max_tokens=4500,
            max_seconds=220,max_questions=10,max_nodes=60,max_edges=80,
            max_output_tokens=512))
        try:
            session=engine.run(self._question(messages))
        except (InquiryError,LocalAIError) as exc:
            raise LocalAIError("REI inquiry could not start: "+str(exc)) from exc
        summary=session.report()
        if session.stop_reason in ("model_error","reported_token_overrun","time_budget"):
            # Don't echo untrusted model output or user data from exception
            # messages into an unauthenticated HTTP error body.
            error_type=next((item.get("error_type")
                             for item in reversed(session.trace)
                             if item.get("event")=="model_error"),None)
            suffix=(" ("+error_type+")" if error_type in
                    ("InquiryError","LocalAIError","JSONDecodeError",
                     "ValueError","TypeError","TimeoutError") else "")
            raise LocalAIError("REI inquiry stopped at "+session.stop_reason+suffix+
                               "; no unaudited answer was generated")
        notes={
            "provisional_claim":summary["root_claim"]["text"],
            "provisional_reasons":[v["text"] for v in summary["reason_nodes"]][-5:],
            "provisional_objections":[v["text"] for v in summary["objection_nodes"]][-5:],
            "unresolved_questions":[x["question"] for x in summary["open_frontier"]][:6],
            "inquiry_stop_reason":session.stop_reason,
            "evidence_status":"NOT VERIFIED: all graph claims are model-origin",
        }
        # Reserve a separate bounded final reply. The printed report counts
        # all model attempts, including the synthesis call.
        answer,_=provider.complete(
            system=SYNTHESIS_SYSTEM,
            user=json.dumps({"conversation":messages,"rei_scaffold":notes},
                            ensure_ascii=False),
            max_output_tokens=512,timeout=150)
        total=sum(x["tokens"] or 0 for x in provider.attempts)
        audit={
            "mode":"rei","model_calls":len(provider.attempts),
            "model_reported_tokens":total,
            "graph_audit_head":summary["graph_audit_head"],
            "checkpoint_sha256":session.to_dict()["checkpoint_hash"],
            "open_questions":notes["unresolved_questions"],
            "investigated_steps":summary["steps"],
            "stop_reason":summary["stop_reason"],
            "evidence_status":"model_proposals_only_unverified",
            "note":"REI structured an inquiry; it did not authenticate factual evidence.",
        }
        return {"answer":answer.strip(),"mode":mode,
                "model":self.model,"audit":audit}
