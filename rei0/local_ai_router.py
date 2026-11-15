"""Deterministic, zero-model-call routing for the REI standalone assistant.

This is an explicit first-generation *cost policy*, NOT a model of
epistemic confidence, an empirical evidence detector, or a proof that
inquiry improves accuracy. It conservatively chooses a one-call direct
reply for clearly bounded tasks, and the existing bounded REI inquiry
for everything else. Users can always override the decision.

Distinct from rei0.adaptive, which governs question selection INSIDE the
original inquiry engine.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

POLICY_VERSION = "local-ai-adaptive-rules-v1"
_ROUTE_NOTE = ("Static intent patterns only; no model call or trained "
               "confidence estimate was used to make this decision.")

_DELIBERATE_INQUIRY = re.compile(
    r"\b(?:investigat\w*|critiqu\w*|challenge\w*|counterargument\w*|"
    r"assumptions?|uncertaint\w*|verify\b|verification\b|validate\b|"
    r"reliab\w*|trustworth\w*|evidenc\w*|fact.check\w*|"
    r"trade.off\w*|risk assessment|is there proof|"
    r"alternative explanations?|competing hypotheses|"
    r"how (?:would|could|do) (?:we|i|you) test|"
    r"should i|compare (?:the|these|two|several))\b", re.IGNORECASE)

_OPTION_LINE = re.compile(r"(?m)^\s*([ABCD])[.)]\s+\S")
_PREPEND_INQUIRY = re.compile(
    # A polite *explicit instruction* must not be silently downgraded to
    # Direct just because four answer-option lines follow it. Do not scan
    # arbitrary option text for epistemic words: that would turn routine
    # questions ABOUT evidence into expensive inquiry.
    r"^(?:(?:please|can you|could you|would you|"
    r"i want you to|i would like you to)\s+)?"
    r"(?:critique|investigate|verify|challenge|audit|analyze the assumptions|"
    r"explore competing explanations)\b", re.IGNORECASE)

_FAST_INTENTS = re.compile(
    r"^(?:hi|hello|hey|good (?:morning|afternoon|evening)|thanks|thank you)[!.? ]*$"
    r"|^(?:translate\b|rewrite\b|rephrase\b|proofread\b|fix (?:the )?"
    r"(?:grammar|spelling)\b|summari[sz]e (?:this|the following|these)\b|"
    r"calculate\b|compute\b|what is \d+\s*[-+*/]\s*\d+\b|"
    r"define\b|what does \w+ mean\b)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Route:
    selected_mode: str
    reason_code: str

    def audit(self) -> dict:
        return {
            "requested_mode": "adaptive",
            "selected_mode": self.selected_mode,
            "policy_version": POLICY_VERSION,
            "reason_code": self.reason_code,
            "basis": "deterministic_intent_rules",
            "additional_router_model_calls": 0,
            "confidence_estimate": None,
            "note": _ROUTE_NOTE,
        }


def choose_route(messages: list[dict[str, str]]) -> Route:
    """Route validated messages with no inference or network access.

    Default inquiry is a workflow policy, NOT calibrated difficulty.
    """
    if not messages or messages[-1].get("role") != "user":
        raise ValueError("adaptive routing requires a final user message")

    latest = messages[-1]["content"].strip()
    if len(messages) != 1:
        return Route("rei", "multi_turn_conservative")
    if not latest or len(latest) > 1800:
        return Route("rei", "long_or_empty_request")

    option_lines = _OPTION_LINE.findall(latest)
    if set(option_lines) == {"A", "B", "C", "D"} and len(option_lines) == 4:
        stem = _OPTION_LINE.split(latest, maxsplit=1)[0]
        if _PREPEND_INQUIRY.search(stem.strip()):
            return Route("rei", "explicit_investigation")
        return Route("direct", "bounded_four_choice_task")

    if _DELIBERATE_INQUIRY.search(latest):
        return Route("rei", "explicit_investigation")
    if _FAST_INTENTS.search(latest):
        return Route("direct", "bounded_simple_intent")
    return Route("rei", "unclassified_conservative")
