"""Challenge 11: active investigation under a fixed, hidden-outcome probe budget.

Pure probability/decision logic. No model, external evidence authority or
truth labels are needed to evaluate expected Bayes risk. Binary latent world,
conditionally independent noisy binary tests, known synthetic likelihoods,
equal cost per probe. These assumptions are explicitly artificial.

The exact two-step lookahead planner is a conventional Bayesian algorithm:
using it inside REI does NOT by itself demonstrate novel AI intelligence.
The correct strong baseline is that same optimal algorithm.
"""
from __future__ import annotations

from dataclasses import dataclass
import functools
import math
import random
from typing import Any

from rei0.models import digest

SCHEMA = "rei.challenge11.active_investigation.v1"
SEED = 20261112
PROBES_PER_CASE = 4
BUDGET = 2
EPS = 1e-12


class InvestigationError(ValueError):
    pass


@dataclass(frozen=True)
class Probe:
    id: str
    sensitivity: float
    false_positive: float

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id.strip():
            raise InvestigationError("probe ID must be nonblank")
        for value in (self.sensitivity, self.false_positive):
            if type(value) not in (float, int) or not math.isfinite(value) or not 0 < value < 1:
                raise InvestigationError("likelihoods must be strictly between 0 and 1")
        if self.sensitivity <= self.false_positive:
            raise InvestigationError("this synthetic protocol requires positively informative probes")

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "sensitivity": self.sensitivity,
                "false_positive": self.false_positive}


@dataclass(frozen=True)
class Scenario:
    id: str
    prior: float
    probes: tuple[Probe, ...]
    # Private test harness fields: NEVER place in a model-visible context.
    truth: bool
    outcomes: tuple[tuple[str, bool], ...]

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id.strip():
            raise InvestigationError("scenario needs ID")
        if type(self.prior) not in (float, int) or not 0 < self.prior < 1:
            raise InvestigationError("prior must be strictly inside (0,1)")
        if type(self.truth) is not bool or type(self.probes) is not tuple:
            raise InvestigationError("invalid private scenario")
        if len(self.probes) != PROBES_PER_CASE:
            raise InvestigationError("four probes required")
        ids = tuple(p.id for p in self.probes)
        if len(set(ids)) != len(ids) or set(dict(self.outcomes)) != set(ids):
            raise InvestigationError("outcome keys must exactly match unique probe IDs")
        if any(type(v) is not bool for _, v in self.outcomes):
            raise InvestigationError("probe outcomes must be bool")

    def public(self, posterior: float | None = None,
               remaining: tuple[Probe, ...] | None = None,
               observations: tuple[dict, ...] = ()) -> dict:
        """A model-safe choice interface; no hidden truth, seed or unobserved draws."""
        return {
            "question": "Which test should we run next to minimize expected binary decision error?",
            "hypotheses": ["H0", "H1"],
            "prior_probability_H1": self.prior,
            "current_probability_H1": self.prior if posterior is None else posterior,
            "remaining_probe_budget": BUDGET - len(observations),
            "available_probes": [p.to_dict() for p in (remaining if remaining is not None else self.probes)],
            "observations": list(observations),
            "assumptions": ("Synthetic known likelihoods; tests independent conditional "
                            "on hidden H; one probe costs one unit; wrong H0/H1 decisions "
                            "cost 1 and correct decisions cost 0."),
        }


def bayes_risk(p: float) -> float:
    if not 0 <= p <= 1:
        raise InvestigationError("posterior outside [0,1]")
    return min(p, 1-p)


def prob_positive(p: float, probe: Probe) -> float:
    return p*probe.sensitivity + (1-p)*probe.false_positive


def update(p: float, probe: Probe, positive: bool) -> float:
    if type(positive) is not bool:
        raise InvestigationError("probe result must be bool")
    q = prob_positive(p, probe)
    n = p*probe.sensitivity if positive else p*(1-probe.sensitivity)
    d = q if positive else (1-q)
    if d <= 0:
        raise InvestigationError("impossible probe observation")
    return n/d


def test_value(p: float, probe: Probe, remaining: tuple[Probe, ...],
               after_this: int, *, lookahead: bool) -> float:
    """Expected *final Bayes error* after selecting this probe."""
    rest = tuple(other for other in remaining if other.id != probe.id)
    q = prob_positive(p, probe)
    if lookahead:
        return (q*optimal_risk(update(p,probe,True),rest,after_this) +
                (1-q)*optimal_risk(update(p,probe,False),rest,after_this))
    return (q*bayes_risk(update(p,probe,True)) +
            (1-q)*bayes_risk(update(p,probe,False)))


@functools.lru_cache(maxsize=250000)
def optimal_risk(p: float, remaining: tuple[Probe, ...], budget: int) -> float:
    """Exact risk-optimal adaptive dynamic program (a strong conventional control)."""
    if not isinstance(remaining, tuple) or type(budget) is not int or budget < 0:
        raise InvestigationError("invalid planner inputs")
    best = bayes_risk(p)
    if budget == 0 or not remaining:
        return best
    for probe in remaining:
        best = min(best, test_value(p,probe,remaining,budget-1,lookahead=True))
    return best


def select(p: float, remaining: tuple[Probe, ...], budget: int, *,
           policy: str = "recursive_voi") -> tuple[str | None, dict[str, float]]:
    """Select among current tests, OR stop if no expected Bayes-risk gain.

    recursive_voi uses exact two-step lookahead; greedy_voi only immediate
    risk reduction. Both have the same test access and budget. They never
    read latent truth or unrevealed measurements.
    """
    if policy not in ("recursive_voi", "greedy_voi") or type(budget) is not int or budget < 0:
        raise InvestigationError("unrecognized policy or invalid budget")
    if not remaining or budget == 0:
        return None, {}
    lookahead = policy == "recursive_voi"
    offers = {probe.id: test_value(p,probe,remaining,budget-1,lookahead=lookahead)
              for probe in remaining}
    winner = min(offers, key=lambda x:(offers[x],x))
    if offers[winner] >= bayes_risk(p)-EPS:
        return None, offers
    return winner, offers


def policy_risk(p: float, remaining: tuple[Probe, ...], budget: int, *,
                policy: str) -> float:
    """Exact expected error for the selected contingent policy (no Monte Carlo)."""
    choice, _ = select(p,remaining,budget,policy=policy)
    if choice is None:
        return bayes_risk(p)
    probe = next(x for x in remaining if x.id == choice)
    rest = tuple(x for x in remaining if x.id != choice)
    q = prob_positive(p,probe)
    return (
        q*policy_risk(update(p,probe,True),rest,budget-1,policy=policy) +
        (1-q)*policy_risk(update(p,probe,False),rest,budget-1,policy=policy)
    )


def generate(seed: int = SEED, count: int = 24) -> tuple[Scenario, ...]:
    """Publish deterministic development cases, never use these as a blind holdout.

    Likelihood combinations include hard decision-boundary problems where
    greedy value-of-information may be worse than a two-step plan.
    """
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise InvestigationError("seed must be a 32-bit nonnegative integer")
    if type(count) is not int or not 4 <= count <= 200 or count % 4:
        raise InvestigationError("count must be a multiple of four, 4-200")
    rng = random.Random(seed)
    pool = (
        (.95,.45), (.60,.05), (.85,.15), (.70,.30), (.65,.20),
        (.95,.65), (.35,.03), (.90,.50), (.55,.10), (.80,.40), (.50,.08),
    )
    result = []
    for i in range(count):
        prior = (.27,.39,.61,.73)[i % 4]
        picked = rng.sample(pool,PROBES_PER_CASE)
        rng.shuffle(picked)
        probes = tuple(Probe(name,*rates) for name,rates in zip(("A","B","C","D"),picked))
        truth = rng.random() < prior
        observations = tuple((probe.id,
                              rng.random() < (probe.sensitivity if truth else probe.false_positive))
                             for probe in probes)
        result.append(Scenario(f"c11-{i+1:03d}",prior,probes,truth,observations))
    return tuple(result)


def public_digest(cases: tuple[Scenario, ...]) -> str:
    """Digest only public problem parameters; no outcome or answer-key leakage."""
    return digest([{"id":case.id, "prior":case.prior,
                    "probes":[p.to_dict() for p in case.probes]} for case in cases])


def choice_table(p: float, remaining: tuple[Probe, ...], budget: int) -> list[dict]:
    """Identical numeric-tool access for REI and conventional model baseline."""
    if budget <= 0:
        return []
    return [
        {
            **probe.to_dict(),
            "immediate_expected_error": round(test_value(
                p,probe,remaining,0,lookahead=False),8),
            "exact_remaining_budget_expected_error": round(test_value(
                p,probe,remaining,budget-1,lookahead=True),8),
        }
        for probe in remaining
    ]
