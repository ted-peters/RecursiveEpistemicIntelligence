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
# A named liquid can be just part of the contents. Its volume bounds the total from below.
LIQUID_PORTION = re.compile(
    rf"there (?:was|were) {VALUE} of (?:water|milk|juice|oil) in (?P<subject>{SUBJECT})"
)
MEASUREMENT_FORMS = [
    ("contained", rf"the total volume of liquid in (?P<subject>{SUBJECT}) was {VALUE}"),
    ("weighed", rf"the (?:scale reading for|mass of) (?P<subject>{SUBJECT}) was {VALUE}"),
    ("weighed", rf"(?P<subject>{SUBJECT})(?: itself)? had a mass of {VALUE}"),
    ("weighed", rf"on the scale, (?P<subject>{SUBJECT}) registered {VALUE}"),
    ("measured", rf"(?:end to end, )?(?P<subject>{SUBJECT}) was {VALUE} long"),
    ("cost", rf"the price (?:charged for|of) (?P<subject>{SUBJECT}) was {VALUE}"),
    ("cost", rf"the seller charged {VALUE} for (?P<subject>{SUBJECT})"),
    ("contained", rf"the liquid in (?P<subject>{SUBJECT}) had a volume of {VALUE}"),
]
PROPERTY = {"weighed": "mass", "cost": "money", "measured": "length",
            "held": "volume", "contained": "volume"}

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
    elif portion := LIQUID_PORTION.fullmatch(text):
        fields = dict(portion.groupdict(), verb="contained", lower_bound=True)
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
    claim_unit = UNITS.get(claim["unit"].removesuffix("s"))
    fact_unit = UNITS.get(fact["unit"].removesuffix("s"))
    if not claim_unit or not fact_unit:
        return None
    if fact.get("lower_bound") and fact_unit[0] != "volume":
        return None
    if claim_unit[0] != fact_unit[0]:
        if PROPERTY.get(claim["verb"]) == claim_unit[0] and PROPERTY.get(fact["verb"]) == fact_unit[0]:
            return "gap"
        return None
    verbs = {claim["verb"], fact["verb"]}
    if len(verbs) > 1 and verbs != {"held", "contained"}:
        return None
    if claim["subject"] not in subjects:
        return "gap"
    bound = normalized_value(claim["number"], claim_unit[1])
    observed = normalized_value(fact["number"], fact_unit[1])
    satisfied = {"at least": observed >= bound, "at most": observed <= bound,
                 "less than": observed < bound, "more than": observed > bound}
    holds = satisfied[claim["bound"]]
    if fact.get("lower_bound"):
        lower_limit_claim = claim["bound"] in ("at least", "more than")
        if holds != lower_limit_claim:
            return "gap"
    return "yes" if holds else "no"


def quantity_verdict(question):
    role = quantity_role(question)
    return None if role == "gap" else role
