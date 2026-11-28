# Reasoning about a portion of the contents

The single-fact quantity rule now interprets a supported volume of a named liquid in a container as a lower bound on the contents. It can reject an upper limit when the liquid alone exceeds it. An explicit total is an exact measurement. The rule handles a limited set of English constructions for water, milk, juice and oil, ordinary volume units, and a single container reference.

| Frozen set | Previous | Updated |
|---|---:|---:|
| Earlier questions, original scoring | 92/94 | 93/94 |
| New controls (six claims, three evidence conditions each) | 10/18 | 18/18 |

On the original silver-pitcher claim (“at most 1.6 liters”), the two prior errors were corrected. The 1601 mL observation in the silver pitcher contradicts the claim. The same observation in the copper pitcher leaves it unresolved. A third verdict changed from yes to uncertain for a passage reporting 1600 mL of water in the silver pitcher. The frozen key expects yes, but the text leaves open whether the pitcher also held something else. The old label remains in the primary score.

Both checkouts processed all 112 prompts through the single-fact entry point. The previous version used 2,153 reported model tokens. Every updated decision used a deterministic rule and consumed zero model tokens. The new cases target the supported constructions and were frozen before inference. Nineteen focused unit tests passed.

To reproduce, run container_volume_trial.py from research/adaptive_rei with the checkout root for each arm. Both arms expect the pinned Ollama model for this comparison.
