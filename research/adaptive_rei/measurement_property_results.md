# Checking what property a passage measures

For explicit single measurements, REI now checks whether the claim and passage describe compatible properties. If their units and verbs clearly identify different properties, the passage becomes a gap in the evidence graph. Thus the mass of a container alone cannot establish the volume of its contents. The check runs in the existing single-fact CLI. Unsupported constructions still use the model fallback.

| Correct verdicts | PR 73 | Property check |
|---|---:|---:|
| PR 72 transfer cases | 59/64 | 62/64 |
| Of those, different-property cases | 13/16 | 16/16 |
| PR 73 alias cases | 12/12 | 12/12 |
| New targeted property cases | 18/18 | 18/18 |

The new controls supplied two decisive measurements and one irrelevant measurement for each of six claims. Both versions got all 18 correct. Across all 94 cases three answers improved, and no previously correct answer regressed. Total model tokens fell from 2,410 to 306. Both remaining errors occurred on paraphrases of how much water was in a pitcher. The aggregate includes development cases, and the new controls represent a narrow grammar.

The confirmation cases and rule were frozen before running both checkouts with the same pinned Llama 3.2 1B digest. Run measurement_property_trial.py with a checkout root from research/adaptive_rei to reproduce the comparison. Seventeen focused tests passed.
