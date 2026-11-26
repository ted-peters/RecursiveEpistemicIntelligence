# Recursive Epistemic Intelligence (REI)

REI is a Python research project for reasoning with evidence. Its starting question is philosophical: when one reason depends on another, how far should an inquiry go? The REI-1.0 engine represents claims, sources, and reasons in a graph. It can ask bounded follow-up questions, track which evidence supports or challenges a claim, and revise an assessment when evidence changes.

The default branch (`main`) contains the graph engine, examples, demos, and the Challenge 5 and 6 studies. Later Adaptive REI experiments use an existing language model to test ways of answering and reviewing questions. Those experiments have their own code and results on research branches.

## Try the graph

From the repository root, run these commands in a Python environment. The package supports Python 3.10 and later. Use Python 3.13 to reproduce the archived report checks used by CI.

```sh
python -m pip install .
python -m examples.quick_example
```

The example asks whether a lamp is lit. Initially the graph reports `NEITHER`. After a scripted reviewer accepts the sensor reading and its connection to the claim, the graph reports `SUPPORT_ONLY`. This example runs locally without a model download or API key. [Example source](examples/quick_example.py)

| Evidence state | What the graph has recorded for the claim |
|---|---|
| `NEITHER` | No admissible evidence on either side |
| `SUPPORT_ONLY` | Admissible evidence for the claim only |
| `ATTACK_ONLY` | Admissible evidence against the claim only |
| `BOTH` | Admissible evidence on both sides |

These states describe the reviewed record. The quality of an assessment depends on the sources and the review. For the interactive examples with fictional evidence and simulated approvals, see the [Gradio demo](space/) or the [static demo](space-static/).

## What has been tested?

**Challenge 5** provides public tasks, a study protocol, and evaluation code. Its synthetic runs exercise the evaluation pipeline. The tasks have circulated publicly, which limits their use as a blind holdout. [Challenge 5 materials](research/challenge5/)

**Challenge 6** ran four methods on the same six hand-authored questions using a pinned Qwen3 4B model through llama.cpp. Failures count in the scores.

| Method | Correct | Reported tokens |
|---|---:|---:|
| Single pass | 2/6 | 1,545 |
| Self-critique | 4/6 | 7,568 |
| Fixed-depth inquiry | 1/6 | 5,222 |
| REI graph-guided inquiry | 3/6 | 7,972 |

Self-critique led this pilot. The small public sample and differing token use limit what it can establish about general model performance. [Challenge 6 results, failures, and reproduction details](research/challenge6/ACTUAL_RESULTS.md)

**Adaptive REI research branches** explore when a second review or a deterministic rule improves an answer. In one Qwen3 4B comparison on 240 BoolQ questions, budgeted review scored 189/240 using 43,392 tokens. The single-pass prompt scored 159/240 using 50,246 tokens. On 18 targeted controls in that same run, single pass scored 18/18 and budgeted review scored 17/18. These scores apply to those prompts, questions, and model. Later work tests whether REI can identify the relevant observation and preserve its timing when extracting evidence from prose. [Paired benchmark report](https://github.com/ted-peters/RecursiveEpistemicIntelligence/blob/04db61bc2beb0785ce0ee511ed131b5b0197b34a/research/adaptive_rei/review_overlap_results.md) · [Prose time-extraction experiment](https://github.com/ted-peters/RecursiveEpistemicIntelligence/pull/54)

## Development and research materials

- Explore the [engine](rei0/), [original REI-1.0 guide](docs/REI_1.0_ORIGINAL_README.md), and [design blueprint](docs/REI_Master_Blueprint_v1.md).
- Run the regression suite from the repository root with `python -m unittest discover -s tests -v`. The [research status notes](docs/RESEARCH_STATUS.md) explain the Python-version sensitivity of the archived checks.
- See the [contribution guide](CONTRIBUTING.md), [publishing guide](PUBLISHING_GUIDE.md), and [MIT license](LICENSE).
