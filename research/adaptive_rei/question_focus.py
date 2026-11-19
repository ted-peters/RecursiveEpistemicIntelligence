"""Experimental one-call fallback that reads the passage before the exact question."""
from adaptive_rei_benchmark import SINGLE_PASS, predict
from evidence_register import evidence_passage, explicit_answer

INSTRUCTION = (
    'Read the passage. Answer the exact question, matching the entity, relationship, '
    'time and qualifiers. A related fact may answer a different question. '
    'Return JSON with answer set to yes, no or uncertain. '
    'Use uncertain if the passage does not settle it.'
)


def prose_prompt(text):
    prose = evidence_passage(text)
    question, delimiter, body = prose.partition("?")
    if not (delimiter and question.strip() and body.strip()) or "?" in body:
        return SINGLE_PASS, prose
    return INSTRUCTION, body.strip() + "\n\nQuestion: " + question.strip() + "?"


def decide(url, model, text):
    result = explicit_answer(text)
    if result is not None:
        return {"answer": result}, 0
    instruction, prose = prose_prompt(text)
    return predict(url, model, instruction, prose)
