"""Public synthetic probe of evidence assessment under swapped priorities."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json

from rei0.local_ai import LocalAIError, LocalOllamaModel, StandaloneREI
from research.standalone_eval.paired_quality import mode_order


@dataclass(frozen=True)
class Case:
    name: str
    evidence: str
    claim: str
    priorities: tuple[str, str]
    expected_evidence: str
    expected_recommendations: tuple[str, str]
    expected_references: tuple[int, ...]


CASES = (
    Case(
        "downtown-access",
        "A randomized pilot compared two designs. A closes the entire street and "
        "prevented 12 pedestrian injuries while retaining 60% of accessible drop-off "
        "points. B closes half the street and prevented 5 injuries while retaining "
        "all accessible drop-off points. The pilot did not measure retail revenue.",
        "The pilot establishes that A increases retail revenue.",
        ("Choose the option that prevented the most injuries.",
         "Choose the option that preserves the most accessible drop-off points."),
        "unknown", ("A", "B"), (4,),
    ),
    Case(
        "library-hours",
        "A randomized pilot compared two schedules at equal cost. A adds morning "
        "hours and was used by 80 older adults and 30 school-age visitors. B adds "
        "evening hours and was used by 40 older adults and 100 school-age visitors. "
        "The pilot found no difference in total program attendance.",
        "More school-age visitors used B than A during the pilot.",
        ("Choose the option used by the most school-age visitors.",
         "Choose the option used by the most older adults."),
        "supported", ("B", "A"), (2, 3),
    ),
    Case(
        "bus-service",
        "A pilot compared two designs. A adds one express route and shortened the "
        "median commute by 8 minutes. B adds more stops and shortened it by 3 minutes. "
        "Neither arm measured travel times for wheelchair users separately.",
        "B shortened the median commute more than A in the pilot.",
        ("Choose the option that shortened the median commute the most.",
         "Choose whichever shortened trips for wheelchair users more. Defer if "
         "the evidence cannot determine which option meets that priority."),
        "contradicted", ("A", "defer"), (2, 3),
    ),
)


CHALLENGE_CASES = (
    Case(
        "conflicting-drainage-studies",
        "Two equally applicable drainage pilots reported runoff relative to baseline. "
        "Pilot 1 found design A reduced runoff by 9% and B by 2%. "
        "Pilot 2 found design A increased runoff by 5% and B reduced runoff by 2%. "
        "A costs 40 credits and B costs 60 credits.",
        "Across the two pilots, the direction of design A's effect on runoff is settled.",
        ("Choose the cheaper design.",
         "Choose the design that reduced runoff in both pilots."),
        "contradicted", ("A", "B"), (2, 3),
    ),
    Case(
        "warehouse-total",
        "Shift 1 recorded 26 completed orders for A and 18 for B. "
        "Shift 2 recorded 13 completed orders for A and 24 for B. "
        "The trial recorded 2 labeling errors for A and 5 for B.",
        "Across both shifts, B completed more orders than A.",
        ("Choose the design with more completed orders across both shifts.",
         "Choose the design with fewer labeling errors."),
        "supported", ("B", "A"), (1, 2),
    ),
    Case(
        "conflicting-insulation-studies",
        "Two equally applicable trials measured winter electricity savings. "
        "Trial 1 found that A saved 12% and B saved 4%. "
        "Trial 2 found that A increased use by 3% and B saved 4%. "
        "Neither trial measured summer electricity use.",
        "Design A reduces winter electricity use in the target buildings.",
        ("Choose the design with winter savings in both trials.",
         "Choose the better design for summer electricity use. Defer if the evidence cannot tell."),
        "unknown", ("B", "defer"), (2, 3),
    ),
)


def prompt(case: Case, side: int) -> str:
    return (
        "For this hypothetical decision, use only the given pilot results. "
        "Assess the specific claim and recommend an option under the stated priority.\n\n"
        f"Pilot results: {case.evidence}\nClaim: {case.claim}\n"
        f"Decision priority: {case.priorities[side]}\n\n"
        'Return only a JSON object with two fields: "evidence" (supported, contradicted, '
        'or unknown) and "recommendation" (A, B, or defer).'
    )


def parse_answer(answer: str) -> dict[str, str] | None:
    try:
        parsed = json.loads(answer)
    except json.JSONDecodeError:
        return None
    if (
        not isinstance(parsed, dict)
        or set(parsed) != {"evidence", "recommendation"}
        or parsed["evidence"] not in ("supported", "contradicted", "unknown")
        or parsed["recommendation"] not in ("A", "B", "defer")
    ):
        return None
    return parsed


def run_turn(agent: StandaloneREI, question: str, mode: str, *, guided: bool = False) -> dict:
    try:
        response = agent.answer(
            [{"role": "user", "content": question}],
            mode=mode, ideological_understanding=guided,
        )
    except LocalAIError as exc:
        return {"answer": "", "error": type(exc).__name__,
                "model_calls": None, "model_reported_tokens": None}
    return {"answer": response["answer"], "error": None,
            "model_calls": response["audit"]["model_calls"],
            "model_reported_tokens": response["audit"]["model_reported_tokens"]}


def grade_side(case: Case, side: int, turn: dict, parsed: dict | None) -> dict:
    return {
        **turn,
        "parsed": parsed,
        "evidence_correct": parsed is not None and parsed["evidence"] == case.expected_evidence,
        "recommendation_correct": parsed is not None
        and parsed["recommendation"] == case.expected_recommendations[side],
    }


def grade_pair(case: Case, mode: str, guidance: str, sides: list[dict]) -> dict:
    first, second = (side["parsed"] for side in sides)
    same_evidence = (
        first is not None and second is not None
        and first["evidence"] == second["evidence"]
    )
    return {
        "case": case.name,
        "mode": mode,
        "guidance": guidance,
        "same_evidence": same_evidence,
        "passed": same_evidence and all(
            side["evidence_correct"] and side["recommendation_correct"] for side in sides
        ),
        "sides": sides,
    }


def run_pair(agent: StandaloneREI, case: Case, mode: str, *, guided: bool) -> dict:
    sides = []
    for side in range(len(case.priorities)):
        turn = run_turn(agent, prompt(case, side), mode, guided=guided)
        sides.append(grade_side(case, side, turn, parse_answer(turn["answer"])))
    return grade_pair(case, mode, "guided" if guided else "baseline", sides)


VERDICTS = ("supported", "contradicted", "unknown")


def assess_evidence(agent: StandaloneREI, case: Case, mode: str) -> dict:
    evidence = run_turn(
        agent,
        "Assess only what the hypothetical pilot results establish about the claim. "
        "Use supported if the pilot establishes it, contradicted if the pilot shows "
        "the opposite, or unknown if it does not resolve the claim. "
        "An outcome the pilot did not measure is unknown. Reply with just one label.\n\n"
        f"Pilot results: {case.evidence}\nClaim: {case.claim}",
        mode,
    )
    verdict = evidence["answer"].strip().lower()
    return {**evidence, "verdict": verdict if verdict in VERDICTS else None}


def screen_evidence(agent: StandaloneREI, case: Case) -> dict:
    passages = case.evidence.split(". ")
    numbered = "\n".join(f"{index}. {passage}" for index, passage in enumerate(passages, 1))
    turn = run_turn(
        agent,
        "Judge the claim using the numbered results. Use supported if established, "
        "contradicted if the opposite is shown, unknown if the outcome was not measured, "
        "or review if the relevant results conflict or are ambiguous. Cite every "
        "number needed for the verdict. Reply with JSON only, for example "
        '{"verdict":"supported","refs":[1,2]}. Use [] for review.\n\n'
        f"Results:\n{numbered}\nClaim: {case.claim}",
        "direct",
    )
    try:
        parsed = json.loads(turn["answer"])
    except json.JSONDecodeError:
        parsed = None
    verdict = None
    references = []
    if isinstance(parsed, dict) and set(parsed) == {"verdict", "refs"}:
        refs = parsed["refs"]
        if (parsed["verdict"] in VERDICTS and isinstance(refs, list) and refs
                and all(type(ref) is int and 1 <= ref <= len(passages) for ref in refs)
                and len(refs) == len(set(refs))):
            verdict = parsed["verdict"]
            references = refs
    return {**turn, "verdict": verdict, "references": references,
            "references_correct": verdict is not None
            and set(references) == set(case.expected_references)}



def check_effect_passages(agent: StandaloneREI, claim: str,
                          passages: list[str]) -> dict:
    """Experimental check for a directional effect claim across comparable studies.

    Callers supply the comparable study results explicitly. Agreement claims and
    pooled totals need their own aggregation rule.
    """
    if not passages or len(passages) > 8:
        raise ValueError("supply 1-8 comparable study passages")
    turns = []
    for passage in passages:
        turn = run_turn(
            agent,
            "Judge this single study against the directional effect claim. Reply "
            "with supports if its measured direction matches, opposes if opposite, "
            "irrelevant if it does not measure that effect, or unclear if ambiguous. "
            "Return only that one word.\n"
            f"Claim: {claim}\nStudy: {passage}",
            "direct",
        )
        turn["relation"] = turn["answer"].strip().lower()
        turns.append(turn)
    relations = {turn["relation"] for turn in turns}
    valid = {"supports", "opposes", "irrelevant", "unclear"}
    verdict = "unknown"
    if relations <= valid and "unclear" not in relations:
        if "supports" in relations and "opposes" not in relations:
            verdict = "supported"
        elif "opposes" in relations and "supports" not in relations:
            verdict = "contradicted"
    return {
        "verdict": verdict,
        "conflict": {"supports", "opposes"} <= relations,
        "valid": relations <= valid and all(turn["error"] is None for turn in turns),
        "model_calls": sum(turn["model_calls"] or 0 for turn in turns),
        "model_reported_tokens": sum(turn["model_reported_tokens"] or 0 for turn in turns),
        "passages": turns,
    }



def compact_decision(agent: StandaloneREI, case: Case, priority: str) -> dict:
    turn = run_turn(
        agent,
        "Compare A and B only on the requested criterion. Extract the relevant "
        "outcome for each option before choosing. Higher or lower depends on the "
        "criterion. For totals, add all shifts. A benefit in both trials requires "
        "a benefit in each trial; increased use is not savings. If the requested "
        "outcome is unmeasured, defer. Return valid JSON with exactly A, B, choice. "
        "A and B must be strings describing the relevant outcomes. "
        "choice must be A, B, or defer.\nResults: "
        + case.evidence + "\nCriterion: " + priority,
        "direct",
    )
    try:
        result = json.loads(turn["answer"])
    except json.JSONDecodeError:
        result = None
    choice = None
    if (isinstance(result, dict) and set(result) == {"A", "B", "choice"}
            and isinstance(result["A"], str) and result["A"].strip()
            and isinstance(result["B"], str) and result["B"].strip()
            and result["choice"] in ("A", "B", "defer")):
        choice = result["choice"]
    return {**turn, "choice": choice}



def run_staged_pair(agent: StandaloneREI, case: Case, evidence_mode: str, *,
                    adaptive: bool = False, compact: bool = False) -> dict:
    screen = screen_evidence(agent, case) if adaptive else None
    expanded = screen is not None and screen["verdict"] is None
    evidence = (
        assess_evidence(agent, case, evidence_mode)
        if screen is None or expanded else screen
    )
    verdict = evidence["verdict"]

    sides = []
    for side, priority in enumerate(case.priorities):
        if verdict is None:
            turn = {"answer": "", "error": "evidence_stage_failed",
                    "model_calls": 0, "model_reported_tokens": 0}
            parsed = None
        elif compact:
            turn = compact_decision(agent, case, priority)
            parsed = ({"evidence": verdict, "recommendation": turn["choice"]}
                      if turn["choice"] is not None else None)
        else:
            turn = run_turn(
                agent,
                "Use the hypothetical pilot results to make a recommendation under the "
                "stated priority. Choose defer if the pilot cannot distinguish the options "
                "under that priority. Reply with just A, B, or defer.\n\n"
                f"Pilot results: {case.evidence}\nClaim: {case.claim}\n"
                f"Recorded claim assessment: {verdict}\nDecision priority: {priority}",
                "direct",
            )
            recommendation = turn["answer"].strip()
            parsed = ({"evidence": verdict, "recommendation": recommendation}
                      if recommendation in ("A", "B", "defer") else None)
        graded = grade_side(case, side, turn, parsed)
        graded["evidence_correct"] = verdict == case.expected_evidence
        sides.append(graded)

    pair = grade_pair(case, evidence_mode, "adaptive" if adaptive else "staged", sides)
    if compact:
        pair["guidance"] += "_compact"
    if screen is not None:
        pair["expanded"] = expanded
    if expanded:
        pair["screen"] = screen
    pair["same_evidence"] = verdict is not None
    pair["evidence_stage"] = {
        **evidence, "verdict": verdict, "correct": verdict == case.expected_evidence,
    }
    return pair


def run_probe(agent: StandaloneREI, *, compare_guidance: bool = False,
              compare_staged: bool = False, compare_adaptive: bool = False,
              cases: tuple[Case, ...] = CASES) -> list[dict]:
    results = []
    for index, case in enumerate(cases):
        if compare_adaptive:
            arms = (("direct", False), ("rei", False), ("rei", True))
            offset = index % len(arms)
            for mode, adaptive in arms[offset:] + arms[:offset]:
                results.append(run_staged_pair(agent, case, mode, adaptive=adaptive))
            continue
        for mode in mode_order(index):
            first_guided = (index % 2 == 0) == (mode == "rei")
            treatments = (first_guided, not first_guided) if compare_guidance else (False,)
            for guided in treatments:
                results.append(run_pair(agent, case, mode, guided=guided))
            if compare_staged:
                results.append(run_staged_pair(agent, case, mode))
    return results


def summarize(results: list[dict], *, cases: tuple[Case, ...] = CASES) -> dict:
    summary = {}
    cases_by_name = {case.name: case for case in cases}
    for pair in results:
        counts = summary.setdefault(pair["mode"], {}).setdefault(pair["guidance"], {
            "pairs": 0,
            "pairs_passed": 0,
            "pairs_with_consistent_evidence": 0,
            "correct_evidence_answers": 0,
            "correct_recommendations": 0,
            "invalid_answers": 0,
            "runtime_errors": 0,
            "known_model_calls": 0,
            "known_model_reported_tokens": 0,
            "expected_deferrals": 0,
            "correct_deferrals": 0,
        })
        counts["pairs"] += 1
        counts["pairs_passed"] += int(pair["passed"])
        counts["pairs_with_consistent_evidence"] += int(pair["same_evidence"])
        if "expanded" in pair:
            counts["expanded_pairs"] = counts.get("expanded_pairs", 0) + int(pair["expanded"])
        if "screen" in pair:
            screen = pair["screen"]
            counts["runtime_errors"] += int(screen["error"] is not None)
            counts["known_model_calls"] += screen["model_calls"] or 0
            counts["known_model_reported_tokens"] += screen["model_reported_tokens"] or 0
        if "evidence_stage" in pair:
            evidence = pair["evidence_stage"]
            counts["correct_shared_verdicts"] = counts.get("correct_shared_verdicts", 0) + int(
                evidence["correct"]
            )
            counts["invalid_evidence_verdicts"] = counts.get("invalid_evidence_verdicts", 0) + int(
                evidence["verdict"] is None
            )
            counts["runtime_errors"] += int(evidence["error"] is not None)
            counts["known_model_calls"] += evidence["model_calls"] or 0
            counts["known_model_reported_tokens"] += evidence["model_reported_tokens"] or 0
        case = cases_by_name[pair["case"]]
        for side, expected in zip(pair["sides"], case.expected_recommendations):
            counts["known_model_calls"] += side["model_calls"] or 0
            counts["known_model_reported_tokens"] += side["model_reported_tokens"] or 0
            counts["expected_deferrals"] += int(expected == "defer")
            counts["correct_deferrals"] += int(expected == "defer" and side["recommendation_correct"])
            counts["correct_evidence_answers"] += int(side["evidence_correct"])
            counts["correct_recommendations"] += int(side["recommendation_correct"])
            counts["invalid_answers"] += int(side["parsed"] is None and side["error"] is None)
            counts["runtime_errors"] += int(
                side["error"] is not None and side["error"] != "evidence_stage_failed"
            )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="qwen3:4b-instruct")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--compare-adaptive", action="store_true",
                            help="Compare staged Qwen, staged REI, and adaptive REI")
    parser.add_argument("--compare-guidance", action="store_true",
                        help="Compare the runtime with ideological understanding off and on")
    parser.add_argument("--compare-staged", action="store_true",
                        help="Add Qwen and REI arms with a shared, priority-blind verdict")
    parser.add_argument("--challenge-cases", action="store_true",
                        help="Use fresh cases with conflicting or distributed evidence")
    args = parser.parse_args()
    cases = CHALLENGE_CASES if args.challenge_cases else CASES
    if args.compare_adaptive and (args.compare_guidance or args.compare_staged):
        parser.error("--compare-adaptive is a standalone comparison")
    try:
        status = LocalOllamaModel(model=args.model, endpoint=args.ollama_url).doctor()
    except LocalAIError as exc:
        parser.exit(2, f"Ollama preflight failed: {exc}\n")
    if not status["model_downloaded"]:
        parser.exit(2, f"Ollama model unavailable: {args.model}\n")
    results = run_probe(
        StandaloneREI(model=args.model, endpoint=args.ollama_url),
        compare_guidance=args.compare_guidance,
        compare_staged=args.compare_staged,
        compare_adaptive=args.compare_adaptive,
        cases=cases,
    )
    print(json.dumps({
        "provider": "ollama_live",
        "model": args.model,
        "case_set": "challenge" if args.challenge_cases else "development",
        "summary": summarize(results, cases=cases),
        "notes": [
            "Public development cases. Calls and tokens are recorded but not matched.",
            "Staged arms share one verdict per pair, so consistency follows from the design.",
            "Adaptive screening validates reference IDs; reference correctness is graded separately.",
            "Usage is the sum of known prompt and completion tokens; failed calls may lack usage.",
        ],
        "pairs": results,
    }, indent=2))
    return int(not all(pair["passed"] for pair in results))


if __name__ == "__main__":
    raise SystemExit(main())
