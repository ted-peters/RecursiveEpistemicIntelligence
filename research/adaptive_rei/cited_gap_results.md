# Recheck denials citing incomplete records

The frozen rule required a negative verdict and an existing citation containing both a record term and a gap term. Eligible cases used the same second opinion as the broad recheck, with the full token charge. Neither gate could change an initial yes or uncertain verdict. One local run used Qwen3 4B. All 24 fresh cases came from eight constructed scenarios with three related evidence variants each.

| Mode | Prior pilot / 14 | Fresh gap / 8 | Fresh witnessed completion / 8 | Fresh witnessed omission / 8 | Fresh tokens |
|---|---:|---:|---:|---:|---:|
| Conventional | 10 | 7 | 3 | 6 | 2,476 |
| Current REI | 13 | 4 | 3 | 6 | 2,947 |
| Recheck all denials | 12 | 8 | 3 | 2 | 4,284 |
| Recheck cited record gaps | 13 | 5 | 3 | 6 | 3,071 |

The narrow rule met all three directional criteria on the fresh set: one fewer mistaken denial, identical direct-evidence verdicts, and fewer tokens than broad review. Its entire improvement came from one gallery cleaning log. The original spot-check denial and three remaining fresh gap denials had no citation to inspect. This supports further testing of citation coverage before routine use. The raw rows include the exact cited text and eligibility decision. Run with local Ollama using python3 research/adaptive_rei/cited_gap_trial.py.
