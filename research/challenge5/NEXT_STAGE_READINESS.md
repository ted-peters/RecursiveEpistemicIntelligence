# REI Challenge 5 — Next-stage readiness and execution gate

Date: 2026-11-11

## Verified now

- Frozen calibration set: 20 questions (4 in each of five categories).
- Frozen held-out evaluation set: 60 questions (12 in each category).
- 12 evaluation cases are designed to have insufficient information; abstention must be assessed separately from incorrect answers.
- `python challenge/validate.py` PASSED.
- `python -m unittest discover -s challenge -p 'test_*.py' -q` PASSED: 9 tests.
- Frozen protocol SHA-256: `17571002884d85f1a524dbb7d854ea930e82bebd1e4205de9032575339ba0b36`.
- Executed external language-model calls in this stage: **0**.
- Observed accuracy difference between REI and conventional AI: **not measured**.

## Gate before a defensible accuracy claim

1. Obtain authorized independent inference access to a named, versioned language model. Keep credentials with an execution operator rather than in the research report.
2. Use exactly the same underlying foundation model and source evidence for all arms; record versions, seeds, raw responses, latency, token counts and failures.
3. Conduct calibration without evaluating on the held-out answers. Freeze thresholds and scoring before evaluation.
4. Primary comparison: REI versus conventional self-critique; secondary comparisons: one-pass and fixed-depth.
5. Execute 60 held-out problems x 3 repetitions x 4 arms = 720 arm-case trials, subject to cost authorization.
6. Report paired correctness difference, bootstrap confidence interval resampled at case level, abstention, quality under contradiction, and actual cost. If actual cost is imbalanced, do not describe the comparison as compute-matched.
7. Run an ablation disabling recursive challenges while retaining memory, provenance and evidence verification to isolate the philosophical mechanism.

## What is and is not possible in this session

The package and deterministic validation can run here. There is no connected independent text-model inference service or provider credential available for executing both live arms. The assistant must not fill in pretend model answers and label them as an observed AI competition.

## Decision

**Engineering readiness: PASS.**
**Independent inference access: BLOCKED.**
**Empirical superiority: UNDETERMINED.**

The next action is not a further architectural release: arrange authorized independent model execution, then run the frozen trial and grade real outputs.
