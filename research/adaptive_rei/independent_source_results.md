# Independent corroboration trial

Eight constructed claims each appeared with an unchecked entry alone, with a derivative copy, with an independent observation supporting a yes answer, and with an independent observation supporting a no answer. The expected verdict for both record-only variants was uncertain. The primary metric required all four verdicts on a claim to be correct. Cases were fixed before inference.

| Mode | Entry / 8 | Copy / 8 | Observed yes / 8 | Observed no / 8 | All four / 8 | Tokens |
|---|---:|---:|---:|---:|---:|---:|
| Conventional | 4 | 6 | 4 | 2 | 1 | 3,226 |
| Budgeted REI | 5 | 5 | 6 | 7 | 4 | 3,620 |
| Prior selective yes review | 5 | 5 | 6 | 7 | 4 | 3,620 |
| Report/event prompt | 8 | 8 | 3 | 3 | 2 | 2,473 |
| Source-tracing prompt | 0 | 0 | 0 | 0 | 0 | 3,026 |

All 32 primary source-tracing outputs failed the one-word parser. A separate spot check showed an answer followed by explanatory prose cut off at the token limit. A post-hoc run constrained both short prompts to the same three strings on the same cases. Source tracing then answered uncertain 32 times, scoring 16/32 and completing zero claims for 2,802 tokens. The constrained report/event control scored 17/32 and completed zero claims for 2,513 tokens. Constraining output fixed parseability but did not establish source discrimination. Retain budgeted REI as the default.

Run independent_source_trial.py for the original trial and independent_source_format_check.py for the diagnostic with the project's local model. The results directory contains every verdict and token charge.
