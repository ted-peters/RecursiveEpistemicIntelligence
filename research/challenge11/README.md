# Challenge 11 — Does REI investigate the right uncertainty?

**Status:** active-investigation research harness. **No claimed AI superiority.**

REI should not spend more tokens simply to restate its thoughts. Challenge 11
tests *experimental design*: given several imperfect measurements of a hidden
binary hypothesis and resources for only **two** experiments, which test should
be run next? Each answer may change which second test is worth running.

## Research question and estimand

The main algorithmic comparison is **exact expected misclassification risk**
under a known synthetic probability model:

- **Recursive VOI**: look ahead two probes; after the first observed outcome,
  update the posterior and reconsider the second probe or stop.
- **Myopic VOI**: choose the best single-step expected error reduction; after
  observing it, independently choose the next best immediate test or stop.
- **Exact Bayesian optimum**: independently computed conventional dynamic
  program over the same possible future outcomes. The recursive implementation
  should match this optimum exactly, to numerical tolerance; this is a strong
  control, **not evidence of a new AI invention**.

The secondary optional real-model comparison is different: an arm-blind Qwen3
4B *self-critique test-selector*, supplied the same public prior, test
likelihoods, previous observations, and **exact Bayesian utility table**, chooses
what to investigate. It gets one draft and one revise decision for each
selected probe. REI uses the deterministic recursive planner and **zero**
language-model calls. Both final H0/H1 classifications use the **same**
posterior-threshold decision rule. This measures selection choices, not
free-form language-model answer quality.

## Experimental controls

| Control | Configuration |
|---|---|
| Hidden truth | Binary H0/H1, sampled privately from an initial known prior |
| Choices | Four synthetic noisy, conditionally independent binary probes |
| Public data | Prior, sensitivity, false-positive rate, prior revealed observations, candidate Bayes errors |
| Hidden from both policies | Actual H, unselected probe results, fixture signing key, scoring labels |
| Budget | At most **two** measurements; one unit per probe |
| Independent reviews | Every selected outcome signed by a fresh ephemeral Ed25519 reviewer, checked through EvidenceLedger |
| Paired environment | Both policies share the **same predrawn potential outcomes** |
| Primary metric | Exact **expected** Bayes error (a property of the policy under assumed synthetic likelihoods) |
| Secondary metrics | Realized correctness, Brier score, probes and verified reviews |
| Live pilot | At most four model calls per case, pinned Qwen3 model and engine, up to 4/8/12 public cases |
| Model costs | Report attempted calls, server-reported tokens including parsable failures, unknown usage and failure counts |
| Blinding | Public development generator; **not a held-out independent evaluation** |

For each test with sensitivity \(s\), false-positive probability \(f\), and
current prior \(p=P(H1)\):

\[
P(+)=ps+(1-p)f,\qquad
P(H1\mid +)=\frac{ps}{ps+(1-p)f}.
\]

With symmetric 0–1 classification error, the Bayes risk is
\(R(p)=\min(p,1-p)\). The **lookahead controller** compares the expected
post-test risk with the best risk attainable after a second contingent test.
The strong conventional dynamic program computes the exact same optimal
quantity. The myopic policy compares only expected error after one test.
Every method may stop if no test has positive expected value.

These probabilities and independence assumptions are **stipulated by the
simulator**. They are not source credibility estimates learned from the
world. A signed synthetic observation authenticates admission into the
test's ledger, not its truth outside this controlled environment.

## How to reproduce

Entirely offline and free (software and synthetic signatures only):

```bash
python -m pip install .
python -m unittest discover -s tests -p test_challenge11_voi.py -v
python -m unittest discover -s tests -p test_challenge11_pilot.py -v

python -m research.challenge11.simulate --count 24 --seed 20261112 \
  --output challenge11-results/policy-audit.json
python -m research.challenge11.simulate --verify-only \
  --output challenge11-results/policy-audit.json

python -m research.challenge11.pilot --mode fixture --count 4 \
  --output challenge11-results/choice-fixture.json
python -m research.challenge11.pilot --verify-only \
  --output challenge11-results/choice-fixture.json
```

The fixture returns scripted probe choices and **is not a real AI experiment**.

The workflow at `.github/workflows/challenge11-active-investigation.yml`
runs those checks automatically and publishes a step summary. It offers a
separately opted-in live pinned Qwen model option; launching it consumes
GitHub Actions CPU time but requires no paid API key. New workflow
dispatches generally must be present on the default branch to appear in the
GitHub Actions interface. A distinct one-shot development workflow may be
used for an explicitly requested live pilot without changing default branch
or the public Hugging Face Space.

The live Qwen provider is intentionally arm-blind: its prompts contain
only public test data, numeric tool utilities, the current stage and draft
choice; the case ID is used for server-side logging only. It cannot see
the latent truth, unrevealed observations or ephemeral signing secret.
Invalid/unavailable model choices fail closed rather than being silently
corrected for free.

## What would count as real progress?

- **Successful engineering**: signed measurement outcomes admitted safely;
  no scoring labels leaked; test budget honored; independent replay agrees.
- **Decision-policy improvement**: a lower exact expected risk than a
  preregistered myopic algorithm on varied scenarios, independently verified
  against the exact dynamic-programming baseline.
- **Model reasoning improvement**: better *investigation choices* and/or
  end-to-end predictive quality than a capable conventional **tool-using**
  baseline under matched actual inference consumption, on a novel blind
  held-out set, across multiple seeds.

The first two are only demonstrations that a conventional recursive Bayesian
planner works. They are not enough to claim REI outperforms state-of-the-art
language models. To test REI-specific advantage, subsequent experiments
must include uncertain likelihood estimates, partially available sources,
differing review reliability, real task semantics and equivalent tool
access—without letting REI read the answer-key ledger or giving it a
secret computation denied to the conventional comparator.

## Known limitations and strict interpretations

1. Public synthetic data can be intentionally or accidentally tuned; do not
   use it as proof of generalization.
2. The hidden H is sampled deterministically by the test harness but cannot
   be passed to a model. The final answer is mechanically formed from the
   posterior, so the LLM is evaluated only on **choice quality**, not on
   numeric posterior arithmetic.
3. The same exact utility calculations are supplied to the conventional
   model; it is not disadvantaged by a withheld numeric tool.
4. The recursive planner is already a conventional exact dynamic program.
   Equal results with exact-optimal planning are expected by construction.
5. The conventional Qwen policy uses more model calls than mathematical
   planning, and so this is **not a compute-matched AI comparison**.
6. The self-critique model's full expected counterfactual risk cannot be
   inferred from its single observed history; report its realized predictive
   outcomes, first-choice regret assuming optimal continuation, and costs.
7. Signatures use ephemeral fixture keys; independent report regrading
   reproduces decisions and numeric scores, **not the original cryptographic
   receipt bytes** unless complete signed artifacts and a trusted key anchor
   are archived separately.
