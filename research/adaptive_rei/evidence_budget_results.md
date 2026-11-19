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
