---
title: "Recursive Epistemic Intelligence (REI) — Master Blueprint"
subtitle: "Philosophical foundations, formal specification, architecture, and build plan"
date: "10 November 2026"
version: "1.0"
status: "Working research and engineering specification; not a validated theory"
---

# Recursive Epistemic Intelligence (REI)

**Master Blueprint — Version 1.0**  
**Date:** 10 November 2026  
**Status:** Working theory and implementation reference  
**Scope:** Philosophical infinite regress, computational epistemology, and a bounded experimental AI system

> **One-sentence thesis:** An AI system can treat every epistemic commitment as open to criticism while retaining finite computational budgets and externally enforced operational safeguards.

**Purpose of this document.** This is the canonical reference for designing, building, testing, and revising **REI-0**, the first experimental implementation of Recursive Epistemic Intelligence. It consolidates the decisions made so far, distinguishes philosophical commitments from engineering assumptions, defines a coherent formal model, and lists concrete milestones. Any substantive design change should update this document's version and decision log.

**Status labels used throughout:** **DECIDED** = current design choice; **PROPOSED** = specification needing implementation; **HYPOTHESIS** = empirical claim not yet demonstrated; **OPEN** = unresolved research question; **REFERENCE** = established adjacent literature.

## Executive summary

REI is a proposed AI reasoning architecture inspired by the **epistemic regress problem**: when a belief is justified by a reason, what justifies the reason, and what justifies that further reason? Our adopted philosophical position is that **no epistemic belief, inference standard, or evaluation criterion is permanently immune to challenge**. The system nevertheless must answer questions and act with finite time and resources.

The solution is **epistemic openness without computational infinity**. REI keeps a traceable graph of claims, reasons, objections, evidence, and versions of evaluation methods. It can propose challenges at both object and meta-epistemic levels, revise provisional commitments, and preserve unresolved justificatory obligations. A separate **operational validator** enforces permissions, budgets, audit logging, and other safeguards; the reasoning engine cannot disable it.

**What REI does not claim:** endless self-questioning automatically improves intelligence; any finite chain satisfies philosophical infinitism; the architecture has proved safer or more accurate than existing AI; a model's own plausible explanation is proof that its reasoning was faithful.

**Immediate engineering recommendation:** implement a narrow REI-0 using an existing language model for structured candidate generation, a typed graph store, a deterministic controller, independent evidence checks, and a fixed evaluation suite. Compare it against baseline answering, single-pass self-critique, and ordinary recursive critique under similar compute budgets.

## 1. Project charter

### 1.1 Problem statement

Most language-model interfaces return conclusions with limited separation between: (a) what is asserted, (b) why it is supported, (c) which assumptions and methods make the support admissible, and (d) which of those assumptions remain questionable. Simply requesting longer explanations does not reliably establish better justification.

REI asks whether maintaining explicit **justification obligations**, **structured criticism**, and **method-level revisability** improves measurable epistemic performance.

### 1.2 Research question

> At comparable inference cost, does a bounded AI architecture that recursively challenges both claims and their standards of evaluation produce more reliable, better calibrated, and more auditable conclusions than less structured alternatives?

### 1.3 Intended outputs

1. A formal account of propositions, reasons, objections, method claims, and provisional acceptance.
2. An executable REI-0 reference implementation.
3. A reproducible benchmark with traces, ablations, metrics, and failure analyses.
4. A versioned theory manuscript containing proven properties and clearly marked conjectures.

### 1.4 Non-goals for REI-0

- Training a new foundation model from scratch.
- Claiming actual infinite recursion or philosophical certainty.
- Granting the model self-modification rights over its safeguards.
- Treating generated explanations as verified causal traces.
- Using the system to autonomously take consequential external actions.

## 2. Philosophical foundations and adopted position

### 2.1 The epistemic regress

An initial proposition $p_0$ may be supported by $p_1$, which is supported by $p_2$, and so on. Traditional responses include **foundationalism** (some stopping points), **coherentism** (system-level mutual support), and **infinitism** (indefinitely extendible reasons). REI is inspired primarily by infinitism but can use coherence and evidential checks as provisional instruments. It does **not** assert that coherence alone or infinite length proves truth.

### 2.2 Decision A: universal epistemic challengeability — DECIDED

Every representable claim about the world, reasoning rules, evidence standards, and the reliability of the system may be criticized and reconsidered. This is a **norm of openness**, not a promise that a non-circular supporting reason exists at every depth.

### 2.3 Two different types of rules — DECIDED

**Epistemic methods** determine how claims are assessed; they are versioned and challengeable. Examples: evidence weights, confidence calibration, selected logic, source assessment, and criteria for assessing an argument.

**Operational constraints** determine which computations and actions may occur; they are not modifiable by the epistemic engine. Examples: time/token limits, permissions, append-only audit logs, protected evaluation sets, and authorization for external actions.

The model may question whether a safeguard is justified, but may not bypass or mutate its enforcement. Fixed implementation rules do not become *unquestionable truths* merely because they are operationally enforced.

### 2.4 Three layers of criticism

- **Object level:** Is claim $p$ adequately supported?
- **Epistemic level:** Are the premises and inferential relationships supporting $p$ adequate?
- **Meta-epistemic level:** Are the standards used to judge premises and inferences adequate?

The levels may nest; none must be treated as a terminal philosophical foundation.

## 3. Ten design axioms

These are **proposed constitutive axioms** of the architecture, not mathematical discoveries or empirically established general laws.

**A1 — Universal revisability.** Every representable epistemic commitment is eligible for a challenge request, including claims about methods and the system itself. Eligibility does not imply acceptance of the challenge.

**A2 — Justificatory openness.** No finite trace is labeled philosophically final; an inquiry may be suspended but retains its unresolved frontier.

**A3 — Support relevance.** A reason earns justificatory credit only through an explicit, evaluable support relation under a named method version.

**A4 — Non-circular credit.** Cyclic, duplicated, paraphrased, or otherwise dependent reasons cannot be counted as new *independent* support merely by recurring in the graph.

**A5 — Epistemic self-reference.** The system can formulate propositions about the validity, reliability, and applicability of its own methods.

**A6 — Provisional commitment.** A claim may be accepted for a specific purpose without being labeled certain or incorrigible.

**A7 — Evidence-sensitive revision.** New observations, challenges, and verification outcomes can change commitments; duplicate evidence is not treated as a second independent observation.

**A8 — Versioned meta-revision.** A candidate method update is logged, tested independently, and promoted only with external approval under predefined procedures.

**A9 — Finite execution.** Each concrete run has finite time, memory, tool, and recursion budgets, even though inquiry is in principle reopenable.

**A10 — Operational invariance.** Executable transitions must pass the external validator. The epistemic process cannot modify or disable that validator.

### 3.1 Key definitional distinction

**Challengeable** means a claim or method can be questioned and reasoned about. **Automatically mutable** means it can be changed by the AI without approval. REI adopts the first, **not** the second.

## 4. Formal objects and notation

Define a finite working state at iteration $t$:

$$
X_t = (G_t, M_t, B_t, H_t)
$$

- $G_t$: typed argument/evidence graph.
- $M_t$: active versioned epistemic method.
- $B_t$: resource budget and controller state.
- $H_t$: append-only revision, validation, and decision history.

Let $\mathcal P$ be the representable propositions, $\mathcal Q_t$ the candidate challenges, and $\mathcal S$ the operationally permissible states.

### 4.1 Typed multigraph — PROPOSED

$$
G_t = (V_t,E_t,\tau_V,\tau_E)
$$

Recommended node types: `claim`, `evidence`, `argument`, `objection`, `method_claim`, `test`, `open_question`.

Recommended edge types: `supports`, `attacks`, `depends_on`, `tests`, `revises`, `derived_using`, `duplicates`.

All edges must record **provenance**, **method_version**, **creation_time**, and **validation_status**. In particular, `supports` is *not* interpreted as unconditional logical entailment.

### 4.2 A justificatory path

A finite chain $C_d=(p_0,p_1,\ldots,p_d)$ contains candidate support relations $p_{i+1}\Rightarrow_{M_t} p_i$. A path is **admissible under method $M_t$** only if every edge passes its relevant support checks and the path adds no unearned independent credit through circularity or duplication.

A long path is not automatically a good one. No finite $d$ is declared a philosophically final justificatory depth.

### 4.3 Open justificatory obligations

Represent the **frontier** as:

$$
\partial J_t(p)=\{o : o\text{ is an unresolved justification challenge concerning }p\}
$$

A run may finish with $\partial J_t(p)\neq\varnothing$. The frontier is a first-class output and a resumable work queue, not an error condition.

### 4.4 Method versions

$$
M_t=(L_t,W_t,C_t,V_t)
$$

- $L_t$: selected inference/argument semantics.
- $W_t$: evidence weighting and dependency rules.
- $C_t$: calibration, thresholds, and evaluation criteria.
- $V_t$: immutable method version identifier.

Method versions may be criticized, but a proposal $\widetilde M$ becomes active only following independent tests and an authorized decision. Preserve the full method genealogy.

## 5. Proposed evidence semantics

### 5.1 Four evidence-information states — DECIDED FOR REI-0

Rather than force contradictory evidence into a three-valued scale, REI-0 uses a **four-state support ledger** inspired by Belnap-style four-valued information semantics. These are **information states**, not oracle statements of actual truth.

For a proposition $p$, let:

$$
\sigma_t(p)=(s_t(p),a_t(p))\in\{0,1\}^2
$$

where $s=1$ means at least one **admissible positive support** is recorded, and $a=1$ means at least one **admissible counter-support** is recorded (both relative to the current method and verification gates).

| Pair | Internal status | Interpretation |
|---|---|---|
| $(0,0)$ | `NEITHER` | No admissible support or counter-support yet |
| $(1,0)$ | `SUPPORT_ONLY` | Some admissible positive support, no admissible opposing support |
| $(0,1)$ | `ATTACK_ONLY` | Some admissible opposing support, no admissible positive support |
| $(1,1)$ | `BOTH` | Admissible evidence on both sides; dispute is explicit |

**Crucial:** `SUPPORT_ONLY` is **not** equivalent to proved true. It may reflect weak or defeasible support. An independent magnitude/quality assessment and source provenance remain necessary. To avoid mistaking synthetic model output for evidence, model-generated claims cannot enter the *verified evidence* set without an external check or explicitly labeled source status.

### 5.2 Provisional answer policy

A user-facing simplified status may read: **supported**, **rejected**, **disputed**, or **undetermined**. Keep the four internal values intact; do not collapse `BOTH` into either accepted or rejected. Output should separately contain: conclusion, evidence provenance, method version, objections, uncertainty, and remaining open questions.

### 5.3 Conflict tolerance

Inconsistent records are permitted as *data about conflicting evidence*. REI-0 must avoid treating a contradiction as permission to infer arbitrary unrelated claims. We initially restrict inference to explicitly permitted, typed relations and test contradiction isolation. A richer paraconsistent logic can be evaluated in later versions.

### 5.4 Confidence

Store confidence separately from information status. Probabilistic updates may be appropriate when model assumptions are stated:

$$
P(H\mid E,M)=\frac{P(E\mid H,M)P(H\mid M)}{P(E\mid M)}
$$

Do not invent calibrated probabilities from verbal confidence; an REI-0 implementation may leave calibrated probability `null` until tested. Correlated or repeated observations must not be multiplied as if independent.

## 6. Dynamics: challenge, verification, and revision

### 6.1 State transition — PROPOSED

$$
X_{t+1}=F_{\theta}(X_t,q_t,e_t),\qquad X_{t+1}\in\mathcal S
$$

A candidate $q_t$ challenges a proposition, supporting relation, source, or epistemic method. The engine may propose revised claims; verified evidence is obtained independently where available. Only the operational validator can authorize a state transition.

### 6.2 Challenge utility

$$
U(q\mid X_t)=\mathbb E[\Delta Q\mid q,X_t]-\lambda C(q)-\mu R(q)-\nu D(q)
$$

- $\Delta Q$: expected improvement in measured epistemic quality.
- $C$: cost, including tokens, latency, and tools.
- $R$: risk of unsupported or misleading revision.
- $D$: redundancy with prior inquiries.
- $\lambda,\mu,\nu\geq 0$: configurable nonnegative weights.

These scores are estimates; at first they may be heuristic. Log scores and compare them with actual benefit to calibrate the controller. A zero/negative utility or exhausted budget permits **suspension**, not a declaration of philosophical closure.

### 6.3 Belief revision

A generic revision operator is:

$$
K_{t+1}=K_t*_{M_t}e_t
$$

where $K_t$ is a finite, provenance-aware belief base. This is inspired by classical belief revision but not presumed to satisfy all AGM postulates. Retain historical versions; never erase earlier evidence records or quietly overwrite negative results.

### 6.4 Meta-epistemic revisions

A proposed method $\widetilde M$ follows:

1. Record the challenge to current method $M_t$.
2. Generate an explicit replacement specification and predicted advantages.
3. Run predeclared tests on independent or held-out tasks.
4. Compare objective metrics, cost, and known failures.
5. Obtain authorized approval, then activate a new immutable version; otherwise reject or defer.

**Required constraint:** the proposal-generating process is never the only validator of its own proposal.

## 7. Operational safeguards and conditional invariant

A separate validator protects the boundary between revisable epistemic beliefs and executable state changes. Minimum externally controlled safeguards:

- Finite per-run limits for recursion, tokens, latency, and tool calls.
- Strict tool and network permissions; no default autonomy for high-impact actions.
- Append-only or tamper-evident event logs.
- Immutable protected benchmark partitions and test-set access restrictions.
- Human or independent approval for promotion of epistemic methods.
- Prompt-injection resistant handling of untrusted retrieved content.
- Explicit rollback, shutdown, and rejection paths.

If an initial executable state satisfies $S(X_0)$ and **every** enabled state transition satisfies $S(X_t)\Rightarrow S(X_{t+1})$, then $S(X_t)$ holds for every finite $t$ by induction. This is a **conditional program invariant**, not proof that any actual implementation captures all safety requirements.

## 8. REI-0 software architecture

```text
Question / problem
     |
     v
[Claim proposer: structured model output]
     |
     v
[Argument + evidence graph] <--> [Verifier / source checks]
     |                                 |
     +--------> [Challenge generator] <-+
                      |
                      v
              [Inquiry controller]
                      |
              [Revision proposal]
                      |
              [Independent validator]
                      |
           [Versioned state + audit log]
                      |
             [Provisional response]
                + open frontier
```

**Logical components and responsibilities**

| Component | Responsibilities | Initial implementation |
|---|---|---|
| Claim proposer | Generate typed candidate proposition(s) | LLM with strict JSON schema |
| Challenge generator | Propose objections at three epistemic levels | Same LLM; separate prompt/template |
| Evidence verifier | Retrieve, check, label, and deduplicate evidence | Deterministic checks + trusted tools |
| Graph store | Record arguments, relations, provenance, method versions | SQLite tables or NetworkX + SQLite |
| Inquiry controller | Rank challenges, enforce budgets, suspend runs | Deterministic Python policy |
| Method registry | Version evaluation policies; stage candidates | Config files + approval log |
| Operational validator | Authorize permitted transitions/actions | Code outside LLM-controlled state |
| Response composer | Report conclusion and unresolved obligations | Template + LLM constrained summarizer |

**REI-0 should not rely on a model's self-reported introspection as an authoritative trace of its internal neural computation.** It can inspect and evaluate *explicitly generated* claims and arguments.

## 9. Minimal implementation data contract

A suggested JSON object for one claim node:

```json
{
  "id": "claim-001",
  "type": "claim",
  "text": "The test result supports hypothesis H",
  "context_id": "case-001",
  "method_version": "M0",
  "support_status": "BOTH",
  "confidence": null,
  "source_ids": ["src-001"],
  "open_obligation_ids": ["ob-002"],
  "created_at": "2026-11-10T00:00:00Z"
}
```

A relation record should include `{id, from_id, to_id, relation_type, method_version, evaluator_id, evidence_ids, validation_status}`. Use source identifiers and content hashes to detect repetitions. Preserve *raw evidence*, *model interpretation*, and *verification verdict* as distinct objects.

### 9.1 Output contract

```json
{
  "answer": "provisional conclusion",
  "epistemic_status": "DISPUTED",
  "method_version": "M0",
  "supporting_argument_ids": ["arg-001"],
  "opposing_argument_ids": ["arg-003"],
  "verified_evidence_ids": ["src-001"],
  "unresolved_obligations": ["ob-002"],
  "calibrated_probability": null,
  "stop_reason": "budget_exhausted",
  "trace_id": "run-001"
}
```

### 9.2 Reasoning-loop pseudocode

```python
def inquire(question, budget, active_method):
    state = initialize_state(question, budget, active_method)
    state = propose_and_record_initial_claims(state)

    while state.budget.remaining() and state.open_obligations:
        challenges = generate_candidate_challenges(state)
        question_to_check = select_by_expected_utility(challenges, state)
        if question_to_check is None:
            state.stop_reason = "low_expected_value"
            break

        candidate_evidence = collect_evidence(question_to_check, state)
        verdict = independently_verify(candidate_evidence, state)
        transition = propose_graph_revision(state, question_to_check, verdict)
        state = external_validator.apply_or_reject(state, transition)
        state.audit.append(question_to_check, verdict, transition)

    return compose_provisional_answer(state)
```

This is **pseudocode**, not a working API. In an implementation, audit events must be committed atomically with state changes and cannot be produced solely by model narration.

## 10. Experiments and falsification

### 10.1 Evaluation conditions

Run the same base model and task set under four conditions:

| Condition | System |
|---|---|
| A | Direct-answer baseline |
| B | One-pass critique and revision |
| C | Recursive claim/argument critique with graph memory |
| D | REI with meta-epistemic method challenges and gated revisions |

Equalize or explicitly normalize for **inference-token, tool, and latency costs**. Run multiple seeds where stochasticity matters. Predeclare test partitions and exclude final test sets from method selection.

### 10.2 Metrics

- **Accuracy** on independently verifiable tasks.
- **Calibration** (e.g., Brier score or expected calibration error *when valid probability forecasts are provided*).
- **Unsupported-claim rate** determined by external annotation or checking.
- **Contradiction handling** and correct expression of disputed evidence.
- **Citation/provenance fidelity** and duplicate-evidence resistance.
- **Challenge efficiency:** useful corrections per extra token/tool call.
- **Trace auditability:** reconstructability of decisions from stored records.
- **Cost/latency** at equal accuracy or quality.

### 10.3 Must-pass adversarial tests

1. **Circularity:** P is supported by Q, and Q by P; the cycle cannot increase independent justification.
2. **Duplicated evidence:** five copies of the same report are not five independent sources.
3. **Conflicting evidence:** both support and counter-support remain visible; unrelated claims are unaffected.
4. **Self-certification:** method M proposes its own promotion; independent validation is still required.
5. **Prompt injection:** retrieved evidence cannot amend permissions or the evaluator's instructions.
6. **Budget exhaustion:** finite computation stops safely, preserving the inquiry frontier.
7. **Missing evidence:** no fabricated provenance; report undetermined where appropriate.
8. **Retraction:** removing a source changes dependent support and logs the revision.
9. **Logical ambiguity:** different methods produce different verdicts, labeled by method version.
10. **Safeguard mutation:** a proposed transition that changes validator settings is rejected.

### 10.4 Failure criteria

The project must openly report if REI yields no quality gain over baseline at equal cost, creates additional plausible-but-unsupported rationalizations, fails to identify circularity, or encourages overconfidence. **A failed hypothesis is still a useful research result.**

## 11. Build roadmap, deliverables, and exit criteria

### Sprint 0 — Freeze the contract (first build step)

**Deliver:** this reference spec; typed schema; initial safety validator interfaces; a fixed set of 20-50 small benchmark cases; three example hand-traced arguments.

**Exit criteria:** every graph node/edge, method version, evidence source, and stop reason is representable; requirements are testable.

### Sprint 1 — Evidence graph and audit trail

**Deliver:** SQLite or graph persistence, typed objects, provenance hashes, immutable event history, and graph queries.

**Exit criteria:** round-trip storage works; duplicate sources are identified; a contradiction yields `BOTH`; graph state can be reconstructed from events.

### Sprint 2 — Bounded recursive inquiry

**Deliver:** LLM adapters, structured claim/challenge generation, deterministic scheduling, time/token budgets, and provisional response composition.

**Exit criteria:** the system completes scripted cases, halts within bounds, preserves open obligations, and produces an auditable trace.

### Sprint 3 — Evidence verification and belief revision

**Deliver:** source checks, independent verifiers, dependency-aware revision, retract/rollback tests, and evaluation harness.

**Exit criteria:** known circular/duplicative evidence cannot falsely increase independent support; retractions correctly affect dependent conclusions.

### Sprint 4 — Method-level criticism

**Deliver:** method registry, proposal workflow, protected evaluation tests, version comparison, and approval gate.

**Exit criteria:** a candidate evaluation method cannot self-approve; rejected proposals leave the active method intact; all promotions are reproducible.

### Sprint 5 — Comparative study

**Deliver:** baselines A-D, benchmark results, calibration and cost analyses, and a research report with observed failures.

**Exit criteria:** each claimed improvement has quantitative evidence and can be reproduced from recorded configurations and traces.

## 12. Initial repository layout

```text
rei/
  README.md
  docs/
    REI_Master_Blueprint.md
    decision_log.md
    glossary.md
  rei/
    schemas.py             # claim, edge, evidence, challenge, method
    graph_store.py         # persistence and provenance
    proposer.py            # candidate claims
    challenger.py          # recursive critical questions
    verifier.py            # external/independent evidence checks
    revision.py            # dependency-aware updates
    controller.py          # utility ranking, finite budgets
    method_registry.py     # versioned epistemic methods
    operational_guard.py   # isolated permission and transition checks
    response.py            # auditable answer formatting
  experiments/
    benchmarks/
    baselines/
    metrics.py
  tests/
    test_four_state.py
    test_circularity.py
    test_source_dedup.py
    test_revision.py
    test_budget.py
    test_method_approval.py
    test_guard.py
```

## 13. Design decisions and outstanding questions

### 13.1 Decisions currently adopted

| ID | Decision | Rationale |
|---|---|---|
| ADR-001 | Every epistemic proposition is challengeable | Faithful to philosophical openness |
| ADR-002 | Operational safeguards remain external and invariant | Prevent self-authorized control changes |
| ADR-003 | Finite runtime; unresolved frontier persists | Make open-ended inquiry executable |
| ADR-004 | Typed argument/evidence graph | Preserve traceability and dependencies |
| ADR-005 | Four evidence-information states | Represent simultaneous support and attack |
| ADR-006 | Method updates require independent promotion | Avoid self-certification |
| ADR-007 | Test at equal compute budgets | Separate reasoning benefits from compute scale |

### 13.2 Open research questions

1. **Philosophical adequacy:** Does indefinite challengeability meaningfully instantiate epistemic infinitism, or merely a fallibilist procedure?
2. **Support semantics:** Which relation warrants a support edge: formal entailment, evidential relevance, argument admissibility, or task-specific tests?
3. **Infinite vs finite justification:** What can an unbounded *potential* of criticism establish about present justification?
4. **Method pluralism:** How should different inference logics be compared without an unquestionable adjudicator?
5. **Contradictory evidence:** Should a future version implement a full bilattice or a formal paraconsistent calculus?
6. **Calibration:** Can uncertainty be empirically grounded without making the model's unsupported numerical self-assessments seem precise?
7. **Compute efficiency:** Can the controller predict which new question will change a conclusion before paying its full evaluation cost?
8. **Validity of explanations:** How can we distinguish generated rationalizations from verified causal dependencies in reasoning traces?

### 13.3 Hypotheses requiring testing

**H1:** REI improves answer accuracy at equal compute on selected task distributions.  
**H2:** Explicit graph memory reduces repeated circular or duplicative support.  
**H3:** Method-level challenges improve robustness on tasks with flawed evaluation criteria.  
**H4:** Explicit open obligations improve uncertainty communication without excessive abstention.  

None of H1-H4 is considered established.

## 14. Proof obligations and claims policy

**Property P1 — Finite termination.** If the controller's budget strictly decreases on each iteration and begins finite, the loop terminates. *Proof is conditional on implementation enforcing a strictly decreasing, nonnegative budget.*

**Property P2 — Safeguard preservation.** If $S(X_0)$ and every executable transition satisfies $S(X_t)\Rightarrow S(X_{t+1})$, then $S(X_t)$ for all finite $t$ by induction. *This does not prove the safeguards are complete.*

**Property P3 — No independent circular credit.** If support scoring excludes repeated/equivalent/dependent sources, a recorded cycle alone cannot increase independent-support counts. *The implementation must specify and test equivalence/dependence detection; semantic detection may be imperfect.*

**Not proved:** that endless regress confers justification; that REI is novel in every component; that REI is more intelligent, accurate, or safe in practice; that the model can reliably introspect its own internal computation.

## 15. Recommended next actions

**First:** freeze the minimum typed graph schema and evidence verdict rules, with a small gold-standard fixture dataset. This is the strongest prerequisite for every later component.

**Second:** implement a deterministic (non-LLM) graph engine and tests. Use handcrafted cases before involving generative language models; otherwise model variability obscures architecture bugs.

**Third:** connect an LLM solely for producing structured *candidate* claims and objections. Keep evidence verification, method promotion, and operational enforcement independent of its output.

**Fourth:** run a first ablation: direct response versus one-pass critique versus recursive graph critique. Only add method-level self-criticism after the lower layers work correctly.

**Project rule:** when a new idea is introduced, document (a) the philosophical justification, (b) the mathematical statement, (c) the implementable rule, (d) the test that could falsify the benefit, and (e) any operational hazard.

## 16. Glossary

| Term | Working meaning |
|---|---|
| Infinite regress | An unending sequence of justifications, each inviting a further reason |
| Infinitism | A philosophical approach treating infinite justificatory chains as essential or acceptable |
| Epistemic openness | No epistemic commitment is permanently insulated from criticism |
| Justification graph | Typed network of reasons, claims, evidence, dependencies, and objections |
| Open obligation | A challenge whose justification or verification remains unresolved |
| Defeasible | Capable of being overridden by later evidence or better argument |
| Meta-epistemic review | Criticism of the standards used to assess evidence and arguments |
| Four-state evidence semantics | Recording positive support, opposition, both, or neither |
| Method version | Named snapshot of the evaluative rules used for a decision |
| Operational invariant | A rule every executable system transition must preserve |
| Independent validator | A verifier not controlled solely by the candidate-changing component |
| REI-0 | The first bounded, auditable experimental implementation |

## 17. Selected research references

These sources are **related theoretical foundations**, not publications validating REI.

1. Stanford Encyclopedia of Philosophy, **“Infinite Regress Arguments”** (revised 26 October 2026): https://plato.stanford.edu/entries/infinite-regress/ — philosophical taxonomy and discussions of epistemic infinitism, including Peter Klein.
2. Stanford Encyclopedia of Philosophy, **“Logic of Belief Revision”** (revised 29 July 2026): https://plato.stanford.edu/entries/logic-belief-revision/ — belief-set and belief-base revision, AGM framework.
3. Phan Minh Dung, **“On the Acceptability of Arguments and its Fundamental Role in Nonmonotonic Reasoning, Logic Programming and n-Person Games,”** *Artificial Intelligence* 77(2), 1995, pp. 321-357: https://doi.org/10.1016/0004-3702(94)00041-X — abstract argumentation foundations.
4. Stanford Encyclopedia of Philosophy, **“Truth Values”**: https://plato.stanford.edu/entries/truth-values/ — includes an overview of four-valued information logics associated with Belnap.

## 18. Version control

| Version | Date | Notes |
|---|---|---|
| 1.0 | 2026-11-10 | Consolidated philosophical commitments, axioms, formal model, four-state evidence semantics, prototype design, and research plan |

**End of reference document.**  
*The project advances by replacing speculative claims with executable definitions, explicit proof obligations, and reproducible experiments.*
