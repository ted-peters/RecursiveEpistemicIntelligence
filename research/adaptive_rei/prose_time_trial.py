"""Extract both original time phrases before applying the bounded clock parser."""
import json
import re
from urllib.request import urlopen

from clock_normalization import clock_minutes
from paperwork_trial import ROOT
from time_before_relation_trial import URL, MODEL, RELATION, DIRECTION, predict

EXTRACT = ("Copy the time asked about and the time of the observation about the requested item. "
           "Exclude filing times and predictions. Preserve dates, time zones and approximate wording. "
           "Copy exact substrings, without leading at/on. JSON fields requested and observed.")
CONTEXT = re.compile(r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|UTC|GMT|around|about|approximately|before|after|exactly|yesterday|tomorrow)\b", re.I)


def clean(span):
    return span.lower().strip().rstrip(".") if isinstance(span, str) else ""


def main():
    with urlopen(URL + "/api/tags", timeout=30) as res:
        digest = next(m["digest"] for m in json.load(res)["models"] if m["name"] == MODEL)
    rows = []
    for question, body, requested, observed, expected, group in json.loads((ROOT / "prose_time_cases.json").read_text()):
        passage = question + "\nPassage: " + body
        base, bt = predict(URL, MODEL, RELATION, passage, max_tokens=32)
        spans, st = predict(URL, MODEL, EXTRACT, passage, max_tokens=80)
        q, o = spans.get("requested"), spans.get("observed")
        verbatim = all(isinstance(s, str) and bool(s.strip()) and s in source
                       for s, source in [(q, question), (o, body)])
        minutes = [clock_minutes(s) for s in (q, o)] if verbatim else []
        routed = bool(minutes and None not in minutes and not CONTEXT.search(passage))
        answer, cost = base.get("answer"), bt
        if routed:
            answer, cost = "irrelevant", 0
            if minutes[0] == minutes[1]:
                direction, cost = predict(URL, MODEL, DIRECTION, passage, max_tokens=32)
                answer = direction.get("answer")
        rows.append(dict(question=question, passage=body, group=group, expected=expected,
                         requested=requested, observed=observed, extracted=spans,
                         both_correct=bool(clean(q)==clean(requested) and clean(o)==clean(observed)),
                         routed=routed, baseline=base.get("answer"), baseline_tokens=bt,
                         candidate=answer, candidate_tokens=st+cost))
    print(json.dumps(dict(model=MODEL, digest=digest, rows=rows), indent=2))


if __name__ == "__main__":
    main()
