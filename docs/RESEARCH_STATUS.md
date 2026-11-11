# REI scientific status

**Research program:** Recursive Epistemic Intelligence (REI).

This repository contains the original REI-1.0 engineering research prototype and research materials. It has a typed epistemic graph, four-state evidence ledger, independent review records, recursive inquiry, source provenance, revision rules, and an experimental evaluation runner.

**Established:** The original 1.0 release report documents 376 passing software regression tests. The public Hugging Face Python demo exercises a limited subset of the *real* graph implementation.

**Not established:** REI has **not** defeated a capable conventional AI in an independently executed, computation-matched live model study. Challenge 5 has no genuine live-model answer set or observed superiority claim. Repeated model-generated reasoning cannot authenticate its own factual support.

**Security:** Demonstration reviews are scripted, synthetic annotations; they are not verified real-world sources or cryptographic approvals. The original local service is research software, not a production security boundary. Do not paste provider API keys into a public app or commit private credentials.

**Recommended next step:** execute a genuinely independent live-model comparison with blinded new holdouts, equal underlying model and tools, matched actual resource usage, independent grading, and a declared primary comparison against self-critique.

**Python-version reproducibility note (November 2026):** The archived REI-0.9 synthetic experiment report contains a Brier-score floating-point sum computed with Python 3.13 behavior. Its strict exact-float verification can fail under Python 3.11 because built-in `sum` rounds two values differently. The CI workflow currently runs the frozen report checks under Python 3.13. This is a legacy cross-version reproducibility limitation, **not** evidence of an AI-performance result. The frozen REI source and preregistration fingerprints were not modified to conceal or bypass this discrepancy. Future research releases should use explicitly stable numerical aggregation and a new preregistration fingerprint.
