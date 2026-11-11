"""Explicit, opt-in model adapters. No tools, evidence verification, or code execution.

ScriptedAdapter is deterministic. ChatCompletionsAdapter is a minimal HTTPS
client for Chat Completions-compatible servers; behavior varies by provider.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler

from .inquiry import InquiryError, ModelTurn


class ScriptedAdapter:
    """Finite fixture of model turns: identical input and ordinal, identical result."""

    def __init__(self, script: dict[str, Any], name: str = "scripted-fixture"):
        if not isinstance(script, dict) or set(script) != {"initial", "responses"}:
            raise InquiryError("script must contain only initial and responses")
        if not isinstance(script["responses"], list):
            raise InquiryError("script responses must be a list")
        self._script = script
        self.name = name

    @classmethod
    def load(cls, path: str | Path) -> ScriptedAdapter:
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    @staticmethod
    def _turn(record: dict[str, Any], max_output_tokens: int) -> ModelTurn:
        if not isinstance(record, dict) or set(record) != {"payload", "tokens_used"}:
            raise InquiryError("script turn needs payload and tokens_used")
        # Scripted use is accounting only; the output cap is meaningful for live providers.
        return ModelTurn(record["payload"], record["tokens_used"])

    def initial(self, question: str, *, max_output_tokens: int, timeout: float) -> ModelTurn:
        return self._turn(self._script["initial"], max_output_tokens)

    def expand(self, context: dict[str, Any], *, ordinal: int,
               max_output_tokens: int, timeout: float) -> ModelTurn:
        try:
            return self._turn(self._script["responses"][ordinal], max_output_tokens)
        except IndexError as exc:
            raise InquiryError("script responses exhausted; unresolved questions retained") from exc


SYSTEM_INITIAL = """You propose a PROVISIONAL answer for a philosophical inquiry research prototype.
Return ONLY a JSON object with exact keys: claim (string), questions (array of 1-4 objects).
Each question has text (string), target (always 'claim'), priority (integer 0-10).
Questions must challenge the grounds or assumptions for the claim.
Do NOT claim verification, do NOT generate citations as evidence, do NOT write code or tool instructions.
No markdown fences."""

SYSTEM_EXPAND = """You answer one epistemic challenge by adding provisional arguments, objections,
and recursively investigable questions. Return ONLY JSON with exact fields:
reasons (array of 0-3 strings), objections (array of 0-3 strings),
followups (array of 0-4 objects {text: string, target: 'claim' or 'reason', priority: integer 0-10}),
note (string). Target 'reason' refers only to your FIRST new reason and requires a reason.
Every reason is tentative. Ask at least one nontrivial question if useful; do not repeat questions.
Never represent generated claims as verified evidence. No instructions or code execution.
No markdown fences."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward a token to a redirected URL.


class ChatCompletionsAdapter:
    """Opt-in HTTPS Chat Completions JSON adapter; no automatic external tools.

    Requires API key via explicit environment variable. We intentionally avoid
    provider-specific SDK dependencies; some models do not support JSON mode.
    """

    def __init__(self, *, model: str, endpoint: str = "https://api.openai.com/v1/chat/completions",
                 api_key_env: str = "REI_LLM_API_KEY", max_response_bytes: int = 64_000):
        if not isinstance(model, str) or not model.strip() or len(model) > 120:
            raise InquiryError("model identifier required")
        parsed = urlparse(endpoint)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password or parsed.fragment:
            raise InquiryError("LLM endpoint must be an HTTPS URL without credentials")
        if not isinstance(api_key_env, str) or not api_key_env.isidentifier():
            raise InquiryError("api_key_env must name an environment variable")
        if type(max_response_bytes) is not int or not (1024 <= max_response_bytes <= 1_000_000):
            raise InquiryError("invalid max_response_bytes")
        self.model = model.strip()
        self.endpoint = endpoint
        self.api_key_env = api_key_env
        self.max_response_bytes = max_response_bytes
        self.name = f"chat-completions:{self.model}"

    def _request(self, system: str, user: str, *, max_output_tokens: int, timeout: float) -> ModelTurn:
        api_key = os.environ.get(self.api_key_env, "")
        if not api_key:
            raise InquiryError(f"set {self.api_key_env} to use the live model adapter")
        if not isinstance(timeout, (float, int)) or timeout <= 0:
            raise InquiryError("time budget exhausted before HTTPS request")
        if type(max_output_tokens) is not int or max_output_tokens <= 0:
            raise InquiryError("max_output_tokens must be positive")
        payload = {"model": self.model, "messages": [{"role": "system", "content": system},
                    {"role": "user", "content": user}], "response_format": {"type": "json_object"},
                   "max_completion_tokens": max_output_tokens}
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = Request(self.endpoint, data=data, headers={"Authorization": f"Bearer {api_key}",
                      "Content-Type": "application/json"}, method="POST")
        try:
            with build_opener(_NoRedirect).open(req, timeout=timeout) as response:
                body = response.read(self.max_response_bytes + 1)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            # Do not log response bodies, which can echo prompts or sensitive tokens.
            raise InquiryError(f"LLM HTTPS request failed ({type(exc).__name__})") from None
        if len(body) > self.max_response_bytes:
            raise InquiryError("LLM response exceeded byte limit")
        try:
            document = json.loads(body.decode("utf-8"))
            if not isinstance(document, dict):
                raise InquiryError("LLM provider response must be an object")
            content = document["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            usage = document.get("usage") or {}
            if not isinstance(usage, dict):
                raise InquiryError("LLM usage record must be an object")
            reported = usage.get("total_tokens")
            # Unknown provider usage must not be silently counted as zero.
            tokens = reported if reported is not None else max_output_tokens
            return ModelTurn(parsed, tokens)
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            raise InquiryError("malformed JSON response from LLM provider") from exc

    def initial(self, question: str, *, max_output_tokens: int, timeout: float) -> ModelTurn:
        return self._request(SYSTEM_INITIAL, question, max_output_tokens=max_output_tokens, timeout=timeout)

    def expand(self, context: dict[str, Any], *, ordinal: int,
               max_output_tokens: int, timeout: float) -> ModelTurn:
        user = json.dumps({"step": ordinal, "context": context}, ensure_ascii=False, sort_keys=True)
        return self._request(SYSTEM_EXPAND, user, max_output_tokens=max_output_tokens, timeout=timeout)
