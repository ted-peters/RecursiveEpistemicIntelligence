"""Answer from a selected sentence in the passage."""
import re
from adaptive_rei_benchmark import predict

RULE = ("Select the line answering the exact question. For what was recorded, use the entry. "
        "For what happened, use a witness to that event at that time. "
        "Return JSON: line (number, 0 if unknown), answer (yes/no/uncertain).")


def decide(url, model, passage):
    question, sep, body = passage.partition("?")
    if not sep or not body.strip():
        raise ValueError("Provide a question followed by a passage.")
    lines = re.split(r"(?<=[.!?])\s+|\n+", body.strip())
    numbered = "\n".join(f"{i}. {line}" for i, line in enumerate(lines, 1))
    result, tokens = predict(url, model, RULE, numbered + "\n" + question + "?", max_tokens=40)
    index = result.get("line")
    cited = type(index) is int and 1 <= index <= len(lines)
    answer = result.get("answer")
    if answer not in ("yes", "no", "uncertain") or (answer != "uncertain" and not cited):
        answer = None
    return {"answer": answer, "line": index, "citation": lines[index-1] if cited else None}, tokens
