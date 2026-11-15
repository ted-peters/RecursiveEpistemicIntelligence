# REI 2.0 candidate — test readiness review (November 15, 2026)

**Project state: RESEARCH PROTOTYPE / NOT A 2.0 RELEASE.**
This document audits the existing `challenge8-structured-output` branch
against the hard R1–R7 release requirements, rather than implying that the
GitHub milestone is finished.

Master release tracker: [#22](https://github.com/ted-peters/RecursiveEpistemicIntelligence/issues/22).
Exact published criteria: [REI 2.0 milestone](REI_2_0_MILESTONE.md).

## Evidence already validated

- Apple Silicon: the user confirmed the local Ollama + REI browser application
  started successfully. That is an installation smoke, **not** an independent
  clean-room Mac setup or stress result.
- Existing full research suite passed on the latest milestone commit:
  [post-merge CI run](https://github.com/ted-peters/RecursiveEpistemicIntelligence/actions/runs/43727841988).
- Real Ollama Qwen3 4B Adaptive route selection and graph inquiry:
  [successful one-time smoke](https://github.com/ted-peters/RecursiveEpistemicIntelligence/actions/runs/43662076430).
- Challenge 12: [completed independent four-arm / 12-public-case evaluation](https://github.com/ted-peters/RecursiveEpistemicIntelligence/actions/runs/43672078062).
  Direct 10/12; Adaptive 11/12; Full REI 9/12; self-critique 9/12.
  All misses were invalid **final-answer format**, not logged Ollama
  generation errors. These 12 questions are PUBLIC development examples, not
  an independent held-out generalization estimate.

## What we are testing at this checkpoint

### New offline preflight (NO REAL MODEL)

`tests/test_rei2_preflight.py` checks 120 local HTTP requests against
a **synthetic fake provider** (60 Direct routes, 60 adaptive inquiry routes)
and validates the model-call/token audit, graph provenance, no invented
confidence, expected route selection, origin/host restrictions, invalid
roles/inputs, fail-closed missing model usage and truthful `/health`.

`tests/test_rei2_report.py` checks that a synthetic report cannot be
presented as an actual model experiment, verifies the frozen public questions
are not populated with answer keys or case IDs, and rejects tampering.

**These do not meet R6:** 120 FAKE local HTTP requests are not 100
successful **real Qwen model completions** and do not measure the
real-model failure/latency rate.

### Independent, small real-model smoke (GENUINE QWEN)

`research/standalone_eval/rei2_preflight_live.py` runs four authentic
Ollama Qwen3 4B calls/series of calls, using two fixed PUBLIC Challenge 12
questions:

1. `percent-increase` in explicit Direct mode (one call).
2. Same task in Adaptive mode (should route Direct; one call).
3. `source-dependence` in Adaptive mode (should enter selective REI graph).
4. Same investigative task in Full REI mode.

Each response is independently regraded against the preexisting frozen case
answer; absent/invalid `Answer: X` counts incorrect. The verifier
rechecks identical case/order, audit provenance, route, budget/calls,
actual Ollama-reported usage, missing-usage counts, and exact output.
The separate one-time GitHub Actions workflow
[real REI 2.0 candidate smoke](https://github.com/ted-peters/RecursiveEpistemicIntelligence/actions/workflows/rei2-real-smoke-once.yml)
records the downloaded model digest and archives every raw answer.

**Limitations:** Only TWO public tasks, FOUR model responses, potentially
different per-arm model-call counts. This tests engineering integration,
not 2.0's accuracy/generalization release threshold.

## Release-gate readiness matrix

| Gate | Current verdict | Why it is NOT a release pass |
|---|---|---|
| **R1 — reproducible local startup** | PARTIAL | Existing user Mac smoke and Linux real-Qwen CI; no independently documented clean-room Mac+Linux installation/restart matrix |
| **R2 — evidence/provenance** | PARTIAL | Provisional claims are marked unverified; no end-to-end independently authenticated source ingestion, conflict and withdrawal regression demonstration in standalone app |
| **R3 — adaptive calibration/cost** | PARTIAL | Router and selective graph budgets work; decisions are heuristic, and there is no validated calibration or robust abstention policy |
| **R4 — unseen benchmark** | **NOT MET** | Only 12 public cases; requirement is >=200 independently keyed unseen tasks and compute-/token-matched conventional baseline |
| **R5 — independent quality/cost gate** | **NOT MET** | Development-set metric cannot substitute for preregistered unseen-split release measurement |
| **R6 — real-model reliability/security** | **NOT MET** | Need >=100 real model completions at >=98% success plus full security review; synthetic 120-request test cannot qualify |
| **R7 — release candidate** | **NOT MET** | Functional UI, CLI and HTTP exist, but tagged candidate, completed gates and go/no-go review do not |

The original R1–R7 criteria remain unchanged and are **not** checked off
because individual pieces of software work.

## Reproduce and inspect locally

From the REI research branch after this test suite is merged:

```bash
# Synthetic CI safety/reliability checks (no Ollama calls):
python -m unittest discover -s tests -p 'test_rei2_*.py' -v

# Real Qwen3 4B (Ollama must be installed and running):
python -m research.standalone_eval.rei2_preflight_live \
  --model qwen3:4b-instruct --output /tmp/rei2-real-preflight.json

# Reopen frozen keys and regrade independently:
python -m research.standalone_eval.rei2_preflight_live \
  --verify-only --output /tmp/rei2-real-preflight.json
```

Keep the browser and Ollama bound to localhost. The real test uses
the computer's model and consumes time/resources; the fake-only preflight
does not. Neither test requires paid cloud AI APIs after Ollama is installed.

## Immediate research priority

The highest-impact next effort is still
[issue #23, held-out compute-matched evaluation](https://github.com/ted-peters/RecursiveEpistemicIntelligence/issues/23).
The earlier pilot's mistakes were **format failures**; future benchmarks
should report BOTH strict output compliance and substantive correctness,
without weakening the locked release score or tuning to these public cases.

Publish **negative results and cost regressions**. An REI 2.0 claim of
superior reasoning requires adequate unseen evaluation and matched
computational budget, not a name change, a passed small smoke, or an
unverified model-generated graph.
