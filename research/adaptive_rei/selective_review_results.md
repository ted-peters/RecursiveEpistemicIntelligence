# Selective review of uncertain answers

The experimental reviewer runs only after a model-backed plain verdict of uncertain. Explicit graph decisions and initial yes/no verdicts go straight through. The reviewer can override an abstention only by returning a yes/no answer and the integer identifier of a passage span. The software checks that the span exists. Whether it supports the conclusion is still a model judgment.

## First reviewer

The first reviewer asked whether one statement settled the question. The comparison used the same initial Qwen answer for both plain verdict and review, so the difference in their costs is exactly the cost of running the second call. Every arm used Qwen3 4B Instruct. The original single-pass JSON baseline ran independently.

| Cases | JSON baseline correct / tokens | Plain verdict correct / tokens | Reviewed correct / tokens | Reviews |
|---|---:|---:|---:|---:|
| 240 fresh BoolQ questions | 176 / 49,228 | 184 / 40,342 | 184 / 42,876 | 14 |
| 18 new controls | 16 / 1,690 | 17 / 990 | 17 / 2,084 | 9 |
| 48 prior controls | 42 / 4,963 | 39 / 2,947 | 39 / 6,028 | 24 |

All 47 reviews kept the first answer. The three sets of controls contained 24 expected abstentions across the 66 control questions, all correctly preserved. The first trial can be reproduced using [the original commit](https://github.com/ted-peters/RecursiveEpistemicIntelligence/commit/87fe5cf) and the checksum-verified BoolQ split.

## Evidence-first reviewer

The revised prompt asks the reviewer to select a passage statement before giving its answer. We compared 120 new BoolQ questions after excluding the questions and passages used in all 760 prior examples. All three arms used the same model digest. The plain-verdict scores use the first call of the reviewed arm, so the measured change is attributable to the second call. The 18 fresh controls and the 18 repeated controls are reported separately.

| Cases | JSON baseline correct / tokens | Plain verdict correct / tokens | Reviewed correct / tokens | Reviews |
|---|---:|---:|---:|---:|
| 120 fresh BoolQ questions | 87 / 24,147 | 93 / 19,723 | 96 / 21,241 | 8 |
| 18 fresh three-label controls | 16 / 1,660 | 17 / 963 | 17 / 1,807 | 7 |
| 18 repeated three-label controls | 16 / 1,687 | 16 / 989 | 17 / 1,963 | 8 |

On BoolQ, review added 1,518 tokens to plain verdict, corrected three abstentions and introduced zero new errors. This is a gain of 2.5 percentage points on this sample. The final cost was 12.0% below the JSON baseline. Only three pairs differed, so the direction of the accuracy change needs replication. On the 36 controls, the extra calls pushed cost above the JSON baseline. Review preserved all 14 correct initial abstentions out of 16 cases labeled uncertain. Both missed abstentions were already wrong before review.

Four overrides matched the expected answers. Checking the actual cited spans exposed a limitation: on BoolQ item 501 the cited sentence says a snake eats venomous snakes. That alone does not establish immunity to their venom. Items 1718 and 2703 cite text distinguishing related categories or states, and the control cites a direct observation of a float passing a line. Agreement with an answer key and adequate justification are separate outcomes.

Use `python3 research/adaptive_rei/adaptive_rei_benchmark.py --cited-review 'QUESTION? PASSAGE'` for the opt-in mode. The output contains the initial and final answers, any cited span, and the cost of each stage. The existing plain-verdict mode remains available for a single-call decision.

[Per-question data](results/evidence_first_review.json) · [Live evaluation](https://github.com/ted-peters/RecursiveEpistemicIntelligence/actions/runs/44770713666)

[Budgeted review follow-up and control results](budgeted_review_results.md)
