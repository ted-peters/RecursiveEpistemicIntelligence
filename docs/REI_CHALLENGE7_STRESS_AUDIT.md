# Challenge 7 — randomized evidence-revision stress audit

**Date:** November 11, 2026. **Study class:** seeded deterministic software test, *not* real-model intelligence evaluation.

This test compared the unchanged `rei0.graph.EpistemicGraph` against an independent conventional provenance-aware evidence ledger. Both systems received the same explicit synthetic documents, their source-origin groups, and event timestamps. Both applied the same public semantics: pending observations do not count, verified observations support or attack, revocation removes an observation, and duplicate-origin reports are one source.

## Reproducible result

| Measure | Result |
|---|---:|
| Pseudorandom seed | `7182026` |
| Histories generated | **400** |
| Incremental post-event assessments | **4,053** |
| State disagreements | **0** |
| NEITHER checkpoints | 1,274 |
| SUPPORT_ONLY checkpoints | 971 |
| ATTACK_ONLY checkpoints | 947 |
| BOTH checkpoints | 861 |

SHA-256 over concatenated SHA-256 history digests: `bc61c8e50b3d4eb7601ee159eafc91aa74344a5edf8e1f15fd6e5061c94521f5`.

The reusable test is `tests/test_challenge7_stress.py`. It generates randomized permitted `PENDING`, `ACCEPT`, `APPROVE` and `REVOKE` operations, including repeated origin IDs and mixed support/opposition. At each event checkpoint it independently computes source groups, evidence states, and replays the REI audit graph.

**Interpretation:** The REI graph and a credible conventional ledger perform identically on these fully specified direct-evidence tasks. This is desirable regression evidence for REI's implementation, but **not evidence of architectural superiority, self-correction beyond the conventional baseline, model reasoning ability, or source authenticity**.

This stress test does not cover inferred hidden provenance, misleading input data, multi-hop dependency revision, adversarial real-world sources, or genuine independent-model reasoning. The separate six-case model-based Challenge 7 workflow measures recursive inquiry prompt behavior on static event transcripts and is not a streaming-memory comparison.