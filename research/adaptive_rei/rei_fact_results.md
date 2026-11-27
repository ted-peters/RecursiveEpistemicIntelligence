# Adaptive REI on one-word evidence reversals

With Llama 3.2 1B as its extractor, the existing recursive REI pipeline returned no verdict on any of the 32 passages. All 32 evidence extractions failed validation before the recursive policy could evaluate them.

| Method | Correct passages / 32 | Both verdicts correct / 16 pairs | Verdicts returned / 32 | Reported tokens |
|---|---:|---:|---:|---:|
| Direct Llama, saved claim/passage wording | 18 | 3 | 32 | 2,542 |
| Direct Llama, same question wording as REI | 16 | 0 | 32 | 2,608 |
| Adaptive REI, Llama evidence extraction | 0 | 0 | 0 | 33,744 |

The saved direct baseline reversed correctly for the drawer, spelling winner and ferry pairs. The matched direct control returned yes on 31 passages and uncertain on one. For REI, the benchmark recorded an empty parsed object on 30 passages. Its parser uses that same representation for invalid JSON and non-object output, so the saved records cannot distinguish those causes. On two more passages, the generated graph included placeholder evidence from the instruction and failed validation. Invalid extractions count as misses. They are distinct from uncertain verdicts.

The runner used the frozen 16 pairs and verified the original model digest. REI needs a question mark before the passage for quote validation. A separate direct control received that same question text. Instructions, output contracts and token limits are method-specific (12 output tokens for direct verdicts, up to 768 for extraction). No expected answer was included in an inference prompt. After an initial interrupted run, the completed run retried one HTTP 500 token-repeat error. Token totals cover successful calls with returned counts and exclude failed or discarded attempts.

This result measures the end-to-end pipeline on these passages. The data provide no score for how the recursive policy would perform given valid evidence graphs.

Run from research/adaptive_rei with the matching Ollama model:

```sh
python3 rei_fact_trial.py > results/rei_fact_trial.json
```
