# REI-0.6 Decision Log

1. **Scope:** evidence-based belief revision with signed-rule propagation and append-only explanation journal. No new LLM requirement.
2. **Trust:** use REI-0.5 independently authenticated evidence for direct information state; never `EpistemicGraph.set_validation` or model-generated claims as direct evidence.
3. **Propagation:** only externally Ed25519-authorized, version-matched conjunctive rules; require unopposed support on all premises.
4. **Conflicts:** retain four states, block rules on `BOTH` and other non-unopposed states; no arbitrary explosion.
5. **Circularity:** reject signed inference rule DAG cycles; existing graph cycle checks remain in force.
6. **Retractions:** recalculate from current validated receipts; no stale derived credit after signed revocation.
7. **Audit:** a separate hash-chained, explainable revision journal with externally pinned audit head option; not a substitute for fact-checking, not atomic with SQLite.
8. **Compatibility:** no migration or changes to the REI-0.5 SQLite schema; all old commands remain.
9. **Future:** rule registry with signed withdrawal/rotation, distributed concurrency, richer formal proof semantics, confidence calibration and benchmark comparisons.
