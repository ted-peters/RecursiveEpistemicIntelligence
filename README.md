# Recursive Epistemic Intelligence (REI)

**A philosophy-driven, evidence-aware AI reasoning research project.**

> **Status:** REI-1.0 research software. **Not a pretrained model. Not yet demonstrated to outperform conventional AI.** Public demos use fictional examples and scripted review metadata.

REI examines how provisional beliefs can remain open to challenge, how sources can support or oppose claims, and how changes in evidence propagate through a structured epistemic graph. The project explores philosophical infinite regress as an **open-ended obligation to justify**, while keeping computation and operational safeguards finite.

## Build a standalone REI-powered AI (local-first)

You can now run REI as a **usable local chat application**, with a browser
interface and an OpenAI-compatible HTTP endpoint. It connects the real
bounded inquiry/graph engine to an independently hosted open-weight
Ollama language model; no ChatGPT account or paid API is required.

**Quick start:** install Docker Desktop, then run
`docker compose up --build` and visit **http://127.0.0.1:7861/**.
On Apple Silicon Macs, run **`bash scripts/start_rei_mac.sh`** from the
cloned repository with native Ollama installed. The browser now offers
**Adaptive (experimental)** mode: zero-cost deterministic routing to Direct
for certain bounded prompts, or the existing selective REI graph inquiry
for investigative questions. The audit always discloses which mode actually
ran, and the explicit Direct/REI choices remain available. It is a
cost-control heuristic, **not** verified evidence or calibrated accuracy.
The first start downloads the open-weight model; model inference runs on
your machine. Keep the app on localhost: it does not include remote user
authentication. For a faster native Mac setup, API examples, and an honest
explanation of what the engine can and cannot verify, see
**[STANDALONE_AI.md](STANDALONE_AI.md)**.

The REI runtime produces model-origin *provisional* reasoning, not
authenticated factual evidence, and it has not been shown to outperform
conventional AI on independent held-out tasks.

## Adaptive REI experiments

An opt-in `--plain-verdict` mode scored 161/200 versus 144/200 for single-pass Qwen on a fresh BoolQ sample while reducing model tokens by 17.4%. On 48 existing three-label controls it scored 39 versus 42. [Usage and paired results](research/adaptive_rei/evidence_budget_results.md#opt-in-plain-verdict)

Short prose passages with explicitly named report dependencies can now use the graph engine directly. In a 30-question synthetic trial covering report chains and ordinary prose controls, this mode scored 29/30 with 572 model tokens. The single-pass baseline scored 19/30 with 3,004 tokens. [Trial breakdown and example](research/adaptive_rei/evidence_budget_results.md#follow-up-trial-on-named-reports-in-prose)

For questions with explicitly declared dependencies, the experimental evidence-budget mode uses the graph engine directly. It scored 24/24 on 12 pairs of synthetic register questions, using zero model tokens. The same Qwen3 4B model with a single evidence prompt scored 13/24. On a separate 24-question prose test, both scored 20/24 and the mode used 6.3% fewer tokens. [Usage, scope and recorded trials](research/adaptive_rei/evidence_budget_results.md)

The [evidence-graph experiments](research/adaptive_rei/rei_findings.md) include the engine, benchmark, measurement scripts and recorded Qwen3 4B outputs. On 18 new synthetic questions, single-pass evidence instructions answered 16 correctly, direct prompting answered 15 and full REI answered 12. The [compact trial](research/adaptive_rei/rei_compact_results.json) answered 4 of those 18 correctly and 3 of 6 additional questions.

Run the deterministic engine comparison from the repository root with `python3 research/adaptive_rei/adaptive_rei_engine.py`. For the Ollama comparison, run `rei_measure.py` from a separate output directory to preserve the recorded results. Pass its `rei_measurements.json` to `rei_compact_trial.py` to repeat the compact trial.

The standalone chat supports opt-in viewpoint comparison through the browser checkbox or the CLI flag `--ideological-understanding`. The [standalone evaluation runs](research/standalone_eval/results/2026-11-18/) record earlier decision-quality and token comparisons.

## REI 2.0 development milestone (not yet released)

The next version is now tracked against measurable release gates in
**[REI 2.0 — Milestone and Release Plan](docs/REI_2_0_MILESTONE.md)**
and [GitHub tracking issue #22](https://github.com/ted-peters/RecursiveEpistemicIntelligence/issues/22).
Its workstreams cover blinded/held-out evaluation, calibrated adaptive cost,
authenticated evidence boundaries, local Mac security/reliability, and a
documented release candidate.

**Latest genuine Qwen3 4B development result (12 public questions):**
Adaptive scored 11/12 using 20,833 tokens, Direct scored 10/12 using
5,551 tokens, Full REI scored 9/12 using 35,889 tokens, and a four-call
self-critique baseline scored 9/12 using 47,419 tokens
([audited run](https://github.com/ted-peters/RecursiveEpistemicIntelligence/actions/runs/43672078062)).
All missed end-to-end grades were output-format failures. This small,
nonblind, non-token-matched study **does not show general superiority**.

**REI 2.0 is a milestone, not a new pretrained foundation model or a
currently available stable release.**

## Start here

- **For visitors:** Explore the Hugging Face demo (after the Space is published). See `space/README.md`.
- **For developers:** Original Python engine is `rei0/`; automated tests are in `tests/`; use `python -m pip install .` and `python -m unittest discover -s tests -v`.
- **For researchers:** Read [`docs/REI_Master_Blueprint_v1.md`](docs/REI_Master_Blueprint_v1.md), [`docs/RESEARCH_STATUS.md`](docs/RESEARCH_STATUS.md) and [`research/challenge5/`](research/challenge5/).
- **For the owner (no command line):** Read [`PUBLISHING_GUIDE.md`](PUBLISHING_GUIDE.md).

## The four evidence states

| State | Meaning |
|---|---|
| `NEITHER` | No admissible verified support or opposition recorded |
| `SUPPORT_ONLY` | Some admissible support and no admissible opposition recorded |
| `ATTACK_ONLY` | Some admissible opposition and no admissible support recorded |
| `BOTH` | Admissible support and opposition coexist |

None of these states establishes objective truth, probability of correctness, or source authenticity.

## Repository guide

```text
rei0/               Original REI-1.0 Python research engine
tests/              REI-1.0 regression tests
docs/               Blueprint, protocols, and research status
examples/           Synthetic development examples
research/challenge5 Public research protocol, code, task statements
space/              Hugging Face Gradio demo source
.github/workflows/   GitHub CI configuration
PUBLISHING_GUIDE.md Publishing without a command line
```

The original REI-1.0 instructions are preserved in [`docs/REI_1.0_ORIGINAL_README.md`](docs/REI_1.0_ORIGINAL_README.md). The MIT license of the source is preserved.

## Important limitations

- This repository has no trained network weights or claimed general-purpose inference endpoint.
- Synthetic benchmark outputs **are not** measured AI performance.
- A verifier signature proves a reviewer made a decision, not that a fact is true.
- Question text from Challenge 5 has circulated and is not a truly blind holdout.
- Public Spaces do not expose secrets or run live, paid inference by default.

## Contributing

Contributions should include tests and distinguish mathematical design, deterministic software behavior, and real empirical findings. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

MIT — see [`LICENSE`](LICENSE).
