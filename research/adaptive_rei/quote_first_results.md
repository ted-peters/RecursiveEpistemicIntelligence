# Quote-first evidence test

Adding a model-selected quote reduced three-way verdict accuracy from 22/48 to 14/48 on the same 48 previously tested passages. The direct and quote-first verdicts used the same prompt, full passage, three labels and 12-token output budget. The only added verdict input was the text returned by the extraction call. Both arms used the pinned Llama 3.2 1B model, temperature 0 and seed 42. The earlier binary direction probe used a different prompt and answer space.

| Expected verdict | Direct correct | Quote-first correct |
|---|---:|---:|
| Yes | 11/16 | 2/16 |
| No | 10/16 | 1/16 |
| Uncertain | 1/16 | 11/16 |

The extraction prompt requested a verbatim excerpt even on inconclusive cases and allowed 96 output tokens. On 1/48 cases the entire returned string was a nonempty, case-sensitive contiguous substring of the passage. That response copied the whole sentence and produced the correct verdict. This strict metric counts commentary around a genuine excerpt as a miss. It measures copying fidelity. Semantic relevance was not graded separately.

For the claim that Ari attended rehearsal, the contradicting passage said “Ari missed the entire rehearsal.” The extractor changed the subject to “I missed the entire rehearsal.” The resulting verdict was yes. On the supporting passage about Ari playing cello throughout rehearsal, the extractor instead said it had no information about attendance. The verdict was uncertain.

The quote-first arm answered uncertain on 33/48 cases, including 22 with decisive evidence. Across all cases it corrected 11 earlier errors and lost 19 earlier correct answers. The direct arm consumed 3,952 prompt plus generated tokens. Quote extraction consumed 4,858 and the subsequent verdicts consumed 4,889, for 9,747 total. All 144 calls used local Ollama.

These paired scores apply to one model and 48 reused passages. They leave open whether supplying a verified excerpt would improve the verdict. On this single-sentence dataset, supplying the source sentence in the selected-quote field would isolate the effect of replacing the generated text with faithful evidence.

To reproduce with the matching Ollama model, run from research/adaptive_rei:

```sh
python3 quote_first_trial.py > results/quote_first_trial.json
```
