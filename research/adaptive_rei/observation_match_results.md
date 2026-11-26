# Checking whether evidence concerns the requested item and time

Six constructed questions each had five shuffled evidence variants. Before inference the primary score required both the right verdict and the right supporting sentence, or no citation when no relevant observation existed. On each nonzero selection, the new verifier judged firsthand relevance before using the existing verdict decoder. Shared calls are billed to each arm that would use them.

| Mode | Correct verdicts / 30 | Verdict and citation / 30 | Tokens |
|---|---:|---:|---:|
| Conventional prompt | 17 | unmeasured | 3,329 |
| Budgeted REI | 9 | unmeasured | 3,251 |
| Select then answer | 20 | 12 | 4,368 |
| Select, verify match, then answer | 25 | 24 | 6,126 |

Unsupported citations fell from 18 to 3. The verifier rejected five of six wrong-item observations, five of six wrong-time observations, and five of six copied claims. It kept all six supporting observations but only three of six contradicting observations. For example, a clerk finding cabinet F shut at midday directly answers whether it was open at noon, yet the verifier rejected this line. The three rejected contradictions also used equivalent time expressions. This design cannot isolate polarity from wording as the cause. All 30 verification outputs were valid yes/no values.

The 40% token increase over selection alone and loss of valid negative evidence warrant further testing on independent examples. Run observation_match_trial.py with local Ollama. The results JSON includes every proposed and retained reference, verifier output, verdict and token charge.
