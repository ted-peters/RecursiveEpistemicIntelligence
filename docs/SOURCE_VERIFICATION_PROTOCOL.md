# REI-0.5 Source Verification Protocol

**Status:** implemented research prototype · Version 0.5.0 · 2026-11-10

## Threat and authority boundaries

The REI reasoning engine and arbitrary clients are untrusted. They can request retrieval from an *operator-configured exact hostname allowlist*, submit a proposed excerpt, and ask for evidence assessment. They **cannot** create reviewer signatures via the verification-service RPC. A trusted offline operator controls an Ed25519 private key. The verification service holds a separate public key only; the inherited HMAC mode remains for compatibility, not as the recommended secure deployment mode.

Network retrieval is **disabled by default** until `service-serve --source-host HOST` is supplied. Even then, clients with socket access can cause requests to the allowlisted hosts; restrict socket access, authenticate callers at the OS boundary, and rate-limit externally in a real deployment. Do not deploy this as an open proxy.

## Protocol

1. Client selects an allowlisted HTTPS URL and immutable `retrieval_id`.
2. `SecureSourceFetcher` enforces HTTPS, port 443, no credentials, no fragments, no literal IP, exact hostname allowlist. It resolves A/AAAA records and rejects *any* non-globally routable address. It pins a validated IP for the TCP connection, using the **original hostname** for TLS certificate validation and SNI. No proxies or redirects are followed. The fetch has a finite timeout, an allowlisted MIME type, and a 2 MB response limit; HTTP 200 is required. No response decompression is performed.
3. Verifier records original response bytes and immutable source metadata (URL, retrieval timestamp, pinned IP, leaf certificate SHA-256 fingerprint, content type, byte count, content SHA-256).
4. SQLite commits the source record, content-addressed original BLOB, and chained audit event atomically; `source_audit_head` can be anchored externally. Reopening an old v0.4 SQLite file automatically adds the source tables without invalidating the v0.4 ledger.
5. `source-submit` references a previously captured `retrieval_id`; client cannot override the captured bytes or claimed source provenance. For UTF-8 textual formats, the proposed excerpt must be an exact substring of the archived bytes. The evidence remains **PENDING**. For PDF, text matching is not attempted and a reviewer must inspect the original manually.
6. `service-challenge` returns the current claim, excerpt, provenance, artifact hash, decision index and previous-signature reference. The independent reviewer retrieves and inspects original bytes, checks the hash, evaluates the claim/source relationship, and signs with an **offline Ed25519 private key**.
7. `service-accept` verifies the signature against the verifier's registered public key, permissions, subject digest, state transition, review order, and audit history before granting evidence credit. Signed revocations remove the credit without deleting the historical receipts.

## Signed review format and migration

- Historical `rei0.review.v1`: HMAC-SHA256, 64-character hex signature. Kept byte-compatible with 0.3/0.4 for audit replay and migration.
- New `rei0.review.v2`: Ed25519 signature, 128-character lowercase hex. Domain-separated canonical UTF-8 JSON input with prefix `REI-0.5-ED25519-REVIEW\0`. Private keys are 32-byte raw Ed25519 seeds. Public-key trust records contain 32-byte public keys only.
- Both formats bind to `key_id`, `reviewer_id`, `submission_id`, `subject_digest`, decision, reason, issued_at, decision_index, and prior_signature. A linked chain may contain old or new review signatures. **The trusted registry chooses the algorithm**, not untrusted receipt input.
- `service-keygen` continues creating symmetric HMAC credentials. `service-keygen-ed25519` creates `rei0.signer.v2` (private) and `rei0.trust.v2` (public only). Keep private files offline and out of the model environment. Do not blindly trust a public key sent by a submitter.

## Source audit semantics

- Audit genesis head: `"0" * 64`. Each event hash is SHA-256 over canonical JSON with `previous_hash`, sequence number, and the full immutable source metadata.
- Content SHA-256 binds stored original bytes to source records. The source-to-evidence link binds a submitted evidence artifact hash to one archived source capture and is validated on replay.
- The `service-verify --expected-source-head` option compares the current source head with an externally stored value. Without a trusted external anchor, an attacker who can replace an entire SQLite database can construct a different internally consistent history.
- A new capture of the same URL must use a new retrieval ID. Distinct captures may differ over time; do **not** assume a URL is immutable. A new TLS certificate fingerprint alone does not imply malice.

## Not automatically established

- HTTPS proves that the fetch reached a TLS endpoint authenticated for the hostname according to the operating trust store at retrieval time. It **does not** prove the publisher's scientific claims, independent authorship, research quality, absence of later changes, or human reviewer correctness.
- Certificate fingerprint is recorded, not pinned across historical sessions; certificate rotation is expected. This prototype does not inspect Certificate Transparency or detect domain ownership changes.
- Exact substring checks support traceability, not relevance, validity, or semantic truth. HTML text can be broken by markup; PDF is not OCRed. Content on the web is untrusted input—never execute active content, HTML scripts, PDFs, or model-output instructions.
- Source grouping currently uses the exact hostname for independence accounting; shared ownership or mirrored documents across different hostnames may be correlated. Additional publisher identity clustering is future research.
- No real-network or adversarial TLS penetration test is included. Automated tests use deterministic transport fixtures, including forged responses that must be rejected by the policy and ledger.
