# Measurement reasoning across equivalent phrasings

With identical frozen inputs, the PR 71 single-fact system scored 41/64 versus 29/64 for PR 70. These 64 prompts represent eight claims with four evidence conditions, each written two ways. Expected answers and wording were committed before inference. All calls used the pinned Llama 3.2 1B digest.

| Correct by evidence type (each out of 8) | PR 70 standard | PR 71 standard | PR 70 paraphrase | PR 71 paraphrase |
|---|---:|---:|---:|---:|
| Supports claim | 4 | 8 | 7 | 7 |
| Contradicts claim | 0 | 8 | 1 | 1 |
| Different object, expected uncertain | 2 | 2 | 2 | 2 |
| Different property, expected uncertain | 8 | 8 | 5 | 5 |

The updated comparator handled all 16 decisive standard passages and zero paraphrases. For example, on the claim that a parcel weighed at most 2.4 kilograms, the updated system correctly rejected a passage stating that it weighed 2402 grams. When the same value was expressed as the scale reading for that parcel, it incorrectly returned yes. Different-object passages also remain difficult: only 4/16 correct abstentions across the two wordings. Model token use fell from 6,218 to 4,692.

These cases were hand-authored for supported unit families. Half of the evidence conditions were deliberately inconclusive. The counts describe this targeted set and include repeated phrasings of the same facts. No production code was changed for this trial.

From research/adaptive_rei, supply each version's checkout root:

```sh
python3 measurement_transfer_trial.py "$PR70_CHECKOUT"
python3 measurement_transfer_trial.py "$PR71_CHECKOUT"
```
