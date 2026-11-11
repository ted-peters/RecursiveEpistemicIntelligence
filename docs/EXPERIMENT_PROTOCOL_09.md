# REI-0.9 Preregistered Experimental Protocol

**Status**: implemented research infrastructure; no live experimental results. Version 0.9.0.

## Research hypotheses and preregistration

Primary, preregistered two-sided comparison: mean paired difference in *overall success* between `rei` and a selected comparator (`baseline` by default) on held-out evaluation cases over repeated trials. `overall_success` means correct reference answer on answerable tasks, or appropriate abstention on unanswerable tasks; error states are never credited. All four arms use the same model, split and resource maxima. Analysis includes unadapted results (primary) and calibration-only abstention adaptation (secondary). PREREG JSON commits via SHA-256 to datasets, private key-set digests, reviewer declarations, provider fingerprint, implementation code fingerprint, trial count/seeds, resource limits, and analysis plan. The date in the JSON is self-declared; timestamp or anchor the hash externally before inspecting held-out outcomes.

## Ground truth and reviewer declarations

Use `rei0.benchmark.cases.v1` + `rei0.benchmark.keys.v1` split files. `rei0.adjudications.v1` binds *each* key record to the SHA-256 of its exact JSON, a curator, different reviewer, reference, and declared review method. For real tasks, collect supporting source records or proof traces and obtain blinded, independent verification externally. A declaration is not an authenticated reviewer signature, and a correctly structured answer key can be false. Synthetic fixtures are labeled and cannot establish performance.

## Execution order, budgets, and leakage risks

For each of calibration and evaluation, repeat randomized paired benchmarking using the same base model and immutable limits. The experiment runner checks preregistration, answer-key and evidence-manifest digests before making any model call. Provider identity mismatch is rejected before the first trial. The model receives questions and intermediate reasoning state, not grading keys. Calibration threshold fitting uses calibration outcomes only. The reported model fingerprint identifies a configured model/endpoint, not an independently attested model snapshot. The live provider uses HTTP JSON and provider-reported total tokens; it does not measure GPU time, dollars, FLOPs, or energy. It may be affected by API caching, model drift, response variability, service rate limits, outages, prompt contamination, or hidden dataset leakage.

`max_calls`, `max_tokens`, `max_output_tokens`, `steps`, `max_seconds`, and `max_total_calls` are ceiling controls. A trial error remains an error; network failures can incur provider charges. Any interrupted *in-flight* trial must be restarted, possibly at added cost. Completed trials are retained as a digest-protected JSON checkpoint, validated via nested score regrading, and replayed on resume.

## Comparability analysis

Each REI-vs-comparator pair (same evaluation case/trial) records provider-reported tokens and actual model calls. `exact_usage_match` requires equality in both. `within_preregistered_tolerance` requires the same number of calls and relative token difference <= frozen tolerance, using the maximum of the two token usages as the denominator. The **primary analysis keeps every trial**, including failures; matched subsets are supplementary and vulnerable to selection bias. A preregistered minimum evaluation-case count and usage-match flag make a design *eligible* for further inferential assessment, not confirm a positive effect. No advantage claim follows automatically.

## Inference, replication and reporting

- Report all four arms, unadapted and adapted scores, paired success differences, case-cluster bootstrap intervals, call/token use, source quality, and failures.
- Do not treat repeated responses to one question as independent tasks; the inherited bootstrap resamples case IDs.
- Preplan a suitable power/precision analysis for the proposed domain; 30 cases is merely a software-defined warning threshold.
- Audit provider-side billing and model versions separately; where possible, include stronger matched-compute controls (e.g. best-of-N baseline under equivalent costs) in a subsequent study.
- Inspect factual explanations and hallucinations independently, not solely by exact-string grading.
- Report negative and null results, dataset selection, missing trials, and all deviations from preregistration.

## Security and integrity

SHA-256 hashes provide tamper-evidence only when independently anchored; a party controlling both data and hashes can forge a consistent report. The experimental runner is not a production sandbox, a confidential multi-tenant grader, or a provider attestation service. No answer key is sent to the model through the intended code path, but a malicious Python plugin/provider running inside the same interpreter is not an isolation boundary. Keep keys and reviewer identities protected by OS permissions and separate trusted environments.
