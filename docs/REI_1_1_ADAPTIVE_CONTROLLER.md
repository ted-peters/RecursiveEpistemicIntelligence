# REI 1.1 — Adaptive Epistemic Controller (experimental)

**Status:** Opt-in engineering prototype, not evidence that REI is more accurate or efficient.

## Purpose

REI 1.0 explores model-proposed challenges by a fixed priority schedule. The
Challenge 8 six-case pilot found REI 2/6, self-critique 4/6, and three failed
REI runs even with schema-constrained responses. An adaptive controller may
allocate model calls more selectively.

## New components

- `rei0/adaptive.py` implements deterministic evidence-aware scoring, explicit
  token reserves, a score threshold, and auditable select/stop decisions.
- `rei0/adaptive_engine.py` provides `AdaptiveInquiryEngine` as an opt-in
  versioned implementation. The original `rei0/inquiry.py` is not changed.
- `tests/test_adaptive.py` checks budget stops, graph review/revocation,
  unverified model evidence, replay and fail-closed controller behavior.

For eligible question q the heuristic score is

    2*q.priority - 2*q.depth + evidence_bonus + ignored_edge_bonus

Evidence bonuses: BOTH=7, NEITHER=3, SUPPORT_ONLY=1, ATTACK_ONLY=1.
Ignored-edge bonus=2 if any unverified/duplicate edges exist. The defaults
are minimum score 10, token reserve 320. Scores are **not calibrated** as
probabilities, correctness improvements, or expected-value estimates.

The original REI graph considers only externally recorded, independently
verified source evidence. Model arguments remain provisional. A signed
reviewer action or synthetic marker is not proof of real-world truth.

## Offline demonstration

```python
from rei0.adapters import ScriptedAdapter
from rei0.adaptive import AdaptiveController
from rei0.adaptive_engine import AdaptiveInquiryEngine
from rei0.inquiry import InquiryLimits

provider = ScriptedAdapter.load("examples/inquiry_script.json")
session = AdaptiveInquiryEngine(
    provider,
    InquiryLimits(max_steps=2, max_model_calls=4),
    controller=AdaptiveController(min_score=10, reserve_tokens=320),
).run("Which assumptions deserve further verification?")
print(session.stop_reason, session.model_calls, session.report())
```

This uses a scripted fixture, **not a live model** or independently authenticated
facts. The decision trace includes state, source counts, score and graph
audit head, and preserves all uninvestigated questions on an adaptive stop.

## Validation

```bash
python -m unittest discover -s tests -p test_adaptive.py -v
python -m unittest discover -s tests -p 'test_*.py' -v
```

Correctness of the controller is not a superiority result. The next stage
is a new preregistered live-model evaluation: the same underlying model and
evidence for REI 1.0, REI 1.1, self-critique and a provenance-aware baseline;
new blinded holdouts, matched resource accounting, multiple seeds, paired
grading, latency, failure and unknown-token reporting. Any comparison without
matched actual compute must be labeled as such.

The current implementation does not autonomously search for, authenticate,
or validate real-world evidence, and it does not repair malformed model
responses. These are distinct future engineering milestones.
