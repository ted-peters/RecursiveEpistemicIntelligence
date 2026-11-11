# REI-1.0 Design Decisions

1. **Additive release:** Keep the existing epistemic graph, evidence verification, revision, and experimental protocol rather than implementing a competing reasoning core.
2. **Read-only dashboard:** Interactive browsing of aggregate experiment results is useful, but modifying scientific records through an unauthenticated local webpage is out of scope.
3. **Regrade at import:** An experiment can enter the workspace only when evaluation-only answer keys are temporarily supplied and grades are recomputed; these keys are never persisted to the workspace.
4. **Immutable import:** Entries are append-only; corrections become a separate versioned artifact, not in-place edits.
5. **Explicit synthetic/live separation:** Demo evaluations are prominently marked `scripted_fixture_not_empirical`. A live outcome also requires real source review and external replication before claims are justified.
6. **Preserve regress:** Inquiry graphs may retain unresolved questions. Working computational budgets do not pretend to terminate the philosophical regress.
7. **Finite trust:** Hashes are consistency checks rather than independent truth, chronology or authority certification. Operator-controlled safeguards remain outside the revisable epistemic engine.
