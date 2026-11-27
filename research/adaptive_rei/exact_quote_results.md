# Repeating the exact evidence in the quote field

Llama 3.2 1B answered 16 of 48 reused passages correctly with the source sentence copied into the quote field. Direct verdicts scored 22/48 and verdicts with the previously generated quote scored 14/48. Every verdict in both control conditions reproduced its saved counterpart.

| Expected verdict | Direct correct | Generated quote correct | Exact quote correct |
|---|---:|---:|---:|
| Yes | 11/16 | 2/16 | 13/16 |
| No | 10/16 | 1/16 | 1/16 |
| Uncertain | 1/16 | 11/16 | 2/16 |

The exact-quote condition answered yes 37 times, including 11 contradicting passages and 13 inconclusive ones. It fixed 12 errors and lost 10 correct answers relative to the generated quote. Against the direct verdict it fixed four and lost ten. For “Ari attended the rehearsal,” repeating “Ari missed the entire rehearsal.” changed the correct direct verdict of no to yes.

All three conditions used the original claim, passage, verdict instruction, enum order, model digest, temperature 0, seed 42 and a 12-token output limit. Each of the 16 claims appeared with three different passages. The exact-quote condition copied the whole source passage into the same field used for generated quotes. This tests evidence repetition under that field label. It does not measure selection from a longer document.

Direct verdicts used 3,952 prompt plus generated tokens. The exact-quote verdicts used 4,678 with no extraction call. Replaying the saved generated quotes cost 4,889 verdict tokens, excluding the original extraction cost. All 144 calls ran locally.

Reproduce from research/adaptive_rei with the pinned Ollama model:

```sh
python3 exact_quote_trial.py > results/exact_quote_trial.json
```
