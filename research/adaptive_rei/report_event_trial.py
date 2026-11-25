"""Frozen criterion: beat budgeted REI on fresh complete triplets at <=100% of its total tokens."""
import json
from urllib.request import urlopen

from paperwork_trial import ROOT, URL, MODEL, SINGLE_PASS, predict, decide
from plain_verdict import decide as plain


def main():
    with urlopen(URL + "/api/tags", timeout=30) as response:
        digest = next(m["digest"] for m in json.load(response)["models"] if m["name"] == MODEL)
    rows = []
    for suite, filename in (("fresh", "report_event_cases.json"), ("prior", "claim_scope_cases.json")):
        for packet, (evidence, *claims) in enumerate(json.loads((ROOT / filename).read_text())):
            for question, expected in claims:
                passage = question + " " + evidence
                direct, dt = predict(URL, MODEL, SINGLE_PASS, passage)
                current, ct = decide(URL, MODEL, passage, skip_gaps=True)
                simple, st = plain(URL, MODEL, passage)
                experimental, et = plain(URL, MODEL, passage, separate_reports=True)
                rows.append(dict(suite=suite, packet=packet, question=question, expected=expected,
                                 conventional=direct.get("answer"), conventional_tokens=dt,
                                 current=current["answer"], current_tokens=ct,
                                 plain=simple["answer"], plain_tokens=st,
                                 candidate=experimental["answer"], candidate_tokens=et))
    print(json.dumps(dict(model=MODEL, digest=digest, rows=rows), indent=2))


if __name__ == "__main__":
    main()
