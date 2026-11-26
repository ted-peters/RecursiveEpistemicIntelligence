# Checking time before classifying evidence

Eight fresh constructed scenarios and six prior scenarios each crossed two observed states with exact, equivalent, and different times. The primary score required the exact relation (supports, contradicts, irrelevant). Both arms received identical quoted evidence. The two-step arm asked the model to judge the time first and classified direction only on a same-time response. Unknown or malformed gate outputs received no credit.

| Fresh exact-relation score | One call | Time first |
|---|---:|---:|
| Exact wording | 15/16 | 16/16 |
| Equivalent time | 11/16 | 6/16 |
| Different time | 4/16 | 14/16 |
| Total | 30/48 | 36/48 |
| Model tokens | 4,674 | 6,298 |

The second step correctly classified direction on all 22 fresh observations that truly matched and passed the time check. The gate nevertheless rejected ten of sixteen equivalent-time observations. It also accepted 08:00 for eight in the evening with either observed state. On the earlier cases the one-call verifier scored 31/36 at 3,398 tokens and time-first scored 29/36 at 4,616 tokens. These are isolated verifier measurements on one model. The question templates repeat within each scenario. Keep the change experimental.

Run time_before_relation_trial.py with the project Ollama model to reproduce. Each row includes both verifier answers, gate output, and token costs.
