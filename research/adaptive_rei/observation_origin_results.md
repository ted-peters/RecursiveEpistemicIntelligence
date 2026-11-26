# Locating an independent observation before answering

Six new scenarios each had four shuffled three-sentence passages. The audit required a relevant firsthand observation of the specified item or event. Each case included an unchecked entry and its copy. The remaining sentence supplied another copy, a wrong-item observation, a supporting observation, or a contradicting observation. The references and trial were committed before inference. The experimental mode selected a numbered sentence or zero. A nonzero selection went to the short verdict decoder with the question; zero yielded uncertain directly.

| Mode | Copies / 6 | Wrong item / 6 | Supports / 6 | Contradicts / 6 | Complete scenarios / 6 | Total tokens |
|---|---:|---:|---:|---:|---:|---:|
| Conventional | 0 | 5 | 3 | 4 | 0 | 2,677 |
| Budgeted REI | 0 | 1 | 3 | 4 | 0 | 2,289 |
| Select then answer | 2 | 6 | 5 | 5 | 2 | 3,449 |

The source-selection score was 13/24. The selector located the decisive sentence in all 12 cases that had one. It correctly selected zero in only 1/12 cases without one. On all six wrong-item cases the verdict was correctly uncertain despite the incorrect nonzero selection. The method improved verdict accuracy on this constructed set, but its output source references remain unreliable when relevant evidence is absent. One model, one run, six distinct claims.

Run observation_origin_trial.py using local Ollama to reproduce the comparison. All presented lines, reference and selected indices, verdicts and token counts are in results/observation_origin_trial.json.
