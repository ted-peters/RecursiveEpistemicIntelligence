# Does Llama recognize when a passage settles a claim?

Eight newly authored claims each had a supporting, contradicting, and inconclusive passage. The previous eight claims were repeated separately. Prompts, cases and model digest were fixed before the primary run. The first stage chose open or settled. Only settled cases proceeded to a binary verdict. Scoring ignored capitalization and surrounding whitespace.

| Fresh mode | Supports / 8 | Contradicts / 8 | Uncertain / 8 | Total correct | Tokens |
|---|---:|---:|---:|---:|---:|
| Conventional | 6 | 8 | 0 | 14/24 | 2,753 |
| Decisive fact first | 8 | 8 | 0 | 16/24 | 3,224 |
| Sufficiency first | 8 | 0 | 0 | 8/24 | 3,778 |

The gate declined zero clear cases and recovered zero inconclusive cases. It returned settled on every fresh and prior passage, and the direction step then returned yes on all 48. On prior cases the direct, decisive-fact and staged arms scored 11, 12 and 8 out of 24 respectively. Reversing the enumeration order for both calls in a post-hoc diagnostic on the fresh set reproduced all 24 settled/yes outputs. This rules out enumeration order alone as the explanation on these cases. The single-model deterministic run cannot distinguish the effects of the constrained string format, prompt design and model. The staged method remains experimental.

Run sufficiency_trial.py against the local pinned Ollama model. To repeat the enumeration diagnostic, save the primary output in results/sufficiency_trial.json and run sufficiency_order_check.py.
