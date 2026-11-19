# Evidence-budget decisions

Use this experimental mode for yes/no/uncertain evidence questions. It accepts ordinary prose or a register whose reports and prerequisites have already been specified. Register resolution uses the existing recursive evidence engine. No language model is needed on that path. For prose, the mode uses the original single-pass evidence instruction with the local Ollama model. It can omit a whole sentence explicitly introduced as an unrelated aside. It preserves unmarked sentences and asides containing a recognized contrast.

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
