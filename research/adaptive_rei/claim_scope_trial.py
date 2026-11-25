"""Evaluate matched questions on the same evidence and repeat the audit pilot."""
import json
from urllib.request import urlopen

from claim_scope import decide as compare
from paperwork_trial import ROOT, URL, MODEL, SINGLE_PASS, predict, decide


def main():
    with urlopen(URL + "/api/tags", timeout=30) as response:
        digest = next(m["digest"] for m in json.load(response)["models"] if m["name"] == MODEL)
    packets = [("fresh", str(i), evidence, claims) for i, (evidence, *claims) in
               enumerate(json.loads((ROOT / "claim_scope_cases.json").read_text()))]
    for p in json.loads((ROOT / "maintenance_audit_cases.json").read_text()):
        packets.append(("pilot", p["id"], " ".join(p["evidence"]), p["claims"]))
    rows = []
    for suite, packet, evidence, claims in packets:
        for question, expected, *_ in claims:
            passage = question + " " + evidence
            direct, dt = predict(URL, MODEL, SINGLE_PASS, passage)
            current, ct = decide(URL, MODEL, passage, skip_gaps=True)
            candidate, tokens = compare(URL, MODEL, passage)
            rows.append(dict(suite=suite, packet=packet, question=question, expected=expected,
                             conventional=direct.get("answer"), conventional_tokens=dt,
                             current=current["answer"], current_tokens=ct, **candidate, tokens=tokens))
    print(json.dumps(dict(model=MODEL, digest=digest, rows=rows), indent=2))


if __name__ == "__main__":
    main()
