"""Experimental short-answer decoder for passage-based yes/no questions."""
import json
import urllib.request

from evidence_register import evidence_passage, explicit_answer


def decide(url, model, text, *, separate_reports=False, trace_sources=False, constrained=False):
    result = explicit_answer(text)
    if result is not None:
        return {"answer": result}, 0
    prompt = ("Use the passage to answer the question. Answer with one word: yes, no, or uncertain.\n\n"
              + evidence_passage(text) + "\n\nAnswer:")
    if separate_reports or trace_sources:
        question, separator, evidence = evidence_passage(text).partition("?")
        if separator and evidence.strip():
            prompt = ("Keep two facts separate: what a source said and what happened. "
                      "Answer only the question asked, at its stated time. Unknown: uncertain.\n"
                      + evidence.strip() + "\n" + question + "?\nAnswer yes, no, or uncertain:")
            if trace_sources:
                prompt = ("Audit the actual fact. Trace each claim to its origin. An unchecked entry "
                          "and copies of it leave the fact uncertain. Use an independent observation "
                          "of the same item and time when present.\n" + evidence.strip() + "\n"
                          + question + "?\nAnswer yes, no, or uncertain:")
    payload = {"model": model, "prompt": prompt, "stream": False,
               "options": {"temperature": 0, "seed": 42, "num_predict": 12}}
    if constrained:
        payload["format"] = {"type": "string", "enum": ["yes", "no", "uncertain"]}
    request = urllib.request.Request(url + "/api/generate", json.dumps(payload).encode(),
                                     {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=90) as response:
        output = json.load(response)
    answer = output["response"].strip().lower().removesuffix(".")
    if constrained:
        try:
            answer = json.loads(output["response"])
        except ValueError:
            answer = None
    return {"answer": answer if answer in ("yes", "no", "uncertain") else None}, (
        output["prompt_eval_count"] + output["eval_count"])
