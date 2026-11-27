# Does repeating evidence without a label improve verdicts?

On 48 previously tested passages, Llama 3.2 1B scored 22/48 for both a single copy and an unlabeled second copy. The unlabeled repeat changed 28 verdicts. It fixed ten errors, lost ten correct answers and switched between incorrect answers eight times.

| Correct answers | Passage once | Twice, unlabeled | Twice, “Passage repeated” | Twice, “Selected quote” |
|---|---:|---:|---:|---:|
| Supporting | 11/16 | 4/16 | 8/16 | 13/16 |
| Contradicting | 10/16 | 11/16 | 9/16 | 1/16 |
| Inconclusive | 1/16 | 7/16 | 0/16 | 2/16 |
| Total | 22/48 | 22/48 | 17/48 | 16/48 |

The single-copy control reproduced all 48 saved raw verdicts. Both current conditions used the same pinned model, instruction, claim, passage, enum order, temperature 0, seed 42 and 12-token output limit. The repeat condition appended one newline and a verbatim copy of the passage. The two labeled columns come from the previous paired trial. The 48 passages represent 16 claims, each with three evidence variants.

Repeating the evidence reduced yes responses from 24 to five. It consumed 4,549 prompt plus generated tokens compared with 3,952 for the direct control. The total accuracy tie masks a loss on supporting evidence and a gain on inconclusive evidence. These scores apply to the reused cases and single model.

Run from research/adaptive_rei with the matching Ollama model:

```sh
python3 unlabeled_repeat_trial.py > results/unlabeled_repeat_trial.json
```
