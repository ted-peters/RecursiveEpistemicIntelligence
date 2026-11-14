# Challenge 11-B: 12-case prospective replication (public development set)

**Protocol committed before running the new model batch.**

## Motivation

The completed real Qwen3 4B four-case pilot (run
[43258949174](https://github.com/ted-peters/RecursiveEpistemicIntelligence/actions/runs/43258949174))
had 4/4 correct realized H0/H1 decisions for both Qwen tool-assisted
self-critique and the conventional exact recursive Bayesian controller.
Although outcomes tied, Qwen chose a strictly suboptimal first probe in 2/4
cases under exact expected error with an optimal future continuation:
mean first-choice optimal-continuation regret 0.00136575. Qwen used 16 model
calls, 10,203 reported tokens; the exact planner used no model calls. Independent
case-level verification is archived at GitHub Actions
[43644482440](https://github.com/ted-peters/RecursiveEpistemicIntelligence/actions/runs/43644482440).

These numbers are exploratory and cannot imply REI beats a conventional
planner: the recursive controller **is** an exact conventional mathematical
planner. The Qwen comparator could also directly call this planner.

## Prospective fixed setup

- **New seed:** 20261114 (fixed before model results).
- **Count:** exactly 12 synthetic *development* cases, not the original four.
- **Hypotheses:** hidden binary H0/H1, one known prior from generator.
- **Choices:** four published noisy test likelihoods per case.
- **Budget:** at most 2 real measurements per case.
- **Pairing:** exact planner and model share the same hidden truth and
  pre-drawn potential measurements; only chosen measurements are signed and
  revealed.
- **Model:** the same pinned Qwen3-4B-Instruct-2507 Q4_K_M, SHA-256
  `85e4a5b7b8ef0e48af0e8658f5aaab9c2324c76c1641493f4d1e25fce54b18b9`.
- **Inference:** llama.cpp b12242, temperature 0, seed 711, structured JSON.
- **Conventional Qwen policy:** draft + revise choice for up to two
  measurements, maximum 4 model requests, 3,200 reported tokens,
  220 seconds per case; server usage including failed parses and unknown usage
  are logged separately.
- **Exact-control policy:** two-step exact Bayesian expected-error minimization;
  no model is queried. Same numeric decision tools/likelihoods are present
  in the model input.
- **Primary diagnostic:** number of Qwen first selections with strictly
  positive regret under the *best possible subsequent* policy, and mean
  first-selection regret. This is **not Qwen's overall expected policy risk**.
- **Secondary:** per-arm realized correctness, Brier scores, signed probe
  counts, per-case divergent investigation paths, failures and actual
  server-reported model tokens.
- **Independent grader:** replays the hidden synthetic truth and selected
  observations, recomputes first choice's expected Bayes risk, verifies model
  request count/stage order and known server tokens, rejects altered
  selected paths and unsigned observations, and independently regenerates
  the public-data digest. It preserves all original model outputs.

## Interpretation rules

The exact planner must have zero first-choice regret relative to itself.
This is a unit test / mathematical invariant, not a discovery of model
superiority. We will report **all 12** outcomes, not only cases where a
different probe was chosen. If Qwen matches exact planning, that is a positive
result for Qwen; if it does worse, that measures Qwen on toy numeric
investigation selection, **not** a generic reasoner ranking.

Correct final decisions alone can hide suboptimal probe selection: distinct
questions may lead to the same right posterior-threshold result by chance.
A single observed outcome path cannot measure the model's complete
counterfactual adaptive policy. The public case generator, known exact
likelihoods and fixed probability assumptions prevent the result from
constituting a blinded real-world benchmark.

The run requires approximately up to 48 inference attempts under the
published 4-call ceiling (not a guarantee of actual calls). There is no paid
model API; GitHub Actions CPU minutes are consumed. No scheduled follow-up
or open-ended recurring compute is authorized.
