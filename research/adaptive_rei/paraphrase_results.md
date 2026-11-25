# Fixed-passage paraphrase trial

Nine new claims each had three authored question wordings and a single fixed passage. Three claims had each of the expected verdicts yes, no and uncertain. The earlier dispatch example was repeated separately. Cases, labels and the primary metric were committed before inference. This run used one Qwen3 4B model and current prompt settings.

| Mode | Fully correct fresh claims / 9 | Correct fresh answers / 27 | Claims with changing answers / 9 | Fresh tokens |
|---|---:|---:|---:|---:|
| Conventional | 3 | 14 | 4 | 2,761 |
| Budgeted REI | 5 | 20 | 4 | 2,862 |
| Report/event REI | 6 | 22 | 2 | 2,086 |

Report/event REI used 27.1% fewer tokens than budgeted REI. It got every wording of the pool notice question right, but abstained on all three wordings about a witnessed delivery. Budgeted REI answered all three delivery questions correctly. On the prior dispatcher claim report/event returned yes, no, yes; budgeted REI returned no on every wording. A verdict that stays the same can still be wrong.

Use python3 research/adaptive_rei/paraphrase_trial.py with local Ollama to repeat the trial. The raw file records each verdict and token charge. The 27 fresh answers represent nine distinct claims, so the one-claim primary gain warrants independent replication.
