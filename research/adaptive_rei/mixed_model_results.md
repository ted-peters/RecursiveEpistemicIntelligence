# Cross-model checks on six reasoning tasks

Two locally hosted models answered identical yes/no/uncertain questions covering counts, logic, time, records versus events, scope and causality. Each set contains one case per reference label per task. Reference labels stayed outside the prompts. In the first 18 cases Qwen3 4B scored 14/18 in both single-pass and budgeted REI modes. Llama 3.2 1B scored 9/18 single-pass and 6/18 with budgeted REI.

After inspecting these errors, we froze a single-call prompt requesting the decisive fact before the verdict and 18 new questions closely matched to the first set. Here are follow-up correct counts and total input plus output tokens.

| Model | Single-pass | Budgeted REI | Decisive fact first |
|---|---:|---:|---:|
| Qwen3 4B | 13/18 (1,670) | 11/18 (1,441) | 15/18 (1,943) |
| Llama 3.2 1B | 9/18 (1,959) | 6/18 (1,262) | 10/18 (2,447) |

Counts in the table ignore capitalization and surrounding whitespace. Under strict lowercase scoring Llama's candidate scored 8/18. All other scores were unchanged. Qwen twice gave a correct explanation of missing evidence but returned no instead of uncertain. It also abstained when a witness confirmed delivery while the status screen said pending.

The candidate is experimental. This comparison uses two differently sized models, single local runs and authored parallel questions, all restricted to three verdicts. It cannot establish general superiority. The within-model comparisons isolate the answering method better than the between-model scores. Both runs save per-item answers, costs and model digests; the follow-up also saves the generated fact. To reproduce, run mixed_model_trial.py with both listed models installed in Ollama, then decisive_fact_trial.py.
