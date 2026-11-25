# When a second opinion earns its tokens

The previous cited reviewer can spend a second model call even when the passage explicitly describes an unresolved gap. We tested two ways to lower that cost on Qwen3 4B Instruct. Both use the same initial plain verdict. Token totals include every call.

## Shorter prompt experiment

The first candidate shortened the evidence-selection prompt and skipped review when a recognized phrase at the end of the passage described an unresolved gap. In development it preserved all previously recorded verdicts, and the cited sentence for BoolQ item 501 directly addressed the property in the question and its limitations. Across 23 previously reviewed items, second-pass tokens fell from 3,336 to 2,519.

| Fresh cases | JSON baseline correct / tokens | Plain verdict correct / tokens | Current reviewer correct / tokens | Shorter reviewer correct / tokens |
|---|---:|---:|---:|---:|
| 200 BoolQ questions | 134 / 41,846 | 156 / 34,473 | 158 / 36,172 | 158 / 35,984 |
| 24 authored controls | 20 / 2,339 | 19 / 1,407 | 20 / 3,128 | 18 / 2,315 |

The 200 questions and their passages were disjoint from 880 earlier BoolQ examples. On the fresh controls the shorter reviewer preserved eight correct abstentions versus eleven for the current reviewer. For instance, discovering a tear after unpacking does not establish when the canvas tore. The shorter prompt remains a research comparison.

[Per-case results](results/compact_review_trial.json) · [Development replay](results/compact_review_development.json)

## Budgeted review confirmation

The shipped option keeps the existing cited-review prompt. It skips a paid second call only when the first answer was uncertain and the final passage span contains a recognized explicit evidence gap without a contrasting clause. The check uses wording, so a missing record about an unrelated detail can still match. The system can then retain an initial abstention even if an earlier sentence could have settled the question.

The confirmation used a separate seed and excluded all questions and passages from the preceding 1,080 BoolQ examples. The 24 new project-authored controls deliberately exercise the rule, including true gaps, counterevidence and incidental missing details. Every billed call is counted, and the two review methods share their first-pass result.

| Confirmation set | Single-pass JSON | Plain verdict | Current cited review | Budgeted review |
|---|---:|---:|---:|---:|
| 96 fresh BoolQ questions, correct / tokens | 62 / 21,050 | 77 / 17,524 | 77 / 18,986 | 77 / 18,986 |
| 24 targeted controls, correct / tokens | 22 / 2,236 | 22 / 1,313 | 20 / 3,101 | 22 / 1,313 |

The gap rule skipped zero calls on BoolQ and 15 calls on the controls. On the controls it prevented two incorrect overrides and retained all 14 correct uncertain answers. In one case the discovery of a crack on arrival could not establish whether it predated packing. The control saving was 1,788 tokens, or 57.7% of current cited-review cost. Plain verdict matched budgeted review on the controls and used fewer tokens on BoolQ. These small targeted controls establish a use case for the rule; they do not measure its frequency in general prose.

Use `python3 research/adaptive_rei/adaptive_rei_benchmark.py --budgeted-review 'QUESTION? PASSAGE'` for this opt-in mode. A skipped evidence-gap review is reported with `review_skipped: explicit_evidence_gap` and zero review tokens. Repeat the confirmation with `python3 research/adaptive_rei/compact_review_trial.py --budgeted`.

[Confirmation data](results/budgeted_review_trial.json) · [GitHub run](https://github.com/ted-peters/RecursiveEpistemicIntelligence/actions/runs/44780671731)
