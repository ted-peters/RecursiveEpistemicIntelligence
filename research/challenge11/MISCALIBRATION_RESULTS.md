# Challenge 11D — How exact investigation planning fails when source reliability is wrong

**Software-only experiment: completed, replayed, and passed.**

[GitHub Actions run #43645608203](https://github.com/ted-peters/RecursiveEpistemicIntelligence/actions/runs/43645608203)

## Question and design

The preceding Challenge 11/11C binary hypothesis experiments assumed that each
test's sensitivity and false-positive rate were known perfectly. That is a
particularly favorable assumption for exact value-of-information (VOI)
planning. This diagnostic asks how the same conventional policies perform when
the nominal *estimated* test reliability differs from the true reliability.

- 5 deterministic development seeds: 20261119–20261123.
- 100 synthetic four-probe decision cases per seed: **500** nominal
  scenarios, repeated at four uncertainty levels.
- Test sensitivity and false-positive rates separately perturbed, with
  maximum absolute errors of **0, 0.05, 0.10 and 0.15**. The perturbations are
  derived from a public deterministic hash seed and clipped to maintain
  informative synthetic tests.
- All nominal policies receive **only the same nominal test reliability
  estimates** and initial prior, never true probabilities or private H.
- True test likelihoods are available solely to the **evaluator**, which
  computes exact expected classification error and expected probes over
  every possible latent H and measurement branch. No sampled outcome noise.
- The measurement budget remains **at most two probes**.
- A probe incurs a hypothetical fixed cost of **0.02 wrong-decision units**.
  This is not a dollar amount or the cost of Qwen inference.

We compared nominal two-step recursive VOI, nominal myopic VOI, nominal
cost-optimal two-step planning, and a **privileged true-likelihood cost
optimum** that receives information withheld from the other three. The
privileged policy is an *unfair informational lower bound on achievable
expected total loss*, **not a fair competing conventional AI**. All four
policies are established conventional Bayesian decision algorithms; no
language model was tested.

For a policy's individual hidden-state branches, expected error and probe
usage are integrated exactly with **true** probabilities, while the
policy's selections, posteriors, and classifications are formed from
**nominal** probabilities. The privileged diagnostic alone may update with
true likelihoods.

## Verified results

Each cell is a mean across the **same 500** nominal scenarios.

| Max likelihood error | Nominal recursive: true total expected loss | Nominal cost-aware: true total expected loss | Privileged true-likelihood lower bound | Nominal cost-aware cases worse than privileged |
|---:|---:|---:|---:|---:|
| 0 | .18523 | .18237 | .18237 | 0/500 |
| ±.05 | .18679 | .18387 | .17980 | 213/500 |
| ±.10 | .19212 | .18848 | .17457 | 324/500 |
| ±.15 | .19929 | .19475 | .16847 | 373/500 |

At the largest perturbation, nominal cost-aware planning has true expected
error **.16494**, takes **1.49033** expected probes, and incurs combined
expected loss **.19475**. The privileged model's lower bound is **.16847**.
The nominal cost-unaware recursive planner takes **1.75196** expected
probes and has combined true loss **.19929**.

Notice that the privileged bound *improves* with more perturbation under this
particular synthetic generator. That is NOT a universal phenomenon: its
true test likelihoods sometimes become more informative, and it has
privileged access to those changes. The meaningful comparison for practical
engineering is between **nominal** policies seeing the same flawed data.

We can only conclude that the benefit of exact two-step planning is
sensitive to reliability misspecification. This study does **not** yet test
whether any algorithm can learn source reliabilities, detect calibration
problems, or improve outcomes from external evidence. The public seeds,
likelihoods, perturbation process and fixed probability assumptions are not
a novel blinded holdout.

## Integrity and reproducibility

- `research/challenge11/likelihood_miscalibration.py`: independent
  true-world branch-weight evaluation for each nominal policy.
- `tests/test_challenge11_likelihood_miscalibration.py`: seven offline tests,
  including zero-perturbation parity with the original exact Bayes-cost
  evaluator, hand-checkable one-probe error, privileged-bound dominance,
  parameter validation and tampering detection.
- `.github/workflows/challenge11-likelihood-miscalibration.yml`: automatically
  evaluates all 500 nominal scenarios at four perturbation levels, reruns
  the complete study to verify the original report, and archives results.
- The full repository regression suite also passed for this code.

Run:

```bash
python -m pip install .
python -m unittest discover -s tests -p test_challenge11_likelihood_miscalibration.py -v
python -m research.challenge11.likelihood_miscalibration --output miscalibration.json
python -m research.challenge11.likelihood_miscalibration --verify-only --output miscalibration.json
```

**Next actual research gate**: independently calibrate uncertain source
reliability using observations; compare a conventional uncertainty-aware
Bayesian baseline with an REI investigation controller under equal evidence
and resource access. A known-parameter Bayesian planner is still the right
strong conventional control for the simpler version of this problem.
