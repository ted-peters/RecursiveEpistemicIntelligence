# REI-0.5 Architectural Decisions

1. **Reviewer isolation:** Add Ed25519 `review.v2` with public-only verifier trust. Preserve HMAC `review.v1` unchanged for old history, avoiding a breaking migration.
2. **Source retrieval:** Make all network fetches originate in the service with an explicit exact-host allowlist; disallow remote fetch by default.
3. **Network boundary:** Require public DNS answers and pinned TLS connection to the resolved IP with SNI/certificate validation for the original hostname; refuse redirects, compression and oversized responses.
4. **Persistence:** Keep source captures/metadata as a separate append-only hash ledger inside the existing SQLite database. Maintain source head distinct from graph and evidence heads.
5. **Provenance:** When evidence refers to a capture, the server constructs provenance and obtains original bytes from SQLite; caller cannot supply replacement bytes or provenance. Text content must contain the proposed excerpt.
6. **Epistemic policy:** Transport provenance and reviewer authentication are **not** factual truth. Only signed review affects the four-state ledger. Model arguments remain non-verifying.
7. **Compatibility:** Keep all previous command-line workflows, graph/inquiry APIs, ledger semantics and legacy test suites.
8. **Next:** Explore publisher-issued digital signatures, cross-domain source dependency, protected external audit anchoring, and independent document-content extraction / claim relevance checking.
