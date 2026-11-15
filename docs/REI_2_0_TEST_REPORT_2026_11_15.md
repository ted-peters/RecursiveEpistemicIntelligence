# REI 2.0 — Candidate readiness test, 2026-11-15

**Status:** DEVELOPMENT MILESTONE TEST, NOT A REI 2.0 RELEASE.
**Test branch:** `rei2-readiness-smoke-20261115`, based on
`challenge8-structured-output`.
**Master tracker:** [#22](https://github.com/ted-peters/RecursiveEpistemicIntelligence/issues/22).
**Release gates:** [REI 2.0 milestone](REI_2_0_MILESTONE.md).

## 1. Tested software and regression evidence

This round checks the real standalone REI application logic with a bounded
offline provider stub and independently runs one small real Qwen experiment.

The first CI run intentionally exposed a routing regression:
[failed test run 43732010282](https://github.com/ted-peters/RecursiveEpistemicIntelligence/actions/runs/43732010282).
A polite, explicit `Please investigate ...` request containing four
multiple-choice option lines was silently routed to `direct`, rather than
`rei`. Both the routing-decision test and the execution-audit test failed.

**Correction:** `rei0/local_ai_router.py` now recognizes narrowly scoped,
polite explicit inquiry prefixes in these four-option tasks, before taking
the one-call Direct fast path. It does not search all answer options for
words like "evidence", which would misroute ordinary questions *about*
evidence. The core REI graph, untrusted evidence labels, original manual
Direct/REI modes, and model-call limits are unchanged.

[Passing regression CI run 43732121479](https://github.com/ted-peters/RecursiveEpistemicIntelligence/actions/runs/43732121479):
**559 tests run: 558 passed and one expected skip**. The new tests check:

- A polite explicit investigation chooses REI, with a provisional,
  unverified inquiry graph and correct mode/call/token audit.
- A routine four-choice question stays on Direct, with one model call
  and no REI graph.
- Multi-turn adaptive routing preserves the conservative REI branch.
- The routing decision never invents a calibrated confidence value.
- 120 separate localhost HTTP requests return complete audits with
  expected synthetically reported usage and no server failures.
- Cross-origin and nonloopback Host requests are refused, and client
  system-prompt injection or unknown modes are rejected.
- The `/health` endpoint reports the local server without falsely
  claiming that Ollama/model availability was verified.

**IMPORTANT:** These 120 requests use a deliberately synthetic scripted
provider with no real Qwen inference. They demonstrate local transport,
routing and software-integrity behavior only. They do **not** satisfy the
REI 2.0 requirement of 100 nontrivial genuine model completions or
establish a real-model reliability percentage.

## 2. Real-model smoke and evidence

A two-case one-time local Qwen3 4B test is separately stored on
`rei2-readiness-qwen-live-once-20261115` and will be evaluated under
[GitHub Actions run 43732246237](https://github.com/ted-peters/RecursiveEpistemicIntelligence/actions/runs/43732246237).

It checked that a routine bounded question uses Direct (1 call),
and a polite explicit source-authentication question builds the REI graph.
It independently scored the exact final `Answer: X` format and retained
wrong/unparseable answers as failures. The downloaded Qwen model's digest,
every answer and model-call audit are preserved in the artifact.

**Result: SUCCESS — genuine Qwen3 4B, both authored PUBLIC smoke cases correct.**

| Task | Adaptive route | Model calls | Server-reported tokens | Final-answer format | Correct |
|---|---|---:|---:|---|---|
| Basic median of 2, 3, 4 | Direct | 1 | 188 | Valid | Yes |
| Polite “Please investigate…” digital-signature question | REI inquiry | 4 | 2,500 | Valid | Yes |

The inquiry answer remained labelled
`evidence_status=model_proposals_only_unverified`. The verified
**engineering behavior** is route selection and audit consistency; the
model did not independently authenticate an outside source.
Two public tasks cannot establish reasoning superiority, reliability
rates or a passing R4/R5/R6 release gate.

Previous real-model evidence:
[Challenge 12](https://github.com/ted-peters/RecursiveEpistemicIntelligence/actions/runs/43672078062)
scored Adaptive 11/12 (20,833 reported tokens), Direct 10/12 (5,551),
always-on REI 9/12 (35,889), and four-call self-critique 9/12
(47,419) on a PUBLIC development set. All missing grades in that
run were output-format failures. It was not hidden or token-matched
and does NOT establish that REI's underlying reasoning surpasses
conventional AI.

## 3. Hard REI 2.0 release-gate assessment

**Conservative rule:** A gate is NOT PASSED until its exact acceptance
tests and required independent evidence exist. Passing a component
or mock test is not permission to mark the whole gate complete.

| Gate | Current assessment | What prevents a release pass |
|---|---|---|
| R1 — reproducible Mac/Linux standalone | **Not fully verified** | The user's Mac and earlier CI Qwen smoke worked, but a documented clean-install two-platform acceptance check is outstanding |
| R2 — authenticated source boundaries | **Not fully verified** | Provisional graph label is enforced, but permissioned source authentication, source dependence, conflict and withdrawal tests in the standalone app remain |
| R3 — bounded adaptive escalation and calibration | **Not fully verified** | Adaptive routes and bounds are tested; no independently measured calibrated correctness probability or full abstention policy |
| R4 — >=200 unseen, independently keyed tasks with compute-matched baselines | **Not satisfied** | Only public small development question sets have been tested, without matched token budgets |
| R5 — preregistered quality/cost accuracy thresholds on the held-out set | **Not evaluated** | Requires R4 results and paired uncertainty intervals |
| R6 — >=98% real local completion reliability over >=100 requests plus security | **Not satisfied** | 120 requests here are synthetically generated, not real local inference |
| R7 — usable 2.0 release candidate | **Not satisfied** | Versioned 2.0 release-candidate acceptance, rollback and go/no-go review remain |

**Release verdict: NOT READY for stable REI 2.0.**

## 4. Next scientifically meaningful gate

Prioritize [#23](https://github.com/ted-peters/RecursiveEpistemicIntelligence/issues/23):
a frozen, genuinely held-out, **token-matched** comparison, with >=200
unseen independently keyed tasks, no leaked answer keys, paired per-case
uncertainty intervals, all request failures, proper token-cost tracking
and a strong conventional reasoning baseline. Add R6 genuine model
reliability stress only after its time and token budget are explicitly
bounded.

This report deliberately preserves the negative first run and the
successful fix. It does not present the model's own inquiry scaffolding
as independent factual evidence or a trained REI-native foundation model.
