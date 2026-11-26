"""Paired three-way verdict benchmark across tasks and installed model families."""
import argparse
import json
from urllib.request import urlopen

from paperwork_trial import ROOT, URL, MODEL, SINGLE_PASS, predict, decide


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=[MODEL, "llama3.2:1b"])
    models = parser.parse_args().models
    with urlopen(URL + "/api/tags", timeout=30) as response:
        installed = {m["name"]: m["digest"] for m in json.load(response)["models"]}
    digests = {name: installed[name] for name in models}
    rows = []
    for name in models:
        for domain, text, expected in json.loads((ROOT / "mixed_model_cases.json").read_text()):
            direct, dt = predict(URL, name, SINGLE_PASS, text)
            rei, rt = decide(URL, name, text, skip_gaps=True)
            rows.append(dict(model=name, domain=domain, question=text, expected=expected,
                             direct=direct.get("answer"), direct_tokens=dt, rei=rei["answer"], rei_tokens=rt))
    print(json.dumps(dict(digests=digests, rows=rows), indent=2))


if __name__ == "__main__":
    main()
