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
# Each exponent converts a value to the smallest supported unit in its group.
UNITS = {
    "liter": ("volume", 3), "milliliter": ("volume", 0),
    "meter": ("length", 3), "centimeter": ("length", 1), "millimeter": ("length", 0),
    "kilogram": ("mass", 3), "gram": ("mass", 0),
    "dollar": ("money", 2), "cent": ("money", 0),
}


def normalized_value(number, exponent):
    value = Decimal(WORDS.index(number) if number in WORDS else number)
    # Adjust the exponent directly to avoid rounding long decimal inputs.
    sign, digits, power = value.as_tuple()
    return Decimal((sign, digits, power + exponent))


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
    claim_unit = UNITS.get(claim["unit"].removesuffix("s"))
    fact_unit = UNITS.get(fact["unit"].removesuffix("s"))
    if not claim_unit or not fact_unit or claim_unit[0] != fact_unit[0]:
        return None
    bound = normalized_value(claim["number"], claim_unit[1])
    observed = normalized_value(fact["number"], fact_unit[1])
    satisfied = {"at least": observed >= bound, "at most": observed <= bound,
                 "less than": observed < bound, "more than": observed > bound}
    return "yes" if satisfied[claim["bound"]] else "no"
