# Challenge 5 — REI vs. conventional AI

**Status: locally frozen exploratory pilot; no live model trials have been executed.**  
**Date:** November 11, 2026. **Research release:** C5-2026-11-11-v1.

## Question
Can REI-1.0 produce more accurate and appropriately cautious answers on unseen, objectively keyed reasoning tasks than conventional AI using the same foundation model and the same supplied information?

## Hypotheses and predeclared comparisons
- **Primary comparator:** `self_critique` (draft → critique → revision), a more capable baseline than one-pass answer generation.
- **Secondary comparators:** `baseline` (one pass) and `fixed_depth` (fixed recursive questioning).
- **Experimental intervention:** existing REI-1.0 graph-mediated epistemic inquiry; no modifications to its implementation during evaluation.
- **Primary endpoint:** overall success (correct exact answer on answerable cases, correct null abstention on unanswerable cases).
- **Secondary endpoints:** answerable accuracy, false-answer rate on unanswerable cases, coverage, confidence calibration where reported, actual model calls, reported token consumption, and failed runs.
- **Research hypothesis:** REI exceeds self-critique on the primary endpoint; exploratory target ≥5 percentage points.

## Dataset design
- **60 evaluation cases:** 12 each of arithmetic, formal entailment, four-state evidence semantics, dependency-aware inference, and insufficient information. Synthetic worlds: every known fact needed to answer is supplied in the text. No real-world source is impersonated.
- **20 disjoint calibration cases:** same five categories, 4 each; calibration is for checking provider compatibility and error handling, not for selecting the best evaluation outcome.
- Correct keys are kept in distinct `*_keys_PRIVATE.json` files and are never supplied to model prompts by the benchmark code. However, because the archive contains keys, independent custody by a separate evaluator would be required for a genuinely concealed holdout.
- Cases are deterministic, generated with recorded seeds and exact evaluators, not independently reviewed by human domain experts. This is an exploratory software-supported benchmark, not a definitive scientific test.

## Protocol (to be followed in a separate authorized model environment)
1. Preserve the `FROZEN_PROTOCOL.json` plus hash outside the evaluation workstation before running models. This is **not** done by local hashing alone.
2. Run a calibration phase on the 20 public calibration cases. Record invalid JSON and model endpoint problems; fix provider compatibility only, without viewing evaluation answers.
3. Use one fixed foundation model/version and provider across all four arms. Supply the same task information to each arm; do not allow extra web tools on one arm only.
4. For each of 60 evaluation cases, run **3 randomized trials per arm**. This implies **720 model-case-arm trials** (not 720 API calls; recursive arms require additional calls).
5. Per case-arm trial: max 4 model calls, 4,000 provider-reported tokens, 30 seconds and 384 output tokens/call. Capture actual consumption; maximum limits do not imply usage is matched.
6. Grade with the frozen keys. Failed/malformed/over-budget runs count as incorrect; do not silently discard trials. Compute paired case-clustered bootstrap intervals (the case, not the repeated trial, is the resampling unit).
7. Report primary difference REI minus self-critique and all three resource ratios. Display baseline and fixed-depth comparisons as secondary; don't select the best-performing comparator post hoc.
8. Repeat on an independently authored, externally blinded benchmark before making a general performance claim.

## Interpretation policy
A preliminary *signal* of advantage requires: (i) mean success difference ≥ +0.05 vs self-critique, (ii) case-clustered 95% bootstrap interval above 0, and (iii) REI reported-token use within ±10% of self-critique. This is a **screening rule**, not proof. Equal provider-reported tokens alone do not prove equal FLOPs, latency, or monetary cost. A robust claim needs independent reviewer oversight and replication on independent problems, and may be infeasible without a genuinely budget-matched external baseline.

A null or negative result is a valid finding. Accuracy could be unchanged while REI adds useful inspectability, or REI could lose due to extra recursive errors. Report all outcomes, including errors and abstentions.

## Trust / validity limitations
- Code execution and offline validation check **engineering correctness**, not model reasoning ability.
- Programmatically generated tasks are narrow and may favor REI's native evidence representation; also test independent open-domain tasks and adversarially worded sources before generalizing.
- The REI arm's benchmark path uses graph inquiry but does **not** automatically run the entire trusted external-source service for each case.
- No live provider identity or benchmark secrecy can be attested from this package alone.
- Local SHA-256 hashes are not an external timestamp or cryptographic experiment attestation.
- Exact-match grading may mark legitimate alternative formats incorrect; the prompts intentionally request one precise output token where possible.

## Expected outputs
- `challenge/calibration_cases.json` and `challenge/evaluation_cases.json` (model-facing)
- Separate `challenge/*_keys_PRIVATE.json` (grader-only)
- `challenge/FROZEN_PROTOCOL.json` (local integrity freeze)
- `results/*.json` live per-trial records and aggregate results **only when separately run with an authorized provider**
- `results/READINESS_REPORT.json` checks that can be performed offline; `scientific_outcome` must be `NOT_MEASURED` until real trials exist.