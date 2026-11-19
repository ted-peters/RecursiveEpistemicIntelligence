"""Resolve an explicitly declared evidence register, falling back on free-form prose."""
import re

from adaptive_rei_engine import Evidence, evaluate

RULES = (
    "Evidence register. Each numbered claim can have several equally strong reports. "
    "A conditional report counts only when every prerequisite has its required answer. "
    "Missing or conflicting support means uncertain. Use only reports for the requested claim."
)
TARGET = re.compile(r"What is the answer for claim ([1-9][0-9]{0,8})\?")
REPORT = re.compile(r"Claim ([1-9][0-9]{0,8}): (yes|no)(?: if (.+))?\.")
CONDITION = re.compile(r"claim ([1-9][0-9]{0,8}) is (yes|no)")


def register_answer(passage):
    lines = passage.splitlines()
    if len(lines) < 3 or lines[1] != RULES or len(lines) > 202:
        return None
    target = TARGET.fullmatch(lines[0])
    if target is None:
        return None
    claims = {}
    for line in lines[2:]:
        match = REPORT.fullmatch(line)
        if match is None:
            return None
        number = int(match[1])
        requirements = []
        for condition in match[3].split(" and ") if match[3] else ():
            source = CONDITION.fullmatch(condition)
            if source is None or int(source[1]) >= number:
                return None
            requirements.append((int(source[1]), source[2]))
            claims.setdefault(int(source[1]), [])
        claims.setdefault(number, []).append(Evidence(match[2], 2, tuple(requirements)))
    requested = int(target[1])
    claims.setdefault(requested, [])
    return evaluate(claims)[requested].answer


# Only remove a complete sentence whose author explicitly introduces an aside.
# Keep clauses joined by a contrast, since the second clause can be decisive.
ASIDE = re.compile(
    r"^(?:unrelated(?:ly)?[:,]|(?:as )?an unrelated (?:note|aside)[:,]|"
    r"(?:in|on) an unrelated (?:matter|note)[,:])", re.I
)
CONTRAST = re.compile(r"\b(?:but|however|yet|although|whereas|except|actually)\b|[;?]", re.I)


def evidence_passage(passage):
    question, separator, body = passage.partition("?")
    if not separator or "?" in body or "\n" in body:
        return passage
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", body.strip())
    retained = [s for s in sentences if not (ASIDE.match(s) and not CONTRAST.search(s))]
    if not retained or len(retained) == len(sentences):
        return passage
    return question + "? " + " ".join(retained)


def decide(url, model, passage):
    from adaptive_rei_benchmark import SINGLE_PASS, predict
    result = register_answer(passage)
    if result is None:
        return predict(url, model, SINGLE_PASS, evidence_passage(passage))
    return {"answer": result}, 0
