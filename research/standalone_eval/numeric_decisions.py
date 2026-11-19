"""Experimental numeric decision extraction with deterministic comparison."""
from __future__ import annotations

import json
import math
import re

from rei0.local_ai import DIRECT_SYSTEM, LocalOllamaModel, StandaloneREI
from .paired_values import Case, run_turn


def choose(measurements: dict) -> str | None:
    if not isinstance(measurements, dict) or set(measurements) != {"rule", "threshold", "A", "B"}:
        return None
    rule = measurements["rule"]
    if rule not in ("max_sum", "min_sum", "all_at_least", "all_positive", "unmeasured"):
        return None
    values = [measurements[option] for option in ("A", "B")]
    if rule == "unmeasured":
        return "defer" if values == [[], []] and measurements["threshold"] is None else None
    if not all(isinstance(group, list) and group and len(group) <= 16
               and all(type(value) in (int, float) and math.isfinite(value)
                       for value in group) for group in values):
        return None
    threshold = measurements["threshold"]
    if rule == "all_at_least":
        if type(threshold) not in (int, float) or not math.isfinite(threshold):
            return None
        eligible = [all(value >= threshold for value in group) for group in values]
    elif rule == "all_positive":
        if threshold is not None:
            return None
        eligible = [all(value > 0 for value in group) for group in values]
    else:
        if threshold is not None:
            return None
        totals = [sum(group) for group in values]
        if not all(math.isfinite(total) for total in totals):
            return None
        if totals[0] == totals[1]:
            return "defer"
        if rule == "max_sum":
            return "A" if totals[0] > totals[1] else "B"
        return "A" if totals[0] < totals[1] else "B"
    if eligible[0] == eligible[1]:
        return "defer"
    return "A" if eligible[0] else "B"


def numeric_decision(agent: StandaloneREI, case: Case, priority: str) -> dict:
    criterion = priority.lower()
    if "at least" in criterion:
        rule = "all_at_least"
    elif re.search(r"\b(each|every|both) (trial|field)", criterion):
        rule = "all_positive"
    elif re.search(r"\b(fewer|fewest|lower|lowest|less|cheaper)\b", criterion):
        rule = "min_sum"
    else:
        rule = "max_sum"
    turn = run_turn(
        agent,
        f"Comparison rule is {rule}. Extract only the requested outcome for each option. "
        "Keep option A's measurements in A and option B's in B. Return JSON with "
        "exactly rule, threshold, A, B. Use the supplied rule, or unmeasured if "
        "the outcome is missing. A and B are number arrays. Preserve negative changes. "
        "threshold is the minimum number for all_at_least and null otherwise. "
        "For unmeasured use empty arrays. Do not choose an option.\nResults: "
        + case.evidence + "\nCriterion: " + priority,
        "direct",
    )
    try:
        measurements = json.loads(turn["answer"])
    except json.JSONDecodeError:
        measurements = None
    return {**turn, "measurements": measurements,
            "choice": choose(measurements)}


def referenced_values(document: dict, passages: list[str]) -> dict | None:
    """Validate cited numeric literals; semantic relevance remains model judged."""
    if not isinstance(document, dict) or set(document) != {"rule", "threshold", "A", "B"}:
        return None
    values = {"rule": document["rule"], "threshold": document["threshold"]}
    for option in ("A", "B"):
        entries = document[option]
        if not isinstance(entries, list) or len(entries) > 16:
            return None
        values[option] = []
        seen = set()
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {"value", "ref"}:
                return None
            value, ref = entry["value"], entry["ref"]
            if (type(value) not in (int, float) or not math.isfinite(value)
                    or type(ref) is not int or not 1 <= ref <= len(passages)
                    or (value, ref) in seen):
                return None
            literals = re.findall(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])",
                                  passages[ref - 1].rstrip("."))
            if abs(value) not in [abs(float(literal)) for literal in literals]:
                return None
            seen.add((value, ref))
            values[option].append(value)
    return values


def extraction_schema(passage_count: int) -> dict:
    entry = {
        "type": "object", "additionalProperties": False,
        "properties": {"value": {"type": "number"},
                       "ref": {"type": "integer", "minimum": 1, "maximum": passage_count}},
        "required": ["value", "ref"],
    }
    branches = []
    for rule in ("max_sum", "min_sum", "all_positive", "all_at_least", "unmeasured"):
        array = {"type": "array", "items": entry,
                 "minItems": 0 if rule == "unmeasured" else 1,
                 "maxItems": 0 if rule == "unmeasured" else 16}
        branches.append({
            "type": "object", "additionalProperties": False,
            "properties": {
                "rule": {"type": "string", "enum": [rule]},
                "threshold": {"type": "number" if rule == "all_at_least" else "null"},
                "A": array, "B": array,
            },
            "required": ["rule", "threshold", "A", "B"],
        })
    return {"oneOf": branches}


def referenced_decision(agent: StandaloneREI, case: Case, priority: str, *,
                        structured_provider: LocalOllamaModel | None = None) -> dict:
    passages = case.evidence.split(". ")
    numbered = "\n".join(f"{i}. {text}" for i, text in enumerate(passages, 1))
    question = (
        "Extract only measurements matching the criterion. Each number must cite "
        "its result number. Exclude unrelated outcomes. Keep A and B separate. "
        "Return JSON with rule, threshold, A, B. rule: max_sum for most/greatest, "
        "min_sum for fewer/lower/cheaper, all_at_least for a minimum in each trial, "
        "all_positive for a benefit in every trial, unmeasured for a missing outcome. "
        'A and B contain objects like {"value":12,"ref":1}. Negative changes stay '
        "negative. threshold is numeric only for all_at_least, otherwise null. "
        "For unmeasured use empty arrays. Do not choose an option.\n"
        + numbered + "\nCriterion: " + priority
    )
    if structured_provider is None:
        turn = run_turn(agent, question, "direct")
    else:
        before = len(structured_provider.attempts)
        answer, tokens = structured_provider.complete_structured(
            system=DIRECT_SYSTEM,
            user=json.dumps({"conversation": [{"role": "user", "content": question}]}),
            schema=extraction_schema(len(passages)),
            max_output_tokens=512, timeout=150,
        )
        turn = {"answer": answer, "error": None,
                "model_calls": len(structured_provider.attempts) - before,
                "model_reported_tokens": tokens}
    try:
        extracted = json.loads(turn["answer"])
    except json.JSONDecodeError:
        extracted = None
    measurements = referenced_values(extracted, passages)
    return {**turn, "extracted": extracted, "measurements": measurements,
            "choice": choose(measurements)}



def text_measurements(extracted: dict, passages: list[str], rule: str,
                      threshold: float | None, benefit_direction: str) -> dict | None:
    if not isinstance(extracted, dict) or set(extracted) != {"A", "B"}:
        return None
    result = {"rule": rule, "threshold": threshold}
    for option in ("A", "B"):
        entries = extracted[option]
        if not isinstance(entries, list) or not 1 <= len(entries) <= 16:
            return None
        result[option] = []
        seen = set()
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {"text", "ref", "direction"}:
                return None
            text, ref, direction = entry["text"], entry["ref"], entry["direction"]
            if (not isinstance(text, str) or re.fullmatch(r"\d+(?:\.\d+)?%?", text) is None
                    or type(ref) is not int or not 1 <= ref <= len(passages)
                    or direction not in ("increase", "decrease", "level")
                    or (text, ref) in seen):
                return None
            literals = re.findall(r"(?<![\w.])\d+(?:\.\d+)?%?(?![\w.])",
                                  passages[ref - 1].rstrip("."))
            if text not in literals and not (not text.endswith("%") and text + "%" in literals):
                return None
            seen.add((text, ref))
            value = float(text.removesuffix("%"))
            if not math.isfinite(value):
                return None
            if rule == "all_positive":
                if direction == "level":
                    return None
                value *= 1 if direction == benefit_direction else -1
            result[option].append(value)
    return result



def owned_values_decision(agent: StandaloneREI, case: Case, priority: str, *,
                         provider: LocalOllamaModel) -> dict:
    """Experimental extraction that keeps measurements next to option labels."""
    entry = {"type": "object", "additionalProperties": False,
             "properties": {
                 "A": {"type": ["number", "null"]},
                 "B": {"type": ["number", "null"]},
             }, "required": ["A", "B"]}
    schema = {"type": "object", "additionalProperties": False,
              "properties": {"rows": {"type": "array", "items": entry,
                                       "minItems": 1, "maxItems": 8}},
              "required": ["rows"]}
    question = (
        "Extract a row for each applicable trial or measurement. In every row, "
        "A is the value belonging to option A and B belongs to option B. "
        "Use only the criterion's outcome. For savings, a decrease in use is positive "
        "and an increase is negative. For increased yield, an increase is positive "
        "and a decrease is negative. If unmeasured return a row with both null. "
        "Do not choose an option.\nResults: " + case.evidence + "\nCriterion: " + priority
    )
    before = len(provider.attempts)
    answer, tokens = provider.complete_structured(
        system=DIRECT_SYSTEM, user=question, schema=schema,
        max_output_tokens=512, timeout=150,
    )
    try:
        parsed = json.loads(answer)
    except json.JSONDecodeError:
        parsed = None
    measurements = None
    if isinstance(parsed, dict) and set(parsed) == {"rows"}:
        rows = parsed["rows"]
        if (isinstance(rows, list) and 1 <= len(rows) <= 8
                and all(isinstance(row, dict) and set(row) == {"A", "B"} for row in rows)):
            criterion = priority.lower()
            threshold = re.search(r"at least\s+(\d+(?:\.\d+)?)", criterion)
            if all(row == {"A": None, "B": None} for row in rows):
                measurements = {"rule": "unmeasured", "threshold": None, "A": [], "B": []}
            else:
                rule = "max_sum"
                if threshold:
                    rule = "all_at_least"
                elif re.search(r"\b(each|every|both) (trial|field)s?\b", criterion):
                    rule = "all_positive"
                elif re.search(r"\b(fewer|fewest|lower|lowest|less|cheaper)\b", criterion):
                    rule = "min_sum"
                measurements = {
                    "rule": rule,
                    "threshold": float(threshold.group(1)) if threshold else None,
                    "A": [row["A"] for row in rows], "B": [row["B"] for row in rows],
                }
    return {"answer": answer, "measurements": measurements,
            "choice": choose(measurements), "error": None,
            "model_calls": len(provider.attempts) - before, "model_reported_tokens": tokens}



def missing_percentage_coverage(selection: dict, candidates: list[dict],
                                passages: list[str]) -> dict[str, list[int]]:
    """Development check for cases with one percentage trial per sentence."""
    required = {i for i, passage in enumerate(passages, 1) if "%" in passage}
    missing = {}
    for option in ("A", "B"):
        entries = selection.get(option, []) if isinstance(selection, dict) else []
        covered = set()
        if isinstance(entries, list):
            for entry in entries:
                if (isinstance(entry, dict) and type(entry.get("id")) is int
                        and 1 <= entry["id"] <= len(candidates)):
                    candidate = candidates[entry["id"] - 1]
                    if candidate["text"].endswith("%"):
                        covered.add(candidate["ref"])
        missing[option] = sorted(required - covered)
    return {option: refs for option, refs in missing.items() if refs}


def targeted_decision(agent: StandaloneREI, case: Case, priority: str, *,
                      provider: LocalOllamaModel, coverage_check: bool = False) -> dict:
    """Use constrained extraction only for explicit universal trial criteria."""
    universal = re.search(r"\b(each|every|both) (trial|field)s?\b", priority.lower())
    if universal is None:
        from .paired_values import compact_decision
        return compact_decision(agent, case, priority)
    passages = case.evidence.split(". ")
    threshold_match = re.search(r"at least\s+(\d+(?:\.\d+)?)", priority.lower())
    threshold = float(threshold_match.group(1)) if threshold_match else None
    rule = "all_at_least" if threshold is not None else "all_positive"
    benefit_direction = (
        "decrease" if re.search(
            r"\b(savings|reducing|reduced|decreasing|decreased)\b", priority.lower()
        ) else "increase"
    )
    percentage_threshold = re.search(
        r"at least\s+\d+(?:\.\d+)?%", priority.lower()
    ) is not None
    percentage_refs = [i for i, passage in enumerate(passages, 1) if "%" in passage]
    entry = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "text": {"type": "string", "pattern": r"^\d+(?:\.\d+)?%?$"},
            "ref": {"type": "integer", "minimum": 1, "maximum": len(passages)},
            "direction": {"type": "string", "enum": ["increase", "decrease", "level"]},
        }, "required": ["text", "ref", "direction"],
    }
    if percentage_threshold:
        entry["properties"]["text"]["pattern"] = r"^\d+(?:\.\d+)?%$"
        entry["properties"]["ref"]["enum"] = percentage_refs
    candidates = []
    for ref, passage in enumerate(passages, 1):
        for match in re.finditer(r"(?<![\w.])\d+(?:\.\d+)?%?(?![\w.])",
                                 passage.rstrip(".")):
            text = match.group()
            if percentage_threshold and not text.endswith("%"):
                continue
            candidates.append({"text": text, "ref": ref})
    if not candidates:
        return {"answer": "", "choice": None, "error": "no_measurements",
                "model_calls": 0, "model_reported_tokens": 0}
    selection = {"type": "object", "additionalProperties": False,
                 "properties": {
                     "id": {"type": "integer", "enum": list(range(1, len(candidates) + 1))},
                     "direction": entry["properties"]["direction"],
                 }, "required": ["id", "direction"]}
    array = {"type": "array", "items": selection, "minItems": 1, "maxItems": 16}
    schema = {"type": "object", "additionalProperties": False,
              "properties": {"A": array, "B": array}, "required": ["A", "B"]}
    numbered = "\n".join(f"{i}. {passage}" for i, passage in enumerate(passages, 1))
    catalog = "\n".join(
        f"ID {i}: {item['text']} in sentence {item['ref']}"
        for i, item in enumerate(candidates, 1)
    )
    question = (
        "Select IDs for each trial's outcome under the criterion, separately for A "
        "and B. Include all applicable trials and exclude costs and unrelated outcomes. "
        "Each entry has id and direction: increase, decrease, or level. "
        "Energy use going down is decrease. Return JSON matching the schema.\n"
        + numbered + "\nMeasurements:\n" + catalog + "\nCriterion: " + priority
    )
    before = len(provider.attempts)
    answer, tokens = provider.complete_structured(
        system=DIRECT_SYSTEM, user=question, schema=schema,
        max_output_tokens=512, timeout=150,
    )
    try:
        extracted = json.loads(answer)
    except json.JSONDecodeError:
        extracted = None
    initial_answer = answer
    missing = missing_percentage_coverage(extracted, candidates, passages) if coverage_check else {}
    retried = bool(missing)
    if retried:
        answer, extra_tokens = provider.complete_structured(
            system=DIRECT_SYSTEM,
            user=question + "\nPrevious selection: " + answer
                 + "\nMissing percentage trial sentences by option: "
                 + json.dumps(missing)
                 + "\nReturn a complete corrected selection covering these sentences.",
            schema=schema, max_output_tokens=512, timeout=150,
        )
        tokens += extra_tokens
        try:
            extracted = json.loads(answer)
        except json.JSONDecodeError:
            extracted = None
    coverage_missing = missing_percentage_coverage(extracted, candidates, passages) if coverage_check else {}
    selected_ids = extracted
    expanded = {}
    if isinstance(extracted, dict) and set(extracted) == {"A", "B"}:
        for option in ("A", "B"):
            entries = extracted[option]
            if not isinstance(entries, list):
                break
            expanded[option] = []
            for item in entries:
                if (not isinstance(item, dict) or set(item) != {"id", "direction"}
                        or type(item["id"]) is not int
                        or not 1 <= item["id"] <= len(candidates)):
                    expanded = {}
                    break
                expanded[option].append({
                    **candidates[item["id"] - 1], "direction": item["direction"],
                })
            if option not in expanded:
                break
    extracted = expanded
    measurements = text_measurements(extracted, passages, rule, threshold, benefit_direction)
    if coverage_missing:
        measurements = None
    return {"coverage_retry": retried, "coverage_missing": coverage_missing,
            "initial_answer": initial_answer,"answer": answer, "selected_ids": selected_ids, "extracted": extracted, "measurements": measurements,
            "choice": choose(measurements), "error": None,
            "model_calls": len(provider.attempts) - before,
            "model_reported_tokens": tokens}


def selected_decision(agent: StandaloneREI, case: Case, priority: str, *,
                      provider: LocalOllamaModel) -> dict:
    """Select relevant source sentences before running the experimental extractor."""
    from dataclasses import replace
    passages = case.evidence.split(". ")
    schema = {
        "type": "object", "additionalProperties": False,
        "properties": {"refs": {"type": "array", "uniqueItems": True,
                               "items": {"type": "integer", "minimum": 1,
                                         "maximum": len(passages)},
                               "maxItems": len(passages)}},
        "required": ["refs"],
    }
    numbered = "\n".join(f"{i}. {text}" for i, text in enumerate(passages, 1))
    answer, tokens = provider.complete_structured(
        system=DIRECT_SYSTEM,
        user="Select every sentence measuring the criterion or explicitly saying "
             "it was not measured. Include all trials and both options. Return only "
             "the refs JSON.\n" + numbered + "\nCriterion: " + priority,
        schema=schema, max_output_tokens=128, timeout=150,
    )
    try:
        selected = json.loads(answer)
    except json.JSONDecodeError:
        selected = None
    refs = selected.get("refs") if isinstance(selected, dict) else None
    if (not isinstance(refs, list) or not refs
            or not all(type(ref) is int and 1 <= ref <= len(passages) for ref in refs)
            or len(refs) != len(set(refs))):
        return {"answer": "", "choice": None, "error": "invalid_selection",
                "selection": answer, "model_calls": 1, "model_reported_tokens": tokens}
    filtered = replace(case, evidence=". ".join(passages[ref - 1] for ref in sorted(refs)))
    result = owned_values_decision(agent, filtered, priority, provider=provider)
    return {**result, "selection": answer,
            "model_calls": result["model_calls"] + 1,
            "model_reported_tokens": result["model_reported_tokens"] + tokens}
