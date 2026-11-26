"""Parse an isolated, unqualified English clock expression as minutes since midnight."""
import re

HOURS = "one two three four five six seven eight nine ten eleven twelve".split()
MINUTES = {"quarter": 15, "half": 30, "five": 5, "ten": 10, "twenty": 20}


def clock_minutes(expression):
    value = " ".join(expression.lower().split())
    if value in ("noon", "midday", "midnight"):
        return 0 if value == "midnight" else 720
    match = re.fullmatch(r"(\d{1,2})(?::([0-5]\d))?\s*([ap])\.?m\.?", value)
    if match:
        hour, minute, period = match.groups()
        if 1 <= int(hour) <= 12:
            return (int(hour) % 12 + 12 * (period == "p")) * 60 + int(minute or 0)
        return None
    match = re.fullmatch(r"([01]\d|2[0-3]):([0-5]\d)", value)
    if match:
        return 60 * int(match[1]) + int(match[2])
    match = re.fullmatch(r"(?:(\w+) (past|to) )?(\w+) in the (morning|afternoon|evening)", value)
    if match and match[3] in HOURS:
        delta, direction, hour, period = match.groups()
        if delta and delta not in MINUTES:
            return None
        h = HOURS.index(hour) + 1
        if h == 12:  # Avoid colloquial ambiguity at noon and midnight.
            return None
        return 60 * (h + 12 * (period != "morning")) + MINUTES.get(delta, 0) * (-1 if direction == "to" else 1)
    return None
