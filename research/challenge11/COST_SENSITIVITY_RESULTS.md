# Challenge 11C — When is another investigation worth its cost?

**Completed**: [1,000-case exact expected-cost study](https://github.com/ted-peters/RecursiveEpistemicIntelligence/actions/runs/43644968350)

This is a *pure mathematical software test*, not a language-model benchmark.
It uses five fixed public seeds (20261114–20261118), 200 independent
synthetic decision scenarios per seed, the same four test likelihoods and
two-test budget as Challenge 11, and four prices for administering one
measurement. Hidden outcomes are irrelevant here: all results are **exact
expected probabilities**, not Monte Carlo correctness.

The quantity optimized is:

    expected binary misclassification loss + c * expected probes used

where a wrong binary decision costs 1, a correct decision costs 0, and each
probe costs `c` units. Cost is **hypothetical**, not currency or actual Qwen
tokens. A two-step conventional Bellman dynamic program chooses the best
probe or stops. A cost-unaware recursive controller and greedy policy remain
unchanged. All policy evaluations use the same publicly defined prior and
synthetic independent test-likelihood assumptions.

## Audited results

| Cost per probe | Risk-only lookahead: expected error | Risk-only lookahead: expected probes | Cost-aware optimal: expected error | Cost-aware: expected probes | Risk-only total expected loss | Cost-aware total expected loss |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | .148217 | 1.729562 | .148217 | 1.729562 | .148217 | .148217 |
| .01 | .148217 | 1.729562 | .148531 | 1.637762 | .165513 | .164908 |
| .02 | .148217 | 1.729562 | .150596 | 1.492245 | .182808 | .180441 |
| .05 | .148217 | 1.729562 | .157276 | 1.295848 | .234695 | .222069 |

At `c=.05`, the cost-aware controller expects **~25.1% fewer probes**
than the cost-ignoring controller, while accepting a **0.91 percentage-point
increase** in expected error. Its combined error-plus-probe cost is lower
(.222069 versus .234695).

The first choice differs from the cost-unaware exact controller in **238,
346 and 448 of 1,000 scenarios** at cost .01, .02 and .05 respectively.
The strong conventional cost-aware controller is guaranteed by Bellman
recursion to have no larger expected *total* loss than any of the compared
fixed policies under its assumptions; this is a mathematical invariant, not
a learned REI achievement.

The source file is `research/challenge11/cost_sensitivity.py`,
tests are in `tests/test_challenge11_cost_sensitivity.py`. An earlier
regression found a Python memoization issue (Boolean `True` could collide
with numeric `1`); validation now runs before the cached function. The
final CI job and full report replay succeeded, and the result was archived
as `challenge11-cost-aware-1000-case-frontier`.

Reproduction:

```bash
python -m pip install .
python -m unittest discover -s tests -p test_challenge11_cost_sensitivity.py -v
python -m research.challenge11.cost_sensitivity --output frontier.json
python -m research.challenge11.cost_sensitivity --verify-only --output frontier.json
```

## Interpretation

The meaningful engineering guidance is to include *the price of information*
in the stopping rule. REI must not recurse merely because more investigation
could reduce error a little; the expected benefit must outweigh real tool,
latency, reviewer and inference costs. That principle also applies to
conventional AI systems. These numerical savings cannot be translated into
dollar savings or model token savings without measured real task costs and
calibrated evidence likelihoods.

A separate, independently preregistered **12-case real Qwen3 4B probe-choice
study**, seed 20261114, was launched in the isolated one-shot GitHub Actions
branch. That experiment compares real model-selected probes against the same
conventional exact Bayesian reference, not against a weaker baseline deprived
of numeric planning tools. Its live results are separate from this 1,000-case
mathematical study.
