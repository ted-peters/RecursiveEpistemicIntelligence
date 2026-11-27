# Does the output format explain the repeated “yes”?

Llama 3.2 1B answered yes to the direction question on all 48 passages in each format. This includes all 16 passages that contradicted the claim. For example, the claim “Ari attended the rehearsal” received the same answer when Ari played throughout the rehearsal and when Ari missed the entire rehearsal.

## Paired test

Each of the 48 previously tested passages received identical sufficiency and direction prompts under both formats. The sole request change was omission of the JSON string enum for plain text. Temperature was 0, seed was 42 and the output limit was 12 tokens per call. The runner checked the model digest against the previous trial. Each historical suite contained eight supporting, eight contradicting and eight inconclusive passages.

| Measure | Constrained JSON | Plain text |
|---|---:|---:|
| Correct final answers under the original exact-label rule | 16/48 | 0/48 |
| Invalid gate responses under that rule | 0/48 | 48/48 |
| Direction responses beginning with yes, including punctuation | 48/48 | 48/48 |
| Gate responses reaching the output limit | 0/48 | 48/48 |
| Prompt plus generated tokens for all 96 calls per format | 7,714 | 8,002 |

The constrained gate chose settled every time. Its 16 correct final answers equal the always-yes baseline on this balanced set. In plain text the direction response was always “Yes.” Neither the exact-label nor the leading-label parser could route any plain-text gate response. A system that stopped at an invalid gate would consume 4,625 tokens in plain text. The experiment also ran direction independently on every passage to test it directly.

## Reading the plain-text responses

A post hoc count of explicit “choose settled.” or “choose open.” phrases recovered 32 settled and three open choices. Thirteen responses ended before making either choice. All three open choices concerned passages with a definite answer. Among the 16 inconclusive passages, ten chose settled and six gave no choice. Routing these recovered choices and accepting “Yes.” as yes gives 10/48 correct with missing responses counted as misses. This diagnostic was chosen after inspection.

Removing the schema changed how the gate expressed its choice. It did not resolve the repeated yes on this model, prompt and passage set. These are reused cases and no other model was evaluated.

Run locally with the matching Ollama model available:

```sh
cd research/adaptive_rei
python3 sufficiency_format_trial.py > results/sufficiency_format_trial.json
```
