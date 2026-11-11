# REI-0 v0.1.0 — Implementation Contract

**Status:** Deterministic research prototype; reconciles initial implementation details with `REI_Master_Blueprint_v1.md`.

## 1. State and graph

The implemented state is `(V, E, H, method_version, limits)`, not yet the full blueprint state `(G, M, B, H)` with challenge budgeting. `method_version` is a fixed non-empty string per graph; `H` is an ordered audit event list.

The graph is a *typed directed multigraph*. Objects are immutable dataclasses, but Python internal state is not a hardened security boundary.

Node types: `claim`, `evidence`, `argument`, `objection`, `method_claim`, `test`, `open_question`.

Edge types: `supports`, `attacks`, `depends_on`, `tests`, `revises`, `derived_using`, `duplicates`.

All new nodes/edges begin `pending`. Fields are explicitly named and validated. Every edge stores a method version equal to its graph's version. Node-level method context is inherited from the graph in this release, rather than repeated on each node.

## 2. Admissible evidence, not automatic truth

For a claim `p`, let `S(p)` be the set of **distinct source groups** of admitted supporting evidence; let `A(p)` be distinct groups of admitted opposing evidence. Then:

```
status(p) = (int(len(S(p)) > 0), int(len(A(p)) > 0))
  (0,0) = NEITHER
  (1,0) = SUPPORT_ONLY
  (0,1) = ATTACK_ONLY
  (1,1) = BOTH
```

An edge is admitted to the status ledger **only if all are true**:

- Its type is `supports` or `attacks` and target is the assessed claim.
- Its source is an `evidence` node.
- Both edge and evidence node currently have status `verified`.
- The origin of the evidence is not `model` (even if a caller labels that node verified).

These are *syntactic admission checks*. The prototype cannot establish that the evidence is true, independent, complete, or relevant. `SUPPORT_ONLY` means only that the current ledger has support without admitted opposition; it does not mean the claim has been proved.

Evidence from a `model` is conservatively excluded from admitted evidence in v0.1. External, human, or system provenance is still caller-declared and requires trusted verification infrastructure before use for consequential decisions.

Duplicate evidence group IDs collapse within each polarity. Explicit `duplicates` relations between evidence nodes collapse groups **only after the relation is verified**. Multiple edges from the same evidence source do not increase the independent-source count. Support and attack are tracked independently even if originating from the same source group.

## 3. Circularity semantics

Canonical justificatory dependency direction is **dependent claim → prerequisite**:

- `A supports B` induces `B → A`.
- `A depends_on B` induces `A → B`.

Adding either edge is blocked if its dependency arc creates a directed cycle in the existing justificatory dependency graph. Such a rejected action appends no event.

`attacks` is *not* itself a positive justificatory dependency; reciprocal attacks can be recorded and cannot grant positive support. `duplicates`, `tests`, `revises`, and `derived_using` do not create arcs in this initial cycle detector. Semantically equivalent language and concealed dependence are beyond its scope.

The graph does **not** perform general logical deduction, transitive proof search, or nonmonotonic argumentation semantics. In particular, claim-to-claim support does not change an assessment's evidence bits.

## 4. Provenance and audit

A `Provenance` contains:

```json
{
  "source_id": "observation-1",
  "source_kind": "external",
  "source_group": "original-study-a",
  "reference": "doi:example-or-url",
  "observed_at": "2026-11-10T00:00:00Z"
}
```

A SHA-256 fingerprint is deterministically computed from this declaration. It confirms byte-level identity, not authenticity of the source.

Valid review transitions are:

- `pending → verified`
- `pending → rejected`
- `verified → revoked`

Transitions record reviewer, reason, and time. A reviewer's exact ID cannot equal the object's source ID. This is an **identity-string sanity check only**; it is not authentication or verified independence. A revoked item remains in the event history and is excluded from future evidence assessments.

The audit log is event-sourced: adding an item or updating its validation produces an ordered event. Each SHA-256 event hash incorporates the prior hash. During `load`, hashes and sequential indices are checked and the events are replayed through the same structural graph validators. JSON snapshots contain the event list, not merely the final projected graph.

A fully privileged adversary could rewrite the entire file and recompute hashes. Authenticity requires a trusted external audit head, digital signatures, or access-controlled transactional storage, none of which are implemented here.

## 5. Operational constraints

- Graph-size limits are enforced by Python methods (`max_nodes`, `max_edges`).
- Method versions are not editable through an event.
- No tool calling, network access, execution of user-provided code, or autonomous external actions.
- Current local Python constraints are not an independent, adversarially hardened validator. The blueprint's external validator and protected evaluation set remain future work.

## 6. Determinism

All calculations sort event edges and source group labels so results are stable for identical graph history. A test or demo may inject a fixed UTC clock. Hash encoding uses canonical JSON with sorted keys and compact separators. No randomness or model inference is used.

## 7. Known implementation gaps

- No LLM proposer, challenger, external verifier, utility-ranked inquiry controller, or method promotion workflow.
- No general source/relevance authentication or automatic semantic duplicate detection.
- No probabilistic inference, calibrated prediction, or learned reasoning quality.
- No durable SQLite event database or multi-process transactions.
- No derived-dependency invalidation beyond direct evidence assessment after revocation.
- No separately authorized operational policy service.

The project should not claim to have established epistemic infinitism or improved AI reasoning from this prototype alone.

---

# REI-0.2 addendum — Bounded Recursive Inquiry Engine

The original v0.1 graph contract above remains applicable. In v0.2 the `questions` relation is added for `open_question -> claim-like` targets, and `explore_question` is a replayable audit event. This event records investigation of a question, *not* epistemic closure or external validation.

## New state and invariants

- Inquiry sessions serialize `(graph, root, queue, counters, trace, stop_reason)` with a SHA-256 checksum. Checkpoint reconstruction additionally runs original graph event replay validation.
- All generated claim/argument/objection/open-question nodes and associated edges begin `pending`, declared `source_kind=model`. They never receive evidence credit from inquiry alone.
- Questions are scheduled deterministically using bounded, model-suggested priority, then depth and insertion order. This is not a calibrated epistemic utility function.
- Initial generation and each challenge expansion are restricted to exact finite JSON shapes (see `INQUIRY_PROTOCOL.md`). Unknown fields do not alter runtime policy.
- A model cannot write arbitrary graph events or mutate evaluation rules through its structured response; it can only propose bounded strings and question priorities.
- A single inquiry can stop because of cumulative step, depth, model-call, reported-token, wall-time, graph, or frontier limits. `stop_reason` and remaining obligations are explicit outputs.
- Offline script fixtures replay fixed responses; live HTTPS Chat Completions mode is opt-in and may incur charges. Real provider interoperability was not verified in this release.

## Important qualification

Operational guards are still in-process Python checks rather than a separately protected service. Wall-time and token limits cannot guarantee the external inference provider will not exceed its latency or billed token usage. The graph/trace checksum remains unkeyed and cannot prove origin authenticity. `open_question` nodes are workflow obligations and do not themselves prove that a non-circular infinite justificatory chain exists.

---

# REI-0.3 addendum — Authenticated Evidence and Review

REI-0.3 adds `EvidenceLedger`, a new audited wrapper around the unchanged v0.2 graph schema. Claims, node/edge provenance, and method version are part of a review subject digest. Only a signed `ReviewReceipt`, authenticated through a separately configured `VerificationBoundary`, may enter the ledger's trusted accepted-evidence view. The legacy graph's caller-declared `set_validation` is kept for test compatibility but is NOT part of the new trusted assessment path.

All new submissions are unreviewed pending records with a SHA-256 of the original bytes. A trusted reviewer must explicitly examine the source and relevant link, then sign `verified` or `rejected`. A previously verified item may receive a signed `revoked` record. Each receipt authenticates a stable subject digest, review reason/time, reviewer key/identity, per-submission decision index, and previous review signature.

Replay verifies full graph events, evidence events, and each reviewer HMAC using independently supplied keys. The system fails closed on unknown keys and altered signed fields. The secure four-state evidence status uses only current signed approvals; it deduplicates exact source groups, references, artifact hashes and statement texts, and does not propagate derived claims.

This boundary authenticates decisions **only while reviewer key material is protected**. Same-process Python with shared environment secrets is not a hardened model isolation boundary. Production builds require protected review service, stable external audit anchors, durable transactional logging and independent source validation.
