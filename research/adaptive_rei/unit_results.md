# Comparing compatible units

The single-fact quantity rule now compares mass (grams and kilograms), length (millimeters, centimeters and meters), volume (milliliters and liters), and money (cents and dollars). Within each group it shifts decimal exponents before checking the bound, including strict and inclusive thresholds. Each rule decision retains the supplied passage in the evidence graph.

Both the previous implementation from PR 70 and the candidate ran through the single-fact entry point on eight newly authored claims. Each had one supporting, one contradicting, and one inconclusive passage. Inputs and expected answers were committed before running inference. Model calls used the same pinned local Llama 3.2 1B digest.

| Measure | Previous | Compatible-unit comparison |
|---|---:|---:|
| Supporting passages correct | 4/8 | 8/8 |
| Contradicting passages correct | 0/8 | 8/8 |
| Inconclusive passages correct | 5/8 | 5/8 |
| All passages correct (count) | 9/24 | 21/24 |
| Both decisive verdicts correct | 0/8 | 8/8 |
| Model tokens | 2,272 | 756 |

All 16 decisive cases were resolved without a model call. All eight inconclusive controls went through the existing model fallback and reproduced their prior answers, including three incorrect yes answers. The exact comparison rule also reproduced its previous output (including deferrals) on all 68 saved questions from PR 70. This latter check compared rule outputs only. The new controls deliberately target the supported unit families.

Run from research/adaptive_rei with the pinned Ollama model available. Pass the repository root for the version to test:

```sh
python3 unit_trial.py "$PREVIOUS_CHECKOUT"
python3 unit_trial.py ../..
```
