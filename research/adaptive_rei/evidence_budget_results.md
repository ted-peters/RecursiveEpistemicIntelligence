# Evidence-budget decisions

Use this experimental mode for yes/no/uncertain evidence questions. It accepts ordinary prose or a register whose reports and prerequisites have already been specified. Register resolution uses the existing recursive evidence engine. No language model is needed on that path. For short prose that explicitly names a source, its verdict, and a copying or sole-source relationship, the mode can trace the reports directly. Other prose uses the original single-pass evidence instruction with the local Ollama model. It can omit a whole sentence explicitly introduced as an unrelated aside. It preserves unmarked sentences and asides containing a recognized contrast.

From the repository root, with Qwen available in Ollama, run:

```sh
python3 research/adaptive_rei/adaptive_rei_benchmark.py --evidence-budget \
  'Was the calibration current? The certificate expired yesterday. Unrelated: the invoice was corrected.'
```

To try a register without Ollama, run these commands in the same shell:

```sh
cd research/adaptive_rei
python3 - <<'PY'
from evidence_register import RULES, decide

lines = ["What is the answer for claim 3?", RULES,
         "Claim 1: yes.", "Claim 2: yes if claim 1 is yes.",
         "Claim 3: yes if claim 2 is yes.", "Claim 3: no."]
print(decide("", "", "\n".join(lines)))
lines[2] = "Claim 1: no."
print(decide("", "", "\n".join(lines)))
PY
```

The first answer is uncertain because two surviving reports disagree. Changing the observation for claim 1 removes support for claim 2, which removes the positive report for claim 3. The independent negative report survives. Reports in this format carry equal weight. Producing and checking the register is upstream work. Its author supplies the facts and dependencies. Unsupported register syntax falls back to the prose model.

## Reports that cite other reports

The same CLI accepts a question and a short passage with named sources. For example:

```sh
python3 research/adaptive_rei/adaptive_rei_benchmark.py --evidence-budget \
  'Did the hatch open? The log says it did. The bulletin copied the log. The memo says it did not. The log was withdrawn.'
```

The surviving memo supports **no**. Removing the last sentence leaves two conflicting sources and changes the answer to **uncertain**. The bulletin supplies no independent observation. In this experimental mode, each surviving original report has equal weight.

The parser accepts a limited set of explicit statements such as “The report relied solely on the log” and “The log was retracted.” An extra observation, an unfamiliar attribution or a conflicting account of a copied verdict sends the whole passage to the usual prose path. Multiple copies and reordered statements do not add independent support.

## Recorded Qwen3 4B comparisons

| Trial | Single-pass correct | Candidate correct | Single-pass tokens | Candidate tokens |
|---|---:|---:|---:|---:|
| Short routed instruction on fresh prose, first prototype | 21/24 | 16/24 | 2,476 | 2,198 |
| Explicit register, 12 paired interventions | 13/24 | 24/24 | 5,015 | 0 |
| Ordinary prose controls in register trial | 6/6 | 6/6 | 558 | 558 |
| Fresh prose with explicit-aside filtering | 20/24 | 20/24 | 2,491 | 2,333 |

The first prototype lost accuracy and is retained for comparison. The register and prose paths above are available through the benchmark CLI. Both arms received the same register text, including its interpretation rules. The register questions were generated in pairs with one root observation changed. Zero tokens indicates zero language-model calls. It excludes the CPU work of parsing and evaluating the supplied register and the cost of creating it.

The final prose trial had eight examples of each label. The filter shortened 12 inputs, and every candidate answer matched its baseline answer. These author-designed suites were fixed before their respective inference runs. They measure performance on the declared formats and synthetic examples. Evidence that the method improves accuracy on unrestricted prose or independent real-world data is still missing.

The raw result files include the model digest, each expected answer, each prediction and the measured input-plus-output token totals. The baseline and the model-backed candidate used temperature 0 and seed 42. To reproduce the studies, select the trial in the GitHub workflow or run the corresponding Python trial against local Ollama.

- [First prototype data](results/budget_prompt_trial.json) · [GitHub run](https://github.com/ted-peters/RecursiveEpistemicIntelligence/actions/runs/44605401844)
- [Register and prose control data](results/budget_register_trial.json) · [GitHub run](https://github.com/ted-peters/RecursiveEpistemicIntelligence/actions/runs/44606434425)
- [Explicit-aside data](results/budget_aside_trial.json) · [GitHub run](https://github.com/ted-peters/RecursiveEpistemicIntelligence/actions/runs/44606670790)

## Follow-up trial on named reports in prose

The 30-question comparison used 12 synthetic pairs with a single evidence change and six additional prose controls. The cases and expected answers were committed before either arm ran. Both arms received the same text. The model, prompt and settings for the baseline match the earlier trials.

| Input | Single-pass accuracy | REI accuracy | Single-pass tokens | REI tokens |
|---|---:|---:|---:|---:|
| Recognized report chains | 14/24 | 24/24 | 2,432 | 0 |
| Other prose, handled by Qwen | 5/6 | 5/6 | 572 | 572 |
| Total | 19/30 | 29/30 | 3,004 | 572 |

The 81.0% reduction is specific to this mix of passages. The 24 chain examples share a small vocabulary, use explicit attribution and were authored for this parser. The controls had identical predictions in both arms. The result does not estimate performance on independently written natural language.

[Individual predictions and token counts](results/report_chain_trial.json) · [GitHub experiment](https://github.com/ted-peters/RecursiveEpistemicIntelligence/actions/runs/44614458220)

## Independent BoolQ evaluation

All 3,270 development questions followed the ordinary Qwen path with identical inputs to the single-pass baseline. The existing graph and aside rules had zero coverage on this split.

On 40 questions selected without replacement using seed 20261119, both arms answered 29 correctly (72.5%) and used 8,299 model-reported tokens each. Every paired prediction matched. Four errors were abstentions on questions labeled no, and seven selected the opposite yes/no label. The benchmark has binary labels and does not assess whether abstention is appropriate when evidence is genuinely missing.

The trial used the original question and passage, added a question-mark separator, and passed no labels to the model. Both arms used the same Qwen3 4B digest and alternated order. The REI policy was frozen before selecting examples. This measures transfer to independently authored information-seeking questions. It does not directly test authored report-chain interventions or rule out exposure to this public corpus during model training.

[BoolQ, Clark et al.](https://github.com/google-research-datasets/boolean-questions) · [Per-example results and dataset checksum](results/boolq_trial.json) · [GitHub run](https://github.com/ted-peters/RecursiveEpistemicIntelligence/actions/runs/44618397433)

## Prose fallback trials after the BoolQ audit

A review of the seven wrong yes/no answers suggested a distinction between the exact question and related statements in the passage. For example, item 2888 distinguishes the right to contest a scrum from common practice. Item 84 describes participating in a World Series and winning a different sport's championship. Items 225 and 2491 change the scope of a category or policy, and item 1159 mentions both an original concert and later performances. The two naming questions (2777 and 2077) illustrate why blanket synonym rules are risky. These are observations about the text and the labels. The experiment did not record an internal explanation for any prediction.

Each candidate was compared with a newly run single-pass Qwen baseline. Each successive random sample excluded questions and passages seen in any preceding sample. All counts include prompt and output tokens. The per-example files contain dataset indices, labels, answers and token counts.

| Trial | Single-pass correct | Candidate correct | Single-pass tokens | Candidate tokens |
|---|---:|---:|---:|---:|
| Passage first, exact question last | 82/120 | 68/120 | 23,557 | 23,400 |
| Allow ordinary implications | 107/160 | 97/160 | 33,015 | 30,255 |

The question-last prompt corrected eight errors and introduced 22. It returned uncertain 38 times, compared with 12 for the baseline. The implication prompt scored 32/40 on the development sample previously used for error analysis, then corrected ten errors and introduced 20 on its fresh sample. On 48 existing three-label controls, the same implication prompt scored 34/48 versus 42/48 for the baseline and recovered 13/16 of the expected uncertain answers versus 16/16. Neither trial supports replacing the default fallback.

[Question-last data](results/boolq_question_focus.json) · [Implication data](results/boolq_implied.json) · [Three-label controls](results/implied_controls.json)

### Opt-in plain verdict

Run `python3 research/adaptive_rei/adaptive_rei_benchmark.py --plain-verdict 'YOUR QUESTION? YOUR PASSAGE'` for a single decision. The CLI returns JSON to its caller. Internally the model receives a short instruction and returns a single word. The mode removes the JSON decoding constraint, caps generation at 12 tokens, and counts an unrecognized reply as a failure. Structured inputs still use the existing graph rules. The prompt, model output format and generation cap changed together, so these data measure their combined effect.

On 200 fresh BoolQ questions, this mode scored **161/200 (80.5%)** against **144/200 (72.0%)** for the single-pass JSON baseline. It corrected 24 errors and introduced seven. Total model tokens fell from **42,519 to 35,101 (17.4%)**. Both arms used Qwen3 4B with temperature 0 and seed 42. The exact two-sided paired McNemar test gives p = 0.0033 on this sample. The trial followed two unsuccessful designs on separate samples of the same public development split.

On the 48 existing three-label controls, plain verdict scored **39/48** against **42/48**, using 2,947 versus 4,963 tokens. Both modes correctly abstained on all 16 cases labeled uncertain. Because of the overall control regression, plain verdict is opt-in. Each arm was run live with the local Ollama model. Sample indices, prompts, decoding settings and per-case results are available for replication.

To reproduce the 200-question comparison, run `python3 research/adaptive_rei/boolq_trial.py --plain`. To repeat the three-label control run, use `python3 research/adaptive_rei/uncertainty_trial.py plain`.

[BoolQ results](results/boolq_plain_verdict.json) · [Three-label controls](results/plain_controls.json)

[Selective review follow-up: accuracy, token costs and citation audit](selective_review_results.md)
