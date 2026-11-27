# Recognizing contradictions on single-fact questions

A second model call asking whether the passage ruled out the claim changed zero verdicts across the original 32 passages and 24 new controls (eight claims with supporting, contradicting and inconclusive evidence). It raised token use from 5,119 to 12,009. It is an experimental comparator, excluded from the normal single-fact CLI.

An exact comparison is now used by the single-fact mode when the claim gives a supported upper or lower bound and the passage supplies an exact measurement for the same definite subject, property and unit. It copies the full passage into the evidence graph and evaluates that graph. Unsupported wording goes through the pre-existing model route. This narrow English grammar covers ordinary decimal values and number words from zero to twelve. It performs no unit conversions.

| Suite | Correct before | Correct after | Complete yes/no reversals before → after | Tokens before → after |
|---|---:|---:|---:|---:|
| Original 16 pairs | 12/32 | 13/32 | 0 → 1 | 2,941 → 2,761 |
| Eight mixed controls | 13/24 | 14/24 | 0 → 1 | 2,178 → 1,996 |
| Four targeted confirmation claims | 2/12 | 11/12 | 0 → 4 | 1,104 → 368 |

On the original pairs the rule covered the jug capacity claim, and on the mixed controls it covered the strict ticket-price threshold. On the separately frozen confirmation cases it handled all eight decisive measurements correctly with zero model tokens. On the four inconclusive cases it deferred to the model, which returned uncertain three times and yes once. One of these fallback calls changed from yes to uncertain between identical-input runs. Eight of the nine confirmation gains are attributable to the comparator. No supporting or inconclusive case acquired a false no. Small hand-authored, targeted sets are insufficient to estimate general accuracy.

All model calls used the pinned Llama 3.2 1B digest. Each question was evaluated separately. Each full reversal required both decisive answers to be correct. Coverage of ordinary prose remains limited.

Reproduce from research/adaptive_rei with the matching Ollama model:

```sh
python3 contradiction_trial.py
python3 contradiction_trial.py --quantity
```
