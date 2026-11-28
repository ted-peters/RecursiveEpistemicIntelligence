# Inclusive measurement ranges

Single-fact REI accepts an observation phrased as “between X and Y [unit], inclusive.” It compares both endpoints with the claim's threshold after unit normalization. Agreement gives a verdict because each supported comparison is monotone. Disagreement leaves the claim unresolved. A reversed interval provides no usable bound. The same comparison handles exact readings and the previously supported partial-volume lower bounds.

| Frozen set | PR 75 | Range-aware |
|---|---:|---:|
| Prior cases | 111/112 | 111/112 |
| New supporting cases | 6/6 | 6/6 |
| New contradicting cases | 0/6 | 6/6 |
| New inconclusive cases | 1/6 | 6/6 |

Both versions ran on identical inputs using the pinned Llama 3.2 1B model for any fallback. All 112 prior result records matched between versions. The existing partial-volume label discrepancy from PR 75 remains. On the 18 new cases the old version used 1,845 model tokens and the new version used zero. The six hand-authored claims cover four comparison operators, endpoint equality, unit conversion, wrong-object and wrong-property evidence. They target an explicit shared-unit construction. General range wording has not been measured.

Twenty-one focused tests passed, including a check of 72 combinations of integer intervals, thresholds and comparison operators. To replay, run measurement_range_trial.py from research/adaptive_rei with the checkout root for each arm.
