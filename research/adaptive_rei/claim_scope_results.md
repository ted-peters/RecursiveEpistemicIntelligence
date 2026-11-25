# Does stating what the evidence establishes improve the verdict?

The experimental --claim-scope mode asks Qwen3 4B to state the target claim and what the passage establishes, then classify their relationship in a single call. The verdict follows from that classification. These short model-generated descriptions are available for inspection. The trial scores the final answer; it does not independently grade the descriptions.

Eight new passages each have three questions, with one supported, one contradicted and one unresolved claim. Inputs and labels were committed before the run. The prior audit pilot is reported separately.

| Mode | Fresh correct / 24 | Entire triplets correct / 8 | Fresh tokens | Prior audit correct / 14 | Audit tokens |
|---|---:|---:|---:|---:|---:|
| Conventional | 18 | 3 | 2,522 | 10 | 1,523 |
| Budgeted REI | 19 | 4 | 2,902 | 13 | 1,950 |
| Claim comparison | 19 | 4 | 3,970 | 12 | 2,426 |

Relative to budgeted REI, the experiment fixed four fresh mistakes and introduced four. It correctly withheld judgment about whether a van returned later, but it lost a correct verdict about four reviewed labels being legible. Both REI modes missed that a return had been recorded even though the van was still on the road. More explicit reasoning produced inspectable intermediate claims but no overall accuracy gain here. Keep the mode experimental.

Run python3 research/adaptive_rei/claim_scope_trial.py against the local Ollama model, or pass --claim-scope 'QUESTION? EVIDENCE' to adaptive_rei_benchmark.py to inspect one answer. The results JSON records every verdict, the model digest, and input plus output tokens.
