"""Reconsider an uncertain prose verdict using an explicitly cited passage span."""
import re

from adaptive_rei_benchmark import predict
from plain_verdict import decide as plain_decide

INSTRUCTION = (
    "Read the numbered passage and answer its question. Select the statement that best "
    "answers it. Use what the statement implies about the exact question. If the evidence "
    "is missing, contradicted, or about a different subject or time, answer uncertain. "
    "Output JSON fields in order: statement (integer), answer (yes, no, or uncertain)."
)


COMPACT_INSTRUCTION = (
    "Which line alone establishes the exact answer? Match the subject and time. A related fact is insufficient. "
    "If contradicted or unsupported, abstain. JSON fields: statement (number), "
    "answer (yes/no/uncertain)."
)

# Require an explicit statement of unresolved evidence at the end of the passage.
UNRESOLVED_END = re.compile(
    r"\b(?:cannot (?:tell|determine|separate)|could not be (?:determined|reconciled)|"
    r"no (?:independent|other|separate) (?:record|observation|check|measurement|evidence)|"
    r"(?:no|neither) .{0,32}recoverable timestamp|no one (?:knows|recorded|checked))"
    r"[^.;!?]{0,100}[.!]?\Z", re.I
)


def decide(url, model, text, *, compact=False, skip_gaps=False):
    first, tokens = plain_decide(url, model, text)
    return review(url, model, text, first, tokens, compact=compact, skip_gaps=skip_gaps)


def review(url, model, text, first, tokens, *, compact=False, skip_gaps=False):
    result = {"answer": first["answer"], "initial_answer": first["answer"],
              "initial_tokens": tokens, "review_tokens": 0, "citation": None}
    question, separator, body = text.partition("?")
    # Free graph decisions already exhaust the explicit evidence policy.
    if first["answer"] != "uncertain" or not tokens or not separator or not body.strip():
        return result, tokens
    spans = re.split(r"(?<=[.!?])\s+(?=[A-Z\"“])|\n+", body.strip())
    spans = [span.strip() for span in spans if span.strip()]
    if (compact or skip_gaps) and spans and UNRESOLVED_END.search(spans[-1]) and not re.search(
            r"\b(?:but|although|however|except|yet)\b", spans[-1], re.I):
        result["review_skipped"] = "explicit_evidence_gap"
        return result, tokens
    numbered = "\n".join(f"{i}. {span}" for i, span in enumerate(spans, 1))
    output, extra = predict(url, model, COMPACT_INSTRUCTION if compact else INSTRUCTION, numbered + "\nQuestion: " + question + "?", max_tokens=40)
    result["review_tokens"] = extra
    index = output.get("statement")
    if (output.get("answer") in ("yes", "no") and type(index) is int
            and 1 <= index <= len(spans)):
        result["answer"] = output["answer"]
        result["citation"] = spans[index - 1]
    return result, tokens + extra
