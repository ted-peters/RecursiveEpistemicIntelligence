"""Isolate support direction and time wording in citation verification."""
import json
from urllib.request import urlopen

from observation_match_trial import VERIFY, URL, MODEL, predict

# The sole change in the second arm is the verifier instruction.
RELATION = ("Classify how the firsthand observation relates to the question. "
            "For the same subject and time, return supports or contradicts, including when "
            "the time is expressed equivalently. For a different time return irrelevant. "
            "Output JSON with one field, answer.")
CASES = [
    ("cabinet F", "open", "shut", "noon", "midday", "dawn"),
    ("the display lamp", "lit", "dark", "sunset", "sundown", "sunrise"),
    ("the store gate", "locked", "unlocked", "six in the morning", "6 a.m.", "6 p.m."),
    ("the sensor", "active", "inactive", "four in the afternoon", "4 p.m.", "4 a.m."),
    ("the kettle", "empty", "full", "half past ten in the morning", "10:30 a.m.", "11:30 a.m."),
    ("the service door", "closed", "open", "quarter past two in the afternoon", "2:15 p.m.", "2:45 p.m."),
]


def main():
    with urlopen(URL + "/api/tags", timeout=30) as response:
        digest = next(m["digest"] for m in json.load(response)["models"] if m["name"] == MODEL)
    rows = []
    for item, state, opposite, exact, equivalent, other in CASES:
        q = f"Was {item} {state} at {exact}?"
        for timing, when in [("exact", exact), ("equivalent", equivalent), ("different", other)]:
            for direction, observed in [("supports", state), ("contradicts", opposite)]:
                quote = f"At {when} a clerk found {item} {observed}."
                passage = q + "\nQuoted sentence: " + quote
                original, ot = predict(URL, MODEL, VERIFY, passage, max_tokens=32)
                relation, rt = predict(URL, MODEL, RELATION, passage, max_tokens=32)
                rows.append(dict(item=item, question=q, observation=quote, timing=timing,
                                 direction=direction, expected=direction if timing != "different" else "irrelevant",
                                 original=original.get("answer"), original_tokens=ot,
                                 relation=relation.get("answer"), relation_tokens=rt))
    print(json.dumps(dict(model=MODEL, digest=digest, rows=rows), indent=2))


if __name__ == "__main__":
    main()
