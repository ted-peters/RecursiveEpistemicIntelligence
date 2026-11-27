"""Compare the existing recursive evidence pipeline with direct Llama verdicts."""
import json
from urllib.error import HTTPError
from urllib.request import urlopen

from adaptive_rei_benchmark import benchmark_rei
from quote_first_trial import MODEL, ROOT, URL, VERDICT, generate


def main():
    previous = json.loads((ROOT / "results/fresh_fact_trial.json").read_text())
    with urlopen(URL + "/api/tags", timeout=30) as response:
        if not any(m["name"] == MODEL and m["digest"] == previous["digest"]
                   for m in json.load(response)["models"]):
            raise ValueError("Model digest mismatch")
    rows = []
    for case in previous["rows"]:
        # REI validates evidence against the passage after the question mark.
        question = f'Is this claim true: "{case["claim"]}"? {case["passage"]}'
        direct = generate(VERDICT + "\n\n" + question,
                          dict(type="string", enum=["yes", "no", "uncertain"]), 12)
        server_errors = []
        for attempt in range(2):
            try:
                rei = benchmark_rei(URL, MODEL, [(question, case["expected"])])["results"][0]
                break
            except HTTPError as error:
                if error.code != 500:
                    raise
                server_errors.append(error.read().decode(errors="replace"))
        else:
            rei = {"request_error": "HTTP 500 after two attempts"}
        if server_errors:
            rei["server_errors"] = server_errors
        rows.append(dict(**case, question=question, matched_direct=direct, rei=rei))
    print(json.dumps(dict(model=MODEL, digest=previous["digest"], rows=rows), indent=2))


if __name__ == "__main__":
    main()
