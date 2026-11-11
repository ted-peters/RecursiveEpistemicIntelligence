# REI-0.5 Security and Trust Model

## Boundaries

- **Untrusted AI or client:** may request bounded retrieval from explicitly allowlisted hostnames; may submit a proposed excerpt from a server-held source; may submit caller-provided evidence under legacy compatibility paths, but all submissions remain pending until a separate authenticated review.
- **Verifier process:** controls its SQLite evidence and source ledgers; accepts signed decisions but provides no signer or private-key endpoint. When configured for Ed25519, it holds a public key only. Source retrieval is disabled by default.
- **Offline reviewer:** holds Ed25519 private signing key and inspects the actual source bytes and claim. The reviewer must not execute in the AI's trust domain.

## Retrieval restrictions

Allowlists are **exact hostname** matches; port 443 only; no HTTP, redirects, userinfo, IP literals, nonpublic DNS addresses, automatic decompression or HTTP proxies. DNS answers are resolved once and pinned to the connection; TLS validates the original hostname with the system CA trust store. The max body size is 2 MB and the network timeout is at most 20 seconds. Public hosts can still serve malicious documents or exploit the Python runtime via unspecified parser vulnerabilities; never execute returned content. The endpoint is for controlled research, not untrusted shared hosting or public access.

## Authentication and authorization

Ed25519 signing uses `rei0.review.v2` and registered public keys; signer secrets are **not included** in the public verifier config. The HMAC `rei0.review.v1` implementation remains for existing histories and compatibility, and does **not** offer this private/public separation. The service never offers `sign`, `approve`, or `revoke` RPC; even revocation requires a signed `accept` receipt. A compromised verifier host can still mutate its SQLite data and potentially cause availability damage or hide evidence unless audit heads are independently anchored and systems are isolated.

## Provenance scope

Source SHA-256 authenticates *archived bytes*, not the truth of statements. HTTPS provides transport authentication for the hostname at retrieval time, not proof of ownership, original publication, correct quotation, independence of studies, or factual validity. Capture metadata includes a leaf TLS certificate fingerprint and pinned IP, which are **observations**, not continuing guarantees. Exact excerpt matching is only a lexical check. For PDFs, only bytes are captured; human or external parser review is required.

## Persistence and rollback

Source records, bytes and chained audit events are stored in the same SQLite database as the original reviewed-evidence ledger; the two chains have separate hashes. Anchor **source**, **evidence** and **graph** heads outside the DB in a protected independent system. Full-database rollback or complete rewrite may not be detected by internal hash chains alone. Keep WAL-aware backups and verify them before restore. Database and socket filesystem modes are owner-only, but processes under the same OS identity may still access each other's data.

## Known production gaps

No authentication of a local peer beyond OS filesystem checks; no rate limiting; no HSM/private-key hardware protection; no Certificate Transparency validation; no independence of cryptographic public key trust provisioning; no publisher cryptographic attestation; no web page malware scanning; no HTML/PDF parsing; no trusted time stamping; no live network penetration testing; no daemon hardening; no distributed authorization policies or remote API. Do not assert that a `VERIFIED` item is true. Use `--source-host` only for fully understood hosts and an OS account isolated from the AI.

## REI-0.6 extension — evidence-based revision

`RevisionEngine` imports existing independently validated evidence decisions, and treats a reviewer-signed conditional rule as *authorization to conduct provisional inference*, not an externally validated truth. Rules are signed offline with an Ed25519 key and can only be verified with its public key; never expose the signer file to the LLM. Inference cycles, unknown nodes, unsigned/modified rules, method mismatches and unauthorized keys are rejected. The skeptical policy blocks inference from disputed premises.

Revision journals use SHA-256 chaining and optional externally stored heads. A malicious actor who can replace both journal and anchor can defeat rollback detection. The journal is separate from SQLite and updates are single-writer, not a distributed ACID transaction. Pin rule-set hashes to detect omitted rules. Neither HMAC nor Ed25519 signatures establish factual correctness; independent inspection and operational access controls remain required. See `docs/REVISION_PROTOCOL.md`.

## REI-0.7 benchmark-specific boundaries

The benchmark grade key is loaded into the local evaluator but never passed as an argument to `FixtureProvider.respond()` or `LiveProvider.respond()`. Do not allow an external model tools or access to local files holding the key. Public question text itself may have appeared in model training, so key separation alone is not proof against contamination. The bundled fixture is not scientific test evidence.

The REI arm uses the v0.2 inquiry engine, whose model-produced supports and attacks are **pending**, not authenticated proof. It rejects any REI run where the graph's direct evidence assessment is not `NEITHER`. Do not allow benchmark model output to construct signed reviewer credentials, or to access verification service administration.

Live benchmarking sends question text, context and tentative reasoning to an operator-selected HTTPS endpoint; keys are never included in the JSON prompt, and redirects are refused. This release does not provide a general SSRF sandbox against a malicious local operator configuring an arbitrary endpoint; deploy only to permitted hosts and keep secrets away from cases and response logs. No live provider compatibility test or external independent grading occurred in this release.

Benchmark reports have a SHA-256 checksum and replayed scoring, but this is **not** a signature. Keep a trusted copy of the digest outside the report file to detect replacement. Strict grading can be gamed or misrepresent semantic correctness. Treat calibration and uncertainty metrics as provisional research results only when test data and provider traces are independently controlled.

## REI-0.8 experimental integrity and adaptive decision restrictions

The study runner adds **no** path for the model to approve its own evidence or alter signed reviewer decisions. The policy fitter receives calibration-phase outcomes plus **calibration labels only**. Evaluation labels are held by the evaluator and used for post-policy scoring and replay, not for training the threshold or as model context. Exact duplicate prompt strings and overlapping case IDs across splits are refused; conceptual overlap, answer-key leakage through datasets or pretraining, and malicious user-provided cases remain possible.

Live study requests require both `--live` and `--acknowledge-live-costs` plus a model ID. The inherited provider fetches its API secret from `REI_LLM_API_KEY` and excludes it from study report metadata; the server endpoint itself is a trust choice. A preflight upper bound limits worst-case cumulative model calls, but does not cap provider billing in currency or guarantee prompt-data confidentiality. Reports contain questions, outputs, and traces, so avoid secrets in study data. Treat the wheel, JSON report and test corpus as research artifacts, **not a hardened execution sandbox**.

Study and subreport SHA-256 hashes provide integrity *relative to a trusted saved digest*, not authenticated provider execution. A forger with write access to files can replace the report, answers and hashes; require separate authentic signatures/anchor for strong claims. The adaptive policy only changes output/abstention categorization and does not revise operational safeguards, epistemic method registry, or source-review status. This release retains all earlier source verification and key-management threat-model limitations.

## REI-0.9 experiment boundary additions

- `experiment-preregister` hashes private answer-key and adjudication documents but does not disclose the key content in its output; **hashing is not encryption**, particularly for small, guessable answer keys. Protect the keys and keep the preregistration with an independently anchored record.
- Source/reference strings in adjudication manifests are declarative only; the tool cannot prove the named person reviewed a source. For consequential studies, use the existing asymmetric signature architecture in a separate controlled workflow or externally signed source judgments.
- The model API receives questions and intermediate reasoning contexts only. Do not run untrusted custom Python provider implementations with access to the evaluator; Python process isolation is not guaranteed.
- The live adapter accepts only explicit HTTPS requests and reads `REI_LLM_API_KEY` from the environment. Provider logs might retain prompts; avoid private data in benchmark questions. Avoid writing secrets into the experiment directory or reports.
- Checkpoints store report metadata and hashes of intermediate model payloads; they do not securely attest to a service's execution. A crash mid-trial may duplicate paid API calls upon resume.
- Maximum token/call ceilings are not spending guarantees. Configure upstream provider account budgets and monitoring separately.
- Report verification regrades and checks hashes; it cannot rule out colluding report authors, backdated preregistration files, or dataset contamination. All claims remain provisional.
