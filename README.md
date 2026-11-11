# Recursive Epistemic Intelligence (REI)

**A philosophy-driven, evidence-aware AI reasoning research project.**

> **Status:** REI-1.0 research software. **Not a pretrained model. Not yet demonstrated to outperform conventional AI.** Public demos use fictional examples and scripted review metadata.

REI examines how provisional beliefs can remain open to challenge, how sources can support or oppose claims, and how changes in evidence propagate through a structured epistemic graph. The project explores philosophical infinite regress as an **open-ended obligation to justify**, while keeping computation and operational safeguards finite.

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
