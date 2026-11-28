"""Resolve explicit bounds against an exact measurement of the same subject."""
from decimal import Decimal
import re

WORDS = "zero one two three four five six seven eight nine ten eleven twelve".split()
NUMBER = r"(?:[0-9]+(?:\.[0-9]+)?|" + "|".join(WORDS) + ")"
SUBJECT = r"the [a-z]+(?: [a-z]+){0,5}?"
FRAME = (rf"(?P<subject>{SUBJECT}) "
         r"(?P<verb>held|contained|weighed|cost|measured) ")
VALUE = rf"(?P<number>{NUMBER}) (?P<unit>[a-z]+)"
CLAIM = re.compile(FRAME + r"(?P<bound>at least|at most|less than|more than) " + VALUE)
OBSERVATION = re.compile(FRAME + r"(?:exactly )?" + VALUE)
ALIAS = re.compile(rf"(?P<primary>{SUBJECT}), also called (?P<alias>{SUBJECT}), (?P<predicate>.+)")
MEASUREMENT_FORMS = [
    ("weighed", rf"the (?:scale reading for|mass of) (?P<subject>{SUBJECT}) was {VALUE}"),
    ("weighed", rf"on the scale, (?P<subject>{SUBJECT}) registered {VALUE}"),
    ("measured", rf"(?:end to end, )?(?P<subject>{SUBJECT}) was {VALUE} long"),
    ("cost", rf"the price (?:charged for|of) (?P<subject>{SUBJECT}) was {VALUE}"),
    ("cost", rf"the seller charged {VALUE} for (?P<subject>{SUBJECT})"),
    ("contained", rf"the liquid in (?P<subject>{SUBJECT}) had a volume of {VALUE}"),
]
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


def observation(text):
    alias = ALIAS.fullmatch(text)
    if alias:
        text = alias["primary"] + " " + alias["predicate"]
    fact = OBSERVATION.fullmatch(text)
    if fact:
        fields = fact.groupdict()
    else:
        for verb, pattern in MEASUREMENT_FORMS:
            fact = re.fullmatch(pattern, text)
            if fact:
                fields = dict(fact.groupdict(), verb=verb)
                break
        else:
            return None
    subjects = {fields["subject"]}
    if alias:
        if fields["subject"] != alias["primary"]:
            return None
        subjects.add(alias["alias"])
    return fields, subjects


def quantity_role(question):
    match = re.fullmatch(r'Is this claim true: "([^"?]+)"\? (.+)', question)
    if not match:
        return None
    claim = CLAIM.fullmatch(match[1].lower().removesuffix("."))
    reading = observation(match[2].lower().removesuffix("."))
    if not claim or not reading:
        return None
    fact, subjects = reading
    verbs = {claim["verb"], fact["verb"]}
    if len(verbs) > 1 and verbs != {"held", "contained"}:
        return None
    claim_unit = UNITS.get(claim["unit"].removesuffix("s"))
    fact_unit = UNITS.get(fact["unit"].removesuffix("s"))
    if not claim_unit or not fact_unit or claim_unit[0] != fact_unit[0]:
        return None
    if claim["subject"] not in subjects:
        return "gap"
    bound = normalized_value(claim["number"], claim_unit[1])
    observed = normalized_value(fact["number"], fact_unit[1])
    satisfied = {"at least": observed >= bound, "at most": observed <= bound,
                 "less than": observed < bound, "more than": observed > bound}
    return "yes" if satisfied[claim["bound"]] else "no"


def quantity_verdict(question):
    role = quantity_role(question)
    return None if role == "gap" else role
