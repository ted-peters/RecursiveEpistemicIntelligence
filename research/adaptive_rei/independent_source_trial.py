"""Primary endpoint: all four verdicts correct for one claim under the audit rubric."""
import json
from urllib.request import urlopen

from paperwork_trial import ROOT, URL, MODEL, SINGLE_PASS, predict, decide
from plain_verdict import decide as plain
from record_yes_trial import eligible
from counterexample_diagnostic import probe


def main():
    with urlopen(URL + "/api/tags", timeout=30) as response:
        digest = next(m["digest"] for m in json.load(response)["models"] if m["name"] == MODEL)
    rows = []
    for question, entry, copy, yes, no in json.loads((ROOT / "independent_source_cases.json").read_text()):
        for kind, extra, expected in [("entry", "", "uncertain"), ("copy", copy, "uncertain"),
                                      ("observed_yes", yes, "yes"), ("observed_no", no, "no")]:
            evidence = (entry + " " + extra).strip()
            passage = question + " " + evidence
            conventional, dt = predict(URL, MODEL, SINGLE_PASS, passage)
            current, ct = decide(URL, MODEL, passage, skip_gaps=True)
            check = probe(question, evidence, 40, constrained=True) if eligible(question, evidence, current) else None
            previous = check["answer"] if check and check["answer"] is not None else current["answer"]
            control, rt = plain(URL, MODEL, passage, separate_reports=True)
            traced, tt = plain(URL, MODEL, passage, trace_sources=True)
            rows.append(dict(question=question, kind=kind, expected=expected,
                             conventional=conventional.get("answer"), conventional_tokens=dt,
                             current=current["answer"], current_tokens=ct, previous=previous,
                             previous_tokens=ct + (check["tokens"] if check else 0),
                             control=control["answer"], control_tokens=rt,
                             traced=traced["answer"], traced_tokens=tt))
    print(json.dumps(dict(model=MODEL, digest=digest, rows=rows), indent=2))


if __name__ == "__main__":
    main()
