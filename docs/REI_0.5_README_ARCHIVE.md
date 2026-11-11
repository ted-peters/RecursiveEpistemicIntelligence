# Recursive Epistemic Intelligence — REI-0.5

**v0.5.0 | Python 3.10+ | `cryptography>=42,<50` | local Unix socket service on macOS/Linux**

REI-0.5 extends REI-0.4 with **independently captured web source bytes, auditable provenance, exact-excerpt verification and Ed25519 public-key review**. It preserves the four-state ledger and bounded recursive inquiry system from the earlier milestones.

> **IMPORTANT:** A retrieved HTTPS document is not guaranteed to be accurate, truthful, independently authored, or safe to execute. The service only authenticates transport/content captures and reviewer decisions. All evidence is pending until a separately authorized signed review. This is a research prototype, not a production security appliance.

## Quick start

```sh
python -m pip install .
python -m unittest discover -s tests -p 'test_*.py' -v
python -m rei0 source-demo         # fully OFFLINE synthetic source capture + Ed25519 review
python -m rei0 service-demo        # inherited offline HMAC service demo
python -m rei0 inquiry-demo        # inherited bounded recursive inquiry demo
```

The new tests use **offline simulated HTTPS responses**, so they do not contact external websites. The `source-demo` uses a fake resolver and synthetic content only; a successful demonstration does not prove the live HTTPS implementation has been externally audited.

## Trust architecture

```text
UNTRUSTED INQUIRY / CLIENT             CONTROLLED VERIFIER (local Unix socket)
  --source URL/ID ------------------>   exact allowlist, pinned public DNS + TLS
  --source excerpt ----------------->   SQLite source evidence and hash-chain
  --request challenge ------------->   no signing/private-key API
                                          | public key only
                                          v
OFFLINE REVIEWER  <--- original bytes + challenge
  independently examines original, claim and context
  -- signs Ed25519 receipt (PRIVATE key kept offline)
                                          |
  --accept signed receipt ----------------+--> four-state ledger update
```

## Local end-to-end workflow

**1. Create a claim graph**

```sh
python -m rei0 inquiry-demo --save-graph inquiry_graph.json
```

The demonstration graph contains claim ID `claim-00001`.

**2. Generate distinct private and public reviewer credentials**

```sh
python -m rei0 service-keygen-ed25519 --trust trust-public.json --signer signer-private.json
```

`signer-private.json` contains the Ed25519 private key and must leave the verifier environment. `trust-public.json` contains **only** the public reviewer key. Both files are written owner-only. No client should be able to modify the verifier's trust registry. The old `service-keygen` HMAC command remains supported for v0.4 compatibility.

**3. Initialize a database**

```sh
python -m rei0 service-init inquiry_graph.json evidence.sqlite --trust trust-public.json
```

**4. Terminal A: start a service with an explicit source allowlist**

```sh
python -m rei0 service-serve evidence.sqlite \
  --socket verifier.sock --trust trust-public.json \
  --source-host example.org
```

Only `https://example.org/...` URLs on port 443 may be fetched in this example. Choose a **real, trusted, authorized hostname** relevant to your research. Without `--source-host`, network retrieval is disabled. Exact hostnames only: a subdomain is not implicitly included. Run the verifier using dedicated OS credentials and protect the socket directory.

**5. Terminal B: capture a live source into SQLite**

```sh
python -m rei0 source-retrieve \
  --socket verifier.sock --retrieval-id paper-001 \
  --url https://example.org/

python -m rei0 source-info --socket verifier.sock --retrieval-id paper-001
```

This makes a real HTTPS connection. It requires an internet connection, a valid public-DNS HTTPS origin, and an approved MIME type. The service records original bytes, URL, retrieval time, pinned public IP, TLS leaf certificate fingerprint, SHA-256, and a source audit event. **Capture is not review or fact checking.** Retrying the same retrieval ID returns the original capture if the URL matches; use a new ID for a fresh fetch.

**6. Submit an exact textual excerpt for the claim**

```sh
python -m rei0 source-submit --socket verifier.sock \
  --retrieval-id paper-001 --submission-id submission-001 \
  --evidence-id evidence-001 --claim claim-00001 \
  --text 'EXACT TEXT FROM THE STORED SOURCE' --polarity supports
```

The quoted text must occur exactly in UTF-8 textual captures. For PDF captures, byte hashing is checked but no automatic PDF text extraction is attempted. **All new source submissions remain `PENDING`** and contribute no trusted evidence credit.

**7. Generate an evidence review challenge**

```sh
python -m rei0 service-challenge --socket verifier.sock \
  --submission-id submission-001 --output challenge.json
```

**8. Offline operator: inspect archived source bytes, original URL, provenance, and claim**

If the verifier database is accessible from a **trusted operator environment** (do not give private DB access to the model), export the source artifact:

```sh
python -m rei0 source-export --database evidence.sqlite \
  --trust trust-public.json --retrieval-id paper-001 \
  --output reviewed-source.html
```

Alternatively, obtain the original independently. The operator should inspect the complete original and verify its SHA-256 against `challenge.json`. The archive alone cannot determine source truth or publication authenticity.

**9. Sign offline with the reviewer PRIVATE key**

```sh
python -m rei0 operator-sign --challenge challenge.json \
  --signer signer-private.json --artifact reviewed-source.html \
  --decision verified --reason 'Personally inspected full original and claim context' \
  --output signed-receipt.json
```

To reject evidence, choose `--decision rejected`. To revoke a previously verified submission, request an updated challenge and sign `--decision revoked`. Do not share the private key with REI or the verifier service.

**10. Admit the signed receipt and assess the claim**

```sh
python -m rei0 service-accept --socket verifier.sock --receipt signed-receipt.json
python -m rei0 service-assess --socket verifier.sock --claim claim-00001
python -m rei0 service-verify --socket verifier.sock
```

Use `service-verify --expected-head ... --expected-graph-head ... --expected-source-head ...` to compare all three recorded heads with hashes independently stored in a protected location.

## Operators and APIs

| Command | Function |
|---|---|
| `source-retrieve` | Controlled HTTPS capture, always service-side and pending |
| `source-info` | Inspect provenance metadata and SHA-256 |
| `source-submit` | Create pending evidence from captured bytes; exact excerpt check |
| `source-export` | Offline/privileged read of archived original bytes |
| `service-keygen-ed25519` | Offline private signer + public-only verifier trust registry |
| `operator-sign` | Offline receipt issuance with matching original artifact hash |
| `service-accept` | Verify and commit signed decision |
| `service-verify` | Validate SQLite, evidence, graph, and source integrity chains |
| `source-demo` | Fully offline synthetic workflow |
| `service-demo`, `inquiry-demo`, `evidence-demo` | Earlier functionality still available |

Python interfaces: `rei0.SecureSourceFetcher`, `rei0.FetchedSource`, `rei0.SourceRepository`, `rei0.EvidenceDatabase`, `rei0.Ed25519ReviewIssuer`, `rei0.Ed25519TrustedReviewer`, and `rei0.VerificationBoundary`. See [source protocol](docs/SOURCE_VERIFICATION_PROTOCOL.md) and [security model](SECURITY.md).

## Integrity, compatibility and limitations

- A `SOURCE_ONLY` truth status does **not** exist: the internal evidence states are `NEITHER`, `SUPPORT_ONLY`, `ATTACK_ONLY`, and `BOTH`. These describe reviewed positive/negative evidence, not absolute truth.
- All REI-0.4 SQLite tables and HMAC v1 review receipts remain readable. Opening a v0.4 database creates extra source tables, initially empty. The source audit head is separate from the evidence/graph heads; preserve all three externally to detect rollback.
- Reviewed evidence's source group uses the exact hostname for the new source path. Different hostnames may still be dependent; this version does not infer publication ownership or truth.
- Only textual exact-substring matching is supported; PDF text verification, external fact-checking, Certificate Transparency, and full authenticated publisher identity are out of scope.
- The service uses Unix sockets and the filesystem access model; do not expose it as a public network API. Different processes running under the same user identity are **not** isolated against compromise.
- The new `cryptography` dependency is required for secure Ed25519 rather than implementing custom cryptography.

## Tests and release verification

```sh
python -m unittest discover -s tests -p 'test_*.py' -v
python tools/verify_manifest.py
```

See `RELEASE_NOTES.md`, `RELEASE_TEST_REPORT.json`, and `docs/SOURCE_VERIFICATION_PROTOCOL.md`. The checksum manifest checks the source archive after extraction; it is not a publisher signature.
