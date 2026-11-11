# REI-0 Decision Log

| Decision | Status | Motivation |
|---|---|---|
| A: Every epistemic commitment remains challengeable | Adopted from blueprint | Philosophical openness without absolute certainty |
| External operational guard, not AI-controlled | Required by blueprint; not fully implemented | Separate epistemic critique from executable authority |
| Four-state evidence information (`NEITHER`, `SUPPORT_ONLY`, `ATTACK_ONLY`, `BOTH`) | Implemented | Represent contradictory evidence explicitly |
| Only verified evidence-edge pairs affect evidence status | Implemented | Prevent unsupported argument chains from being laundered into evidence |
| Model-origin evidence excluded from admissible evidence | Conservative implementation rule | A model's assertion is not independently checked observation |
| `source_group` + verified duplicate edges define source dependence | Implemented | Do not count republished evidence multiple times |
| No positive justificatory cycles | Implemented on explicit graph arcs | Block obvious circular support without claiming semantic completeness |
| Event history with SHA-256 hash chaining | Implemented | Reconstruct updates and detect local unanchored tampering |
| Single fixed method version per graph | Implemented | Avoid self-approval until method registry exists |
| No confidence probabilities | Implemented | Don't invent calibration |
| JSON snapshots, not SQLite | Initial simplification | Enables zero dependencies and deterministic samples; production persistence later |

**Important:** The review identity in `verified_by` is a declaration, not an authenticated external approval. In later releases, independent verification must be enforced by trusted code outside the model process.

## 2026-11-10 — REI-0.2 recursive inquiry engine

- Add an isolated inquiry controller rather than changing v0.1 evidence admission rules.
- Add `questions` edge to link an explicit open obligation to its challenged claim/argument.
- Introduce `explore_question` audit events; explored means the controller processed the obligation, not that a final justification was established.
- Accept only strict, bounded JSON drafts. The engine creates all node IDs and provenance itself; model output remains pending.
- Use deterministic priority/depth/order scheduling as a reproducible baseline. Model-proposed priorities are **not** trusted quality estimates.
- Preserve checkpoints with hash checks and graph event replay; do not misstate hashes as authentication.
- Expose an offline scripted adapter by default for `inquiry-demo`; require explicit `--script` or `--live` for arbitrary `inquire` commands.
- Allow a minimal HTTPS Chat Completions adapter for opt-in experimentation. No external evidence tools or side-effecting actions are available to the model.
- Defer hardening (authenticated review, SQLite transactions, signed trace anchoring, independent critic calibration) to a future release.

## REI-0.3 decisions — 2026-11-10

- Added a new versioned evidence ledger rather than modifying the legacy graph validation semantics, preserving REI-0.1/v0.2 regression behavior and making trusted admission explicit.
- Selected offline HMAC-SHA256 signed reviewer receipts as the first authenticated boundary. Keys must be supplied independently of the graph/model. This is not a production sandbox, identity provider, or factual verification system.
- Kept original artifact bytes outside the ledger, storing their SHA-256 and a link to the claimed provenance. Added an exact byte recheck command.
- Added signed revocation, verified review-sequence chaining, and evidence audit replay. External hashes are needed to detect full rollback.
- Applied conservative exact matching for source duplication. Semantic independence detection remains an open research problem.
- Separated two stages: reviewers sign, then the ledger independently verifies and accepts the signed decision. An explicit local shortcut is retained for experimentation.

## REI-0.4 — 10 November 2026

- Retain REI-0.3 signed receipt format and trust verification, but remove issuance capabilities from the new verification service RPC.
- Introduce SQLite atomic snapshots + normalized event/review/submission mirrors + original bytes. A missing original for a new submission is an integrity failure.
- Explicitly mark old v0.3 evidence imports as lacking original bytes rather than inventing recovery.
- Use per-request idempotency and stale-revision guards for safe retry and concurrency.
- Keep signer credentials outside the service's public interface; clearly document that HMAC is symmetric and same-UID process separation is not a hardened boundary.
- Preserve earlier code paths for regression only; new trusted applications must use the service verification path.
