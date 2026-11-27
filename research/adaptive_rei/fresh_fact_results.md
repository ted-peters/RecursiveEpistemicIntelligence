# Does the verdict follow a one-word evidence change?

Llama 3.2 1B got both verdicts right for 3/16 fresh claim pairs. It answered 18/32 individual passages correctly, with 9/16 correct on each side. Each claim was fixed while one word or number in the passage switched the correct answer from yes to no.

| Verdict on supporting passage | Verdict on contradicting passage | Pairs |
|---|---|---:|
| Yes | No | 3 |
| No | Yes | 1 |
| Yes | Yes | 6 |
| No | No | 6 |

Correct reversals concerned the drawer containing a key, the winner of a spelling final and completion of a ferry crossing. For the kiln threshold of at least 800 degrees, the model said no for both 805 and 795 degrees. For the latch claim, it said no to “fastened” and yes to “unfastened.” All four numerical pairs received unchanged verdicts.

The 16 pairs were authored and committed before inference. Each passage was shown once in an independent local call with the same direct verdict prompt and three possible outputs as the preceding study. The runner alternated which side of a pair was presented first, verified the model digest, and used temperature 0, seed 42 and a 12-token output limit. The 32 calls used 2,542 prompt plus generated tokens. This small set tests decisive evidence reversals on the direct Llama baseline. It contains no ambiguous cases and does not evaluate the adaptive REI engine.

Run from research/adaptive_rei with the matching Ollama model:

```sh
python3 fresh_fact_trial.py > results/fresh_fact_trial.json
```
