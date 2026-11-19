"""Resolve short passages that explicitly attribute a yes/no report to a source."""
import re

from adaptive_rei_engine import Evidence, evaluate

# Only recognize source names, so modifiers such as "incorrectly" cannot become
# part of an identifier. Qualifiers or additional prose defer the entire passage.
SOURCE = r"the (?:(?:station|harbor|field|office|crew|daily|evening|morning|shift|depot|control|inspection) )?(?:log|report|bulletin|memo|notice|summary|record|ledger|digest|register|transcript)"
CLAIM = re.compile(rf"({SOURCE}) (?:says|said|states|stated) (?:that )?it (did not|did)")
COPY = re.compile(rf"({SOURCE}) (?:copied|was copied from|relied solely on) ({SOURCE})")
INVALID = re.compile(rf"({SOURCE}) (?:was withdrawn|was retracted|was invalidated)")


def report_chain_answer(passage):
    question, mark, body = passage.lower().partition("?")
    if not mark or not re.fullmatch(r"did [a-z][a-z0-9 '’-]*", question.strip()):
        return None
    if re.search(r"\b(?:not|never|say|claim|report|both|either)\b|n['’]t\b", question):
        return None
    body = body.strip()
    if not body.endswith(".") or len(body) > 4000:
        return None
    statements = re.split(r"\.\s+", body[:-1])
    observations, parents, withdrawn = {}, {}, set()
    for statement in statements:
        if match := CLAIM.fullmatch(statement):
            source, value = match.groups()
            if source in observations and observations[source] != value:
                return None
            observations[source] = value
        elif match := COPY.fullmatch(statement):
            child, parent = match.groups()
            if child in parents and parents[child] != parent:
                return None
            parents[child] = parent
        elif match := INVALID.fullmatch(statement):
            withdrawn.add(match[1])
        else:
            return None
    if not parents or not observations:
        return None

    # Each surviving report must trace back to a source with an explicit verdict.
    # Multiple copies of that verdict contribute only one piece of evidence.
    evidence = {}
    for source in observations.keys() | parents.keys():
        seen, stated = set(), set()
        while source not in withdrawn:
            if source in seen:
                return None
            seen.add(source)
            if source in observations:
                stated.add(observations[source])
            if source not in parents:
                if len(stated) > 1 or (stated and source not in observations):
                    return None
                if source in observations:
                    evidence[source] = Evidence("yes" if observations[source] == "did" else "no", 2)
                break
            source = parents[source]
    return evaluate({1: tuple(evidence.values())})[1].answer
