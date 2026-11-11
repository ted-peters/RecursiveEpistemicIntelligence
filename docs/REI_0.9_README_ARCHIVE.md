# Recursive Epistemic Intelligence — REI-0.9

**Version 0.9.0** · Python 3.10+ · `cryptography>=42,<50` · live-model inference OFF by default.

REI-0.9 extends the tested REI-0.8 codebase with **preregistered, resumable, evaluator-isolated model experiments**. Existing epistemic graphs, recursive inquiry, source provenance, Ed25519 evidence review, belief revision, benchmark and study commands remain available.

> **Research finding: NONE YET.** No external-provider experiment has been performed in this release. `experiment-demo` is a deterministic software check using scripted responses, synthetic adjudication entries, and synthetic reported token use. It cannot demonstrate AI superiority. In particular, REI uses more calls than one-pass baselines in the example; **a shared call ceiling is not an equal-cost comparison**.

## Install and run offline

```sh
python -m pip install .
python -m unittest discover -s tests -p 'test_*.py' -v
python -m rei0 experiment-demo --output-dir rei09_demo
python -m rei0 experiment-verify \
  --report rei09_demo/experiment_report.json \
  --adjudications rei09_demo/adjudications.json \
  --calibration-cases rei0/data/study_calibration_cases.json \
  --calibration-keys rei0/data/study_calibration_keys.json \
  --evaluation-cases rei0/data/study_evaluation_cases.json \
  --evaluation-keys rei0/data/study_evaluation_keys.json
```

The demo produces `preregistration.json` (immutable protocol hash), `adjudications.json` (explicitly **synthetic** source-review declarations), `checkpoint.json` (completed trials), and `experiment_report.json` (all outcomes, original 0.8 study, budget-matching diagnostics, and regrading hash).

## Design and trust boundaries

- Four pre-existing arms: `baseline`, `self_critique`, `fixed_depth`, `rei` (actual bounded inquiry engine). The same reference questions are given to all four.
- Frozen before running: model/endpoint fingerprint, both public dataset digests, both private key-set digests, adjudication manifest digest, hypotheses, comparator, confidence-threshold policy, trial count, seeds, budgets, grading method, actual-token tolerance, and minimum evaluation case count.
- Independent reviewer **declarations**: each case/answer key has a label hash, source reference, curator, independent reviewer, and review procedure. **Those strings are not authenticated, nor are their factual claims verified by this software.** Inspect the real supporting publications or proofs independently and freeze the manifest before testing.
- Calls only become live with BOTH `--live --model ... --acknowledge-live-costs`; `REI_LLM_API_KEY` is obtained from the environment. Existing provider adapter uses HTTPS JSON Chat Completions. It does not call tools or use external answer keys in prompts.
- Each completed trial is atomically checkpointed and validated before a resume. If interrupted **during** a trial, re-running may repeat provider calls and incur further costs. Trial trace hash/regrading is not remote-provider attestation. Preregistration timestamps and report hashes are not trusted timestamping: publish/anchor the preregistration digest with an independent service before exposure to any evaluation results.
- The post-hoc exact/near-usage matched subset is descriptive only. Selection on actual spend can introduce bias. `confirmatory_design_eligible` merely reports **design conditions**, not evidence of a positive result or validation of case quality.

## Prepare a real (independently checked) dataset

First prepare `cal_cases.json`, `cal_keys.json`, `eval_cases.json`, `eval_keys.json` in the inherited benchmark schemas. Use different, independently adjudicated cases for calibration vs. held-out evaluation. The model gets only the questions and supplied context; **do not** place answer keys, private reviewer data, or secrets in the public case files.

Create an adjudication template (the empty entries intentionally FAIL validation until completed):

```sh
python -m rei0 experiment-adjudication-template \
  --calibration-keys cal_keys.json --evaluation-keys eval_keys.json \
  --output adjudications.json
```

For each record, fill `curator`, `reviewer`, `reference`, `procedure`. The reviewers must differ from the curators and the record hash must match the grading key. For a credible real study, use source-backed records signed and independently archived outside REI. The software checks declared separation, not human identities.

### Step 1 — Freeze the protocol (BEFORE running evaluation)

```sh
python -m rei0 experiment-preregister \
  --calibration-cases cal_cases.json --calibration-keys cal_keys.json \
  --evaluation-cases eval_cases.json --evaluation-keys eval_keys.json \
  --adjudications adjudications.json \
  --study-id REI09-TRIAL-001 --repetitions 3 \
  --max-total-calls 2000 --comparator baseline \
  --relative-token-tolerance 0.10 --confirmatory-min-cases 30 \
  --live --model YOUR_SUPPORTED_MODEL_ID --acknowledge-live-costs \
  --output prereg.json
```

`--max-total-calls` is a worst-case *preflight* upper bound. A large case set may require adjusting it, and the provider may bill differently. Store `prereg.json` and publish its SHA-256 commitment through an independently trusted timestamp or repository before the run. Do not change the plan afterward; create a new study ID for protocol changes.

For a scripted dry run, use `--fixture fixture.json` **instead of** `--live --model ... --acknowledge-live-costs`, and preregister that same fixture.

### Step 2 — Run and checkpoint

```sh
export REI_LLM_API_KEY='YOUR_SECRET_FROM_SECURE_VAULT'
python -m rei0 experiment-run \
  --prereg prereg.json \
  --calibration-cases cal_cases.json --calibration-keys cal_keys.json \
  --evaluation-cases eval_cases.json --evaluation-keys eval_keys.json \
  --adjudications adjudications.json \
  --live --model YOUR_SUPPORTED_MODEL_ID --acknowledge-live-costs \
  --checkpoint trials.checkpoint.json --output experiment_report.json
```

The completed-trial checkpoint is reused on a second identical command. If the provider identity, dataset, label digest, resource limit, or preregistration differs, the run rejects the change. Keep answer keys and checkpoint files private. The current design runs the calibration trials before held-out evaluation trials, but fitted abstention thresholds are selected by the independent analysis after recordings are complete; no held-out labels are passed to a model.

### Step 3 — Regrade independently

```sh
python -m rei0 experiment-verify \
  --report experiment_report.json \
  --calibration-cases cal_cases.json --calibration-keys cal_keys.json \
  --evaluation-cases eval_cases.json --evaluation-keys eval_keys.json \
  --adjudications adjudications.json
```

This checks all nested study reports, case-level scores, calibration policy, resource comparisons, hashes, and frozen design. **It does not prove that a live provider actually returned the recorded responses**, verify the authorship of an adjudication, or rule out pretraining contamination. Audit actual usage and endpoint logs externally.

## Report interpretation

`resource_comparability.actual_usage_status` is one of `exactly_matched`, `within_tolerance`, `imbalanced` for the preregistered REI-vs-comparator pairs. The primary metric is the difference in average per-case-trial overall success. The inherited case-cluster bootstrap intervals are descriptive; with 4 synthetic evaluation cases they have no scientific inferential value. At least 30 independent held-out cases is the default **design screening threshold**, NOT a power calculation. Pre-register a task-specific power/precision analysis and multiple-comparison policy before publishable studies.

## Previous releases and interfaces

All 0.8 commands (`study-demo`, `study-run`, `study-verify`), 0.7 benchmarks, bounded inquiry, evidence review services, and signed-revision features remain available. See `docs/STUDY_PROTOCOL.md` (0.8) and `docs/EXPERIMENT_PROTOCOL_09.md` (0.9), plus `SECURITY.md` and `RELEASE_TEST_REPORT.json`.

---

## REI-0.8 compatibility reference

# Recursive Epistemic Intelligence — REI-0.8

**Version 0.8.0** · Python 3.10+ · `cryptography>=42,<50` inherited from REI-0.5 · offline by default.

REI-0.8 **extends the complete REI-0.7 project**, adding reproducible repeated-trial experiments with **disjoint calibration and held-out evaluation datasets**, conservative **confidence-based abstention-policy adaptation**, case-level bootstrap comparisons, stability statistics, budget/accounting diagnostics, and independent report regrading. The prior graph, recursive inquiry, reviewed evidence, source verification, signed inference rules, belief revision, benchmarks, and CLI commands are preserved.

> **Scientific status:** No genuine external-model experiment has been performed as part of this distribution. The included scripted example uses hand-authored outputs and fabricated token counts and is **a deterministic integration test, NOT evidence that REI improves reasoning**. The live adapter has not been tested against a real provider account for this release. Calibration adjusts a post-answer abstention threshold; **it does not train neural weights or prove epistemic truth**.

## Install and run (offline)

```sh
python -m pip install .
python -m unittest discover -s tests -p 'test_*.py' -v
python -m rei0 study-demo --repetitions 2 --output study_report.json
python -m rei0 study-verify \
    --report study_report.json \
    --calibration-cases rei0/data/study_calibration_cases.json \
    --calibration-keys rei0/data/study_calibration_keys.json \
    --evaluation-cases rei0/data/study_evaluation_cases.json \
    --evaluation-keys rei0/data/study_evaluation_keys.json
```

This demonstrator reuses eight scripted cases from 0.7, split into **four calibration and four held-out evaluation cases**, each with all four experimental arms and two identical scripted responses per arm/case. It demonstrates split isolation and trace regrading; it is too small and synthetic to estimate model performance or generalization.

The demo report is a regular JSON file containing both raw and adapted results, policies trained on the calibration split alone, per-case/trial usage, failure flags, SHA-256 of underlying subreports, and case-level confidence intervals. A compact example is included at `examples/study_demo_summary.json`.

## Four comparison arms (unchanged from REI-0.7)

| Arm | Protocol |
|---|---|
| `baseline` | Single model answer |
| `self_critique` | Draft → critique → revised answer |
| `fixed_depth` | Initial claim, FIFO questions, final synthesis |
| `rei` | Actual bounded `InquiryEngine`, prioritized epistemic graph, final synthesis |

Every case/arm/repetition gets the **same configured maximum** calls, tokens, output tokens, steps and time. Actual consumption differs by arm. **REI-0.8 does not claim an equal-FLOP or equal-dollar comparison**: it reports per-arm calls/tokens, and counts case-trials with exactly matching *reported* calls and tokens. The original REI-0.7 experiment remains available via `benchmark-demo`, `benchmark-run`, `benchmark-verify`.

## Run a custom offline study

Prepare separate JSON documents using the v0.7 schemas:

- `calibration_cases.json`, `evaluation_cases.json`: public `rei0.benchmark.cases.v1` documents with distinct case IDs and distinct normalized question/context pairs.
- `calibration_keys.json`, `evaluation_keys.json`: evaluator-only `rei0.benchmark.keys.v1` answer-key documents whose case IDs exactly match each split.
- `fixture.json`: optional synthetic `rei0.benchmark.fixture.v1` scripted turns for every case × arm, with the required stage order. The **same script is reset per repetition**, so repetition is deterministic, not a stochastic model trial.

```sh
python -m rei0 study-run \
    --calibration-cases calibration_cases.json \
    --calibration-keys calibration_keys.json \
    --evaluation-cases evaluation_cases.json \
    --evaluation-keys evaluation_keys.json \
    --fixture fixture.json \
    --repetitions 3 --seed 19 \
    --max-calls 4 --max-tokens 4000 --steps 2 \
    --max-total-calls 1000 \
    --output study_report.json
```

The `--max-total-calls` bound is checked **before any provider is constructed** using a conservative worst-case formula: `(calibration_cases + evaluation_cases) × four arms × repetitions × max_calls`. Each provider-reported call token count is charged to the existing 0.7 meter; output time/call/token caps remain in force. Failures are graded as failures, not successful abstentions. The study's maximum number of repetitions is 30.

## Optional external-model experiment (explicit opt-in)

Only use public, non-sensitive prompts and a provider/endpoint you trust. Put the evaluator-only keys on the trusted host, not in prompts or model tools.

```sh
export REI_LLM_API_KEY='YOUR_PROVIDER_KEY'
python -m rei0 study-run \
    --calibration-cases calibration_cases.json \
    --calibration-keys calibration_keys.json \
    --evaluation-cases evaluation_cases.json \
    --evaluation-keys evaluation_keys.json \
    --live --acknowledge-live-costs --model YOUR_SUPPORTED_MODEL_ID \
    --endpoint https://api.openai.com/v1/chat/completions \
    --repetitions 3 --seed 19 --max-total-calls 1000 \
    --max-calls 4 --max-tokens 4000 --max-output-tokens 384 \
    --max-seconds 30 --steps 2 --output live_study.json
```

The live connector reuses the 0.7 HTTPS Chat Completions-compatible JSON interface. It requires provider-reported `usage.total_tokens`, declines redirects and never sends held-out answers as model inputs. Provider-specific API behavior, model version, repeated-trial independence, price, benchmark contamination and external model quality **have not been independently verified**. API costs may arise. No live endpoint is called without `--live --acknowledge-live-costs` and a model ID.

## Adaptive epistemic decision policy

REI-0.8 does **not** self-modify inference rules or external safeguards. It calibrates one **confidence threshold per arm** on calibration trials, using the fixed threshold grid `0, .25, .5, .75, .9, 1` and a minimum calibration answerable-coverage requirement (default 50%). It selects the threshold with highest calibration success, breaking ties toward the smallest threshold. If no threshold can achieve the coverage target, it retains threshold zero and records the unmet constraint.

For evaluation only, an answered response with reported correctness-confidence below the learned threshold is converted to an **explicit abstention**; unknown confidence is converted to abstention only for thresholds above zero. An API failure **never** becomes a valid abstention. The original answer, confidence, rationale and trace remain intact in the recorded subreport, and the policy is evaluated separately from raw performance. Neither calibration nor held-out labels ever reach model requests. The withheld evaluation keys are **only** used during trusted scoring, not policy fitting.

**Important:** A tuned abstention policy is a *very limited* form of adaptation. This is not online model learning, meta-epistemic logic revision, or source authentication. Calibration can overfit tiny datasets. Policy selection never alters protected review keys, evidence signatures, or graph semantics.

## Report analysis and integrity

The study report retains:

- All v0.7 per-trial subreports including usage, failure flags, reasoning traces, and subreport checksums.
- Case-cluster paired bootstrap 95% descriptive intervals, with repeated trials of a case kept together; per-arm resource accounting; response stability across repetitions; and score breakdown by public category.
- Raw and adapted accuracy, abstention, coverage, Brier-on-answered and paired success differences; fit scores and selected thresholds from *calibration only*.
- Dataset/key digests, provider fingerprint, seeded trial order, budget configuration, and SHA-256 of the combined report.

```sh
python -m rei0 study-verify \
    --report live_study.json \
    --calibration-cases calibration_cases.json \
    --calibration-keys calibration_keys.json \
    --evaluation-cases evaluation_cases.json \
    --evaluation-keys evaluation_keys.json
```

The verification routine checks outer/subreport hashes, data digests, each trial's expected phase/seed/provider/budget, per-trial scores, adapted policy trained on calibration only, cluster intervals, resource accounting, and all analysis fields. **Regrading is not an attestation of actual external model responses**; someone who can rewrite both data and hashes can forge a self-consistent report. Independently anchor the hash or obtain authenticated provider receipts for stronger provenance.

## Legacy functionality

```sh
python -m rei0 benchmark-demo
python -m rei0 inquiry-demo
python -m rei0 revision-demo
python -m rei0 source-demo
python -m rei0 service-demo  # Unix sockets: macOS/Linux
```

## Research references and security

- `docs/STUDY_PROTOCOL.md` — preregistration, datasets, statistical units, adaptation and failure criteria.
- `docs/REI_0.8_DECISION_LOG.md` — implementation decisions and remaining open problems.
- `docs/BENCHMARK_PROTOCOL.md` — inherited 0.7 base benchmark.
- `docs/REI_Master_Blueprint_v1.md` — original philosophy and axiom specification.
- `SECURITY.md` — network, prompt, review boundary and evaluation-integrity limitations.
- `RELEASE_TEST_REPORT.json` — exact release-check details.

The fundamental principle remains: **unbounded *possibility* of epistemic challenge with bounded computation and independently enforced operational constraints**.
