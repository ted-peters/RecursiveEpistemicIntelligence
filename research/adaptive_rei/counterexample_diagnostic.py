"""Repeat the counterexample arm at two output limits, preserving raw model responses."""
import json
import re
from urllib.request import Request, urlopen

from paperwork_trial import ROOT, URL, MODEL
from source_selection import RULE, GUIDANCE


def probe(question, evidence, limit, constrained=False, check_opposite=True):
    lines = re.split(r"(?<=[.!?])\s+|\n+", evidence.strip())
    numbered = "\n".join(f"{i}. {line}" for i, line in enumerate(lines, 1))
    payload = dict(model=MODEL, prompt=RULE + (GUIDANCE if check_opposite else "") + "\n\n" + numbered + "\n" + question,
                   stream=False, format="json", options=dict(temperature=0, seed=42, num_predict=limit))
    if constrained:
        payload["format"] = {"type": "object", "properties": {
            "line": {"type": "integer", "minimum": 0, "maximum": len(lines)},
            "answer": {"type": "string", "enum": ["yes", "no", "uncertain"]}},
            "required": ["line", "answer"], "additionalProperties": False}
    request = Request(URL + "/api/generate", json.dumps(payload).encode(), {"Content-Type": "application/json"})
    with urlopen(request, timeout=90) as response:
        output = json.load(response)
    raw = output["response"]
    try:
        parsed = json.loads(raw)
    except ValueError:
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}
    answer, line = parsed.get("answer"), parsed.get("line")
    if answer not in ("yes", "no", "uncertain") or (answer != "uncertain" and not (
            type(line) is int and 1 <= line <= len(lines))):
        answer = None
    return dict(limit=limit, constrained=constrained, check_opposite=check_opposite, raw=raw, reason=output.get("done_reason"), answer=answer,
                tokens=output["prompt_eval_count"] + output["eval_count"])


if __name__ == "__main__":
    rows = []
    for packet, (evidence, *claims) in enumerate(json.loads((ROOT / "counterexample_cases.json").read_text())):
        for question, expected in claims:
            rows.append(dict(packet=packet, question=question, expected=expected,
                             probes=[probe(question, evidence, limit) for limit in (40, 128)] + [probe(question, evidence, 40, True), probe(question, evidence, 40, True, False)]))
    print(json.dumps(rows, indent=2))
