# Transfer to externally authored inference questions

The unchanged prompts ran locally against 30 fixed validation pairs from MultiNLI. The sample used the first 100 matched validation rows as the pool and selected two per label in each of five genres. Entailment maps to yes, contradiction to no, and neutral to uncertain. Scoring ignores answer capitalization and surrounding whitespace. Pair IDs were frozen before scoring, the same pairs were used on both models, and reference labels were withheld from prompts.

| Model | Conventional correct (tokens) | Budgeted REI correct (tokens) | Decisive fact first correct (tokens) |
|---|---:|---:|---:|
| Qwen3 4B | 18/30 (3,351) | 21/30 (3,943) | 22/30 (3,906) |
| Llama 3.2 1B | 15/30 (3,922) | 10/30 (2,774) | 11/30 (5,101) |

The Qwen candidate gained two correct neutral decisions but lost one correct entailment relative to budgeted REI. Both got nine contradictions correct. On Llama, all three modes missed all ten neutral cases. The candidate gained one correct entailment versus conventional but lost five correct contradictions. The two models differ in size. This one small public sample cannot establish absence of training exposure, general superiority, or a full-benchmark score.

The completed run used the cached dataset response from the URL in external_transfer_trial.py. The result includes its SHA-256 digest. Run the script with the pinned Ollama models installed to repeat the comparison.
