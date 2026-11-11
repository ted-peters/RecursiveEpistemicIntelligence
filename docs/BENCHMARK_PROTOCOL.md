# REI-0.7: Paired Benchmark and Evaluation Protocol

**Status:** implemented research harness, synthetic integration study verified. No claim of model superiority.

## 1. Research questions

- H1: Does an explicit recursive epistemic graph improve objective task success over a single-pass model at a specified compute allowance?
- H2: Does it improve success over standard draft→critique→revise prompting?
- H3: Does graph-frontier prioritization and traceability improve outcomes compared with FIFO fixed-depth questioning?
- H4: Does recursion improve abstention on underdetermined tasks without excessive over-abstention?

These hypotheses are OPEN and NOT supported by the bundled synthetic response fixture.

## 2. Experimental units and data splits

A case has `{id, question, context, category}`; the independent key has `{case_id, acceptable, unanswerable}`. Both documents have schema tags and are checked for exact field sets, duplicate IDs, missing labels and malformed answers. Public questions and context are provided to all arms unchanged; key records are passed only to the evaluator. No source-retrieval or grading-key tool is available to the model.

The bundled eight-case dataset is an executable *contract fixture*, not a held-out scientific benchmark. Independent studies should keep hidden cases outside development and prompt-selection paths, preregister metrics and use sufficiently representative tasks.

## 3. Four treatment conditions

1. **Baseline:** one final answer.
2. **Self-critique:** draft, critique, revised answer.
3. **Fixed depth:** identical initial and expansion JSON formats, FIFO challenges, no persistent epistemic graph.
4. **REI:** actual REI-0.2 `InquiryEngine`, priority-ordered frontier and auditable typed graph, followed by final answer. The graph contains provisional model arguments and does not change the evidence ledger.

Each case/arm has a meter enforcing the *same maximum* calls, tokens, wall time, and per-call output cap. No failed call is free. Reported token overruns are recorded and treated as failed trials. Model requests are scheduled by seeded shuffle; this mitigates simple fixed-order confounding but does not eliminate provider caching or stochastic variation.

## 4. Outcome data

Every trial retains:

- `case_id`, `arm`, `answer`, `confidence`, `rationale` or explicit error;
- number of model calls and provider-reported total tokens;
- stage trace with stage, usage and SHA-256 of model payload, no API key;
- high-level algorithm metadata, including REI graph audit head, steps, frontier size, stop reason and verified evidence state.

A failed trial has `error!=null`, and *always* scores incorrect. A valid `answer=null` with `error=null` is an explicit abstention. Confidence is the probability the proposed answer is correct, not an ungrounded claim of truth or independently verified support. Abstention requires confidence=null.

## 5. Primary and secondary metrics

Primary: `overall_success`, computed as exact reference-match for answerable cases, plus correct abstention on declared unanswerable cases. Secondary: answerable accuracy, selective accuracy, coverage, incorrect guesses on unanswerables, Brier on *answered cases with non-null numeric confidence*, mean paired score difference, nonparametric case-level bootstrap interval, and consumed calls/tokens.

The report includes an *exact measured-usage subset* for each REI-versus-comparator pairing: only a case with identical reported total tokens **and** number of calls in both arms enters this subset. Equal reported tokens are not necessarily equal FLOPs, money or runtime. The broader paired comparison should never be mislabeled as equal-compute.

The bootstrap uses reproducible fixed-seed sampling with replacement of paired case-level score differences (1000 repetitions). It is not a valid generalization guarantee when cases are handcrafted, contaminated, or otherwise nonrepresentative. Intervals are exploratory.

## 6. Data-integrity and security semantics

Canonical SHA-256 fingerprints bind the report to the public questions and answer key; verify command recalculates scores and intervals. Self-consistent rewrite attacks remain possible without an external trusted head or digital signature. An external model provider must not be given signer private keys, grader references, authenticated evidence review APIs or unilateral ability to update the underlying signed ledger.

The REI arm's `evidence_state` must equal `NEITHER` in this first experiment; otherwise the run fails. A future evidence-enabled experiment must carry signed review receipts and source provenance through a separately authorized verification boundary rather than accepting LLM-generated citations.

## 7. Known limitations and next extension

- Single sample per case/arm; no repeated stochastic trials or evaluator-blind adjudication.
- Exact-match grading undercounts semantically equivalent answers unless aliases are enumerated.
- No standardized full cost accounting (latency, device energy, provider-specific billing, FLOPs).
- Self-critique gets three calls, baseline gets one, fixed-depth and REI get up to four; shared upper limits are **not equal consumed compute**.
- Sample prompts and stages are not proven optimized or fair to every approach.
- Scripted fixture outputs and usage are fabricated to exercise accounting and comparisons.
- Live external API behavior, rate limits and provider compatibility are not integration-tested here.
- Brier labels reflect benchmark correctness, not philosophical justification.

**Release criterion:** software can run, replay, budget, grade, and audit controlled experiments. Scientific success would require a separate preregistered live-model study with independent evaluation.
