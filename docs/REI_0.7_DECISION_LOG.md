# REI-0.7 Decision Log — 2026-11-10

1. **Preserve REI-0.6.** No mutations to signed evidence, source retrieval, graph persistence, review authority, revision logic or legacy test APIs.
2. **Benchmark before stronger performance claims.** Implement reproducible comparisons first; never treat scripted fixtures as empirical results.
3. **Four conditions.** Single-answer baseline, ordinary self-critique, FIFO fixed-depth inquiry, and existing REI graph-frontier inquiry.
4. **Do not trust explanations as evidence.** All model-generated argument nodes remain pending. REI benchmark explicitly checks `NEITHER`.
5. **Explicit budget accounting.** Apply equal caps but record consumed calls and provider-reported tokens separately. A failed or oversized call still consumes budget.
6. **Separate scorer from model inputs.** Keys are locally loaded but never sent in model prompt payloads. This is a software boundary, not proof against training contamination.
7. **Strict reproducible grader.** Exact normalized strings with enumerated aliases; explicit abstention labels, conservative error scoring, uncalibrated confidence metric kept separate.
8. **Record variance honestly.** Seeded arm scheduling and paired bootstrap intervals do not erase small-sample or non-independent data limitations.
9. **Protect inference opt-in.** Offline by default; HTTPS JSON adapter requires an explicit `--live` flag, environment API token and provider-reported exact token usage; no redirects.
10. **Integrity not cryptographic attestation.** Report hash/regrading detects uncoordinated edits; source-of-truth preservation requires externally anchored report hashes.

## Unresolved work

Develop representative hidden held-out datasets; blind reference grading for open-ended tasks; provider-side reproducibility and snapshot pinning; repeated seeds; honest equal-*consumed*-compute treatment arms; calibrated confidence evaluation; real-evidence-enabled studies with signed source provenance. Scientific H1–H4 remain OPEN.
