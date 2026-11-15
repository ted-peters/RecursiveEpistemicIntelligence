# REI 2.0 — Development Milestone and Release Gates

> **Status:** Planned milestone; not a released version.
>
> **Tracking:** [REI 2.0 master issue #22](https://github.com/ted-peters/RecursiveEpistemicIntelligence/issues/22).
> **Implementation base:** `challenge8-structured-output` research branch (not the default `main` branch).
> **Target release date:** Not committed. Advancement is gated by evidence, not calendar time.

## 1. What REI 2.0 will be

REI 2.0 is the proposed next **standalone, locally deployable AI application
and epistemic reasoning controller**, built on the current REI evidence graph
and bounded inquiry engine. It will integrate an existing open-weight
language model (currently Ollama + Qwen3 4B Instruct by default) for language
generation.

The research objective is **not** to invent a new pretrained frontier
foundation model or equate recursive self-criticism with verified facts.
The objective is to offer measurable benefits over an ordinary direct
model **when a task merits investigation**, while otherwise spending
fewer resources, reporting uncertainty without fabrication, and
respecting reproducible provenance and user privacy.

A version number must describe **delivered software** and its tested
limits, not a claim of general intelligence, sentience or unconditional
accuracy superiority.

## 2. Known, reproducible baseline

### What already works

- Working REI local chat app on Apple Silicon using native Ollama/Qwen,
  plus an OpenAI-style localhost API and CLI.
- Bounded REI inquiry graph and audit with model-generated provisional
  claims, reasons and objections.
- `Adaptive` front-end mode with transparent zero-extra-call
  intent routing and budget-aware graph question selection.
- Regression and security checks, with prior real-Qwen inference smokes.
- Public quality benchmark tooling with independent answer grading,
  model-reported token counts, and explicit failed-format handling.

### Challenge 12: real Qwen3 4B on 12 *public development* questions

**Authoritative run:** [GitHub Actions 43672078062](https://github.com/ted-peters/RecursiveEpistemicIntelligence/actions/runs/43672078062)
(with complete graded artifact, model identity and case-level outputs).

| Arm | Correct / 12 | Calls | Known reported tokens | Elapsed seconds | Format failures | Generation errors |
|---|---:|---:|---:|---:|---:|---:|
| Direct | 10 | 12 | 5,551 | 444.180 | 2 | 0 |
| Adaptive REI | **11** | 30 | 20,833 | 1,286.312 | 1 | 0 |
| Always-on REI | 9 | 48 | 35,889 | 2,163.929 | 3 | 0 |
| Four-call self-critique | 9 | 48 | 47,419 | 2,714.819 | 3 | 0 |

Of the 12 cases, Adaptive and Direct were both correct on 10, Adaptive
alone was correct on 1, neither was correct on 1, and there were no
Direct-only wins. **All incorrect grades in this run were missing or
invalid final `Answer: X` format**, so do not interpret these exact
scores as a validated improvement in the underlying reasoning ability.
Formatting compliance and substantive correctness must be separated
in later evaluation, and the strict end-to-end score must still be
reported.

For this study, Adaptive consumed ~3.75 times the Direct tokens but
~42% fewer tokens than always-on REI. Full REI and four-call critique
both made 48 calls; different token use does not establish equivalent
compute budgets. One small **public, nonblinded** study cannot establish
statistical significance, generalizability, or calibrated confidence.

**Prior six-case development run:** Direct and always-on REI both
achieved 6/6 on simple public questions, but REI used far more tokens:
[run 43653923859](https://github.com/ted-peters/RecursiveEpistemicIntelligence/actions/runs/43653923859).

### Existing limitations

- Adaptive routing and internal graph scores are heuristic, not
  trained/validated predictions of correctness or actual information gain.
- REI-generated reasons and objections are not independently verified facts.
- No default retrieval or autonomous external tooling; no persistent
  authenticated evidence store in the standalone app.
- No independent held-out, compute-matched demonstration of superiority.
- Local app is unauthenticated and intended for localhost only;
  it must not be exposed directly to the internet.
- The app depends on separate Ollama-hosted pretrained model weights.

## 3. Architecture target

```text
User / local browser / CLI / localhost API
                  |
        Bounded input validation
                  |
    Adaptive cost/uncertainty policy  <- calibrated evidence from held-out tests
            /             \
      Direct mode     REI inquiry mode
       one call       bounded claim / objection graph
            \           /         |
             \         /     Optional *permissioned*
              \       /      source evidence ingestion
              Model-based synthesis
                      |
       Auditable answer: provenance state,
       executed mode, model calls, tokens,
       stop reason, limits, uncertainty
```

**Trust boundary:** No model-authored claim, source URL, argument,
self-critique, or digital signature is by itself proof of factual truth.
An outside source must pass independent provenance/admission procedures
to earn an authenticated-evidence label. Optional tools require
explicit user permission and constrained access.

## 4. Milestone workstreams

| Priority | Workstream and owned tracking issue | Delivery |
|---|---|---|
| **P0** | [#23 — held-out evaluation and compute-matched baselines](https://github.com/ted-peters/RecursiveEpistemicIntelligence/issues/23) | A genuine measurement basis for deciding whether to invest in a reasoning strategy |
| **P1** | [#24 — adaptive calibrated escalation and cost budgets](https://github.com/ted-peters/RecursiveEpistemicIntelligence/issues/24) | Selective inquiry, honest uncertainty, bounded cost and explicit abstention |
| **P1** | [#25 — authenticated evidence and source independence](https://github.com/ted-peters/RecursiveEpistemicIntelligence/issues/25) | Clear external-evidence trust and provenance boundaries; evidence revision |
| **P1** | [#26 — Apple Silicon reliability, security and failure recovery](https://github.com/ted-peters/RecursiveEpistemicIntelligence/issues/26) | Repeatable local installation, robust runtime, privacy by default |
| **P2** | [#27 — release-candidate UX and go/no-go](https://github.com/ted-peters/RecursiveEpistemicIntelligence/issues/27) | Usable documented application, release candidate and review |

The workstreams can proceed incrementally but cannot be marked
complete merely because a demonstration works. Every change should
have code, regression tests, CI evidence and a linked PR.

## 5. Hard release gates (definition of done)

| Gate | Criterion | Proof required |
|---|---|---|
| **R1** | Reproducible local Apple Silicon + Linux setup; no paid API; default localhost-only operation | Clean-install and restart test, documented model dependency |
| **R2** | Model-generated text never promoted to authenticated evidence; source independence, conflict and withdrawal treated correctly | Automated provenance tests and auditable source state |
| **R3** | Bounded adaptive escalation with no guessed probabilities and tested failure/abstain behavior | Cost/stop traces, measured calibration or explicit not-calibrated label |
| **R4** | >=200 unseen, independently keyed tasks, with held-out case evaluation and repeat trials/seeds/orders where feasible; Direct, Adaptive, Full REI, compute-matched conventional baseline | Frozen protocol, raw cases/grades, independently replayable reports and uncertainty intervals |
| **R5** | On the preregistered held-out case mix: Adaptive point-estimate accuracy >= Direct minus 2 percentage points **and** reported tokens >=25% lower than always-on REI; report paired confidence intervals | Regraded accuracy/cost table and all failures. This does not itself prove superiority |
| **R6** | >=98% successful responses across >=100 nontrivial local requests; regression and bounded-resource/security checks pass; no critical outstanding vulnerability | CI plus real local runtime stress and negative tests |
| **R7** | Browser + CLI + localhost API expose executed mode, token/call audit and provenance; Mac/Linux setup and rollback guidance; release notes | Release-candidate checklist and an explicit documented go/no-go decision |

Release criteria may be revised if they prove misleading or impractical,
but changes must be documented **before** a new qualifying evaluation,
with the prior values retained in version history.

### Claim gate: when may we say REI is *better*?

**Not when a small study merely gives a higher score.** Public claims
that REI 2.0 improves answer correctness over conventional methods
require a separate independent, adequately powered held-out comparison
with matched computational budget, preregistered primary endpoint,
uncertainty bounds, all model errors and negative controls reported.
If only engineering/cost/reliability gates pass, release as a stronger
**software system**, not as demonstrated more intelligent base weights.

## 6. Execution order

1. **Baseline freeze (now):** preserve Challenge 12 results and
   existing standalone behavior; add this milestone document and issues.
2. **Measurement infrastructure:** deliver #23 first so future
   routing/calibration changes cannot exploit public dev examples.
3. **Adaptive policy and evidence integrity:** pursue #24 and #25
   against development splits while protecting held-out evaluation.
4. **Runtime and UX:** finish #26 and progressively implement #27,
   maintaining localhost security.
5. **Evaluation + release review:** run locked held-out trials,
   record each hard gate R1–R7, decide go/no-go, and tag a **2.0 release
   candidate** only if gates are satisfied.

No release date or guarantee of surpassing strong general-purpose
models is implied. The schedule is driven by repeatable empirical
results and the user's priorities, not a fictional product launch.

## 7. How to contribute or verify

- Original research: `rei0/`, `docs/`, `research/`.
- Existing standalone: `STANDALONE_AI.md`, `rei0/local_ai*.py`,
  `scripts/start_rei_mac.sh`.
- Challenge 12 study: `research/standalone_eval/CHALLENGE12_PROTOCOL.md`,
  `challenge12_cases.json`, `challenge12_quality.py`.
- Base CI: `python -m unittest discover -s tests -p 'test_*.py' -v`.
- Master release tracker: [issue #22](https://github.com/ted-peters/RecursiveEpistemicIntelligence/issues/22).

**Publishing policy:** keep research branch changes separate from
default `main` and the existing Hugging Face demo until the intended
release explicitly approves promotion.
