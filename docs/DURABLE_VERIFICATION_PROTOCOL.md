# REI-0.4 Durable Verification Protocol

**Protocol:** `rei0.sqlite.v1` and `rei0.challenge.v1`.

## State and invariants

A durable state is `(D, rev, E, A)`, where `D` is the canonical v0.3 evidence-ledger document (containing the graph and signed audit history), `rev` a strictly increasing commit revision, `E` the relational mirrors of submissions/events/reviews, and `A` content-addressed original source artifacts.

Every mutation must commit **atomically** all of: (1) the graph/ledger snapshot, (2) new normalized rows, (3) original artifact bytes when submitting, (4) audit-chain events, and (5) a request-id/response record. A rejected operation must leave all five unchanged.

The store's replay checker reconstructs a v0.3 `EvidenceLedger` under independently supplied reviewer keys, checks its graph/evidence event hashes and receipt authentication, compares the relational mirror with reconstructed objects, rehashes every retained source artifact, and refuses missing bytes unless explicitly marked as a legacy-import gap.

A revision is not an epistemic justification level. It is a database commit counter.

## Read RPCs

Every request and reply is one newline-delimited UTF-8 JSON object on an owner-only Unix stream socket. Requests are at most 3,100,000 bytes; responses are at most 1,000,000 bytes. The server deliberately does not have a signer endpoint.

- `status` with `{}`: revision, submission/review counts, evidence and graph audit heads.
- `challenge` with `{ "submission_id": "..." }`: signed-subject digest, prior receipt signature, next sequence number, source/provenance preview, and artifact hash for independent review. The challenge itself is **not** cryptographically signed and must be obtained over a trusted service connection; final receipt verification prevents a mismatched challenge from being accepted.
- `assess` with `{ "claim_id": "..." }`: the current verified four-state assessment.
- `verify` with `{ "expected_head": "...", "expected_graph_head": "..." }` (both optional): replay, integrity and optional externally anchored comparison.

## Write RPCs

Every write includes `request_id`. An unchanged, already committed request ID returns its recorded response; changing its operation, payload or expected revision produces an error.

- `submit`: claims an evidence node, source provenance, polarity and base64-encoded original bytes; adds a PENDING submission only.
- `accept`: receives an externally signed, authenticated `ReviewReceipt`; checks all v0.3 review invariants before appending a decision.

Optional `expected_revision` provides optimistic concurrency protection, preventing stale writes. SQLite's `BEGIN IMMEDIATE` ensures a serialized writer; `WAL`, `synchronous=FULL` and foreign-key checking provide database atomicity under normal SQLite filesystem assumptions.

## Human review and signing

The independent `operator-sign` command reads a challenge and protected signing secret from **local files**, verifies exact original SHA-256 for `verified`, and writes a portable signed receipt to a fresh file. It does not access the database and cannot submit directly. The service verifies whether the challenge is current when it later receives `accept`.

A registered reviewer must not be the declared source ID. Verification of cryptographic receipt does not validate factual statements, publication ownership, measurement integrity, or reviewer competence.

## Migration

`service-import` replays `rei0.evidence.v1` from 0.3 using the registered keys. Since old JSON has no artifact BLOBs, all imported submission IDs are explicitly marked `legacy_artifact_gaps`; they will appear in integrity reports until source bytes are recovered and verified. Missing bytes after *new* 0.4 submissions are always an integrity error.

## Termination and recovery

SIGTERM and Ctrl-C stop the process and release its socket. When restarted, database startup replays and validates the entire ledger. Open transactions are recovered by SQLite. The caller can safely replay a write with the same request ID and identical payload after a lost response. Use SQLite-aware backup and independent audit anchors for disaster recovery and rollback detection.

## Future upgrade proposals

- Asymmetric reviewer signatures / hardware or remote signer, so the verifier need not hold forging-capable secrets.
- Key rotation and retention policies for historical receipts.
- Dedicated provenance verification plugins, independent source retrieval, source authority metadata.
- Structured human review tools and signed external audit-head append service.
- Automatic dependency-aware belief revision and benchmark evaluation of epistemic improvement.
