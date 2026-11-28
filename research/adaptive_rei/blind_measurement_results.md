# Blind measurement test at PR 76

REI answered 14/30 correctly and direct Llama answered 10/30. An independent AI author received the task specification without conversation history, engine source, previous examples or outputs. The key and runner were committed locally before inference. The 30 prompts cover five claims with three evidence conditions each and two paraphrases per condition. They include differences, elapsed time and distances over multiple laps alongside simpler thresholds.

| Measure | REI single-fact | Direct Llama |
|---|---:|---:|
| Supporting evidence correct | 8/10 | 10/10 |
| Contradicting evidence correct | 2/10 | 0/10 |
| Inconclusive evidence correct | 4/10 | 0/10 |
| Both decisive verdicts correct for a claim and wording | 1/10 | 0/10 |
| Same verdict on equivalent phrasings | 10/15 | 15/15 |
| Prompt plus generated tokens | 3,334 | 2,998 |

Direct Llama always answered yes. REI used its model fallback on every question; none triggered its exact measurement rules. For example, it correctly accepted that a full jug holding 1,600 mL exceeds 1.5 L, but also accepted the same claim for a jug holding exactly 1,500 mL. The score is descriptive: repeated phrasings within five topics are correlated, and this baseline uses one model and prompt.

Both arms received the same claim and passage, using the PR 76 code, pinned local Llama 3.2 1B digest, seed 42 and temperature 0. Each method kept its existing instruction and output contract. No production code or key changed after scoring. This concludes the measurement round.

Reproduce from research/adaptive_rei with python3 blind_measurement_trial.py.
