# REI-0.8: Repeated-Study and Calibration Protocol

**Version:** 0.8.0 — implementation specification. This protocol is prospective; its bundled fixture results are NOT empirical findings.

## 1. Intended scientific questions

Compare the same underlying model and public task data across one-pass answering, self-critique, FIFO fixed-depth recursive inquiry, and prioritized graph-based REI. Preregister hypotheses about task success, correct abstention, uncertainty calibration, robustness to misleading inputs, and resource consumption **before running any held-out data**. Do not claim novelty, model superiority, or truth because a graph trace is longer.

## 2. Data and split firewall

Calibration and evaluation cases must be separate by ID **and** by normalized question/context. Both splits use v0.7 public question schema and separate evaluator-only key schema. REI-0.8 checks exact duplicate prompts; it **cannot** detect semantic near-duplicates, source leakage, or data already present in pretrained model weights. Acquire genuinely independent answer keys; consider external blinded reviewers and frozen signed dataset manifests. Evaluation keys are accessed only by local grading and replay, not model turns or threshold selection. The bundled 4+4 split is for software testing, not scientific inference.

## 3. Repeated trials

Set trial count and seed in advance. Each repetition uses a fresh provider instance; case/arm order is independently and deterministically shuffled per split/repetition. Multiple calls to an externally hosted model are not guaranteed independent: caching, model snapshot drift, deterministic decoding and temporal effects can correlate runs. Scripted fixtures repeat identical predefined turns and do not represent observed variance. Case IDs, provider fingerprint, exact reports and usage are retained for each trial.

## 4. Fixed resource limits and cost comparability

Every arm has the same maximum calls, provider-reported tokens, output tokens, steps and wall-clock seconds. Compare actual calls and tokens, and examine exactly matched case-trial pairs; do not describe shared maxima as equal actual computation. The baseline requires one call, self-critique three, and REI/fixed-depth approximately four under default fixture configuration. Provider-reported token usage is not FLOPs, total compute, energy or billing cost. A preflight bound limits worst-case total model calls for explicit live-cost exposure. Budget failures are counted as failures.

## 5. Adaptive abstention policy (calibration only)

Candidate thresholds: `{0, .25, .5, .75, .9, 1}`. Fit per-arm threshold maximizing calibrated split overall success under answerable-case coverage ≥ configured bound, preferring lower thresholds on ties. If coverage cannot be met even at threshold zero, keep zero and report constraint unmet. An answered result with `confidence < threshold` is converted to abstention for adapted evaluation only; missing confidence abstains for positive thresholds. Errors never convert to valid abstentions. Original replies remain unchanged. **This is decision calibration, not changing model weights, epistemic logic, reviewer decisions or operational safeguards.** Evaluation labels are inaccessible to policy fit.

## 6. Statistics and reporting

Use original exact-match v0.7 grading. Aggregate by arm, report raw and adapted metrics separately. For case-repeated trials compute per-case mean paired score differences, then resample **case IDs**, not repeated case-trials, for seeded percentile bootstrap intervals. These are descriptive, not guarantees of deployment generalization. Also report actual tokens/calls, exact usage match count, response stability, category-level scores and failure rate. Confidence is self-reported probability of correct answer and may be badly calibrated; it is distinct from verified evidence.

## 7. Provenance and audit checks

Each v0.7 subreport includes checksum, input/key digest, model fingerprint, seed, budget, reasoning trace and grade. The outer study adds digests of both split documents and reference keys, selected calibration policy, held-out analysis, and checksum. `study-verify` independently recomputes all nested/outer metrics. A SHA digest does not authenticate provider execution or the actor generating the report. Use external signing/attestation and immutable storage in a consequential research setting. The REI arm still treats all *model-generated* evidence as `NEITHER`; no live-reviewed source evidence enters this benchmark.

## 8. Publication acceptance criteria

Before reporting a favorable or unfavorable empirical effect: freeze representative held-out cases, verifier and scoring aliases; document randomization, model IDs/snapshots, prompts, decoding parameters, tool access and actual cost; preregister primary outcome and statistical unit; use enough genuinely independent cases, replicate across seeds/providers, inspect failure traces and publish negative outcomes. Analyze both intention-to-treat all-trial comparisons and subsets matched on **actual** resource use. Confirm there are no undocumented evaluation-policy changes after seeing held-out results.

**Current release finding:** the software can orchestrate, grade and regrade this experiment. It has not experimentally established a real-world REI advantage.
