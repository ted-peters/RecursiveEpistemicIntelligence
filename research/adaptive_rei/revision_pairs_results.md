# November 19 versus November 27 on the frozen reversal pairs

The November 19 and November 27 adaptive REI research revisions returned identical extraction records on all 32 passages. Neither produced a verdict. The earlier revision was the first consolidated version of this engine (408641d). The newer revision was the tip of the research branch used for PR #67 (8797b9b). The recursive engine and the benchmark code executed on this path were unchanged between those revisions.

| Live run | Valid verdicts | Correct passages | Both sides correct | Reported tokens |
|---|---:|---:|---:|---:|
| November 19 recursive REI | 0/32 | 0/32 | 0/16 | 33,744 |
| November 27 recursive REI | 0/32 | 0/32 | 0/16 | 33,744 |
| November 27 optional budgeted prose review | 32/32 | 16/32 | 0/16 | 2,339 |

For each recursive run, the benchmark recorded 30 empty parsed objects and rejected two graphs with invalid evidence. Each run retried one server error. Token totals cover successful calls with reported counts. Accuracy among returned verdicts is undefined for the two recursive runs. Their end-to-end scores count missing verdicts as misses.

The newer optional prose mode returned no for every passage. All 16 contradicting passages scored correctly and all 16 supporting passages scored incorrectly. None triggered its uncertainty review. This additional arm measures a different mode available at the newer revision. The saved direct Llama baseline from PR #66 scored 18/32 and 3/16 complete reversals using its original wording.

All three live runs used the same exact question strings from PR #67, the same Ollama llama3.2:1b digest, temperature 0 and seed 42. Both recursive runs used their original extraction prompts, validation and token limits. Comparisons apply to these 16 frozen claims and this model. Neither recursive run reached the reasoning stage.

Run from research/adaptive_rei in a checkout containing the trial. Supply the path to a checkout of the indicated revision:

```sh
python3 revision_pairs_trial.py "$OLD_CHECKOUT" old > results/revision_old.json
python3 revision_pairs_trial.py "$NEW_CHECKOUT" new > results/revision_new.json
python3 revision_pairs_trial.py "$NEW_CHECKOUT" prose > results/revision_prose.json
```
