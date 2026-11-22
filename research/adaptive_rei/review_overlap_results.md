# When a second opinion pays off

The local Qwen3 4B trial paired the same initial verdict and identical eligible reviews across all REI modes. Sampling excluded the questions and passages from 1,176 previously used BoolQ indices. Controls were written for this experiment.

| Mode | BoolQ correct / 240 | BoolQ tokens | Controls correct / 18 | Control tokens |
| --- | ---: | ---: | ---: | ---: |
| Plain verdict | 181 | 41,408 | 17 | 976 |
| Budgeted review | 185 | 44,121 | 17 | 2,057 |
| Experimental word-overlap filter | 182 | 42,588 | 17 | 976 |

The filter skipped eight additional reviews on BoolQ. On indices 3199, 295 and 2117 it retained uncertainty where budgeted review recovered the correct answer. It skipped nine control reviews without changing any verdict. Keep budgeted review available for accuracy-sensitive use. Low word overlap alone is insufficient grounds to skip a review.

Run `python3 research/adaptive_rei/review_overlap_trial.py` with the project's Ollama model. The GitHub comparison workflow also measures the conventional single-pass JSON prompt and archives all per-question verdicts and token counts. Token totals include model input and output.
