"""Read a single explicit capacity or contents observation about a named vessel."""
import re
from decimal import Decimal

from quantity_comparison import COMPARISONS, NUMBER, SUBJECT, normalized_value

N = rf"(?P<number>(?:[0-9]{{1,3}}(?:,[0-9]{{3}})+(?:\.[0-9]+)?|{NUMBER}))"
VOLUME = N + r"\s*(?P<unit>millilit(?:er|re)s?|lit(?:er|re)s?|ml|l)\b"
S = rf"(?P<subject>{SUBJECT})"
BOUND = r"(?P<bound>at least|at most|less than|more than)"
AMOUNT = rf"(?:exactly )?{VOLUME}(?: of water)?"
FULL = r"(?:when (?:completely full|full|filled to the brim)|when filled completely)"
CLAIMS = [
    rf"{S} holds {BOUND} {VOLUME}(?: of water)? {FULL}",
    rf"{S} can hold {BOUND} {VOLUME}(?: of water)?",
    rf"the (?:total )?capacity of {S} is {BOUND} {VOLUME}",
    rf"{S} has a (?:total )?capacity of {BOUND} {VOLUME}",
]
EXACT = [
    rf"{S} (?:holds|contains) {AMOUNT} {FULL}",
    rf"when filled to the brim, {S} (?:holds|contains) {AMOUNT}",
    rf"filling (?P<subject>the empty [a-z]+(?: [a-z]+){{0,4}}) to the brim takes {AMOUNT}",
    rf"it takes {AMOUNT} to fill (?P<subject>the empty [a-z]+(?: [a-z]+){{0,4}}) completely",
    rf"the (?:total )?capacity of {S} is {AMOUNT}",
    rf"{S} has a (?:total )?capacity of {AMOUNT}",
]
ROOM = r"(?: and (?:still )?has (?:some )?room (?:left|at the top)|, which is only partly full)"
CURRENT = [
    rf"{S} (?:currently )?(?:holds|contains) {AMOUNT}(?P<room>{ROOM})?",
    rf"there (?:are|is) {AMOUNT} in {S}(?P<room>{ROOM})?",
]


def first_match(patterns, text):
    for pattern in patterns:
        match = re.fullmatch(pattern, text)
        if match:
            return match
    return None


def milliliters(match):
    exponent = 0 if match["unit"].startswith("m") else 3
    return normalized_value(match["number"].replace(",", ""), exponent)


def read_capacity(claim, passage):
    claim = first_match(CLAIMS, claim.lower().removesuffix("."))
    if not claim:
        return None
    text = passage.strip().lower().removesuffix(".")
    reading = first_match(EXACT, text)
    kind = "capacity"
    if not reading:
        reading = first_match(CURRENT, text)
        if not reading:
            return None
        kind = "partial_contents" if reading["room"] else "current_contents"
    subject = reading["subject"]
    if text.startswith(("filling ", "it takes ")):
        subject = subject.replace("the empty ", "the ", 1)
    if subject != claim["subject"]:
        return "gap", kind
    observed, threshold = milliliters(reading), milliliters(claim)
    compare = COMPARISONS[claim["bound"]]
    at_low = compare(observed, threshold)
    if kind == "partial_contents" and observed == threshold:
        at_low = claim["bound"] in ("more than", "at least")
    if kind != "capacity" and at_low != compare(Decimal("Infinity"), threshold):
        return "gap", kind
    return ("yes" if at_low else "no"), kind
