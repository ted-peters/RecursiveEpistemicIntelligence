# Labeling a repeated passage

Changing the prefix of a second copy of the passage from “Selected quote” to “Passage repeated” changed 28 of 48 verdicts. It corrected nine errors and lost eight correct answers. Eleven other changes switched between two incorrect answers.

| Correct verdicts | Passage once | Selected quote | Passage repeated |
|---|---:|---:|---:|
| Supporting evidence | 11/16 | 13/16 | 8/16 |
| Contradicting evidence | 10/16 | 1/16 | 9/16 |
| Inconclusive evidence | 1/16 | 2/16 | 0/16 |
| Total | 22/48 | 16/48 | 17/48 |
| Prompt plus generated tokens | 3,952 | 4,678 | 4,719 |

“Passage repeated” reduced yes answers from 37 to 23. On the three passages about Ari attending rehearsal, “Selected quote” produced yes for all three and “Passage repeated” produced no for all three. Neither label distinguished supporting, contradicting and inconclusive evidence for that claim. Showing the passage once remained the most accurate of these conditions.

The trial reused the previous 48 passages (three variants for each of 16 claims) and the same local Llama 3.2 1B digest, three verdict options, temperature 0, seed 42 and 12-token output cap. Both control conditions reproduced all 48 previous raw responses. The repeated conditions differed only in the field label. Neither repeated condition tested a second copy with no label.

Run from research/adaptive_rei with the matching Ollama model:

```sh
python3 repeated_label_trial.py > results/repeated_label_trial.json
```
