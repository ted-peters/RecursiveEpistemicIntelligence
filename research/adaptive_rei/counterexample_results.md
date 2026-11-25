# Checking whether the opposite answer fits

Labels and the primary endpoint (all three verdicts correct per fresh passage) were frozen before inference. Eight new passages each ask one supported, one contradicted and one unresolved question. The prior nine pairs are diagnostics.

| Fresh mode | Complete / 8 | Correct / 24 | Tokens |
|---|---:|---:|---:|
| Conventional single pass | 2 | 15 | 2,383 |
| Budgeted REI | 2 | 16 | 2,320 |
| Source selection | 0 | 14 | 2,605 |
| Source selection with opposite-answer check | 0 | 9 | 3,833 |

The original pear-tree error persisted in the primary run. The check returned 15 unusable fresh answers. A post-hoc repeat collected raw output: 14 generations reached the 40-token cap, often while explaining a verdict inside unfinished JSON. Raising the cap to 128 gave the same accuracy at 5,065 tokens. We kept the original scoring; unparseable or unsupported decisive verdicts count as wrong.

A second post-hoc diagnostic constrained output to the line and answer fields. At the original 40-token cap the counterexample check scored 17/24 (7/8 yes, 2/8 no, 8/8 uncertain), completed 2/8 passages and used 3,443 tokens. One decisive answer lacked a valid citation. With the same schema and no counterexample instruction, source selection scored 14/24 and completed 0/8, using 2,605 tokens. Budgeted REI got 8/8 no and 3/8 uncertain. These diagnostics reused the fresh passages and are exploratory. Keep budgeted REI as default.

Run counterexample_trial.py and counterexample_diagnostic.py from research/adaptive_rei with the project Ollama model. Verdicts, line references, raw diagnostic responses and token costs are in results/.
