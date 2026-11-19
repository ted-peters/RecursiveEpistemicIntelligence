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


def decide(url, model, passage):
    from adaptive_rei_benchmark import SINGLE_PASS, predict
    result = register_answer(passage)
    if result is None:
        return predict(url, model, SINGLE_PASS, passage)
    return {"answer": result}, 0
