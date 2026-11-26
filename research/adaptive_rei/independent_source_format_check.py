"""Matched diagnostic: constrain both prompts to the same three verdict strings."""
import json
from paperwork_trial import ROOT, MODEL, URL
from plain_verdict import decide


def main():
    rows = []
    for question, entry, copy, yes, no in json.loads((ROOT / "independent_source_cases.json").read_text()):
        for kind, extra, expected in [("entry", "", "uncertain"), ("copy", copy, "uncertain"),
                                      ("observed_yes", yes, "yes"), ("observed_no", no, "no")]:
            passage = question + " " + (entry + " " + extra).strip()
            row = dict(question=question, kind=kind, expected=expected)
            for key, options in [("control", {"separate_reports": True}), ("traced", {"trace_sources": True})]:
                result, cost = decide(URL, MODEL, passage, constrained=True, **options)
                row[key], row[key + "_tokens"] = result["answer"], cost
            rows.append(row)
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
