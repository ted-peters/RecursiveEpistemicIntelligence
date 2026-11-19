"""Reconsider an uncertain prose verdict using an explicitly cited passage span."""
import re

from adaptive_rei_benchmark import predict
from plain_verdict import decide as plain_decide

INSTRUCTION = (
    'Does one numbered statement settle the question? Check its subject, time, and '
    'the direction of the claim. If other evidence defeats it, or assumptions are '
    'needed, keep uncertain. Return JSON {"answer":"yes|no|uncertain","statement":0}. '
    'For yes or no, replace 0 with the number of the decisive statement.'
)


def decide(url, model, text):
    first, tokens = plain_decide(url, model, text)
    result = {"answer": first["answer"], "initial_answer": first["answer"],
              "initial_tokens": tokens, "review_tokens": 0, "citation": None}
    question, separator, body = text.partition("?")
    # Free graph decisions already exhaust the explicit evidence policy.
    if first["answer"] != "uncertain" or not tokens or not separator or not body.strip():
        return result, tokens
    spans = re.split(r"(?<=[.!?])\s+(?=[A-Z\"“])|\n+", body.strip())
    spans = [span.strip() for span in spans if span.strip()]
    numbered = "\n".join(f"{i}. {span}" for i, span in enumerate(spans, 1))
    output, extra = predict(url, model, INSTRUCTION, question + "?\n" + numbered, max_tokens=40)
    result["review_tokens"] = extra
    index = output.get("statement")
    if (output.get("answer") in ("yes", "no") and type(index) is int
            and 1 <= index <= len(spans)):
        result["answer"] = output["answer"]
        result["citation"] = spans[index - 1]
    return result, tokens + extra
