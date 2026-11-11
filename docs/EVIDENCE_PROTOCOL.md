# REI-0.3 Evidence and Authentication Protocol

## Status

Version `rei0.evidence.v1`, 2026-11-10. This document defines deterministic, **procedural** admission of evidence under independently authenticated reviewer decisions. It does not specify epistemic truth or direct automatic fact verification.

## Threat model

**Untrusted:** LLM-generated claims/questions/reasons, externally supplied evidence text, artifact bytes, claimed reference and source identifiers, serialized ledger files, unauthenticated graph validation flags, and received review receipts.

**Trusted in the pilot:** independently supplied reviewer keys in `VerificationBoundary`, the ledger software's signature and graph replay implementation, an authorized human/operator who reviews an original artifact and its evidential relation, and optional audit-head anchors retained outside the ledger.

**Not covered:** compromise of the reviewer key or process, dishonest/confused reviewers, false source provenance accepted by reviewers, a malicious Python interpreter, or reliable semantic verification of natural-language statements.

## Source record

`EvidenceSubmission`: `submission_id`, `evidence_id`, `link_id`, `claim_id`, `artifact_sha256`, `submitted_at`. The graph independently records the evidence-node text, source kind, source ID, source group, exact reference, observation time, edge polarity, and method version. All new graph nodes and edges start `pending`.

The `artifact_sha256` value is computed from input bytes at ingestion time. These bytes are not stored in the JSON ledger. A later `evidence-check-artifact` call checks whether supplied bytes still match this hash. A matching hash attests byte equality, *not* original publication authenticity.

## Signed review receipt

Version `rei0.review.v1`. Exact fields are:

```
{
  "schema_version": "rei0.review.v1",
  "key_id": "...", "reviewer_id": "...",
  "submission_id": "...", "subject_digest": "<sha256>",
  "decision": "verified | rejected | revoked",
  "reason": "...", "issued_at": "UTC ISO8601 ...Z",
  "decision_index": 1,
  "prior_signature": "<64 lowercase hex>",
  "signature": "<64 lowercase hex>"
}
```

The `subject_digest` hashes a canonical JSON object with scope `rei0.evidence.subject.v1` and the immutable attributes of the submission, evidence node, support/attack edge, and target claim plus active graph method version. *Current mutable legacy graph validation flags are excluded* because a signed review applies to stable evidence content and relation, not the legacy status labels.

Signature uses HMAC-SHA256 with explicit domain separator `b"REI-0.3-REVIEW\\x00"`, a registered key of at least 32 bytes, and deterministic UTF-8 canonical JSON (sorted keys, no insignificant whitespace). Signature verification uses `hmac.compare_digest`.

Reviewer key ID and identity are bound by a key registry supplied **outside the ledger**. Key permissions independently distinguish verify/reject and revoke. The `reviewer_id` must differ from the declared evidence `source_id`, and model-origin evidence cannot be approved. These are necessary checks, not proofs of human or organizational independence.

## Transition table

| Current review status | Allowed next signed decision |
|---|---|
| `pending` | `verified`, `rejected` |
| `verified` | `revoked` |
| `rejected` | none |
| `revoked` | none |

Each review receipt is linked to the previous signed receipt for that submission. Replay and duplicate decisions fail because the next `decision_index` and `prior_signature` must match. A separate `evidence-sign` command produces a portable signed receipt, without granting credit; `evidence-accept` verifies the receipt and atomically records the review in the logical ledger. (The prototype uses in-memory edits plus a JSON file save, not a transactional database.)

## Trusted assessment

`EvidenceLedger.assess(claim_id)` includes an evidence submission only when its latest **authenticated** review is `verified`. The verdict is four-state: `(support_present, attack_present)`, mapping to `NEITHER`, `SUPPORT_ONLY`, `ATTACK_ONLY`, `BOTH`. Both polarities are preserved if contradictory information is admitted. No confidence probability or universal conclusion is inferred.

Exact source-group identifiers, exact references, identical original-byte SHA-256 hashes, or identical evidence text collapse source credits **within each polarity**. These are only heuristics for duplicate/dependent evidence, not universal guarantees of independence. Stronger entity resolution and citation network analysis are future work.

`EpistemicGraph.assess` remains an intentionally backward-compatible **untrusted legacy view**. The authenticated view is `EvidenceLedger.assess`. Never use the legacy view for consequential trusted evidence decisions.

## Replay and tamper evidence

The evidence ledger serializes `{schema_version, graph, events}`. The graph contains its own event chain. Evidence events `submitted` and `reviewed` form a second ordered SHA-256 hash chain. Loading the ledger checks both chains, typed graph rules, submission-to-node/edge bindings, registered reviewer signatures, method/target/content binding, review transitions, and complete serialization round-trip. The reviewer key is not exported.

Hash chains alone are *not* an authenticity anchor. Truncation to an earlier valid snapshot remains possible if the observer does not know a separately trusted previous head. `evidence-verify --expected-head ... --expected-graph-head ...` supports comparison with an externally retained anchor.

## Replayable tests and failure conditions

The tests cover pending evidence remaining `NEITHER`, all four information states, signature tampering (including a modified review with a recomputed unkeyed audit hash), altered claim content with a recomputed graph hash chain, wrong or unregistered signing keys, reviewer permission constraints, circularity preservation, group/artifact/reference/text deduplication, signed revocation, loss of a key, duplicate signed receipt replay, empty/oversized artifact failures, and command-line sign-then-accept flows.

A release fails if unreviewed evidence earns status, a signed revocation fails to remove credit, a changed claim can reuse an earlier approval, or unauthorized keys authenticate.
