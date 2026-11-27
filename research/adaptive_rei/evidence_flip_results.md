# Holding claims fixed while changing the evidence

Eight new author-constructed claims each have supporting, contradicting and inconclusive passages. Both local models used the unchanged prompts and claim wrapper from the external transfer trial. Labels and cases were fixed before inference. Each variant was submitted separately. Scoring ignores capitalization and surrounding whitespace. A complete claim requires all three verdicts.

| Model and mode | Yes / 8 | No / 8 | Uncertain / 8 | Complete / 8 | Tokens |
|---|---:|---:|---:|---:|---:|
| Qwen single pass | 5 | 8 | 7 | 4 | 2,378 |
| Qwen budgeted REI | 7 | 8 | 8 | 7 | 2,764 |
| Qwen decisive fact first | 7 | 8 | 8 | 7 | 2,842 |
| Llama single pass | 4 | 7 | 0 | 0 | 2,832 |
| Llama budgeted REI | 0 | 8 | 0 | 0 | 1,907 |
| Llama decisive fact first | 7 | 5 | 0 | 0 | 3,357 |

On inconclusive passages Llama single pass returned five yes and three no answers; budgeted REI returned eight no answers; decisive fact first returned six yes and two no answers. For the observatory claim, Llama cited Nia buying a ticket for her brother and inferred she visited. Qwen cited the same fact and withheld judgment. These related authored variants diagnose verdict sensitivity in these two models at the tested settings; they do not establish why the model errs in general.

Run evidence_flip_trial.py with the local models from the preceding mixed-model trial. The saved rows contain all prompts' verdicts and costs.
