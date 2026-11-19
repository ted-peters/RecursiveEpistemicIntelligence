"""Adaptive REI evidence engine. Run this file to compare decision policies."""
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Evidence:
    answer: str
    strength: int
    requires: tuple[tuple[int, str], ...] = ()
    target: int | None = None


@dataclass(frozen=True)
class Decision:
    answer: str
    state: str


POLICIES = (
    ("flat", False, False),
    ("source_only", False, True),
    ("dependency_only", True, False),
    ("recursive", True, True),
)


def evaluate(claims, *, recursive=True, disqualify_sources=None):
    """Resolve ordered, numbered claims from a snapshot of their evidence.

    Each claim lists yes/no evidence, gaps, or source undercuts.
    An undercut targets an earlier yes/no item in the same claim.
    Gaps record missing evidence without voting. Strength 1 is provisional.
    Strength 2 or 3 may substantiate an answer. Dependencies must refer to
    earlier claims. A prerequisite must itself be substantiated.
    """
    if disqualify_sources is None:
        disqualify_sources = recursive
    for number, evidence in claims.items():
        for position, item in enumerate(evidence, 1):
            if item.answer not in ("yes", "no", "gap", "undercut") or item.strength not in (1, 2, 3):
                raise ValueError(f"Invalid evidence for claim {number}")
            if item.answer == "undercut":
                if (
                    type(item.target) is not int or not 1 <= item.target < position
                    or evidence[item.target - 1].answer not in ("yes", "no")
                ):
                    raise ValueError(f"Invalid undercut target for claim {number}")
            elif item.target is not None:
                raise ValueError(f"Unexpected evidence target for claim {number}")
            for prerequisite, answer in item.requires:
                if prerequisite not in claims or prerequisite >= number or answer not in ("yes", "no"):
                    raise ValueError(f"Invalid prerequisite for claim {number}")

    @lru_cache(maxsize=None)
    def resolve(number):
        applicable = [
            (position, item) for position, item in enumerate(claims[number], 1)
            if not recursive or all(
                resolve(prerequisite) == Decision(answer, "substantiated")
                for prerequisite, answer in item.requires
            )
        ]
        disqualified = {
            item.target for _, item in applicable
            if disqualify_sources and item.answer == "undercut" and item.strength >= 2
        }
        eligible = [
            item for position, item in applicable
            if item.answer in ("yes", "no") and position not in disqualified
        ]
        if not eligible:
            return Decision("uncertain", "unsupported")
        strongest = max(item.strength for item in eligible)
        answers = {item.answer for item in eligible if item.strength == strongest}
        if len(answers) != 1 or strongest == 1:
            return Decision("uncertain", "provisional")
        return Decision(answers.pop(), "substantiated")

    return {number: resolve(number) for number in reversed(sorted(claims))}


def compare():
    yes, no = Evidence("yes", 2), Evidence("no", 2)
    report = Evidence("yes", 3, ((1, "yes"),))
    gap = Evidence("gap", 2)
    undercut = Evidence("undercut", 2, target=1)
    cases = [
        ("Direct observation", {1: (yes,)}, "yes"),
        ("Equal independent reports conflict", {1: (yes, no)}, "uncertain"),
        ("Weak evidence only", {1: (Evidence("yes", 1),)}, "uncertain"),
        ("No evidence", {1: ()}, "uncertain"),
        ("Missing causal comparison", {1: (gap,)}, "uncertain"),
        ("Missing timestamp alongside conflicting witnesses", {1: (yes, no, gap)}, "uncertain"),
        ("Copied record is disqualified", {1: (yes, undercut, gap)}, "uncertain"),
        ("Disqualifying one source leaves independent evidence intact",
         {1: (Evidence("yes", 3), no, undercut)}, "no"),
        ("Verified prerequisite", {1: (yes,), 2: (report,)}, "yes"),
        ("Report relies on a missing prerequisite", {1: (), 2: (report,)}, "uncertain"),
        ("Report relies on a provisional prerequisite",
         {1: (Evidence("yes", 1),), 2: (report,)}, "uncertain"),
        ("Report relies on a disproven prerequisite", {1: (no,), 2: (report, no)}, "no"),
        ("A broken prerequisite propagates through two links",
         {1: (no,), 2: (report,), 3: (Evidence("yes", 3, ((2, "yes"),)), no)}, "no"),
        ("Disputed premise has no bearing on separate evidence",
         {1: (yes, no), 2: (yes,)}, "yes"),
    ]
    totals = dict.fromkeys((name for name, _, _ in POLICIES), 0)
    for name, claims, expected in cases:
        target = max(claims)
        answers = {
            policy: evaluate(claims, recursive=dependencies, disqualify_sources=sources)[target].answer
            for policy, dependencies, sources in POLICIES
        }
        for policy, answer in answers.items():
            totals[policy] += answer == expected
        print(f"{name}: {answers}, expected={expected}")
    print(f"Correct out of {len(cases)}: {totals}")

    chain = {1: (yes,), 2: (report,), 3: (Evidence("yes", 3, ((2, "yes"),)), no)}
    before = evaluate(chain)[3]
    chain[1] = (yes, Evidence("no", 3))
    after = evaluate(chain)[3]
    print(f"After a stronger premise correction, claim 3: {before.answer} -> {after.answer}")


if __name__ == "__main__":
    compare()
