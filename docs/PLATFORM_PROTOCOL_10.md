# REI-1.0 Integrated Research Platform Protocol

**Status:** implementation contract, research prototype. **Schema:** `rei0.platform.workspace.v1`.

## 1. Integration boundaries

The research workspace consolidates immutable *copies* of three existing artifacts; it does not rewrite them:

1. `graph`: a v0.1+ `EpistemicGraph` event document, fully replayed before import.
2. `revision`: a v0.6+ `RevisionJournal`, whose append-only events and change explanations are replayed before import. Replay alone does not authenticate reviewer signatures; the independent revision authority is a separate pre-import check.
3. `experiment`: a v0.9+ preregistered experiment report, checked by `verify_experiment()` against four original datasets and the adjudication manifest. This recomputes grades, calibration adaptation, paired comparisons, and usage diagnostics. It cannot establish that a provider executed the reported requests or that answer keys are factually correct.

REI-0.1–0.9 components remain available unchanged. The platform does not ingest arbitrary JSON as verified research.

## 2. Event and artifact integrity

Let `D` be a canonical JSON artifact and `Q(D)` its deterministic *validated summary*. The importer computes:

- `payload_sha256 = SHA256(canonical_json(D))`
- `summary_sha256 = SHA256(canonical_json(Q(D)))`
- `artifact_id = kind + '-' + first_32_hex(payload_sha256)`

For each new artifact, a single SQLite `BEGIN IMMEDIATE` transaction inserts a write-once artifact and a linked audit record with sequence, prior hash, artifact ID, artifact hash, summary hash, type, and timestamp. The event hash covers the canonical event body. Duplicate imports with the same validated content are idempotent and do not create a second event.

All `platform-verify` calls recompute the stored content digests and the entire audit chain. Graphs/journals are replayed again. **Experiment records are regraded at import, not on every workspace verification**, because raw answer keys are deliberately not copied to this database. To regrade, call `experiment-verify` with separately protected original datasets and adjudications.

`--expected-head` is a comparison with an externally retained digest; without an independent anchor, a sufficiently privileged attacker can replace a whole internally consistent ledger. Data integrity checks are not signatures, trusted timestamps, or remote attestation. SQL triggers stop accidental edits but can be disabled by privileged actors.

## 3. Reproduction inputs and privacy

- Experiment summaries keep the full registered input digests, provider mode, study ID, case count, per-arm measured success, abstention, calls, and reported tokens.
- The workspace persists the original experiment report, not the grading keys or independent reviewer manifest. Reports may contain sensitive model-generated text. Owner-only file permissions are used on creation, but backups and process privileges remain operator responsibilities.
- The web interface exposes only summaries and audit metadata; no arbitrary file reading, source bytes, raw prompts, evidence details, private keys, or local shell operations are available.
- Outputs from a scripted model have mode `scripted_fixture_not_empirical`, accompanied by a warning; real externally supplied reports have mode `live_external_model` but still lack provider attestation.

## 4. Local browser service

- Bind to `127.0.0.1` only. The interface supports GET/HEAD at `/` and `/api/summary` and refuses other paths/mutation methods.
- Require an expected loopback/localhost Host header, as a modest DNS-rebinding mitigation. Apply `no-store`, `nosniff`, `DENY` frame policy, strict CSP, and HTML escaping.
- The server has **no authentication**, so any process/user able to reach the loopback port can read the aggregate data. Do not treat loopback as a multi-user isolation boundary; use a separately authenticated reverse proxy only after a dedicated security review.
- Every request rechecks workspace integrity; failures return an error rather than an unverified research result.

## 5. Research claims and preconditions

`confirmatory_design_eligible` describes *registered design conditions only*. A report can be eligible while source labels, model identity, independence, or external task selection remain inadequate. Scripts are pipeline checks. Fair causal comparison requires matching actual compute by design, sufficient independently selected cases, repeated runs, protected answer keys, prepublished protocol commitments, independent reviewer authentication, and replication. The included sample is **not** such a study.

### Non-goals for 1.0

Real-model execution without external credentials; new neural weight training; unsupervised promotion of reasoning rules; automatic truth adjudication; public internet hosting; stronger-than-OS cryptographic protection of local workspace databases; provider-signed response receipts; remote-time attestation.

## 6. Next research tasks

Conduct independently curated and preregistered live pilot studies; evaluate the marginal benefit of recursive challenges at matched actual compute; use authenticated external labels and remote attestation where available; audit audit-head anchors outside the host; explore adversarial false-premise detection and abstention calibration without changing protected tests.
