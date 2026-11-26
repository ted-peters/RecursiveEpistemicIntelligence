"""Primary endpoint is correct citation (including no citation) and verdict together."""
import json
import random
from urllib.request import urlopen

from observation_origin_trial import ROOT, URL, MODEL, SINGLE_PASS, predict, decide, plain, select_line

VERIFY = ("Does the quoted sentence give firsthand evidence about the EXACT item at the EXACT "
          "time in the question? Either a positive or a negative observation qualifies. "
          "A plan or copy does not. Reply as JSON with field answer, yes or no.")


def main():
    with urlopen(URL + "/api/tags", timeout=30) as res:
        digest = next(m["digest"] for m in json.load(res)["models"] if m["name"] == MODEL)
    rows = []
    rng = random.Random(50)
    for q, entry, copy, yes, no, other, earlier in json.loads((ROOT / "observation_match_cases.json").read_text()):
        for kind, extra, expected in [("support", yes, "yes"), ("contradiction", no, "no"),
                                      ("other_item", other, "uncertain"), ("other_time", earlier, "uncertain"),
                                      ("copy", "The daily summary cited the same published status.", "uncertain")]:
            lines = [entry, copy, extra]
            rng.shuffle(lines)
            key = 0 if expected == "uncertain" else lines.index(extra) + 1
            passage = q + " " + " ".join(lines)
            base, bt = predict(URL, MODEL, SINGLE_PASS, passage)
            current, ct = decide(URL, MODEL, passage, skip_gaps=True)
            index, st = select_line(q, lines)
            answer = "uncertain" if index == 0 else None
            at = vt = 0
            kept = index
            check = None
            if index:
                selected = lines[index-1]
                verdict, at = plain(URL, MODEL, q + " " + selected)
                answer = verdict["answer"]
                check, vt = predict(URL, MODEL, VERIFY, q + "\nQuoted sentence: " + selected, max_tokens=32)
                kept = index if check.get("answer") == "yes" else 0
            rows.append(dict(question=q, kind=kind, lines=lines, expected=expected, key=key,
                             base=base.get("answer"), base_tokens=bt, current=current["answer"], current_tokens=ct,
                             index=index, original=answer, original_tokens=st+at, check=check, kept=kept,
                             checked="uncertain" if kept == 0 else answer,
                             checked_tokens=st+vt+(at if kept else 0)))
    print(json.dumps(dict(model=MODEL, digest=digest, rows=rows), indent=2))


if __name__ == "__main__":
    main()
