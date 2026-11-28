# Constrained extraction on 16 frozen evidence reversals

| Method | Verdicts returned | Correct passages | Both sides correct | Reported tokens |
|---|---:|---:|---:|---:|
| Saved recursive REI control (PR 68) | 0/32 | 0/32 | 0/16 | 33,744 |
| Full graph schema | 0/32 | 0/32 | 0/16 | 33,654 |
| Single-fact relation schema | 32/32 | 12/32 | 0/16 | 2,941 |

The full graph trial changed only the output format. The benchmark again recorded 30 empty parsed objects and two graphs containing placeholder evidence. The parser maps incomplete or invalid JSON and non-object outputs to the same empty object.

After seeing those failures, we ran an exploratory second arm for single-fact passages. Software inserts the supplied passage as evidence, the model assigns a relation, and the existing evidence parser and evaluator produce the verdict. This mode changes the instruction and uses a 32-token output limit. It assigns clear strength to a model-classified relation, which can give an incorrect answer substantiated status. It does not perform extraction across multiple facts or identify dependencies.

The single-fact mode produced 12 correct supporting answers, zero correct contradicting answers and no complete reversals. Seven claims changed from yes to uncertain when contradicted. The model never returned no. This improves coverage and reduces token usage on this set, while the saved direct baseline remains more accurate at 18/32 and 3/16 complete pairs. These cases have been used throughout development and contain no inconclusive passages.

Run from research/adaptive_rei with the pinned Llama 3.2 1B model available to Ollama:

```sh
python3 schema_fact_trial.py
python3 schema_fact_trial.py --single-fact
```

The benchmark CLI exposes the full graph option with --rei-schema and the one-question mode with --single-fact-schema. Both are opt-in.
