# REI-0.9 Decision Log

- Continue directly from REI-0.8; preserve the four benchmark arms, calibration isolation, legacy APIs and tests.
- Add frozen, immutable study protocol with digest commitments, but do not misrepresent local timestamps as notarization.
- Require per-key independent-adjudication declarations in study registration, with the explicit limitation that they do not authenticate identity or factual truth.
- Reuse the existing v0.8 benchmark, adaptation, and regrading machinery; do not rewrite baseline grading.
- Add atomic checkpointing of completed trials; disclose that failed in-flight trials can cause repeated paid model calls.
- Add exact and tolerance-based *observed* usage matching as diagnostics; no claim that common resource limits cause equal actual compute.
- Keep live model requests explicitly opt-in with an acknowledged cost flag and credentials supplied only through the environment.
- Never interpret a synthetic fixture as evidence of AI superiority or a validated scientific result.
