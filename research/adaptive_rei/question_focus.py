"""Experimental one-call fallback that reads the passage before the exact question."""
from adaptive_rei_benchmark import SINGLE_PASS, predict
from evidence_register import evidence_passage, register_answer
from report_chain import report_chain_answer

INSTRUCTION = (
    'Read the passage. Answer the exact question, matching the entity, relationship, '
    'time and qualifiers. A related fact may answer a different question. '
    'Return JSON with answer set to yes, no or uncertain. '
    'Use uncertain if the passage does not settle it.'
)


def decide(url, model, text):
    for resolver in (register_answer, report_chain_answer):
        result = resolver(text)
        if result is not None:
            return {"answer": result}, 0
    prose = evidence_passage(text)
    question, delimiter, body = prose.partition("?")
    if not (delimiter and question.strip() and body.strip()) or "?" in body:
        return predict(url, model, SINGLE_PASS, prose)
    return predict(url, model, INSTRUCTION, body.strip() + "\n\nQuestion: " + question.strip() + "?")
