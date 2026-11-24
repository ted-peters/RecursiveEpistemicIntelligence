"""Compare frozen audit claims with the two existing answer modes using local Ollama."""
import argparse
import json
from pathlib import Path
from urllib.request import urlopen

from adaptive_rei_benchmark import SINGLE_PASS, predict
from boolq_trial import MODEL
from selective_review import decide


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:11434")
    args = parser.parse_args()
    packets = json.loads(Path(__file__).with_name("maintenance_audit_cases.json").read_text())
    with urlopen(args.url + "/api/tags", timeout=30) as response:
        digest = next(m["digest"] for m in json.load(response)["models"] if m["name"] == MODEL)
    rows = []
    for packet in packets:
        evidence = packet["evidence"]
        for question, expected, support in packet["claims"]:
            passage = question + " " + " ".join(evidence)
            baseline, direct_tokens = predict(args.url, MODEL, SINGLE_PASS, passage)
            rei, rei_tokens = decide(args.url, MODEL, passage, skip_gaps=True)
            rows.append(dict(packet=packet["id"], question=question, expected=expected,
                             single_pass=baseline.get("answer"), single_pass_tokens=direct_tokens,
                             rei=rei["answer"], rei_tokens=rei_tokens, citation=rei["citation"],
                             citation_sufficient=bool(rei["citation"] and len(support) == 1
                                                      and rei["citation"] == evidence[support[0]-1]
                                                      and rei["answer"] == expected)))
    print(json.dumps(dict(model=MODEL, digest=digest, rows=rows), indent=2))


if __name__ == "__main__":
    main()
