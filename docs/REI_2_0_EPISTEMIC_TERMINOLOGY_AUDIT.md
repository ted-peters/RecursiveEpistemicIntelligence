# Epistemic versus ideological — REI 2.0 terminology and test audit

**Decision:** Retain **Recursive Epistemic Intelligence (REI)** as the name
of the research project and its target software system. The term
*epistemic* describes its intended procedure; it is not a guarantee of
correct conclusions or proof that the underlying model is intelligent.
No rename to *ideological* is warranted.

**Definitions and limits**

- **Epistemic**: pertaining to knowledge, what warrants a belief, evidence,
  uncertainty, source reliability, and when a conclusion should be
  challenged or revised. This is what the REI graph and evidence-review
  architecture are built to examine.
- **Epistemological**: pertaining to the philosophical theory of
  knowledge. A sensible description of the *research foundation*, but
  `Epistemological Intelligence` is a less accurate name for a working
  software process than `Epistemic Intelligence`.
- **Ideological** (sometimes misspelled `idealogical`): pertaining to a
  worldview, organized values, group commitments, social perspectives,
  or political doctrines. These may be **subjects of analysis**, not
  sources of epistemic authority merely because someone endorses them.
- **Ideational**: relating to ideas or their generation. Would fit
  creative brainstorming, but not specifically justification and
  evidence-tracking.
- **Recursive**: REI revisits and expands questions under explicit
  resource limits. It does not solve infinite philosophical regress by
  running infinite computation.
- **Intelligence**: the project name and a target capability, *not* a
  claim of a newly trained foundation model, general AI superiority,
  human-level reasoning or calibrated correctness.

For philosophical background, see the Stanford Encyclopedia of
Philosophy on [Epistemology](https://plato.stanford.edu/entries/epistemology/),
[Evidence](https://plato.stanford.edu/entries/evidence/), and
[Ideology](https://plato.stanford.edu/entries/ideology/).

## What the existing code operationalizes

The original `EpistemicGraph` class tracks claims, objections, tests,
source provenance and evidence relations. Its four evidence states are
`NEITHER`, `SUPPORT_ONLY`, `ATTACK_ONLY`, and `BOTH`. The presence
of one of these states does **not** assign a probability or show a claim
is true. Model-authored arguments cannot count as independent evidence
in the graph.

The optional `EvidenceLedger` accepts externally submitted artifacts
into `PENDING` state and uses independently trusted, signed reviewer
decisions to determine evidence *admissibility*. Repeated evidence
sharing a source group, reference, content or artifact hash should not
be treated as independent corroboration. A signed review authenticates
a reviewer decision; it is **not** a source-truth oracle. Contradictions
must remain visible, and revocation must remove old support without
erasing the audit history.

The **standalone Ollama + Qwen** chat app currently builds an auditable
but *model-origin, provisional* reasoning graph. It does not use that
permissioned evidence ledger to automatically authenticate real-world
sources. This limitation must not be hidden by the project name.

## Epistemic-integrity regression suite

`tests/test_rei2_epistemic_integrity.py` introduces ten independent,
deterministic, entirely synthetic checks:

| # | Epistemic property | Expected result |
|---|---|---|
| 1 | A popular or unpopular value-based claim without admissible review | `NEITHER` |
| 2 | Text saying "verified by experts" without a signed trusted decision | `NEITHER` |
| 3 | A model tries to authenticate its own statements through an evidence review | Rejected |
| 4 | An independent signed reviewer admits synthetic evidence | `SUPPORT_ONLY`, confidence unset |
| 5 | Three sites echo one original anonymous source | One independent source group, not three |
| 6 | Independently admitted opposing evidence then revocation | `BOTH` → `ATTACK_ONLY` |
| 7 | An unreviewed preference is added alongside admitted evidence | No increase in evidential support |
| 8 | Evidence source signs its own account as proof | Rejected |
| 9 | A model *falsely boasts it checked outside sources* | Audit remains unverified; **text itself remains misleading** |
| 10 | Direct model text asserts external certainty | Audit remains `not_verified` |

These checks are **software invariants, not measured model accuracy,
ideological impartiality, or factual reliability**. For the audit to
support more than a code claim, pair them with real-model, independently
graded tasks that measure source independence, hidden-base-rate errors,
evidence withdrawal, confirmation bias, and format compliance.

### A known and consequential limitation

The ninth test intentionally creates a synthetic model that says
"I independently verified this through outside sources" despite having
accessed no sources. The standalone `audit.evidence_status` correctly
says `model_proposals_only_unverified`, but the *text* can still
contradict that metadata.

**This is not a hallucination-prevention success.** The model's
unsupported sentence might still mislead users if they read only the
answer. A deterministic provenance banner in the UI/API and a stronger
unsupported-verification-claim guard are candidates for R2, with
tests that avoid corrupting legitimate quoted discussion or strict
benchmark response formats. Do not rely solely on a prompt asking a
model to be honest.

## Practical naming and reporting rules

| Good wording | Avoid until independently demonstrated |
|---|---|
| Epistemic inquiry and provisional reasoning graph | Verified autonomous reasoning |
| Evidence-admission / provenance review | Automatically authenticated truth |
| Bounded recursive investigation | Infinite proof or infinite recursion |
| Adaptive-cost reasoning heuristic | Calibrated confidence or learned optimal reasoning |
| REI-powered local AI application with Qwen weights | Independently pretrained REI model |
| Epistemic research framework | Ideological intelligence / value-advocacy engine |

## Release implication

**Keep the name, strengthen the epistemic behavior.** This study
supports the project's conceptual vocabulary; it does **not** close
REI 2.0 [R2](https://github.com/ted-peters/RecursiveEpistemicIntelligence/issues/25)
(verified-source handling) or
[R4](https://github.com/ted-peters/RecursiveEpistemicIntelligence/issues/23)
(held-out independent reasoning evaluation), nor establish a truth
oracle. The strongest next step is to build and test truthful,
user-visible provenance separation, then run genuinely unseen,
compute-matched evaluations.
