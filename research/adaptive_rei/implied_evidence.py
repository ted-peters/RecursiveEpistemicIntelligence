"""One-call prose candidate for questions supported by ordinary implications."""
from adaptive_rei_benchmark import predict
from evidence_register import evidence_passage, explicit_answer

INSTRUCTION = (
    "Answer from the passage, including ordinary implications. Match exactly who did what, "
    "when, and under which conditions. Return JSON with answer yes, no, or uncertain."
)


def decide(url, model, text):
    result = explicit_answer(text)
    if result is not None:
        return {"answer": result}, 0
    return predict(url, model, INSTRUCTION, evidence_passage(text))
