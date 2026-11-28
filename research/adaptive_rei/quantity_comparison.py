"""Resolve explicit bounds against an exact measurement of the same subject."""
from decimal import Decimal
import re

WORDS = "zero one two three four five six seven eight nine ten eleven twelve".split()
NUMBER = r"(?:[0-9]+(?:\.[0-9]+)?|" + "|".join(WORDS) + ")"
FRAME = (r"(?P<subject>the [a-z]+(?: [a-z]+){0,5}?) "
         r"(?P<verb>held|contained|weighed|cost|measured) ")
VALUE = rf"(?P<number>{NUMBER}) (?P<unit>[a-z]+)"
CLAIM = re.compile(FRAME + r"(?P<bound>at least|at most|less than|more than) " + VALUE)
OBSERVATION = re.compile(FRAME + r"(?:exactly )?" + VALUE)
UNITS = {"liter", "liters", "meter", "meters", "kilogram", "kilograms", "gram", "grams",
         "dollar", "dollars", "cent", "cents"}


def quantity_verdict(question):
    match = re.fullmatch(r'Is this claim true: "([^"?]+)"\? (.+)', question)
    if not match:
        return None
    claim, fact = (pattern.fullmatch(text.lower().removesuffix("."))
                   for pattern, text in zip((CLAIM, OBSERVATION), match.groups()))
    if not claim or not fact or claim["subject"] != fact["subject"]:
        return None
    verbs = {claim["verb"], fact["verb"]}
    if len(verbs) > 1 and verbs != {"held", "contained"}:
        return None
    if (claim["unit"] not in UNITS or fact["unit"] not in UNITS
            or claim["unit"].rstrip("s") != fact["unit"].rstrip("s")):
        return None
    bound, observed = [Decimal(WORDS.index(n) if n in WORDS else n)
                       for n in (claim["number"], fact["number"])]
    satisfied = {"at least": observed >= bound, "at most": observed <= bound,
                 "less than": observed < bound, "more than": observed > bound}
    return "yes" if satisfied[claim["bound"]] else "no"
