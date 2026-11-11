# REI-0.6 Revision Protocol — formal contract

## State and semantics

Let `G` be the typed proposition graph and `L` the independently authenticated REI-0.5 evidence ledger. For claim `p`, `direct(p)` is the two-bit pair `(s,a)` obtained from `L.assess(p)` **after** replay-verifying the evidence receipt chain. Information status is:

| bits `(s,a)` | state |
|---|---|
| `(0,0)` | `NEITHER` |
| `(1,0)` | `SUPPORT_ONLY` |
| `(0,1)` | `ATTACK_ONLY` |
| `(1,1)` | `BOTH` |

A signed authorized rule `r = (P, c, polarity, method_version)` with premise set `P` may add defeasible support or opposition to `c`, but **only if** `forall p in P: status(p) == SUPPORT_ONLY`. The rule's signed rationale is an operator assertion of the conditional relationship; this is not a proof of material implication or empirical validity.

In topological order, with `S_r(c)` and `A_r(c)` indicating whether a signed `supports` or `attacks` rule fires for target claim `c`, compute:

```
status(c) = (direct_support(c) OR S_r(c), direct_attack(c) OR A_r(c))
```

No other unreviewed graph edge is propagated. Non-verified, rejected, revoked and model-generated submissions remain inadmissible. The signed review's conditions (source/reviewer independence, artifact/provenance binding, review sequence) are inherited from REI-0.5.

### Determinism and boundedness

Claim IDs and rule IDs are ordered lexicographically; rules use sorted, distinct premises. The engine rejects rules referencing nonexistent claim nodes or inconsistent graph method versions, signatures that fail public-key checks, and any dependency cycle (including cycles spanning several rules). Resource caps default to 10,000 claims and 5,000 rules. Inference reports are deterministic for the same verified snapshot and same signed rule set.

### Conflict behavior

`BOTH` is never simplified into true or false. A rule with a `BOTH` premise does not fire, even when there is some support. This skeptical policy sacrifices completeness to reduce propagation from disputed claims. A direct attack on a derived conclusion can yield `BOTH`, and then blocks downstream rules depending on that conclusion. This is *not* a complete paraconsistent inference calculus; it is a restricted defeasible forward-chaining policy.

### Revision and revocation

The engine does not mutate accepted review receipts; it recomputes status from current, separately verified evidence after every review/revocation. Changes in direct evidence or the signed rule set produce new reports. The journal compares state and explanation fields, stores explicit before/after values, signed rule definitions and graph/evidence audit heads, and links reports with a SHA-256 hash chain. A withdrawn review is visible in the evidence ledger and ceases to contribute to all downstream rules.

### Authenticity boundary

- Evidence: existing public-key Ed25519 and legacy HMAC receipt verification (0.5).
- Rules: separate `REI-0.6-INFERENCE-RULE\x00` Ed25519 domain, verified against the **public reviewer key only**. The offline `revision-rule-sign` command can sign a prepared rule; the verifier and model service provide **no signing endpoint**.
- Rule validity: cryptographic authorization does **not** make the logical/material conditional true. A trusted operator must review rule semantics and its appropriate use.
- Journal: hash-chain verification checks internal integrity but not the truth of conclusions. Protect a last-known audit head outside the process to detect rollback.

### Open limitations

No probability calibration, source factuality oracle, general natural-language entailment verifier, automatic premise equivalence detection, rule withdrawal certificate, soundness proof for arbitrary signed conditionals, distributed journal locking, or atomic journal+database transactions. Withdrawal of a signed rule means assessing with a separately controlled rule set; to prevent silent omission, externally pin the complete rule-set hash. Multi-user deployments need an access-controlled registry and externally governed rule-set versions.

## Evidence-driven acceptance is provisional

`SUPPORT_ONLY` signifies only that the current evidence-plus-authorized-rules ledger has admissible supporting information without recorded admissible opposition. It is **not** absolute knowledge. The philosophical regress remains open: every claim and every rule may be questioned independently of the external operational safeguards.

A journal-only `revision-verify` run checks structural and hash integrity; `revision-verify --trust` additionally authenticates embedded rule signatures. Neither option rechecks external evidence unless the current evidence database is opened and replay-verified by `revision-assess`. Optional `--expected-evidence-head`, `--expected-graph-head` and `--expected-source-head` pin externally trusted database heads.
