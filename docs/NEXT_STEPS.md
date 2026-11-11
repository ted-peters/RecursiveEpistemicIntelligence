# Next steps after REI-0.4

1. **REI-0.5 — Key isolation and genuine source checks:** replace shared HMAC with asymmetric reviewer signatures or hardware-backed signing; protect the signing operation under a different identity. Add allowlisted evidence fetchers that preserve response metadata and verify independent origin when available.
2. **REI-0.6 — Belief revision:** implement principled dependency-aware invalidation, source-retraction propagation and reason/evidence influence boundaries, with auditable revision history.
3. **REI-0.7 — Empirical research:** benchmark standard LLM, self-critique, recursive justifications and REI with equal budgets; track accuracy, calibration, explanation faithfulness, and costs.

All improvements remain hypotheses until independently measured. See `docs/REI_Master_Blueprint_v1.md`.

## After REI-0.6

- Separate rule-approval authority and its revocation registry, with signed policy versions and key rotation.
- Benchmark accuracy and calibration versus fixed-depth/self-critique baselines at equal compute.
- Add explicit entailment-proof objects and property-based testing of multi-premise conflict propagation.
- Make revision journal write-through transactional with durable DB or add a verified external append-only audit store.
- Permit controlled rule-level skepticism and evaluation-method revisions without letting the model approve its own changes.
