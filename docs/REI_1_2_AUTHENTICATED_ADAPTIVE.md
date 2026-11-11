# REI 1.2 — Authenticated Evidence Before Adaptive Reasoning

**Experimental security/engineering milestone. No model performance claim.**

## The problem this fixes

REI 1.1's experimental AdaptiveController reads
`EpistemicGraph.assess()`. The graph's legacy
`set_validation(..., VERIFIED)` interface accepts a caller-supplied reviewer
name without cryptographic authentication. A forged "verified" label can
therefore affect the 1.1 scheduler. The existing REI 1.0
`EvidenceLedger.assess()` already distinguishes signed review decisions from
such unauthenticated labels.

**Never use the 1.1 controller as a trusted evidence-admission gate.**
It remains preserved for reproducibility as an experimental baseline.

## REI 1.2 security boundary

`rei0.authenticated_adaptive.AuthenticatedAdaptiveController` implements the
same inquiry-controller protocol as the earlier controller, but uses only
`EvidenceLedger.assess(target_id)` to determine an evidence state. Each
decision rechecks signatures, review sequencing, revocations and underlying
evidence bindings through REI's established trusted ledger.

It refuses to run when the attached ledger is not the inquiry session's
actual graph. It also refuses malformed budgets and invalid candidates.
Unsigned, rejected or revoked evidence gives no support/attack credit.
Ignored and duplicated edges **never increase the question score**.

For a pending question, the deterministic scheduling score is:

    2 * question_priority - 2 * recursion_depth + evidence_state_bonus

Bonus: BOTH=7, NEITHER=3, SUPPORT_ONLY=1, ATTACK_ONLY=1. Default threshold=10,
token reserve=320. These are arbitrary, disclosed heuristics, not calibrated
confidence or a demonstrated value-of-information estimate.

Controller audit records include the signed ledger head, graph head, accepted
source counts, excluded edges, selected evidence state, threshold and reason
to continue or stop. Questions are left open when a budget or low-value stop
occurs. The controller does **not** verify that reviewed content is true.

## Resuming an actual inquiry

A separate trusted review service must issue and store review receipts.
An inference model must **never** hold or operate the signing key. The runtime
using this controller needs only a `VerificationBoundary` initialized from
independently configured trusted review public keys, and a pair of matching
saved documents.

```python
from rei0.authenticated_adaptive import load_authenticated_inquiry
from rei0.adaptive_engine import AdaptiveInquiryEngine
from rei0.review import VerificationBoundary, Ed25519TrustedReviewer

# Public key bytes are supplied by the trusted operator, NOT by the model.
public_key = bytes.fromhex("...")  # illustrative; supply the actual public key
boundary = VerificationBoundary({
    "trusted-review-key": Ed25519TrustedReviewer("reviewer", public_key)
})
session, controller = load_authenticated_inquiry(
    "session.json", "evidence-ledger.json", boundary,
    min_score=10, reserve_tokens=320,
)
# provider must be separately initialized; no model credentials in ledger.
engine = AdaptiveInquiryEngine(provider, controller=controller)
continued = engine.run(resume=session)
```

The loader checks the checkpoint checksum, validates the evidence-ledger audit
history and all signed receipts, compares the full graph histories, then
rebinds the session and ledger to the same graph object. Mismatched snapshots,
wrong public keys and forged receipt contents are rejected before model
expansion. The two files are not a transactional distributed snapshot and
their checksums are not external audit anchors; the operator must preserve
both consistently.

## Offline checks

```bash
python -m unittest discover -s tests -p test_authenticated_adaptive.py -v
python -m unittest discover -s tests -p 'test_*.py' -v
```

Synthetic tests demonstrate:
- The legacy graph can say BOTH with unsignable labels while 1.2 remains NEITHER.
- Legitimate Ed25519-reviewed support and opposition can change inquiry
  priority, and a signed revocation removes that credit.
- Duplicate, pending or model-authored documents do not purchase recursion.
- An invalid reviewer public key, detached ledger or mismatched checkpoint
  fails closed.
- The trusted controller can drive a resumed real REI inquiry engine while
  preserving original REI 1.0 experiment and checkpoint formats.

These are tests of **software boundaries** with fictional evidence.
They do not measure model intelligence, truthfulness or factual accuracy.

## Next scientific gate: Challenge 9

Run a blinded, paired real-model comparison of original REI, adaptive REI 1.1,
signed-evidence adaptive REI 1.2, and a conventional provenance-aware
self-critique baseline given the **same signed evidence** and equivalent
tools. Predeclare the primary accuracy metric and use consistent model
weights, prompt custody, temperature, seed, real token/latency accounting,
and a compute-matched analysis. Include intentional pending evidence, forged
legacy labels, duplicates, signed contradictory evidence, and revocations.
Report paired correctness, abstention, errors, verified-review fidelity and
cost. More recursion is not success unless it improves outcomes.

No such blind comparative result is claimed here.
