# REI-0.8 decisions — 10 November 2026

1. Keep 0.7 algorithms, graph evidence semantics, authorization service and signed rule protocol unchanged. The study runner orchestrates existing `run_benchmark` rather than redefining what REI means.
2. Require disjoint calibration/evaluation case identifiers and exact normalized prompt fingerprints. Recognize that semantic near-duplicates remain possible.
3. Never select adaptive policy from evaluation labels; fit one per-arm confidence threshold from calibration grades, then freeze before evaluation analysis. Existing model responses are immutable for scoring and replay.
4. Classify adapted thresholding as a **limited decision policy**; do not misrepresent it as neural-network training, epistemic logic revision, independent fact verification, or an evolved AI.
5. Track repeated trial grouping by case and randomize stage/case treatment order per repetition. Use case-level bootstrap, not naïve trial-level independent resampling.
6. Preflight worst-case provider calls and require explicit operator consent for live network calls. Retain per-case call/token caps, signed evidence boundaries and no automatic source approval.
7. Report actual resource disparities and warnings against calling unequal consumption 'equal compute'. Emit full raw and adapted measures, including failures and Brier on numeric-confidence answered trials only.
8. Regrade every nested report as well as the policy/analysis under preserved answer keys, and record canonical report SHA-256. Hash checking is integrity against accidental/unanchored modifications, not signer authentication.
9. Preserve 267 inherited tests and provide additional regression coverage for budget caps, withheld labels, tampering, repeated trials and CLI usability.

Open: cross-provider API compatibility, true stochastic repeat independence, external oracle construction, real-time source-grounded test tasks, independent attestation, matched-cost algorithms, prospective research findings, more general adaptive epistemic policies.
