# Adaptive REI measurement results

A frozen program and qwen3:4b-instruct (Ollama model ID 0edcdef34593) were tested on 18 newly authored English cases. Six cases had each expected label. Labels and wording were set before inference. All invalid extractions count as failures. Prompt settings were temperature 0 and seed 42. The model never received the expected label. Cases are related synthetic examples chosen by the evaluator and do not represent a random sample of real use.

| Method | Correct | Tokens | Calls |
|---|---:|---:|---:|
| Direct | 15 | 1,220 | 18 |
| Single-pass evidence instruction | 16 | 1,810 | 18 |
| Adaptive review | 10 | 3,239 | 33 |
| Always review | 8 | 3,507 | 36 |
| Focused review | 15 | 1,220 | 18 |
| Full REI | 12 | 7,407 | 18 |

Token counts include input and generation. Calls and tokens are attributed to each method as if it ran on its own. Focused review's trigger never fired. For direct, single-pass and REI, median elapsed time per case was 0.153, 0.188 and 1.075 seconds respectively. These local serial timings include API and inference time. REI timing also includes evaluation of all four engine policies. The order of the three approaches rotated by case.

## REI outcomes

All four REI policies scored 12/18. Of six examples per label, full REI scored 5 yes, 6 no and 1 uncertain correctly. Three graphs failed validation. Of 14 decisions labeled substantiated, 11 were correct. One decision was provisional and correct. None of the accepted graphs included a usable dependency between claims. On the frozen regression suite, full REI scored 25/25 and the flat policy 18/25; those cases had already guided implementation.

The timestamped mural and stale bus note were incorrectly accepted as proof for the requested date. The queue case treated a before/after association as sufficient evidence of causation. The copied tray mark produced a self-reference, the sample certificate produced an empty directional quote and the runner case used an out-of-range strength. The underlying model supplied useful evidence for the runner before the extraction was rejected.

## Robustness and scale

Three same-input, same-seed repeats reproduced their original graphs and outcomes, including two rejected graphs. Three deliberately selected paraphrases of failed cases changed all three outcomes: two became correct and one was rejected. Of three sentence reorderings, two preserved correct answers and one changed a rejection into a correct answer. These selected probes cannot estimate a population-wide instability rate.

For synthetic chains of 256 claims the recursive engine took a median 0.213 ms across 11 evaluations. It raised RecursionError at 512 and 1,024 claims. For a graph of 1,024 claims sharing a premise it completed in a median 0.856 ms. These in-memory engine tests bypass the extractor, whose parser limits graphs to 20 claims.

## Files

The JSON files contain per-case results, model outputs, evidence graphs, timings, repeat checks and scale probes. The Python files include frozen copies of the engine, benchmark and measurement scripts. To reproduce the main comparison, run python3 rei_measure.py with Ollama serving the installed model on localhost. The supplementary scripts write results to /tmp. First-pass quality is reported separately from repeat and robustness runs. Production performance, cross-model transfer and confidence calibration on independent real-world data remain open.
