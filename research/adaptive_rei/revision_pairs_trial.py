"""Run one arm against its pinned checkout, using PR 67's frozen question strings."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from urllib.error import HTTPError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
OLD = "408641d7744c8690f61be06517f8acc23064737d"
NEW = "8797b9b5b84d7550935267763dbb8f57ff171ef5"
URL = "http://127.0.0.1:11434"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("arm", choices=("old", "new", "prose"))
    args = parser.parse_args()
    revision = OLD if args.arm == "old" else NEW
    checkout = args.checkout.resolve()
    source = checkout / "research/adaptive_rei"
    files = subprocess.check_output(["git", "-C", str(checkout), "diff", revision,
                                     "--name-only", "--", "research/adaptive_rei/*.py"], text=True)
    if any(Path(f).name != Path(__file__).name for f in files.splitlines()):
        raise ValueError("Checkout differs from pinned Python sources")
    sys.path.insert(0, str(source))
    from adaptive_rei_benchmark import benchmark_rei
    if args.arm == "prose":
        from selective_review import decide
    prior = json.loads((ROOT / "results/rei_fact_trial.json").read_text())
    model = prior["model"]
    with urlopen(URL + "/api/tags", timeout=30) as response:
        if not any(m["name"] == model and m["digest"] == prior["digest"]
                   for m in json.load(response)["models"]):
            raise ValueError("Model digest mismatch")
    rows = []
    for case in prior["rows"]:
        row = {k: case[k] for k in ("claim", "question", "expected")}
        errors = []
        for attempt in range(2):
            try:
                if args.arm == "prose":
                    result, tokens = decide(URL, model, row["question"], skip_gaps=True)
                    row.update(result=result, tokens=tokens, answer=result["answer"])
                else:
                    result = benchmark_rei(URL, model, [(row["question"], row["expected"])])["results"][0]
                    row.update(result=result, tokens=result["tokens"],
                               answer=result.get("recursive", {}).get("answer"))
                break
            except HTTPError as error:
                if error.code != 500:
                    raise
                errors.append(error.read().decode(errors="replace"))
        else:
            row.update(answer=None, tokens=None)
        if errors:
            row["request_errors"] = errors
        rows.append(row)
    print(json.dumps(dict(revision=revision, arm=args.arm, model=model,
                          digest=prior["digest"], rows=rows), indent=2))


if __name__ == "__main__":
    main()
