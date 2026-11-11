# Challenge 7 — Dynamic evidence revision vs self-critique

## Why this test

Challenge 6's six-case real-model pilot found **self-critique (4/6) ahead of REI (3/6)**. Challenge 7 focuses on a domain that REI was specifically designed to address: sequential evidence, duplicate sources, approvals, contradictions and revocations. Do not reinterpret the earlier pilot as a win.

This is a **six-case, nonblind exploratory experiment**, not a statistically powered test. All episodes, labels and reference answers are published. Every event and source is fictional; nobody has authenticated any real-world evidence. The purpose is to reveal strengths and failure modes, not to validate a general intelligence-superiority claim.

## Two comparisons, two different questions

1. **Deterministic architecture parity.** Independent conventional provenance-aware ledger logic computes each evidence state. The actual original `rei0.graph.EpistemicGraph` independently processes the very same events and validates/revokes graph nodes and edges. Both have access to declared source origins. We test for *agreement at all 24 chronological checkpoints*. A tie demonstrates honest baseline selection; beating a simplistic vote counter is not the objective.
2. **Real language-model reasoning.** The *same SHA-256-pinned Qwen3-4B-Instruct-2507 Q4_K_M* runs through the inherited, unchanged REI-1.0 benchmark's four methods: single pass, self-critique, fixed depth, REI recursive inquiry. Each is asked to interpret identical chronological event descriptions and output the final four-state label. The benchmark automatically records actual tokens, calls, errors and paired case outcomes. REI's questions and claims remain **provisional model-generated work**, not authenticated evidence.

## Limitations committed before model evaluation

- Original benchmark stage prompts and strict schema are unchanged; they sometimes reject malformed model responses, correctly counting them as failures.
- One model, one seed, six public cases, only 24 separate case-arm outputs. Even a six-case victory is not proof of superiority.
- Each arm has a maximum of three model calls, 2,600 reported tokens, 140 seconds, and one inquiry expansion for recursive methods. **Actual consumed compute is not equal.** Match or adjust compute in a later registered study.
- The text is presented as a *complete record*, not streamed as a stateful multi-turn interaction. A model can read the entire timeline. The REI recursive benchmark does **not** call the deterministic graph oracle when grading; the two comparisons must not be conflated.
- Strong conventional ledger parity is expected on the fully specified direct evidence records. Dependency-aware inference, unreliable provenance and independently sourced scientific evidence are not tested here.
- Public gold answers in `keys.json` are never sent in model prompts; they are available for independent grading and auditing. **Not blinded.**

## Protocol and reproduction

- `episodes.json` is the frozen source of the synthetic timelines.
- `build_cases.py` generates `cases.json`, `keys.json`, `oracle_traces.json` and asserts full parity between the conventional ledger and original REI evidence graph; source grouping is supplied metadata.
- `python -m unittest discover -s tests -p test_challenge7.py -v` validates generated tasks, each incremental state, and fail-closed event transitions.
- The GitHub workflow `.github/workflows/challenge7-dynamic-evidence.yml` retrieves and checks the exact same model/engine as Challenge 6 (no API key or provider invoice) and writes an independently regraded JSON report to a retained GitHub Actions artifact.
- Compare **REI vs self-critique first**, report totals, differences and *actual* token use and errors. No post-hoc modification of case texts, answer keys or scoring after viewing results.

## Interpretation

If REI wins on these synthetic questions, that is encouraging preliminary evidence about *recursive question-asking with a small model*, not evidence it improves real-world factual accuracy over capable conventional AI. If the conventional method wins or ties, report that result prominently. Stronger follow-ups should add a genuinely blind evaluator, multiple random seeds and a stateful persistent-memory component with matched resources.