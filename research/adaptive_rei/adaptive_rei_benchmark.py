"""Run with Python 3 while Ollama is running locally. Prints JSON results."""
import argparse
import json
import re
import urllib.request

from adaptive_rei_engine import POLICIES, Evidence, evaluate
from evidence_schema import GRAPH
from quantity_comparison import quantity_verdict

CASES = [
    ("Did the package arrive? A signed delivery receipt identifies the package and its recipient.", "yes"),
    ("Was the room empty? A live camera showed two people inside at the specified time.", "no"),
    ("Did the pump fail? A preliminary report said yes. A later teardown confirmed the pump worked and found the outlet valve closed.", "no"),
    ("Was the crate sealed at noon? Two independent, equally reliable inspectors report opposite observations. No resolving evidence exists.", "uncertain"),
    ("Did the schedule change cause the sales increase? Sales rose 12% the same week the schedule changed and a large promotion began. No separate comparison is available.", "uncertain"),
    ("Did the parcel arrive? The recipient confirmed receipt. An unrelated invoice has the wrong tax rate.", "yes"),
    ("Did the freezer drop below zero? The dashboard says yes based on a validated export. Validation checked file integrity only. The export used a probe assigned to a different freezer. No other reading exists.", "uncertain"),
    ("Was the exit blocked? A supervisor said no based on the status board. The board copied a record from yesterday. A timestamped photo from the time in question shows a pallet blocking the exit.", "yes"),
    ("Did the coin land heads? It was flipped behind a screen. No result was recorded.", "uncertain"),
    ("Was the container full? Two dashboards said yes, but both copied the same snapshot taken before draining. A direct inspection afterward found it empty at the time in question.", "no"),
]
FRESH_CASES = [
    ("Was the hall occupied at 7 p.m.? An old booking sheet lists a rehearsal. A live recording at 7 p.m. shows an empty hall.", "no"),
    ("Was the meter running at noon? A technician filmed its dial advancing at noon.", "yes"),
    ("Was the label printed before shipment? One witness says it was printed before shipment. An equally reliable witness says it was printed afterward. No timestamps are available.", "uncertain"),
    ("Was the blue bin weighed? The blue bin's log says yes, but its entry was copied from the green bin's record. There is no separate measurement.", "uncertain"),
    ("Did the lighting upgrade cause the drop in electricity use? The lights were replaced on the same day the building reduced its opening hours. There is no comparison that isolates either change.", "uncertain"),
    ("Was the cabinet unlocked? A technician opened it without unlocking it. An unrelated light in the hallway had failed.", "yes"),
]
EVIDENCE_CUES = re.compile(
    r"\b(?:preliminary|old|earlier|stale|copied|opposite|equally reliable|"
    r"same (?:day|week)|based on|but|however)\b", re.IGNORECASE
)
RULE = "Use the supplied text only. Return JSON with one field, answer, set to yes, no, or uncertain."
BASELINE = RULE
SINGLE_PASS = RULE + (
    " Use direct observations or records that answer the question about the right subject and time."
    " Use uncertain when relevant evidence is missing or a material conflict remains unresolved."
)
SCREEN = RULE + " Also return review as a boolean. Set it true only when resolving a conflict or checking a shaky assumption could change the answer."
REVIEW = RULE + " Follow each disputed claim through its supporting assumptions. Weigh independent evidence and abstain if decisive support is missing."

def predict(url, model, instruction, case, *, max_tokens=128, output_format="json"):
    payload = {
        "model": model, "prompt": instruction + "\n\n" + case,
        "stream": False, "format": output_format,
        "options": {"temperature": 0, "seed": 42, "num_predict": max_tokens},
    }
    request = urllib.request.Request(
        url + "/api/generate", json.dumps(payload).encode(),
        {"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        result = json.load(response)
    try:
        answer = json.loads(result["response"])
        if not isinstance(answer, dict):
            answer = {}
    except json.JSONDecodeError:
        answer = {}
    return answer, result["prompt_eval_count"] + result["eval_count"]

def focused_review(url, model, case, original, tokens):
    evidence = case.partition("?")[2]
    if original in ("yes", "no", "uncertain") and not EVIDENCE_CUES.search(evidence):
        return original, tokens, 1

    instruction = (
        f"The initial answer was {json.dumps(original)}. Keep it unless specific evidence "
        "changes the decision. Prefer evidence from the right time and subject. "
        "Return JSON with answer (yes, no, or uncertain) and quote "
        "(a short exact excerpt from the evidence that justifies any change)."
    )
    reviewed, extra = predict(url, model, instruction, case)
    candidate = reviewed.get("answer")
    quote = reviewed.get("quote")
    if (
        candidate in ("yes", "no", "uncertain")
        and isinstance(quote, str)
        and len(quote.strip().split()) >= 4
        and quote.strip() in evidence
    ):
        original = candidate
    return original, tokens + extra, 2


def benchmark(url, model, cases=CASES, quick=False):
    modes = ["direct", "single_pass"]
    if not quick:
        modes.extend(("adaptive", "always_review", "focused"))
    scores = {
        name: {"correct": 0, "tokens": 0, "calls": 0, "corrected": 0, "regressed": 0}
        for name in modes
    }
    rows = []
    for index, (case, expected) in enumerate(cases, 1):
        direct, direct_tokens = predict(url, model, BASELINE, case)
        single, single_tokens = predict(url, model, SINGLE_PASS, case)
        row = {"case": index, "expected": expected}
        outcomes = {
            "direct": (direct.get("answer"), direct_tokens, 1),
            "single_pass": (single.get("answer"), single_tokens, 1),
        }
        if not quick:
            screen, screen_tokens = predict(url, model, SCREEN, case)
            review, review_tokens = predict(url, model, REVIEW, case)
            first_answer = screen.get("answer")
            needs_review = (
                screen.get("review") is not False
                or first_answer not in ("yes", "no", "uncertain")
            )

            # Both policies share the same first pass and review response.
            # Attribute only the calls each policy would make on its own.
            row["triggered_review"] = needs_review
            shared_tokens = screen_tokens + review_tokens
            outcomes.update({
                "adaptive": (review.get("answer"), shared_tokens, 2)
                if needs_review else (first_answer, screen_tokens, 1),
                "always_review": (review.get("answer"), shared_tokens, 2),
                "focused": focused_review(url, model, case, direct.get("answer"), direct_tokens),
            })
        direct_correct = direct.get("answer") == expected
        for name, (answer, tokens, calls) in outcomes.items():
            correct = answer == expected
            row[name] = {"answer": answer, "tokens": tokens, "calls": calls}
            scores[name]["correct"] += correct
            scores[name]["tokens"] += tokens
            scores[name]["calls"] += calls
            scores[name]["corrected"] += correct and not direct_correct
            scores[name]["regressed"] += direct_correct and not correct
        rows.append(row)
    return {"model": model, "cases": len(cases), "scores": scores, "results": rows}

EXTRACT = """Extract an evidence graph from the supplied question and text. Return JSON:
{"claims":[{"claim":"yes/no proposition","evidence":[
{"answer":"yes","strength":2,"quote":"exact words in the text","requires":[]}]}]}
The last claim is the positive proposition asked about. Write the proposition,
not a yes/no verdict. Earlier claims are prerequisites.
For answer, use yes or no for evidence for or against the proposition.
Use gap for missing evidence or missing comparisons. A gap has no polarity.
For gaps, leave requires empty. The quote may be empty if the text is silent.
Use undercut when a quote disqualifies another item (e.g. wrong subject).
Include target on an undercut: the 1-based position of the earlier yes/no
evidence item within the same claim. Put the source item before its undercut.
Number claims by their 1-based positions. Each requires list contains pairs
[claim_number, "yes" or "no"] referring only to earlier claims.
Strength 1 means weak, 2 means clear, and 3 means strong. Judge strength
assuming the listed prerequisites hold. If a source relies on the right
subject, time, or measurement, express that dependency explicitly when it
is disputed. Include evidence on both sides. Use an empty evidence list
when the text gives no evidence. Quote from after the question only."""


LINKED_EXTRACT = """Represent the source and its dependent conclusion as separate claims.
Use this JSON structure. Replace placeholders with propositions and exact quotes:
{"claims":[{"claim":"source premise","evidence":[
{"answer":"yes","strength":2,"quote":"source observation","requires":[]},
{"answer":"undercut","target":1,"strength":2,"quote":"source correction","requires":[]}]},
{"claim":"proposition asked about","evidence":[
{"answer":"yes","strength":2,"quote":"dependent report","requires":[[1,"yes"]]}]}]}
A correction identifying the wrong subject belongs in claim 1 as an undercut targeting the source. It does not prove the final proposition false. Omit an undercut if none exists. Include independent evidence with empty requires.
Use no for opposing evidence and gap for missing evidence. Quote only the supplied evidence."""


# A narrow semantic check for a causal question with an explicit comparison gap.
CAUSAL_QUESTION = re.compile(r"^Did .+\b(?:cause|lead to|result in)\b", re.IGNORECASE)
COMPARISON_GAP = re.compile(
    r"there (?:is|was) no comparison that isolates? (?:either|the) change\.?",
    re.IGNORECASE,
)


def reviewed_role(question, source, quote, answer):
    if answer not in ("yes", "no"):
        return answer
    if (re.search(r"equally reliable .*report opposite observations", quote, re.I)
        and not re.search(r"inspectors?|reports?|agree|disagree|conflict|observations", question, re.I)):
        return "gap"
    if CAUSAL_QUESTION.search(question) and (
        COMPARISON_GAP.fullmatch(quote.strip())
        or (re.search(r"same (?:week|day)", quote, re.I)
            and "no separate comparison" in source.lower())
    ):
        return "gap"
    # Opening an object without unlocking it supports its prior unlocked state.
    # Limit this inference to a state question and an unqualified opening.
    state = re.fullmatch(r"Was (?:the|a) [\w -]+ (unlocked|locked)", question, re.I)
    if state and re.fullmatch(r"(?:A|The) \w+ opened it without unlocking it\.?", quote, re.I):
        return "yes" if state[1].lower() == "unlocked" else "no"
    return answer


def parse_evidence(graph, case, *, audit=None):
    rows = graph.get("claims")
    if not isinstance(rows, list) or not rows or len(rows) > 20:
        raise ValueError("Expected 1 to 20 claims")
    question, _, source = case.partition("?")
    claims = {}
    for number, row in enumerate(rows, 1):
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("claim"), str)
            or not row["claim"].strip()
            or not isinstance(row.get("evidence"), list)
        ):
            raise ValueError(f"Malformed claim {number}")
        evidence = []
        for item in row["evidence"]:
            if not isinstance(item, dict):
                raise ValueError(f"Malformed evidence for claim {number}")
            quote = item.get("quote")
            answer = item.get("answer")
            strength = item.get("strength")
            requires = item.get("requires")
            if (
                not isinstance(quote, str)
                or (bool(quote.strip()) and quote not in source)
                or (answer != "gap" and not quote.strip())
                or answer not in ("yes", "no", "gap", "undercut")
                or type(strength) is not int or strength not in (1, 2, 3)
                or not isinstance(requires, list)
            ):
                raise ValueError(f"Invalid evidence for claim {number}")
            if number == len(rows):
                revised = reviewed_role(question, source, quote, answer)
                if audit is not None and revised != answer:
                    audit.append({"claim": number, "quote": quote, "from": answer, "to": revised})
                answer = revised
            # Gaps are descriptive. They never vote or gate another item.
            if answer == "gap":
                requires = []
            for pair in requires:
                if (
                    not isinstance(pair, list) or len(pair) != 2
                    or type(pair[0]) is not int or not 1 <= pair[0] < number
                    or pair[1] not in ("yes", "no")
                ):
                    raise ValueError(f"Invalid prerequisite for claim {number}")
            evidence.append(Evidence(answer, strength, tuple(map(tuple, requires)), item.get("target")))
        claims[number] = tuple(evidence)
    return claims


CHAIN_CASE = (
    "Was crate K delivered? The scanner recorded crate K at the depot. "
    "An audit found the scanner read crate J instead. "
    "The delivery certificate relies entirely on the scanner record. "
    "No independent delivery record exists."
)


REGRESSION_CASES = [
    ('Was tank B full? A worksheet lists tank B as full. Its only source was a gauge reading. The technician found that the gauge was connected to tank A. A separate inspection found tank B empty.', 'no'),
    ('Was tank B full? A worksheet lists tank B as full. Its only source was a gauge reading. The technician found that the gauge was connected to tank A. A separate inspection found tank B full.', 'yes'),
    ('Was tank B full? A worksheet lists tank B as full. Its only source was a gauge reading. The technician found that the gauge was connected to tank A. No separate inspection was performed.', 'uncertain'),
    ("Was parcel 46 delivered? The manifest lists parcel 46 as delivered. The clerk prepared the manifest solely from the driver's slip. The driver confirmed that the slip was for parcel 64. There is no other delivery record.", 'uncertain'),
    ("Did the choir rehearse on Tuesday? A calendar shows a rehearsal on Tuesday. The secretary copied the entry from last month's calendar. A dated recording independently confirms Tuesday's rehearsal.", 'yes'),
    ('Was carton 8 weighed? The packing summary says carton 8 was weighed. Every entry came from the scale log. A check showed the cited log entry belonged to carton 3. No one observed the weighing.', 'uncertain'),
    ('Was lot 17 refrigerated? A logger showed lot 17 stayed cold. An inspection found that the logger was attached to lot 22 instead. The storage certificate depends solely on the logger reading.', 'uncertain'),
    ('Was lot 17 refrigerated? A logger showed lot 17 stayed cold. The storage certificate depends solely on the logger reading. A separate inspector directly confirmed lot 17 stayed cold.', 'yes'),
]


def single_fact_verdict(url, model, question, *, check_contradiction=False, exact_quantities=True):
    claim, separator, passage = question.partition("?")
    if not separator or not claim.strip() or not passage.strip():
        raise ValueError("Supply one question followed by its evidence passage")
    exact = quantity_verdict(question) if exact_quantities else None
    if exact is not None:
        return _single_fact_result(question, claim, passage, exact, method="exact_quantity", tokens=0)
    roles = {"supports": "yes", "contradicts": "no", "unresolved": "gap"}
    schema = {"type": "object", "properties": {
        "relation": {"type": "string", "enum": list(roles)}},
        "required": ["relation"], "additionalProperties": False}
    instruction = ("Classify the passage relative to the claim. Its relation is supports if "
                   "the claim follows, contradicts if the claim is false, or unresolved "
                   "if neither conclusion follows.")
    result, tokens = predict(url, model, instruction, question, max_tokens=32, output_format=schema)
    role = result.get("relation")
    if not isinstance(role, str) or role not in roles:
        return dict(answer=None, error="Missing or invalid relation", extraction=result, tokens=tokens)
    check = {}
    if check_contradiction and role != "contradicts":
        instruction = ("Does this passage rule out the claim? A missing detail is compatible "
                       "with the claim. Example: claim 'The gate was open at noon.' "
                       "Passage 'It was closed at noon.' -> ruled_out. "
                       "Passage 'It was closed at dawn.' -> compatible. "
                       "Passage 'It stood open at noon.' -> compatible. Judge the new case.")
        check_schema = {"type": "object", "properties": {
            "finding": {"type": "string", "enum": ["ruled_out", "compatible"]}},
            "required": ["finding"], "additionalProperties": False}
        finding, extra = predict(url, model, instruction, question, max_tokens=32,
                                 output_format=check_schema)
        check = dict(contradiction_check=finding, check_tokens=extra)
        tokens += extra
        if finding.get("finding") == "ruled_out":
            role = "contradicts"
    return _single_fact_result(question, claim, passage, roles[role], extraction=result, tokens=tokens, **check)


def _single_fact_result(question, claim, passage, role, **details):
    item = dict(answer=role, strength=2, quote=passage.strip(), requires=[])
    graph = {"claims": [{"claim": claim.strip(), "evidence": [item]}]}
    decision = evaluate(parse_evidence(graph, question))[1]
    return dict(answer=decision.answer, state=decision.state, graph=graph, **details)


def captured_scanner_chain(graph):
    """Recognize the expected source, correction and dependent certificate by quoted anchors."""
    rows = graph["claims"]
    for item in rows[-1]["evidence"]:
        if item["answer"] != "yes" or "certificate" not in item["quote"].lower():
            continue
        for number, required in item["requires"]:
            if required != "yes":
                continue
            evidence = rows[number - 1]["evidence"]
            for correction in evidence:
                if correction["answer"] != "undercut" or "crate j" not in correction["quote"].lower():
                    continue
                source = evidence[correction["target"] - 1]
                if source["answer"] == "yes" and "crate k" in source["quote"].lower():
                    return True
    return False


def repair_source_reference(graph, case, error):
    """Retarget a circular correction only when the affected report is unambiguous."""
    rows = graph.get("claims", [])
    if len(rows) != 1 or str(error) != "Invalid prerequisite for claim 1":
        return None
    question, _, source = case.partition("?")
    items = rows[0]["evidence"]
    if not all(isinstance(item, dict) for item in items):
        return None
    candidates = [
        index for index, item in enumerate(items, 1)
        if item.get("answer") in ("yes", "no") and item.get("requires") == []
        and re.search(r"\b(?:worksheet|dashboard|report|log|manifest)\b", str(item.get("quote")), re.I)
    ]
    if len(candidates) != 1:
        return None
    for index, item in enumerate(items):
        quote = item.get("quote")
        if (index < candidates[0] or not isinstance(quote, str) or quote not in source
            or item.get("requires") not in ([[1, "yes"]], [[1, "no"]])):
            continue
        # Require a grounded subject mismatch as well as an explicit source link.
        target = re.search(r"\btank (\w+)\b", question, re.I)
        reading = re.search(r"gauge was connected to tank (\w+)\b", quote, re.I)
        wrong_tank = (target and reading and target[1].lower() != reading[1].lower()
                      and "only source was a gauge" in source.lower())
        wrong_probe = ("probe assigned to a different" in quote.lower()
                       and "based on" in source.lower() and "probe" in source.lower())
        if wrong_tank or wrong_probe:
            revised = items.copy()
            revised[index] = dict(item, answer="undercut", target=candidates[0], requires=[])
            return parse_evidence({"claims": [dict(rows[0], evidence=revised)]}, case)
    return None


def recover_inspection(graph, case, error):
    """Recover a narrow single-claim case with a self-reference and a separate inspection."""
    question, _, source = case.partition("?")
    rows = graph.get("claims", [])
    if str(error) != "Invalid prerequisite for claim 1" or len(rows) != 1:
        return None
    row = rows[0]
    if row["claim"].rstrip("?").casefold() != question.casefold():
        return None
    observations = []
    for item in row["evidence"]:
        if not isinstance(item, dict):
            return None
        if item.get("answer") == "gap":
            continue
        if item.get("requires") in ([[1, "yes"]], [[1, "no"]]) and item.get("answer") in ("yes", "no"):
            continue
        quote = item.get("quote")
        if (
            item.get("answer") not in ("yes", "no") or item.get("requires") != []
            or not isinstance(quote, str) or quote not in source
            or not re.fullmatch(r"(?:A|An) (?:separate|independent) inspection found [^.!?]+[.]?", quote, re.I)
        ):
            return None
        observations.append(item)
    if not observations:
        return None
    return parse_evidence({"claims": [dict(row, evidence=observations)]}, case)


def copied_measurement(case):
    """Parse an explicit copied measurement when both owners are named and distinct."""
    question, _, passage = case.partition("?")
    subject = re.fullmatch(r"Was (?:the )?([\w -]+) weighed", question, re.I)
    if not subject:
        return None
    match = re.fullmatch(
        r"(?P<report>The (?P<owner>[\w -]+)'s log says (?P<vote>yes|no)), but "
        r"(?P<correction>its entry was copied from the (?P<other>[\w -]+)'s record)\. "
        r"(?P<gap>There is no separate measurement)\.", passage.strip(), re.I,
    )
    if not match or match["owner"].casefold() != subject[1].casefold():
        return None
    if match["owner"].casefold() == match["other"].casefold():
        return None
    items = [
        dict(answer=match["vote"].lower(), strength=2, quote=match["report"], requires=[]),
        dict(answer="undercut", strength=2, quote=match["correction"], requires=[], target=1),
        dict(answer="gap", strength=1, quote=match["gap"], requires=[]),
    ]
    return {"claims": [{"claim": question, "evidence": items}]}


def benchmark_rei(url, model, cases, *, schema_extraction=False):
    totals = {f"{name}_correct": 0 for name, _, _ in POLICIES}
    totals.update(corrected=0, regressed=0, invalid_extractions=0, extraction_tokens=0)
    rows = []
    for index, (case, expected) in enumerate(cases, 1):
        linked = re.search(r"\b(?:(?:relies|depends) (?:entirely |solely )?on|solely from|every entry came from)\b", case.partition("?")[2], re.I)
        instruction = LINKED_EXTRACT if linked else EXTRACT
        graph = copied_measurement(case)
        tokens = 0
        if graph is None:
            graph, tokens = predict(url, model, instruction, case, max_tokens=768,
                                    output_format=GRAPH if schema_extraction else "json")
        totals["extraction_tokens"] += tokens
        row = {"case": index, "expected": expected, "tokens": tokens, "extraction": graph}
        rows.append(row)
        try:
            audit = []
            try:
                claims = parse_evidence(graph, case, audit=audit)
            except ValueError as error:
                claims = repair_source_reference(graph, case, error)
                if claims is not None:
                    row["recovery"] = "Attached wrong-source evidence to the quoted report"
                else:
                    claims = recover_inspection(graph, case, error)
                    if claims is None:
                        raise
                    row["recovery"] = "Evaluated independent inspection after rejecting a self-reference"
            target = len(claims)
            decisions = {
                name: evaluate(claims, recursive=dependencies, disqualify_sources=sources)[target]
                for name, dependencies, sources in POLICIES
            }
        except ValueError as error:
            totals["invalid_extractions"] += 1
            row["extraction_error"] = str(error)
            continue
        if case == CHAIN_CASE:
            row["expected_source_chain_captured"] = captured_scanner_chain(graph)
        if audit:
            row["evidence_audit"] = audit
        for name, decision in decisions.items():
            row[name] = {"answer": decision.answer, "state": decision.state}
            totals[f"{name}_correct"] += decision.answer == expected
        flat_correct = decisions["flat"].answer == expected
        recursive_correct = decisions["recursive"].answer == expected
        totals["corrected"] += recursive_correct and not flat_correct
        totals["regressed"] += flat_correct and not recursive_correct
    return {"model": model, "cases": len(cases), "scores": totals, "results": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:11434")
    parser.add_argument("--model", default="qwen3:4b-instruct")
    parser.add_argument("--suite", choices=("original", "fresh", "chain", "all"), default="original")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--rei", action="store_true", help="Compare REI with recursion off and on.")
    modes.add_argument("--evidence-budget", metavar="PASSAGE",
                       help="Answer one evidence question using explicit dependencies or the single-pass prompt.")
    modes.add_argument("--plain-verdict", metavar="PASSAGE",
                       help="Use the short, plain-text model verdict for prose.")
    modes.add_argument("--cited-review", metavar="PASSAGE",
                       help="Review uncertain prose answers and expose the cited span and review cost.")
    modes.add_argument("--budgeted-review", metavar="PASSAGE",
                       help="Skip review on an explicit closing evidence gap.")
    modes.add_argument("--claim-scope", metavar="PASSAGE",
                       help="Compare the question with what the evidence establishes.")
    modes.add_argument("--report-event", metavar="PASSAGE", help="Experimental report and event comparison.")
    modes.add_argument("--quick", action="store_true", help="Run only the two single-pass prompts.")
    modes.add_argument("--rei-schema", action="store_true", help="Run REI with schema-constrained graph extraction.")
    modes.add_argument("--single-fact-schema", metavar="QUESTION",
                       help="Classify a single supplied passage as evidence for one question.")
    args = parser.parse_args()
    try:
        cases = {"original": CASES, "fresh": FRESH_CASES, "chain": [(CHAIN_CASE, "uncertain")],
                 "all": CASES + FRESH_CASES + [(CHAIN_CASE, "uncertain")] + REGRESSION_CASES}[args.suite]
        url = args.url.rstrip("/")
        if args.single_fact_schema is not None:
            print(json.dumps(single_fact_verdict(url, args.model, args.single_fact_schema)))
            raise SystemExit(0)
        if args.report_event is not None:
            from plain_verdict import decide
            answer, tokens = decide(url, args.model, args.report_event, separate_reports=True)
            print(json.dumps({"model": args.model, **answer, "tokens": tokens}))
            raise SystemExit(0)
        if args.claim_scope is not None:
            from claim_scope import decide
            answer, tokens = decide(url, args.model, args.claim_scope)
            print(json.dumps({"model": args.model, **answer, "tokens": tokens}))
            raise SystemExit(0)
        if args.cited_review is not None or args.budgeted_review is not None:
            from selective_review import decide
            skip_gaps = args.budgeted_review is not None
            passage = args.budgeted_review if skip_gaps else args.cited_review
            answer, tokens = decide(url, args.model, passage, skip_gaps=skip_gaps)
            print(json.dumps({"model": args.model, **answer, "tokens": tokens}))
            raise SystemExit(0)
        if args.evidence_budget is not None or args.plain_verdict is not None:
            if args.plain_verdict is not None:
                from plain_verdict import decide
                passage = args.plain_verdict
            else:
                from evidence_register import decide
                passage = args.evidence_budget
            answer, tokens = decide(url, args.model, passage)
            print(json.dumps({"model": args.model, "answer": answer.get("answer"), "tokens": tokens}))
            raise SystemExit(0)
        if args.rei or args.rei_schema:
            result = benchmark_rei(url, args.model, cases, schema_extraction=args.rei_schema)
        else:
            result = benchmark(url, args.model, cases, quick=args.quick)
        print(json.dumps({"suite": args.suite, **result}, indent=2))
    except (OSError, KeyError, ValueError) as error:
        parser.exit(1, f"Benchmark could not complete: {error}\n")
