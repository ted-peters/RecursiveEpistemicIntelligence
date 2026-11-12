# Challenge 9 — Signed-Evidence Revisions and Paired Model Pilot

**Status: engineering experiment.** This work extends REI 1.2's authenticated
adaptive controller without changing the frozen REI 1.0/1.1/1.2 modules or
any earlier experiment results. The initial automated audit is **synthetic**
and uses **no model inference**. The real-model pilot runs only after explicit
GitHub Actions dispatch; it has not been run by adding this code.

## Question

Can signed-review-aware adaptive reasoning handle contradictory, revoked,
duplicated and forged evidence more reliably—and at a competitive cost—than
a capable conventional self-critique method that receives the **same review
information**?

The immediate test is split into two distinct claims:

1. **Security/engineering:** Does the authentic REI EvidenceLedger agree with
   a separately implemented event reducer at every checkpoint? Are forged
   "verified" labels ignored, revocations honored, and model-authored reports
   excluded? This is what the free automated audit verifies.
2. **Empirical reasoning:** Does the REI 1.2 two-arm protocol achieve more
   correct **answers** than self-critique under the same model, interface
   constraints and **measured** actual token/time use? The real-model runner
   can measure this; the included fixture cannot.

We must not conflate these claims. Even a successful real-model test on
these **public** cases would be only an exploratory development result.

## What is implemented

- `interventions.py`: generates 12 cases balanced among the four final
  evidence states (three each), each with signed approvals, signed revocations,
  source-group duplication, two forged unsigned validation labels, and a
  model-origin report. Checks the signed EvidenceLedger against a **separate**
  chronological reducer after every event. A new ephemeral Ed25519 signer is
  used for each case; **no private signing keys are retained or passed to any
  model**. The signed ledger is reloaded using the public verification key.
- `public_docket()`: exposes only source group, source kind, polarity, and
  current signed-review status. Does **not** expose the final state, scoring
  key, private key, receipts, or model answer. A model could derive the state
  from this evidence, as it should.
- `paired_trial.py`: runs `self_critique` versus `rei12` on identical
  dockets with the same model and budget ceilings. The conventional arm uses
  draft -> critique -> final. REI 1.2 starts with a provisional model proposal,
  lets its signed-ledger-aware controller conditionally run **at most one**
  expansion, then requests a final answer. Its controller's internally
  computed aggregate state is **not** placed directly into the final prompt.
  The conventional model has the corresponding per-document statuses, so
  both have logically sufficient information, though the scheduling
  controllers are not identical.
- `arm_blind_provider.py`: a dedicated schema-constrained local Qwen adapter
  that excludes the arm and case ID from the **model request**, while
  recording them in local audit logs. Failed parses still contribute
  server-reported tokens where available. Network timeouts may have unknown
  usage and must not be counted as zero-cost inference.
- `run_trial.py`: runs a cheap offline fake-provider integration test,
  or a separately activated pinned local-model experiment. Independent
  regrading verifies coverage, scores, paired comparison and checksum.
- `tests/test_challenge9_interventions.py` and
  `tests/test_challenge9_trial.py`: offline software checks with no
  external model or paid API use.

## Predeclared exploratory pilot

| Item | Value |
|---|---|
| Primary comparator | Self-critique vs signed-adaptive REI 1.2 |
| Model | Qwen3-4B-Instruct-2507 Q4_K_M (same pinned SHA-256 as Challenge 8) |
| Inference | Same pinned llama.cpp b12242, temperature 0, seed 711 |
| Development cases | 4 by default; options 8 or 12; all **public, not blind** |
| Maximum calls per case | 3 for each method |
| Reported token ceiling | 2,600 per case |
| Time ceiling | 140 seconds per case |
| Output cap | 320 tokens per turn |
| Adaptive inquiry | At most 1 expansion; stop score threshold 22, reserve 320 tokens |
| Primary metric | Paired difference in final-state exact-match correctness |
| Additional metrics | Failed cases, abstentions, model calls, server-reported tokens (including failed parses), unknown usage, elapsed time |
| Actual compute-matched? | **No**; comparable ceilings only |

The 22-point threshold deliberately makes the first prototype more likely to
inspect contradictory signed evidence and stop elsewhere, but model-proposed
question priority can affect this decision. This threshold is a declared
heuristic, **not** a calibrated expected-value estimate.

### Run the entirely free audit and synthetic comparison

```bash
python -m pip install .
python -m unittest discover -s tests -p test_challenge9_interventions.py -v
python -m unittest discover -s tests -p test_challenge9_trial.py -v
python -m research.challenge9.interventions --count 12 --output challenge9-results/signed-audit.json
python -m research.challenge9.run_trial --mode fixture --count 4 --output challenge9-results/paired-fixture.json
python -m research.challenge9.run_trial --mode fixture --count 4 --verify-only --output challenge9-results/paired-fixture.json
```

The fixture responds with `NEITHER` irrespective of the evidence. Its
accuracy numbers are **programming fixtures**, not measured AI results.

### Run an actual local-model paired pilot (opt-in)

The file `.github/workflows/challenge9-signed-evidence.yml` contains a
manual `workflow_dispatch` with `mode=live` and
`case_count=4`/8/12. A workflow must be available on GitHub's default branch
before its manual dispatch reliably appears in the Actions UI; the development
branch can still run the automatic free audit on push.

Live mode downloads a pinned open-weight model, compiles llama.cpp, runs both
methods, independently regrades the JSON report and writes a visible Actions
step summary. Artifact upload is **best effort** because an earlier run had
a GitHub upload-service error. No external paid inference endpoint is required,
though GitHub runner minutes and compute are consumed. **Do not treat results
as authoritative if the job aborts before recording a complete paired report.**

## Critical limitations

1. Reviewer signatures authenticate **review decisions**, not factual
   accuracy or real-world independent source authenticity. All documents,
   reviewer approvals and answer keys here are *synthetic*.
2. The signed development fixtures are built by a trusted test harness before
   inference, and signing capabilities are not passed to model code. A
   production deployment would require a separately isolated review
   authority and an externally anchored ledger.
3. Cases and generator logic are public, with overlapping task ideas from
   earlier Challenges 7/8. These do not qualify as a novel blind holdout.
4. Same model and maximum budgets do **not** ensure equal consumed compute.
   Distinguish server-measured token totals from unknown failed-call usage.
5. REI's controller has structured signed-state assessment available to its
   scheduler. Self-critique receives each individual signed-review status and
   can calculate that aggregate itself. This supports a useful diagnostic,
   but is not a perfectly matched algorithmic intervention.
6. No trained REI model is created: REI is an evidence-aware orchestration and
   reasoning-control research prototype.

**Next scientific milestone:** an independently held, unpublished case set
with a strong conventional model, equivalent evidence/tool interfaces,
multiple seeds, independent grading, and matched actual model computation.
Only replicated results on that design could support a broad advantage claim.
